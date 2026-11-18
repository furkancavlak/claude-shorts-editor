"""kamera_bul.py - suggest where the streamer's camera box is in a long recording (Klip style, 17.11.2026).

    python kod/kamera_bul.py <recording> <out_dir> [--bas S --son S] [--kare 24]

Writes <out_dir>/kamera.json, <out_dir>/kamera-kare.jpg (a clean frame, for the panel) and
<out_dir>/kamera-bak.jpg (same frame with the face in green and the suggested box in magenta, for the eye check).
Prints one line "KAMERA x0,y0,x1,y1 YUZ x0,y0,x1,y1 (n/N kare)" or "KAMERA YOK: <reason>". Exit code 0 either way.

How: ~24 frames spread over the recording. A face detector (YuNet, kod/model/yunet.onnx, MIT; the grouping and
edge code is our own) looks for faces. A camera box shows the same face at the same
place in most frames (game characters move), so the biggest group of face centres that stay put is the streamer.
Around that face the box is the largest rectangle whose four sides are edges in almost every frame along their
whole length (the border of an OBS camera source never moves; game and room edges do not form a full rectangle).
A side may lie on the frame edge. This is only a suggestion: Claude looks at kamera-bak.jpg and confirms or corrects it
(panel/AJAN-TALIMATI.md, A, step 1), the user can redraw it in the panel.
A face that is not a human face (a cartoon or 3D character) is usually not found: then "KAMERA YOK" here does not
mean there is no camera; Claude decides from the frame.
"""
import ctypes, json, os, subprocess, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw

KOK = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(KOK, "model", "yunet.onnx")
EN = 1920          # frames are read at most this wide (faces in a small camera box need the pixels)
KUCUK = 960        # edge and motion maps at this width
EN_KUCUK_YUZ = 0.003   # a face smaller than this share of the frame area is not a streamer camera (a scoreboard avatar)
SIRA_UST = 0.15        # faces lined up side by side in the top strip of the frame are a player list, not a camera
ESIK = 0.8         # face score: at 0.6 game frames gave false faces (wheels, trees: 0.64-0.76); real faces scored >= 0.857


def kisa_yol(p):
    """8.3 short path on Windows: OpenCV cannot open a path with Turkish letters (e.g. a folder named VİDEO)."""
    if os.name != "nt": return p
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(p, buf, 1024)
    return buf.value if n else p


def bilgi(dosya):
    j = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                            "stream=width,height:format=duration", "-of", "json", dosya], text=True))
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def kare_al(dosya, t, w, h):
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", dosya, "-frames:v", "1", "-vf", f"scale={w}:{h}",
                        "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    return np.frombuffer(b, np.uint8).reshape(h, w, 3) if len(b) == w * h * 3 else None


def yuz_eleme(yuzler, w, h):
    """Drop faces that cannot be the streamer camera (17.11.2026, CS2 scoreboard avatars were taken for the camera):
    smaller than EN_KUCUK_YUZ of the frame area, or in the top SIRA_UST strip with 2+ faces of similar size in a row
    beside them in the same frame. Returns (kept, dropped count)."""
    kalan, at = [], 0
    for a in yuzler:
        if a[3] * a[4] < EN_KUCUK_YUZ * w * h: at += 1; continue
        cy = a[2] + a[4] / 2
        if cy < SIRA_UST * h:
            sira = [b for b in yuzler if b is not a and b[0] == a[0] and abs(b[2] + b[4] / 2 - cy) < 0.5 * a[4]
                    and 0.6 < (b[3] * b[4]) / (a[3] * a[4]) < 1.6]
            if len(sira) >= 2: at += 1; continue
        kalan.append(a)
    return kalan, at


def yuz_grubu(yuzler, w):
    """yuzler: [(frame index, x, y, fw, fh, score)] -> the biggest group whose centres stay within 6 % of the width."""
    en_iyi = []
    for a in yuzler:
        ca = (a[1] + a[3] / 2, a[2] + a[4] / 2)
        g = [b for b in yuzler if abs(b[1] + b[3] / 2 - ca[0]) < 0.06 * w and abs(b[2] + b[4] / 2 - ca[1]) < 0.06 * w]
        g = list({b[0]: b for b in sorted(g, key=lambda b: b[5])}.values())     # one face per frame
        if len(g) > len(en_iyi): en_iyi = g
    return en_iyi


