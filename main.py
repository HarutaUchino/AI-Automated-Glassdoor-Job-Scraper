from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from seleniumbase import Driver
import time
import json
import os
from dotenv import load_dotenv
from pathlib import Path
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate

base_directory = Path('/home/admin/gloosdoor')
my_directory = Path('0818')
load_dotenv(base_directory/my_directory / '.env')

groq_api_key = os.environ.get("GROQ_API_KEY")
EMAIL_GLASSDOOR = os.getenv('EMAIL_GLASSDOOR')
PASSWORD_GLASSDOOR = os.getenv('PASSWORD_GLASSDOOR')

chat = ChatGroq(temperature=0, groq_api_key=groq_api_key, model_name="llama-3.1-70b-versatile")
JSON_FILENAME = (base_directory/my_directory /'visited_job_ids.json')

def save_job_ids_to_json(job_ids):
    with open(JSON_FILENAME, 'w') as file:
        json.dump(list(job_ids), file)

def load_job_ids_from_json():
    try:
        if JSON_FILENAME.exists():
            with open(JSON_FILENAME, 'r') as file:
                content = file.read().strip()
                if content:
                    return set(json.loads(content))
                else:
                    print("JSON file is empty. Creating a new set.")
                    return set()
        else:
            print(f"File not found: {JSON_FILENAME}")
            print("Creating a new JSON file.")
            JSON_FILENAME.parent.mkdir(parents=True, exist_ok=True)
            with open(JSON_FILENAME, 'w') as file:
                json.dump([], file)
            return set()
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print("Resetting file contents.")
        with open(JSON_FILENAME, 'w') as file:
            json.dump([], file)
        return set()
    except Exception as e:
        print(f"Unexpected error occurred: {e}")
        return set()

def initialize_api_rate_limiter(min_interval):
    last_call_time = 0
    def wait_if_needed():
        nonlocal last_call_time
        current_time = time.time()
        elapsed_time = current_time - last_call_time
        if elapsed_time < min_interval:
            wait_time = min_interval - elapsed_time
            print(f"Waiting for {wait_time:.2f} seconds...")
            time.sleep(wait_time)
        last_call_time = time.time()
    return wait_if_needed

def login(driver):
    SignIn = driver.find_element("div[id*='SignInButton']")
    SignInButton = SignIn.find_element("css selector", "button[aria-label*='sign']")
    SignInButton.click()
    email = driver.find_element("div[class*='TextInputWrapper']")
    email_input = email.find_element("css selector", "input[type*='email']")
    email_input.send_keys(EMAIL_GLASSDOOR)
    email_input.send_keys(Keys.RETURN)
    check_and_close_popup(driver)
    password = driver.find_element("div[data-test*='passwordInput']")
    password_input = password.find_element("css selector", "input[type*='password']")
    password_input.send_keys(PASSWORD_GLASSDOOR)
    password_input.send_keys(Keys.RETURN)
    check_and_close_popup(driver)

def search(driver, keyword, location):
    search_keyword_input = driver.find_element("css selector", "input[id*='searchBar-jobTitle']")
    search_keyword_input.clear()
    search_keyword_input.send_keys(keyword)
    search_keyword_input.send_keys(Keys.RETURN)
    check_and_close_popup(driver)
    search_place_input = driver.find_element("css selector", "input[id*='searchBar-location']")
    search_place_input.clear()
    search_place_input.send_keys(location)
    search_place_input.send_keys(Keys.RETURN)
    check_and_close_popup(driver)
    button_xpath = "//button[contains(text(), 'Easy Apply only')]"
    driver.click("xpath", button_xpath)

