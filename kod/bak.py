"""bak.py - look at a source window before writing a proof entry.

    python bak.py <video> <start_orig_sec> <end_orig_sec> <step_sec> <out.jpg> [--ofset S|otomatik] [--bolge x0,y0,x1,y1]
    python bak.py <video> --aralik            # only print which seconds the file holds

Writes a contact sheet (4 columns, 640 px wide tiles). Every tile shows the ORIGINAL-video second
(file second + ofset; ofset "otomatik" = the file's start_time, which parts cut out of a longer video carry)
and a 10 % grid with 0-1 labels, so a proof region can be read off as normalised x/y of the full
frame. --bolge draws a candidate region in yellow to check it before it goes into plan.json.
A second outside the file is an error (exit 2) that names the file's real range; it never repeats a frame.
"""
import argparse, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor import kaynak_bilgi, kare_al, aralik_yazi  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("bas", type=float, nargs="?"); ap.add_argument("bit", type=float, nargs="?")
ap.add_argument("adim", type=float, nargs="?"); ap.add_argument("cikti", nargs="?")
ap.add_argument("--ofset", default="otomatik"); ap.add_argument("--bolge"); ap.add_argument("--aralik", action="store_true")
a = ap.parse_args()
k = kaynak_bilgi(a.video, a.ofset)
if a.aralik:
    print(f"{a.video}: görüntü {aralik_yazi(k)}"); sys.exit(0)
if a.cikti is None: ap.error("bas, bit, adim ve cikti gerekli (ya da yalnız --aralik)")
if a.bas < k["ilk"] - 0.05 or a.bit > k["bitis"] + 0.05 or a.bit < a.bas:
    print(f"HATA: {a.bas:g}–{a.bit:g} sn istendi ama bu dosyanın görüntüsü yalnız {aralik_yazi(k)}.\n"
          f"Saniyeleri bu aralıktan seç (bu dosyada en erken {k['ilk']:.2f}, en geç {k['bitis']:.2f}).", file=sys.stderr)
    sys.exit(2)
f = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 20)
tiles, t = [], a.bas
son_kare = k["bitis"] - 1.0 / k["fps"] - 0.002    # the last frame starts one frame before the end
while t <= a.bit + 1e-6:
    im = Image.fromarray(kare_al(k, min(t, son_kare))).resize((640, int(640 * k["h"] / k["w"])))
    d = ImageDraw.Draw(im); W, H = im.size
    for i in range(1, 10):
        d.line([(W * i / 10, 0), (W * i / 10, H)], fill=(255, 255, 255, 90), width=1)
        d.line([(0, H * i / 10), (W, H * i / 10)], fill=(255, 255, 255, 90), width=1)
        d.text((W * i / 10 + 2, H - 22), f".{i}", font=f, fill="cyan")
        d.text((2, H * i / 10 + 1), f".{i}", font=f, fill="cyan")
    if a.bolge:
        x0, y0, x1, y1 = map(float, a.bolge.split(","))
        d.rectangle([x0 * W, y0 * H, x1 * W, y1 * H], outline="yellow", width=3)
    d.rectangle([0, 0, 120, 26], fill="black"); d.text((4, 2), f"{t:.2f}", font=f, fill="yellow")
    tiles.append(im); t += a.adim
cols = 4; rows = (len(tiles) + cols - 1) // cols
th = tiles[0].height
sheet = Image.new("RGB", (640 * cols, th * rows))
for i, im in enumerate(tiles): sheet.paste(im, ((i % cols) * 640, (i // cols) * th))
sheet.save(a.cikti, quality=88); print(a.cikti, len(tiles), "kare", "| dosyanın görüntüsü", aralik_yazi(k))