def adaylar(E, yuz, yon, h, w, en_cok=8):
    """Positions of straight lines that are an edge in >= 70 % of the frames, on one side of the face (nearest first).
    E = Ev for left/right, Eh for top/bottom; measured over the face's span widened by half a face."""
    x0, y0, x1, y1 = yuz; fw, fh = x1 - x0, y1 - y0
    if yon in ("sol", "sag"):
        sp = slice(max(0, int(y0 - 0.5 * fh)), min(h, int(y1 + 0.5 * fh)))
        prof = E[sp, :].mean(axis=0)
        ara = range(int(x0) - 2, 0, -1) if yon == "sol" else range(int(x1) + 2, w - 1)
    else:
        sp = slice(max(0, int(x0 - 0.5 * fw)), min(w, int(x1 + 0.5 * fw)))
        prof = E[:, sp].mean(axis=1)
        ara = range(int(y0) - 2, 0, -1) if yon == "ust" else range(int(y1) + 2, h - 1)
    out = []
    for c in ara:
        if prof[c] >= 0.7 and prof[c] >= prof[c - 1] and prof[c] >= prof[min(len(prof) - 1, c + 1)]: out.append(c)
        if len(out) >= en_cok: break
    out.append({"sol": 0, "ust": 0, "sag": w, "alt": h}[yon])          # the frame edge is always a candidate
    return out


def hat_puani(Ev, Eh, x0, y0, x1, y1):
    """How much of each side of the rectangle is a lasting edge (0-1); a side on the frame edge counts 1."""
    h, w = Ev.shape
    # the weakest tenth of the side counts: a side that runs past the real box corner into the game is not an edge there
    def zayif(v): return float(min(p.mean() for p in np.array_split(v, 10))) if len(v) >= 10 else 0.0
    def dikey(c):
        if c <= 0 or c >= w: return 1.0
        return zayif(Ev[y0:y1, max(0, c - 1): c + 2].max(axis=1))
    def yatay(r):
        if r <= 0 or r >= h: return 1.0
        return zayif(Eh[max(0, r - 1): r + 2, x0:x1].max(axis=0))
    return {"sol": dikey(x0), "sag": dikey(x1), "ust": yatay(y0), "alt": yatay(y1)}


def kutu_bul(Ev, Eh, yuz):
    """The camera box = the largest rectangle around the face whose four sides are lasting edges along their whole
    length (the border of an OBS camera source never moves; a game edge or a room edge does not run a full rectangle).
    Returns ((x0, y0, x1, y1), per-side scores) in KUCUK pixels, or (None, None)."""
    h, w = Ev.shape
    A = {y: adaylar(Ev if y in ("sol", "sag") else Eh, yuz, y, h, w) for y in ("sol", "sag", "ust", "alt")}
    en, en_alan, en_p = None, 0, None
    for x0 in A["sol"]:
        for x1 in A["sag"]:
            for y0 in A["ust"]:
                for y1 in A["alt"]:
                    alan = (x1 - x0) * (y1 - y0)
                    if alan > 0.6 * w * h or alan <= en_alan: continue
                    p = hat_puani(Ev, Eh, x0, y0, x1, y1)
                    # every side a lasting edge (>= 0.6); one weaker side (>= 0.45: a busy HUD bar under the box in
                    # dark game frames) is allowed when the four sides together are clearly a frame (mean >= 0.8)
                    v = list(p.values())
                    if min(v) >= 0.6 or (min(v) >= 0.45 and sum(v) / 4 >= 0.8): en, en_alan, en_p = (x0, y0, x1, y1), alan, p
    return en, en_p


def dedektor(w, h, esik=ESIK):
    """YuNet face detector for frames of w x h."""
    # short dir + real file name: OpenCV picks the model format from the ".onnx" extension
    return cv2.FaceDetectorYN.create(os.path.join(kisa_yol(os.path.dirname(MODEL)), "yunet.onnx"), "", (w, h), esik)