def filter_jobs(driver):
    job_data = []
    visited_job_ids = load_job_ids_from_json()
    loop_count = 0
    job_index = 0
    check_and_close_popup(driver)
    while True:
        try:
            column_left = driver.find_element("div[class*='TwoColumnLayout_columnLeft']")
            wrapper = column_left.find_element("css selector", "div[class*='JobsList_wrapper']")
            x1 = driver.find_element("ul[aria-label*='Jobs List'][class*='JobsList_jobsList_']")
            job_items = x1.find_elements("css selector", "li[class*='JobsList_jobListItem']")
            while job_index < len(job_items):
                print(loop_count)
                job = job_items[job_index]
                job_com_url, job_glassdoor_url, job_glassdoor_id, job_description, ans_yes_no, ans_ex, ans_yes_no_myskills, ans_myskills_ex, ans_yes_no_coding, ans_coding_ex = [""] * 10
                if loop_count > 0:
                    action_chain = ActionChains(driver)
                    action_chain.move_to_element(job).perform()
                    driver.execute_script("window.scrollBy(0, 80);")
                job.click()
                check_and_close_popup(driver)
                if loop_count > 0 and loop_count % 29 == 0:
                    showwrapper_job_list = driver.find_element("div[class*='JobsList_buttonWrapper']")
                    show_job_list_button = showwrapper_job_list.find_element("css selector", "button[class*='button_Button']")
                    show_job_list_button.click()
                    check_and_close_popup(driver)
                    time.sleep(2)
                    job_index += 1
                    loop_count += 1
                    break
                check_and_close_popup(driver)
                job_glassdoor_id = job.get_attribute("data-jobid")
                if job_glassdoor_id in visited_job_ids:
                    job_index += 1
                    loop_count += 1
                    continue
                click_show_more_if_not_expanded(driver)
                check_and_close_popup(driver)
                job_description_element = driver.find_element("css selector", "div[class*='JobDetails_jobDescription']")
                job_description = job_description_element.text
                visited_job_ids.add(job_glassdoor_id)
                save_job_ids_to_json(visited_job_ids)
                print(f'Job ID: {job_glassdoor_id}')
                ans_yes_no, ans_ex = groq_chatmodel_if(driver, job_description)
                print("ans_yes_no", ans_yes_no)
                if "yes" in ans_yes_no.lower():
                    ans_yes_no_coding, ans_coding_ex = groq_chatmodel_coding(driver, job_description)
                    if "yes" in ans_yes_no_coding.lower():
                        ans_yes_no_myskills, ans_myskills_ex = groq_chatmodel_myskills(driver, job_description)
                        if "yes" in ans_yes_no_myskills.lower():
                            click_bookmark_button(driver, job_glassdoor_id)
                check_and_close_popup(driver)
                job_data.append({
                    "job_glassdoor_id": job_glassdoor_id,
                    "job_description": job_description,
                    "ans_yes_no": ans_yes_no,
                    "ans_ex": ans_ex,
                    "ans_yes_no_coding": ans_yes_no_coding,
                    "ans_coding_ex": ans_coding_ex,
                    "ans_yes_no_myskills": ans_yes_no_myskills,
                    "ans_myskills_ex": ans_myskills_ex
                })
                with open(base_directory/my_directory/'job_data.json', 'w') as f:
                    json.dump(job_data, f, indent=4)
                loop_count += 1
                job_index += 1
        except Exception as e:
            print(f"An error occurred: {e}")
            break

def check_and_close_popup(driver):
    try:
        driver.wait_for_element("button[data-test='job-alert-modal-close']", timeout=2)
        if driver.is_element_visible("button[data-test='job-alert-modal-close']"):
            driver.click("button[data-test='job-alert-modal-close']")
            driver.assert_element_not_visible("div[class*='JobAlertModal_modalWrapper']")
        return True
    except:
        return False

def click_show_more_if_not_expanded(driver):
    try:
        driver.wait_for_element("button[class*='JobDetails_showMore']", timeout=2)
        if driver.is_element_visible("button[class*='JobDetails_showMore']"):
            show_more_button = driver.find_element("button[class*='JobDetails_showMore']")
            is_expanded = show_more_button.get_attribute("aria-expanded")
            if is_expanded == "false":
                show_more_button.click()
            return True
    except:
        return False

def send_prompt(driver, web_content_text, prompt_template, follow_up_template=None):
    while True:
        driver.rate_limiter()
        template = PromptTemplate.from_template(prompt_template)
        prompt = template.format(webcontent=web_content_text)
        output = chat.invoke(prompt)
        output_str = str(output.content)
        if follow_up_template:
            template_ex = PromptTemplate.from_template(follow_up_template)
            prompt_ex = template_ex.format(webcontent_ex=output_str)
            output_ex = chat.invoke(prompt_ex)
            output_ex_str = str(output_ex.content)
            return output_ex_str, output_str
        else:
            return output_str

def groq_chatmodel_if(driver, web_content_text):
    prompt_template = """
    I would like to apply for an internship. Can I apply for the following internship, please tell me with the explanation? Take your time and do it right
    ###my information###
    - I am a first year master's student living in Japan and will graduate in March 2026. So I cannot graduate before that, in 2024 and 2025 or in 2027 and 2028.
    - I have academic terms until March 2026.
    - My major is computer science.
    - I am available for internships from the summer of 2024 until the winter of 2025.
    - I can speak English and willing to work in any location.
    - If the job description explicitly states that the company does not provide visa sponsorship, please respond with 'No'. If there is no mention of visa sponsorship or if the company is open to sponsoring visas, please respond with 'Yes'.
    {webcontent}
    """
    follow_up_template = "Please answer with Yes or No. Am I eligible to apply for this internship?{webcontent_ex}"
    return send_prompt(driver, web_content_text, prompt_template, follow_up_template)

