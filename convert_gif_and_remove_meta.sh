ffmpeg -i video.mp4 -vf "fps=30,scale=1280:720:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5" -loop 0 demo1.gif
mat2 -s demo1.gif
mat2 -L demo1.gif