_DEDEKTOR = {}


def yuz_var_mi(dosya, kutu, zamanlar, esik=0.7):
    """Is there a face inside the camera box `kutu` (0-1 of the frame) at these seconds of the recording?
    Used by klip_bul.py: a moment where the streamer's chair is empty is a weak clip. The box is widened by 10 %
    (the face may lean out of a tight box) and read at >= 320 px wide. Returns [(second, score or 0.0)]."""
    W0, H0, _ = bilgi(dosya)
    x0, y0 = max(0.0, kutu[0] - 0.1 * (kutu[2] - kutu[0])), max(0.0, kutu[1] - 0.1 * (kutu[3] - kutu[1]))
    x1, y1 = min(1.0, kutu[2] + 0.1 * (kutu[2] - kutu[0])), min(1.0, kutu[3] + 0.1 * (kutu[3] - kutu[1]))
    cx, cy = int(x0 * W0) // 2 * 2, int(y0 * H0) // 2 * 2
    cw, ch = max(16, int((x1 - x0) * W0) // 2 * 2), max(16, int((y1 - y0) * H0) // 2 * 2)
    ow = max(320, cw) // 2 * 2; oh = int(round(ch * ow / cw)) // 2 * 2
    if (ow, oh, esik) not in _DEDEKTOR: _DEDEKTOR[(ow, oh, esik)] = dedektor(ow, oh, esik)   # one per size: called per candidate
    det = _DEDEKTOR[(ow, oh, esik)]; out = []
    for t in zamanlar:
        b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", dosya, "-frames:v", "1", "-vf",
                            f"crop={cw}:{ch}:{cx}:{cy},scale={ow}:{oh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                           capture_output=True).stdout
        if len(b) != ow * oh * 3: out.append((t, 0.0)); continue
        _, fs = det.detect(np.frombuffer(b, np.uint8).reshape(oh, ow, 3).copy())
        out.append((t, max((float(f[14]) for f in fs), default=0.0) if fs is not None else 0.0))
    return out


def bul(dosya, N=24, bas=None, son=None):
    """The camera box suggestion without writing anything -> (sonuc dict, frames [(t, bgr)], face group, w, h)."""
    W0, H0, sure = bilgi(dosya)
    bas = 0.0 if bas is None else bas
    son = sure if son is None else son
    w = min(EN, W0) // 2 * 2; h = int(round(H0 * w / W0)) // 2 * 2
    kw, kh = KUCUK, int(round(KUCUK * h / w)) // 2 * 2
    det = dedektor(w, h)
    kareler, yuzler = [], []
    for i, t in enumerate(np.linspace(bas + 0.04 * (son - bas), son - 0.04 * (son - bas), N)):
        f = kare_al(dosya, t, w, h)
        if f is None: continue
        kareler.append((t, f))
        _, fs = det.detect(f)
        for y in (fs if fs is not None else []):
            yuzler.append((len(kareler) - 1, *[float(v) for v in y[:4]], float(y[14])))
    sonuc = {"kayit": os.path.abspath(dosya), "kayit_px": [W0, H0], "kare": len(kareler), "yuz_bulunan_kare": 0,
             "kamera": None, "yuz": None, "kenar_puan": None, "not": ""}
    yuzler, elenen = yuz_eleme(yuzler, w, h)
    sonuc["elenen_yuz"] = elenen
    grup = yuz_grubu(yuzler, w)
    if len(kareler) < 4:
        sonuc["not"] = "kayittan kare okunamadi"
    elif len(grup) < max(3, 0.4 * len(kareler)):
        sonuc["not"] = (f"sabit yerde duran yuz yok ({len(grup)}/{len(kareler)} karede ayni yerde yuz); kamera bulunamadi. "
                        "Karakter ya da cizgi yuz bulunmayabilir: kareye bakip karar ver")
        sonuc["yuz_bulunan_kare"] = len(grup)
    else:
        yb = np.median(np.array([[g[1], g[2], g[1] + g[3], g[2] + g[4]] for g in grup]), axis=0)
        sonuc["yuz_bulunan_kare"] = len(grup)
        # lasting-edge maps (small grey frames): share of frames in which a pixel is a vertical / horizontal edge
        # colour frames: a thin coloured border on a sky of the same brightness is invisible in grey
        G = np.stack([cv2.resize(f, (kw, kh), interpolation=cv2.INTER_AREA).astype(np.float32) for _, f in kareler])
        Ev = np.zeros((kh, kw), np.float32); Eh = np.zeros((kh, kw), np.float32)
        Ev[:, 1:] = (np.abs(np.diff(G, axis=2)).max(axis=3) > 18).mean(axis=0)
        Eh[1:, :] = (np.abs(np.diff(G, axis=1)).max(axis=3) > 18).mean(axis=0)
        q = kw / w; yk = yb * q
        kutu, puan = kutu_bul(Ev, Eh, yk)
        sonuc.update(yuz=[round(v, 4) for v in (yb[0] / w, yb[1] / h, yb[2] / w, yb[3] / h)])
        if kutu is None:
            sonuc["not"] = (f"yuz {len(grup)}/{len(kareler)} karede ayni yerde ama cevresinde kenarlari sabit bir kutu yok: "
                            "kayit belki tamamen kamera ya da kutunun kenari oyunla karisiyor; kareye bakip karar ver")
        else:
            # the right/bottom side is the first edge pixel of the half-size map, i.e. already outside the camera and
            # rounded up to that coarser grid: one frame pixel in (18.11.2026: 444/364 found, 443/363 real on 1920x1080)
            x1 = kutu[2] / kw - (1 / w if kutu[2] < kw else 0)
            y1 = kutu[3] / kh - (1 / h if kutu[3] < kh else 0)
            sonuc["kamera"] = [round(kutu[0] / kw, 4), round(kutu[1] / kh, 4), round(x1, 4), round(y1, 4)]
            sonuc["kenar_puan"] = {k: round(v, 2) for k, v in puan.items()}
            dayali = [k for k, v in zip(("sol", "ust", "sag", "alt"), kutu) if v in (0, kw, kh) ]
            sonuc["not"] = "kenarlar cizgiden bulundu" + (f"; karenin kenarina dayali: {', '.join(dayali)}" if dayali else "")
    return sonuc, kareler, grup, w, h


def main(a):
    dosya, cikti = a[0], a[1]
    os.makedirs(cikti, exist_ok=True)
    N = int(a[a.index("--kare") + 1]) if "--kare" in a else 24
    bas = float(a[a.index("--bas") + 1]) if "--bas" in a else None
    son = float(a[a.index("--son") + 1]) if "--son" in a else None
    sonuc, kareler, grup, w, h = bul(dosya, N, bas, son)
    # frames for the panel and for the eye check: a frame where the face is (or the middle one)
    if kareler:
        i = grup[len(grup) // 2][0] if len(grup) >= 3 else len(kareler) // 2
        t, f = kareler[i]
        img = Image.fromarray(f[:, :, ::-1]); img.save(os.path.join(cikti, "kamera-kare.jpg"), quality=88)
        d = ImageDraw.Draw(img)
        if sonuc["yuz"]:
            y = sonuc["yuz"]; d.rectangle([y[0] * w, y[1] * h, y[2] * w, y[3] * h], outline=(60, 220, 90), width=3)
        if sonuc["kamera"]:
            # magenta: stream overlays are often yellow, a yellow suggestion was mistaken for the stream's own frame
            k = sonuc["kamera"]; d.rectangle([k[0] * w, k[1] * h, k[2] * w - 1, k[3] * h - 1], outline=(255, 0, 255), width=4)
        img.save(os.path.join(cikti, "kamera-bak.jpg"), quality=88)
        sonuc["kare_sn"] = round(float(t), 2)
    json.dump(sonuc, open(os.path.join(cikti, "kamera.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    f2 = lambda r: ",".join(f"{v:.3f}" for v in r)
    if sonuc["kamera"]:
        print(f"KAMERA {f2(sonuc['kamera'])} YUZ {f2(sonuc['yuz'])} ({sonuc['yuz_bulunan_kare']}/{sonuc['kare']} kare; {sonuc['not']})")
    else:
        print(f"KAMERA YOK: {sonuc['not']}")


if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