def groq_chatmodel_myskills(driver, web_content_text):
    prompt_template = """
    I would like to apply for an internship. Can I apply for the following internship with my skills, please tell me with the explanation? Take your time and do it right
    Answer with either 'Yes' or 'No', and provide a brief explanation for your decision.
    Based on my skill set and interests, please evaluate whether the presented internship opportunity meets the following criteria:
    ###My Skills and interests###
    - I understand C, Python, JavaScript, programming languages and HTML.
    - I know Interface of Linux operating system.
    - I know SQLlite database.
    - I have experience with Selenium and Beautiful Soup for web scraping.
    - I have experience with GDB and Valgrind for debugging.
    ###job description###
    {webcontent}
    """
    follow_up_template = "Please answer with only Yes or No ,{webcontent_ex}"
    return send_prompt(driver, web_content_text, prompt_template, follow_up_template)

def groq_chatmodel_coding(driver, web_content_text):
    prompt_template = """
    Please determine whether this job is primarily focused on programming and coding tasks. Answer with either 'Yes' or 'No', and provide a brief explanation for your decision. Take your time and do it right.
    I am currently actively seeking job opportunities in software development and related fields. I have a strong interest in roles that involve substantial programming and coding. Based on my skills and interests, please evaluate whether the presented job opportunity meets the following criteria:
    ### good example output###
    Yes, job_type: SWE, ex: This job is primarily focused on programming and coding tasks. The position is for a worki~~
    ###Important notes###
    - I am not interested in consulting or administrative roles
    - The position should primarily involve hands-on coding and development tasks
    ###Preferred job types###
    "Software Engineer (SWE) / Software Developer (SD)", "Full Stack Developer (FSD)", "Backend Engineer (BE)", "Frontend Engineer (FE)", "Machine Learning Engineer (MLE)", "Mobile App Developer", "DevOps Engineer", "Cloud Engineer (CE)", "Game Developer", "Embedded Systems Programmer"
    ###Non-coding job types###
    "Project Manager (PM)", "Product Owner (PO)", "Business Analyst (BA)", "User Experience/User Interface Designer (UX/UI)", "Data Analyst (DA) (non-programming focused)", "Systems Administrator (SA)", "Network Engineer (NE)", "Quality Assurance Engineer (QA) (manual testing focused)", "Technical Analyst (TA)", "Security Engineer (SE) (policy and risk assessment focused)", "Database Administrator (DBA) (configuration and optimization focused)", "Artificial Intelligence Researcher (AI) (theoretical research focused)", "Internet of Things Strategist (IoT) (strategy and management focused)", "Technical Writer", "IT Project Coordinator", "IT Trainer", "IT Procurement Specialist", "IT Compliance Analyst", "IT Service Desk Analyst", "IT Asset Manager"
    ###Job description###
    {webcontent}
    """
    follow_up_template = """
    Based on this information, is this job primarily focused on programming and coding tasks? Please answer that Yes or No.{webcontent_ex}
    """
    return send_prompt(driver, web_content_text, prompt_template, follow_up_template)

def click_bookmark_button(driver, job_id):
    try:
        container = driver.find_element("css selector", "div[class*='JobDetails_jobDetailsContainer']")
        header = container.find_element("css selector", "header[class*='JobDetails_jobDetailsHeaderWrapper']")
        z1 = header.find_element("css selector", "div[class*='JobDetails_webActionWrapper']")
        bookmark_button = z1.find_element("css selector", "button[class*='BookmarkButton_buttonWrapper']")
        button_state = bookmark_button.get_attribute("aria-label")

        if button_state == "Saved":
            print(f"Job ID {job_id} has already been saved.")
        else:
            bookmark_button.click()
            print(f"Job ID {job_id} has been saved.")
            check_and_close_popup(driver)
            
    except Exception as e:
        print(f"Error: {e}")

def click_button_by_text(driver, button_text):
    try:
        # Get all button elements
        buttons = driver.find_elements("tag", "button")
        
        # Look for the button containing the specified text
        for button in buttons:
            if button.text.strip().lower() == button_text.lower():
                # If found, click the button
                driver.click(button)
                print(f"'{button_text}' button clicked successfully.")
                return True
        
        print(f"'{button_text}' button not found.")
        return False
    except Exception as e:
        print(f"Error occurred while trying to find and click '{button_text}' button: {e}")
        return False

def main():
    driver = Driver(uc=True, headless=False)
    
    try:
        driver.rate_limiter = initialize_api_rate_limiter(min_interval=15)
        driver.get("https://www.glassdoor.com/Job/index.htm")
        driver.maximize_window()
        login(driver)
        search(driver, "Software Intern", "United States")
        print("login and search done")
        #time.sleep(120)
        input("Press Enter to continue...")
        filter_jobs(driver)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()

