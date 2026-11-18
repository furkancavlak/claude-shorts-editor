"""serit.py - strip of frames from a finished Short, time-stamped, for self-review.

    python serit.py <short.mp4> <out.jpg> [n=8]              # n evenly spaced frames (first at 0, last near the end)
    python serit.py <short.mp4> <out.jpg> --t 0 1.5 3.2      # chosen seconds
Tiles are 360x640 (a phone-sized look at the 1080x1920 frame).
The last tile is taken from the video stream's own end (the audio can run a few frames longer); a second past
the last frame shows the last frame instead of crashing.
"""
import subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

v, out = sys.argv[1], sys.argv[2]


def sure_al(ek):
    o = subprocess.check_output(["ffprobe", "-v", "error"] + ek + ["-of", "csv=p=0", v], text=True).split()
    return min((float(x) for x in o if x.replace(".", "", 1).isdigit()), default=None)


sure = sure_al(["-show_entries", "format=duration"])
vs = sure_al(["-select_streams", "v:0", "-show_entries", "stream=duration"])
if vs: sure = min(sure, vs)
if "--t" in sys.argv: ts = [float(x) for x in sys.argv[sys.argv.index("--t") + 1:]]
else:
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    ts = [round(i * (sure - 0.1) / (n - 1), 2) for i in range(n)]
f = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 22)


def kare(t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", v, "-frames:v", "1", "-vf", "scale=360:640",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return raw if len(raw) >= 360 * 640 * 3 else None


tiles = []
for t in ts:
    raw, tt = kare(t), t
    while raw is None and tt > 0:          # past the last frame: step back one frame at a time (max ~1 s)
        tt = max(0.0, tt - 1 / 30); raw = kare(tt)
        if t - tt > 1.0: break
    if raw is None: sys.exit(f"HATA: {t:.2f}. saniyede kare yok (video {sure:.2f} sn)")
    im = Image.fromarray(np.frombuffer(raw[: 360 * 640 * 3], np.uint8).reshape(640, 360, 3)).copy()
    d = ImageDraw.Draw(im); d.rectangle([0, 0, 92, 28], fill="black"); d.text((4, 2), f"{tt:.2f}s", font=f, fill="yellow")
    tiles.append(im)
sh = Image.new("RGB", (364 * len(tiles), 640), "white")
for i, im in enumerate(tiles): sh.paste(im, (i * 364, 0))
sh.save(out, quality=90); print(out, ts)
