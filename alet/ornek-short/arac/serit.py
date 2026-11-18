"""Strips of chosen frames from a render, with frame number and time burned in.

    py -3 serit.py <video> <out.jpg> <cols> <frame> [<frame> ...]
    py -3 serit.py <video> <out.jpg> <cols> even <count>      # evenly spaced, first and last included
    py -3 serit.py <video> <out.jpg> <cols> range <a> <b>      # every frame a..b
"""
import subprocess, sys

vid, out, cols = sys.argv[1], sys.argv[2], int(sys.argv[3])
args = sys.argv[4:]
n = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames", "-of", "csv=p=0", vid], capture_output=True, text=True).stdout.strip())
if args[0] == "even":
    k = int(args[1]); frames = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
elif args[0] == "range":
    frames = list(range(int(args[1]), int(args[2]) + 1))
else:
    frames = [int(a) for a in args]
rows = (len(frames) + cols - 1) // cols
sel = "+".join(f"eq(n\\,{f})" for f in frames)
vf = (f"select='{sel}',scale=360:-1,drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':"
      f"text='f%{{n}}':x=6:y=6:fontsize=1:fontcolor=black,"
      f"tile={cols}x{rows}:padding=4:color=0x202020")
# frame labels: drawtext cannot print the source frame after select, so draw them per tile with a second pass
labels = []
for i, f in enumerate(frames):
    x, y = (i % cols) * 364, (i // cols) * 644
    labels.append(f"drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{f}  {f / 30:.2f}s':x={x + 8}:y={y + 8}:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.7")
vf = f"select='{sel}',scale=360:640,tile={cols}x{rows}:padding=4:color=0x202020," + ",".join(labels)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-vf", vf, "-frames:v", "1", "-fps_mode", "passthrough", out], check=True)
print(out, len(frames), "frames of", n)
