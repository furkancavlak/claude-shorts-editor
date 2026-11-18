"""motor.py - GTA Shorts edit engine, first pass (17.11.2026).

    python motor.py <plan.json> <out.mp4>

Every spoken sentence carries its PROOF: which source file, which seconds, which region of the frame
shows what the sentence claims. A sentence without a proof entry is refused (exit 3, nothing rendered).

Output: vertical 1080x1920 30 fps H.264 + AAC. Picture = proof footage framed toward the proof region
(slow push-in, follows the region if it moves), split screen for comparisons, word-by-word centred
captions locked to the voice (Anton, white, one emphasis colour #FFD43B), optional ring / arrow / frame
on the proof. Sound = the creator's voice + a quiet self-made music bed (muzik.py). Source audio is never
decoded (-an on every read). Ends on the last sentence; nothing is added after it.

Side files: <out>.rapor.json (what the gate checks), <out>.ses.wav / .muzik.wav / .mix.wav (stems).

Plan (times in ORIGINAL video seconds for sources, region coordinates 0-1 of the full source frame):
{
  "ses": "ses/ses.wav", "kelimeler": "ses/ses.json",        # from ses_yazi.py
  "kaynaklar": {"v5": {"dosya": "ham/v5/video.mp4", "ofset": "otomatik", "alan": "otomatik",
                       "etiket": "GTA V  2011"}},           # ofset: original second of file t=0. DEFAULT and
                                                            # almost always right: "otomatik" (= the file's own
                                                            # start_time, the seconds bak.py prints). A number is
                                                            # only for a clip whose seconds you want to count from
                                                            # some other video (e.g. cut at 95 s -> "ofset": 95).
  "cumleler": [
    {"metin": "Sentence as spoken.", "vurgu": ["word"],     # emphasis words (as written in metin)
     "duzen": "tek" | "bolunmus",                           # bolunmus = split screen, needs 2 proofs (top, bottom)
     "kanit": [{"kaynak": "v5", "bas": 31.5, "hiz": 0.5, "son": 32.6,
                "bolge": [x0,y0,x1,y1]  or  {"iz": [{"t": 31.5, "b": [..]}, {"t": 32.6, "b": [..]}]},
                "ne": "what the region shows that proves the sentence",
                "doluluk": 0.8, "itme": 0.08, "karart": 0,
                "alinti": {"metin": "Physical copies include a download code.",   # OPTIONAL quote card: the proof
                           "vurgu": ["download code"],                             # is the source's own sentence,
                           "ceviri": "Kutulu kopyada indirme kodu var.",           # typeset (never a fake
                           "kaynak_satiri": "Kaynak: ..., 24 Haziran 2026",        # screenshot). kaynak_satiri is
                           "baslik": "ROCKSTAR'IN KENDİ İFADESİ", "y": 0.16}}],    # REQUIRED; footage = moving bg.
              # playback: src = bas + t*hiz, frozen at son. doluluk = share of panel width the region fills.
              # SPEED (17.11 judder fix): sources are 30 fps like the output, so hiz < 1 by repeating frames
              # stutters. hiz 1.0 = normal (every output frame is the next source frame). 0 < hiz < 1 needs
              # "ara_kare": true = ffmpeg minterpolate makes the in-between frames (motion-compensated, per
              # shot, only the cropped area and seconds). A slowed shot without it is still rendered with
              # in-between frames (never repeats), but kapi.py fails the plan until it says so. hiz 0 = a still.
              # Do not let bas..son cross a scene cut: minterpolate morphs or holds a frame there.
     "isaretler": [{"panel": 0, "tur": "halka"|"ok"|"cerceve", "x": .5, "y": .5, "r": .3,
                    "kutu": [x0,y0,x1,y1], "yon": "ust", "t0": 0.3}],  # x/y/kutu relative to the proof region
     "cizim": {"tarif": "cizim/212.json", "kip": "ust"|"giris"|"kose"|"ara", "bas": 0.0}
              # OPTIONAL self-drawing sketch (cizim.py, guide CIZIM-REHBERI.md). ust/giris/kose = transparent layer
              # on the proof footage (proof still required); giris = only sentence 1, the hook; ara = the sketch
              # REPLACES the footage for this sentence: no "kanit" needed, but the recipe must carry a "kaynak"
              # line (the source of the fact). bas = seconds after the sentence starts (ara always 0).
              # QUOTE CARD vs SKETCH (17.11 v3): in a sentence with an ust/giris/kose sketch the card is drawn as a
              # one-line source strip at the top (kart_bicimi; the sketch tells the fact). Sentences without a
              # sketch in a plan that has sketches get the short card (no header). alinti.bicim "kart"|"kisa"|"serit"
              # or plan "kart": "tam"|"kisa" override. Plans without sketches look exactly as before.
              # PLACE: an ust/giris sketch whose recipe has no region (or "bolge": "otomatik") is moved, same size,
              # to the calmest band of its sentence's footage (bos_yer); "cizim": {..., "yer": "sabit"} keeps it.
    }],
  "muzik": {"db": -20, "acik": true}                         # bed level under the voice (dB vs voice RMS)
}
"""
import difflib, json, math, os, re, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1080, 1920, 30, 48000
KOK = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(KOK, "font", "Anton.ttf")
BEYAZ, VURGU = (255, 255, 255), (0xFF, 0xD4, 0x3B)
SAFE_L, SAFE_R = 60, 150          # Shorts buttons sit on the right edge
BANT = 160                        # split screen: dark band between the panels that carries the caption
KUYRUK = 0.45                     # seconds kept after the last word (no outro, no call to action)


# ---------------------------------------------------------------- sources
def kaynak_bilgi(dosya, ofset="otomatik", alan="otomatik"):
    # HLS downloads of H.264 come out as MPEG-TS (even when named .mp4): input seeking in TS is off by up to
    # ~1 s. Remux once (stream copy, video only) to a real MP4 next to it and keep the original start second.
    fmt = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=format_name,start_time",
                                   "-of", "csv=p=0", dosya], text=True).strip().split(",")
    if fmt[0] == "mpegts":
        ts_bas = float(fmt[-1]); mp4 = dosya + ".remux.mp4"
        if not os.path.isfile(mp4):
            subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", dosya, "-map", "0:v:0", "-c", "copy", "-an", mp4])
        k = kaynak_bilgi(mp4, "otomatik", alan)
        yeni = ts_bas if ofset == "otomatik" else float(ofset)        # -ss is relative to the file start
        k["ilk"] += yeni - k["ofset"]; k["bitis"] += yeni - k["ofset"]; k["ofset"] = yeni
        return k
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,r_frame_rate:format=start_time,duration", "-of", "json", dosya],
                                  text=True)
    j = json.loads(out); s = j["streams"][0]; n, d = s["r_frame_rate"].split("/")
    k = {"dosya": dosya, "w": int(s["width"]), "h": int(s["height"]), "fps": float(n) / float(d),
         "bas_dosya": float(j["format"].get("start_time", 0) or 0), "sure": float(j["format"]["duration"])}
    k["ofset"] = k["bas_dosya"] if ofset == "otomatik" else float(ofset)
    # the seconds that really hold pictures, in ORIGINAL seconds. Clips cut out of a longer video often start
    # at 46.8 s or 136.4 s and their container "duration" counts from 0, so duration alone is misleading.
    ilk, son = _goruntu_araligi(dosya, k["fps"])
    if ilk is None: ilk, son = k["bas_dosya"], k["bas_dosya"] + k["sure"]
    k["ilk"] = round(k["ofset"] + (ilk - k["bas_dosya"]), 3); k["bitis"] = round(k["ofset"] + (son - k["bas_dosya"]), 3)
    if alan == "otomatik":
        r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", str(min(1.0, k["sure"] / 2)), "-t", "2", "-i", dosya, "-an",
                            "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"], capture_output=True, text=True).stderr
        m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r)
        if m:
            cw, ch, cx, cy = map(int, m[-1]); k["alan"] = [cx / k["w"], cy / k["h"], (cx + cw) / k["w"], (cy + ch) / k["h"]]
        else: k["alan"] = [0, 0, 1, 1]
    else: k["alan"] = alan
    return k


def _goruntu_araligi(dosya, fps):
    """(first, end) presentation seconds of the video stream as stored in the file (end = last frame + 1/fps).
    Reads packet times only (no decoding)."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time",
                              "-of", "csv=p=0", dosya], capture_output=True, text=True, check=True).stdout
        t = [float(x) for x in out.split() if x.replace(".", "", 1).replace("-", "", 1).isdigit()]
        return (min(t), max(t) + 1.0 / fps) if t else (None, None)
    except (subprocess.CalledProcessError, ValueError):
        return None, None


def aralik_yazi(k):
    """Turkish one-liner: which original seconds this file covers."""
    v = lambda x: f"{x:.2f}".replace(".", ",")
    return f"{v(k['ilk'])} – {v(k['bitis'])} sn ({v(k['bitis'] - k['ilk'])} sn görüntü, ofset {v(k['ofset'])})"


def _oku(k, bas, sure, kutu=None, tek=False):
    """Frames from original second `bas` for `sure` s, cropped to pixel box kutu=(x,y,w,h). Video only."""
    rel = max(0.0, bas - k["ofset"])
    vf = f"crop={kutu[2]}:{kutu[3]}:{kutu[0]}:{kutu[1]}" if kutu else "null"
    w, h = (kutu[2], kutu[3]) if kutu else (k["w"], k["h"])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{rel:.3f}", "-i", k["dosya"]] + (["-frames:v", "1"] if tek else ["-t", f"{sure:.3f}"]) + ["-an",
                          "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    n = len(raw) // (w * h * 3)
    if n == 0: raise RuntimeError(f"kare okunamadı: {k['dosya']} @ {bas} sn. Bu dosyanın görüntüsü {aralik_yazi(k)}. "
                                  "Saniye bu aralıkta değilse planda o kaynağın \"ofset\" değeri yanlıştır (\"otomatik\" yaz).")
    return np.frombuffer(raw[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)


def kare_al(k, t):
    return _oku(k, t, 0, tek=True)[0]


# ---------------------------------------------------------------- speed / motion method
ARA_KARE_VF = "minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"


def hareket_yontemi(kn):
    """How a proof shot moves: 'donuk' (hiz 0, a still), 'normal' (hiz >= 1, every frame is a real frame),
    'ara_kare' (0 < hiz < 1 with generated in-between frames). Slowing down by repeating frames is gone."""
    hiz = kn.get("hiz", 1.0)
    if hiz <= 0: return "donuk"
    if hiz >= 1 - 1e-9: return "normal"
    return "ara_kare"


def ara_kare_uret(k, bas, son, hiz, kutu, hedef):
    """Slow motion without repeated frames: crop kutu=(x,y,w,h) of original seconds bas..son, stretch time by
    1/hiz and let minterpolate build motion-compensated frames at the output rate. Output frame n shows
    original second bas + n*hiz/FPS. Stored losslessly-enough (x264 crf 8) as `hedef`."""
    rel = max(0.0, bas - k["ofset"]); sure = son - bas + 2.5 / k["fps"]
    vf = (f"crop={kutu[2]}:{kutu[3]}:{kutu[0]}:{kutu[1]},setpts=(PTS-STARTPTS)/{hiz:.6f},"
          + ARA_KARE_VF.format(fps=FPS))
    # -t BEFORE -i: it limits the source seconds read; after -i it would cut the stretched output short
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{rel:.3f}", "-t", f"{sure:.3f}", "-i", k["dosya"], "-an",
                    "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "8", "-pix_fmt", "yuv444p", hedef],
                   check=True)
    return hedef


# ---------------------------------------------------------------- plan checks
def kanit_hatalari(plan, kaynaklar=None):
    """List of reasons the plan must not be rendered. Empty list = every sentence has a proof."""
    err = []
    for i, c in enumerate(plan.get("cumleler", []), 1):
        if (c.get("cizim") or {}).get("kip") == "ara": continue      # a sketch sentence: its source line is the proof (cizim_hatalari)
        ks = c.get("kanit") or []
        if not ks: err.append(f"cumle {i} KANITSIZ: '{c.get('metin', '')}'"); continue
        gerek = 2 if c.get("duzen") == "bolunmus" else 1
        if len(ks) != gerek: err.append(f"cumle {i}: duzen '{c.get('duzen', 'tek')}' {gerek} kanit ister, {len(ks)} var")
        for j, kn in enumerate(ks):
            nm = f"cumle {i} kanit {j + 1}"
            if kn.get("kaynak") not in plan.get("kaynaklar", {}): err.append(f"{nm}: kaynak yok '{kn.get('kaynak')}'"); continue
            if not str(kn.get("ne", "")).strip(): err.append(f"{nm}: 'ne' bos (bolge neyi gosteriyor?)")
            if not isinstance(kn.get("bas"), (int, float)): err.append(f"{nm}: 'bas' saniyesi yok")
            a = kn.get("alinti")
            if a is not None:   # quote card: the quote and where it was said must both be on screen
                if not isinstance(a, dict) or not str(a.get("metin", "")).strip(): err.append(f"{nm}: alinti kartinda metin yok")
                elif len(str(a.get("kaynak_satiri", "")).strip()) < 12: err.append(f"{nm}: alinti kartinda kaynak satiri yok")
            b = kn.get("bolge")
            kutular = [z["b"] for z in b["iz"]] if isinstance(b, dict) and "iz" in b else [b]
            for kb in kutular:
                if not (isinstance(kb, list) and len(kb) == 4 and 0 <= kb[0] < kb[2] <= 1 and 0 <= kb[1] < kb[3] <= 1):
                    err.append(f"{nm}: bolge gecersiz {kb}"); break
            if kaynaklar and kn.get("kaynak") in kaynaklar and isinstance(kn.get("bas"), (int, float)):
                k = kaynaklar[kn["kaynak"]]
                son = kn.get("son", kn["bas"] + 1)
                if kn["bas"] < k["ilk"] - 0.05 or son > k["bitis"] + 0.05:
                    err.append(f"{nm}: {kn['bas']}-{son} sn dosyada yok; '{kn['kaynak']}' görüntüsü {aralik_yazi(k)}. "
                               "Saniyeleri bak.py karesindeki gibi yaz, ofset \"otomatik\" kalsın")
    if not plan.get("cumleler"): err.append("plan bos: cumle yok")
    err += tekrar_hatalari(plan)
    err += cizim_hatalari(plan)
    return err


def cizim_tarif(plan, cz):
    """Recipe of a sentence's sketch with the plan's placement mode written into it (file relative to the plan, or inline)."""
    t = cz.get("tarif")
    if isinstance(t, dict): T = json.loads(json.dumps(t))
    else:
        yol_ = t if os.path.isabs(str(t)) else os.path.join(plan.get("_kok", "."), str(t))
        T = json.load(open(yol_, encoding="utf-8"))
    y = T.get("yerlesim"); y = {"kip": y} if isinstance(y, str) else dict(y or {}); y["kip"] = cz.get("kip", "ust"); T["yerlesim"] = y
    if y["kip"] != "ara": T["itme"] = 0        # on footage the engine's own push-in moves the picture; the sketch rides on it
    return T


def cizim_hatalari(plan):
    """Sketch entries that must not be rendered: unreadable recipe, a HATA from cizim.dogrula, a sketch that replaces
    the footage without a source line, a hook sketch outside the first sentence."""
    err = []
    for i, c in enumerate(plan.get("cumleler", []), 1):
        cz = c.get("cizim")
        if not cz: continue
        kip = cz.get("kip", "ust")
        if kip not in ("ara", "ust", "giris", "kose"): err.append(f"cumle {i} cizim: kip '{kip}' yok (ara / ust / giris / kose)"); continue
        try: T = cizim_tarif(plan, cz)
        except Exception as ex: err.append(f"cumle {i} cizim: tarif okunamadi ({ex})"); continue
        import cizim
        hs = [m for m in cizim.dogrula(T) if m.startswith("HATA")]
        if hs: err.append(f"cumle {i} cizim: " + "; ".join(hs))
        turler = {str(o.get("tur", o.get("type", ""))).lower() for o in T.get("ogeler", []) if isinstance(o, dict)}
        if kip == "ara" and not turler & {"kaynak", "source", "kaynak_satiri"}:
            err.append(f"cumle {i} cizim (ara): tarifte kaynak satiri yok; goruntunun yerine gecen cizim kaynagini ekranda yazmali")
        if kip == "giris" and i != 1: err.append(f"cumle {i} cizim: 'giris' (kanca) kipi yalniz ilk cumlede olur")
    return err


def tekrar_hatalari(plan):
    """The same shot must not be shown twice. Two proofs of DIFFERENT sentences that read overlapping seconds of the
    same file (bas..son, son defaults to bas + 1) are refused. This is how a list intro montage used to repeat an
    item's shot in short clips (kabul testi 17.11: intro 'ucak 54,5-55,1', item 3 'ucak 54,45-56,35'). Fix in the
    plan: give the intro the first part of the shot and start the item after it, or shorten the montage."""
    dosya = lambda ad: os.path.normcase(os.path.normpath(str(plan.get("kaynaklar", {}).get(ad, {}).get("dosya", ad))))
    araliklar = []
    for i, c in enumerate(plan.get("cumleler", []), 1):
        for kn in c.get("kanit") or []:
            if not isinstance(kn.get("bas"), (int, float)): continue
            son = kn.get("son", kn["bas"] + 1)
            if kn.get("hiz", 1.0) <= 0: son = kn["bas"] + 0.05       # a still shows one frame
            araliklar.append((i, kn.get("kaynak"), dosya(kn.get("kaynak")), float(kn["bas"]), float(son)))
    err = []
    for x in range(len(araliklar)):
        for y in range(x + 1, len(araliklar)):
            i, ka, da, a0, a1 = araliklar[x]; j, kb, db, b0, b1 = araliklar[y]
            ortak = min(a1, b1) - max(a0, b0)
            if i != j and da == db and ortak > 0.1:
                err.append(f"cumle {i} ve cumle {j} ayni cekimi gosteriyor: '{ka}' {max(a0, b0):.2f}-{min(a1, b1):.2f} sn "
                           f"iki kez ({ortak:.2f} sn). Cekimi bol (biri bitince digeri baslasin) ya da girisi kisalt")
    return err


# ---------------------------------------------------------------- words -> sentences
TR = str.maketrans({"İ": "i", "I": "ı"})


def norm(w): return re.sub(r"[^0-9a-zçğıöşü]", "", w.translate(TR).lower())


def hizala(cumleler, kelimeler):
    """Script words (plan spelling) get the voice timings of the Whisper words they match."""
    sk = [(ci, w) for ci, c in enumerate(cumleler) for w in c["metin"].split()]
    sn = [norm(w) for _, w in sk]; wn = [norm(k[0]) for k in kelimeler]
    zam = [None] * len(sk)
    for op, a0, a1, b0, b1 in difflib.SequenceMatcher(None, sn, wn, autojunk=False).get_opcodes():
        if op == "equal" or (op == "replace" and a1 - a0 == b1 - b0):
            for d in range(a1 - a0): zam[a0 + d] = [kelimeler[b0 + d][1], kelimeler[b0 + d][2]]
        elif op == "replace":
            t0, t1 = kelimeler[b0][1], kelimeler[b1 - 1][2]
            L = [max(1, len(sn[a])) for a in range(a0, a1)]; acc = t0
            for a, l in zip(range(a0, a1), L):
                d = (t1 - t0) * l / sum(L); zam[a] = [acc, acc + d]; acc += d
    for i in range(len(zam)):                       # fill words Whisper did not hear by interpolation
        if zam[i] is None:
            j = i
            while j < len(zam) and zam[j] is None: j += 1
            a = zam[i - 1][1] if i > 0 else 0.0
            b = zam[j][0] if j < len(zam) else (kelimeler[-1][2] if kelimeler else a + 0.4 * (j - i))
            for q in range(i, j): zam[q] = [a + (b - a) * (q - i) / (j - i), a + (b - a) * (q - i + 1) / (j - i)]
    out = [[] for _ in cumleler]
    for (ci, w), z in zip(sk, zam): out[ci].append({"w": w, "a": round(z[0], 3), "b": round(z[1], 3)})
    return out


# ---------------------------------------------------------------- drawing
_fcache = {}


def font(s):
    if s not in _fcache: _fcache[s] = ImageFont.truetype(FONT, s)
    return _fcache[s]


def yazi(metin, boyut, renk, kontur=None):
    f = font(boyut); st = kontur or max(6, boyut // 11)
    bb = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), metin, font=f, stroke_width=st)
    img = Image.new("RGBA", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((10 - bb[0], 10 - bb[1]), metin, font=f, fill=renk, stroke_width=st, stroke_fill="black")
    return img


def yazi_taban(metin, boyut, kontur=None):
    """y of the font baseline inside the image yazi() returns (it crops to the ink, so this differs per word)."""
    f = font(boyut); st = kontur or max(6, boyut // 11)
    bb = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), metin, font=f, stroke_width=st)
    return 10 - bb[1] + f.getmetrics()[0]


def ok_ciz(d, tx, ty, yon, e):
    v = {"ust": (0, -1), "alt": (0, 1), "sol": (-1, 0), "sag": (1, 0)}[yon]
    L = 170 * e; ux, uy = v; px, py = -uy, ux
    bx, by = tx + ux * (40 + L), ty + uy * (40 + L)
    for w_, c, k in ((42, "black", 70), (26, VURGU, 62)):
        d.line([(bx, by), (tx + ux * 30, ty + uy * 30)], fill=c, width=w_)
        d.polygon([(tx - ux * (5 if c == "black" else 0), ty - uy * (5 if c == "black" else 0)),
                   (tx + ux * k + px * k * .7, ty + uy * k + py * k * .7),
                   (tx + ux * k - px * k * .7, ty + uy * k - py * k * .7)], fill=c)


def smooth(a): a = max(0.0, min(1.0, a)); return a * a * (3 - 2 * a)


# ---------------------------------------------------------------- quote card (proof = the source's own words)
KART_PX = {"baslik": 44, "metin": 60, "ceviri": 46, "kaynak": 40}   # font sizes in px of the 1080x1920 frame
_WINF = r"C:\Windows\Fonts"


def _kfont(ad, s):
    """Readable sans for running text (Segoe UI, then Arial); Anton if neither exists (non-Windows)."""
    for f in {"kalin": ("segoeuib.ttf", "arialbd.ttf"), "duz": ("segoeui.ttf", "arial.ttf")}[ad]:
        p = os.path.join(_WINF, f)
        if os.path.isfile(p):
            key = (p, s)
            if key not in _fcache: _fcache[key] = ImageFont.truetype(p, s)
            return _fcache[key]
    return font(s)


def _sar(parcalar, f, gen):
    """Word wrap of [(word, colour)] to width gen -> lines of [(word, colour)]."""
    satirlar, cur, w = [], [], 0.0; bosluk = f.getlength(" ")
    for p in parcalar:
        lw = f.getlength(p[0])
        if cur and w + bosluk + lw > gen: satirlar.append(cur); cur, w = [], 0.0
        w += (bosluk if cur else 0) + lw; cur.append(p)
    if cur: satirlar.append(cur)
    return satirlar


def alinti_kart(a, gen=W - 2 * SAFE_L):
    """Typeset quote card: header, the source sentence (English as written, key words in VURGU), a Turkish
    gloss and the source line. Returns (RGBA image, metrics for the gate)."""
    pad, ic = 44, gen - 2 * 44 - 14
    vur = {norm(w) for v in a.get("vurgu", []) for w in v.split()}
    fq, fg, fs = _kfont("kalin", KART_PX["metin"]), _kfont("kalin", KART_PX["ceviri"]), _kfont("duz", KART_PX["kaynak"])
    q = "\u201c" + a["metin"].strip() + "\u201d"
    qs = _sar([(w, VURGU if norm(w) in vur else BEYAZ) for w in q.split()], fq, ic)
    gs = _sar([(w, (228, 228, 228)) for w in a.get("ceviri", "").split()], fg, ic) if a.get("ceviri") else []
    ss = _sar([(w, (205, 205, 205)) for w in a["kaynak_satiri"].split()], fs, ic)
    bas = a.get("baslik", "ROCKSTAR'IN KENDİ İFADESİ")
    hb = font(KART_PX["baslik"]).getbbox(bas)
    lh = lambda f, k: int(f.size * k)
    yuk = pad + (hb[3] + 26) + len(qs) * lh(fq, 1.22) + (40 + len(gs) * lh(fg, 1.25) if gs else 0) + 30 + len(ss) * lh(fs, 1.3) + pad - 8
    img = Image.new("RGBA", (gen, yuk), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, gen - 1, yuk - 1], 26, fill=(12, 12, 16, 236))
    d.rounded_rectangle([0, 0, 14, yuk - 1], 7, fill=VURGU)
    x0, y = 14 + pad, pad
    d.text((x0, y - hb[1]), bas, font=font(KART_PX["baslik"]), fill=VURGU); y += hb[3] - hb[1] + 26
    def yaz_sat(satirlar, f, k):
        nonlocal y
        for s in satirlar:
            x = x0
            for w, c in s: d.text((x, y), w, font=f, fill=c); x += f.getlength(w + " ")
            y += lh(f, k)
    yaz_sat(qs, fq, 1.22)
    if gs:
        y += 22; d.line([(x0, y), (x0 + 120, y)], fill=(110, 110, 120), width=3); y += 18; yaz_sat(gs, fg, 1.25)
    y += 30; ys = y; yaz_sat(ss, fs, 1.3)
    cap = lambda f: f.getbbox("H")[3] - f.getbbox("H")[1]
    m = {"metin_px": fq.size, "metin_buyuk_harf_px": cap(fq), "ceviri_px": fg.size if gs else 0,
         "kaynak_px": fs.size, "kaynak_buyuk_harf_px": cap(fs), "kaynak_satiri": a["kaynak_satiri"],
         "satir": {"alinti": len(qs), "ceviri": len(gs), "kaynak": len(ss)}, "kaynak_y": ys}
    return img, m


KART_KISA_PX = {"metin": 56, "ceviri": 44, "kaynak": 40}   # short card (17.11 v3): no header, tighter, still >= gate sizes


def alinti_kart_kisa(a, gen=W - 2 * SAFE_L):
    """Short quote card for plans with sketches: no header line, smaller gaps, 56 px quote - about a third less
    height than alinti_kart (which stays as it was, so old plans render the same). Same metrics."""
    pad = 32; ic = gen - 2 * pad - 14
    vur = {norm(w) for v in a.get("vurgu", []) for w in v.split()}
    fq, fg, fs = (_kfont("kalin", KART_KISA_PX["metin"]), _kfont("kalin", KART_KISA_PX["ceviri"]),
                  _kfont("duz", KART_KISA_PX["kaynak"]))
    q = "“" + a["metin"].strip() + "”"
    qs = _sar([(w, VURGU if norm(w) in vur else BEYAZ) for w in q.split()], fq, ic)
    gs = _sar([(w, (228, 228, 228)) for w in a.get("ceviri", "").split()], fg, ic) if a.get("ceviri") else []
    ss = _sar([(w, (205, 205, 205)) for w in a["kaynak_satiri"].split()], fs, ic)
    lq, lg, ls = int(fq.size * 1.18), int(fg.size * 1.22), int(fs.size * 1.26)
    yuk = pad + len(qs) * lq + (14 + len(gs) * lg if gs else 0) + 18 + len(ss) * ls + pad - 10
    img = Image.new("RGBA", (gen, yuk), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, gen - 1, yuk - 1], 24, fill=(12, 12, 16, 232))
    d.rounded_rectangle([0, 0, 14, yuk - 1], 7, fill=VURGU)
    x0, y = 14 + pad, pad - 4
    def yaz_sat(satirlar, f, l):
        nonlocal y
        for s in satirlar:
            x = x0
            for w, c in s: d.text((x, y), w, font=f, fill=c); x += f.getlength(w + " ")
            y += l
    yaz_sat(qs, fq, lq)
    if gs: y += 14; yaz_sat(gs, fg, lg)
    y += 18; ys = y; yaz_sat(ss, fs, ls)
    cap = lambda f: f.getbbox("H")[3] - f.getbbox("H")[1]
    m = {"bicim": "kisa", "metin_px": fq.size, "metin_buyuk_harf_px": cap(fq), "ceviri_px": fg.size if gs else 0,
         "kaynak_px": fs.size, "kaynak_buyuk_harf_px": cap(fs), "kaynak_satiri": a["kaynak_satiri"],
         "satir": {"alinti": len(qs), "ceviri": len(gs), "kaynak": len(ss)}, "kaynak_y": ys, "yukseklik": yuk}
    return img, m


def kaynak_serit(a, gen=W - 2 * SAFE_L):
    """Source strip (17.11 v3): in a sentence with a sketch on the footage the sketch tells the fact, so the big
    quote card would only fight it; one line with the source is the proof's other half. 50 px (48 px if that
    makes it one line); a longer line wraps to two at 50 px rather than shrinking (40 px was too small on a
    phone), never cut: the gate compares it with the plan. It sits above the Shorts buttons, so it may use the
    full width between the side margins. Keep source lines short: "Kaynak: rockstargames.com/VI"."""
    s = a["kaynak_satiri"].strip(); ic = gen - 2 * 22 - 10
    fs = _kfont("duz", 50)
    if fs.getlength(s) > ic and _kfont("duz", 48).getlength(s) <= ic: fs = _kfont("duz", 48)
    fk = _kfont("kalin", fs.size)
    vurgulu = s.split()[0].lower().rstrip(":") in ("kaynak", "source")      # "Kaynak:" bold, in the accent colour
    ss = _sar([(w, (232, 232, 232)) for w in s.split()], fs, ic); lh = int(fs.size * 1.28)
    yuk = 14 + len(ss) * lh + 8
    img = Image.new("RGBA", (gen, yuk), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, gen - 1, yuk - 1], 18, fill=(12, 12, 16, 222))
    d.rounded_rectangle([0, 0, 10, yuk - 1], 5, fill=VURGU)
    y = 10
    for si, satir in enumerate(ss):
        x = 10 + 22
        for wi, (w, c) in enumerate(satir):
            f, c2 = (fk, VURGU) if (vurgulu and si == 0 and wi == 0) else (fs, c)
            d.text((x, y), w, font=f, fill=c2); x += f.getlength(w) + fs.getlength(" ")
        y += lh
    cap = fs.getbbox("H")[3] - fs.getbbox("H")[1]
    m = {"bicim": "serit", "metin_px": 0, "metin_buyuk_harf_px": 0, "ceviri_px": 0, "kaynak_px": fs.size,
         "kaynak_buyuk_harf_px": cap, "kaynak_satiri": a["kaynak_satiri"], "satir": {"alinti": 0, "ceviri": 0, "kaynak": len(ss)},
         "kaynak_y": 10, "yukseklik": yuk}
    return img, m


SERIT_Y = 0.155        # strip top (share of frame height): under the list counter (y 150-270), above any sketch
SERIT_ALT = 0.255      # a sketch placed by the engine starts below the strip (two 50 px lines end at ~0.235 H)


def bos_yer(czi, lst, ust=0.17, alt=0.66):
    """Calmest place for a sketch on its sentence's footage (17.11 v3). The sketch keeps its size and its x; only
    its height on screen is chosen, between `ust` and `alt` (shares of H): the band whose footage moves and
    changes least (Sobel edge energy of 8 frames over the sketch's time) and does not cover a proof region
    (a region that is the proof itself, not a quote card's background). Returns the region [x0, y0, x1, y1]."""
    import cv2
    k = czi["icerik"]; S = 10
    hh = k[3] - k[1]; gx0, gx1 = max(0, int(k[0] / S)), min(W // S, int(math.ceil(k[2] / S)))
    acc = np.zeros((H // S, W // S), np.float32); ozne = np.zeros_like(acc)
    son = czi["f0"] + max(1, czi["beklenen"]) - 1
    for f in sorted({int(v) for v in np.linspace(czi["f0"], son, 8)}):
        small = np.zeros_like(acc)
        for p in lst:
            n = min(max(0, f - p["f0"]), len(p["kar"]) - 1)
            x0, y0, cw, ch = p["kar"][n]; F = p["frames"]
            a = min(max(0, int(math.floor((p["src"][n] - p["kn"]["bas"]) * p["kps"] + 1e-6))), len(F) - 1)
            cr = F[a][max(0, int(y0 - p["uy"])):int(y0 - p["uy"] + ch), max(0, int(x0 - p["ux"])):int(x0 - p["ux"] + cw)]
            if cr.size == 0: continue
            g = cv2.resize(cv2.cvtColor(np.ascontiguousarray(cr), cv2.COLOR_RGB2GRAY), (p["PW"] // S, p["PH"] // S),
                           interpolation=cv2.INTER_AREA).astype(np.float32)
            oy = p["oy"] // S; small[oy:oy + g.shape[0], :g.shape[1]] = g[: acc.shape[0] - oy]
            if not p["kn"].get("alinti"):           # the region IS the proof: keep the sketch off it
                R = p["R"][n]; sc = p["PW"] / cw
                bx = [(R[0] - x0) * sc / S, (R[1] - y0) * sc / S + oy, (R[2] - x0) * sc / S, (R[3] - y0) * sc / S + oy]
                ozne[max(0, int(bx[1])):int(bx[3]) + 1, max(0, int(bx[0])):int(bx[2]) + 1] = 1
        acc += np.hypot(cv2.Sobel(small, cv2.CV_32F, 1, 0), cv2.Sobel(small, cv2.CV_32F, 0, 1))
    acc = acc / max(1e-6, acc.mean()) + 6.0 * ozne
    y_ust, y_alt = ust * H, alt * H
    if hh >= y_alt - y_ust:       # taller than the room: fill it (the fit shrinks the sketch)
        return [k[0] / W, ust, k[2] / W, alt]
    adaylar = np.arange(y_ust, y_alt - hh + 1, 0.01 * H)
    puan = [float(acc[int(y / S):int((y + hh) / S) + 1, gx0:gx1].mean()) + 0.4 * abs(y - k[1]) / H for y in adaylar]
    y = float(adaylar[int(np.argmin(puan))])
    return [(k[0] - 2) / W, y / H, (k[2] + 2) / W, (y + hh) / H]


def kart_bicimi(plan, c, a):
    """How a quote proof is typeset: 'kart' (full card, as before), 'kisa' (short card) or 'serit' (one source line).
    alinti.bicim wins; else a sentence with a sketch on the footage (ust / giris / kose) gets the strip; else the
    plan's "kart" ("tam" / "kisa"); else the short card when the plan has any sketch, the full card otherwise
    (plans without sketches render exactly as before)."""
    b = str(a.get("bicim", "")).lower()
    if b in ("kart", "tam"): return "kart"
    if b in ("kisa", "serit"): return b
    if (c.get("cizim") or {}).get("kip") in ("ust", "giris", "kose"): return "serit"
    pk = str(plan.get("kart", "")).lower()
    if pk in ("kart", "tam"): return "kart"
    if pk == "kisa": return "kisa"
    return "kisa" if any(x.get("cizim") for x in plan["cumleler"]) else "kart"


# ---------------------------------------------------------------- framing
def bolge_at(kn, s):
    b = kn["bolge"]
    if not (isinstance(b, dict) and "iz" in b): return list(b)
    iz = b["iz"]
    if s <= iz[0]["t"]: return list(iz[0]["b"])
    for p, q in zip(iz, iz[1:]):
        if p["t"] <= s <= q["t"]:
            u = (s - p["t"]) / max(1e-6, q["t"] - p["t"])
            return [p["b"][i] + (q["b"][i] - p["b"][i]) * u for i in range(4)]
    return list(iz[-1]["b"])


def kadraj(k, R, PW, PH, doluluk, zoom):
    """Crop box (x, y, w, h) in source px of aspect PW:PH around region R (px), clamped to the picture area."""
    rw, rh = R[2] - R[0], R[3] - R[1]
    cw = max(rw / doluluk, rh / doluluk * PW / PH) / zoom
    ch = cw * PH / PW
    ax0, ay0, ax1, ay1 = k["alan"][0] * k["w"], k["alan"][1] * k["h"], k["alan"][2] * k["w"], k["alan"][3] * k["h"]
    s = min(1.0, (ax1 - ax0) / cw, (ay1 - ay0) / ch)
    # min(): when the crop fills the whole picture height/width, float rounding can leave it 1e-13 px too big,
    # which put the box at -1e-13 and crashed PIL ("box offset can't be negative")
    cw, ch = min(cw * s, ax1 - ax0), min(ch * s, ay1 - ay0)
    cx, cy = (R[0] + R[2]) / 2, (R[1] + R[3]) / 2
    x0 = max(ax0, min(max(cx - cw / 2, ax0), ax1 - cw)); y0 = max(ay0, min(max(cy - ch / 2, ay0), ay1 - ch))
    return x0, y0, cw, ch


# ---------------------------------------------------------------- render
def main(plan_yolu, cikti):
    plan = json.load(open(plan_yolu, encoding="utf-8"))
    kok = os.path.dirname(os.path.abspath(plan_yolu)); plan["_kok"] = kok
    yol = lambda p: p if os.path.isabs(p) else os.path.join(kok, p)
    err = kanit_hatalari(plan)
    if err: print("RED - render yok:\n  " + "\n  ".join(err)); sys.exit(3)
    kaynaklar = {ad: kaynak_bilgi(yol(v["dosya"]), v.get("ofset", "otomatik"), v.get("alan", "otomatik")) | {"etiket": v.get("etiket", "")}
                 for ad, v in plan["kaynaklar"].items()}
    err = kanit_hatalari(plan, kaynaklar)
    if err: print("RED - render yok:\n  " + "\n  ".join(err)); sys.exit(3)

    sj = json.load(open(yol(plan["kelimeler"]), encoding="utf-8"))
    cs = plan["cumleler"]; kel = hizala(cs, sj["kelimeler"])
    sinir = []
    for i, c in enumerate(cs):
        a = 0.0 if i == 0 else kel[i][0]["a"] - 0.08
        sinir.append(a)
    son = kel[-1][-1]["b"] + KUYRUK
    sinir.append(son)
    nkare = int(math.ceil(son * FPS))

    # sketches (cizim.py): when each starts, its recipe with the placement mode, the sentence's words on its clock
    cizimler = [None] * len(cs)
    if any(c.get("cizim") for c in cs):
        import cizim, cizim_ses
        for i, c in enumerate(cs):
            cz = c.get("cizim")
            if not cz: continue
            T = cizim_tarif(plan, cz); kip = T["yerlesim"]["kip"]
            t0 = sinir[i] + (0.0 if kip == "ara" else float(cz.get("bas", 0.0)))
            if kip == "ara": T["sure"] = max(cizim.sure(T), round(sinir[i + 1] - t0, 3))   # the board holds (and keeps moving) to the cut
            kel_c = [{"w": w["w"], "a": round(w["a"] - t0, 3)} for w in kel[i]]
            f0 = int(math.ceil((t0 - 1e-9) * FPS)); f1 = int(math.ceil((sinir[i + 1] - 1e-9) * FPS))
            # place on the footage (17.11 v3): a sketch on the footage (ust / giris) without a region in its recipe, or
            # with "bolge": "otomatik" / plan "yer": "otomatik", is moved (same size) to the calmest band of its
            # sentence's footage, never onto the proof region. Done when the sentence's frames are loaded (bos_yer).
            Y = cizim.yerlesim(T)
            oto = kip in ("ust", "giris") and str(cz.get("yer", "")).lower() != "sabit" and (
                Y.get("otomatik") or str(cz.get("yer", "")).lower() == "otomatik" or Y.get("bolge") is None)
            cizimler[i] = dict(T=T, kip=kip, f0=f0, t0=t0, kel=kel_c, zk=None, zemin=str(T.get("zemin", "tahta")),
                               kutular=[k["kutu"] for k in cizim.kutular(T)], beklenen=max(0, f1 - f0),
                               mesaj=[m for m in cizim.dogrula(T) if not m.startswith("HATA")], oto=oto, yer=None,
                               icerik=cizim.icerik_kutusu(T) if oto else None)

    # per sentence, per panel: crop boxes for every output frame, then read only the union of them
    paneller = []   # [sentence][panel] -> dict
    for i, c in enumerate(cs):
        bol = c.get("duzen") == "bolunmus"; PW, PH = W, ((H - BANT) // 2 if bol else H)
        lst = []
        ara_cizim = cizimler[i] is not None and cizimler[i]["kip"] == "ara"
        for j, kn in enumerate([] if ara_cizim else c["kanit"]):
            k = kaynaklar[kn["kaynak"]]; t0, t1 = sinir[i], sinir[i + 1]
            hiz = kn.get("hiz", 1.0); sonsn = kn.get("son", kn["bas"] + (t1 - t0) * hiz)
            kar, srcs, Rs, don = [], [], [], []
            # frames that belong to this sentence are exactly those with t0 <= f/FPS < t1 (as in the frame loop);
            # round() used to drop the last one, which then repeated the previous frame at every sentence end
            fa, fb = int(math.ceil((t0 - 1e-9) * FPS)), int(math.ceil((t1 - 1e-9) * FPS))
            for f in range(fa, fb):
                u = (f / FPS - t0) / max(1e-6, t1 - t0)
                s = min(kn["bas"] + (f / FPS - t0) * hiz, sonsn)
                b = bolge_at(kn, s); R = [b[0] * k["w"], b[1] * k["h"], b[2] * k["w"], b[3] * k["h"]]
                kar.append(kadraj(k, R, PW, PH, kn.get("doluluk", 0.8), 1 + kn.get("itme", 0.08) * smooth(u)))
                srcs.append(s); Rs.append(R)
                don.append(hiz <= 0 or kn["bas"] + (f / FPS - t0) * hiz > sonsn + 1e-6)   # picture not advancing
            ux0 = max(0, int(min(x for x, y, w, h in kar))); uy0 = max(0, int(min(y for x, y, w, h in kar)))
            ux1 = min(k["w"], int(math.ceil(max(x + w for x, y, w, h in kar))) + 1)
            uy1 = min(k["h"], int(math.ceil(max(y + h for x, y, w, h in kar))) + 1)
            ux0 -= ux0 % 2; uy0 -= uy0 % 2; bw = (ux1 - ux0) // 2 * 2; bh = (uy1 - uy0) // 2 * 2
            yontem = hareket_yontemi(kn)
            if yontem == "ara_kare" and not kn.get("ara_kare"):
                print(f"UYARI cumle {i + 1}: hiz {hiz} ama planda \"ara_kare\": true yok - yine ara kareyle "
                      "yavaşlatılıyor (kare tekrarı yok); kapı bu planı planda yazana kadar geçirmez")
            lst.append(dict(kn=kn, k=k, kar=kar, src=srcs, R=Rs, don=don, frames=None, ux=ux0, uy=uy0, PW=PW, PH=PH,
                            oy=j * (PH + BANT), f0=fa, yontem=yontem, hiz=hiz, sonsn=sonsn,
                            kutu=(ux0, uy0, bw, bh), ara=(f"{cikti}.ara_c{i + 1}k{j + 1}.mp4" if yontem == "ara_kare" else None),
                            onceki=None, tekrar=0))
        paneller.append(lst)

    # in-between frames for slowed shots: one minterpolate job per shot, run side by side (ffmpeg's
    # minterpolate is mostly single-threaded), before the frame loop
    from concurrent.futures import ThreadPoolExecutor
    isler = [p for lst in paneller for p in lst if p["ara"]]
    if isler:
        t_ara = __import__("time").time()
        with ThreadPoolExecutor(max_workers=min(4, len(isler))) as ex:
            list(ex.map(lambda p: ara_kare_uret(p["k"], p["kn"]["bas"], p["sonsn"], p["hiz"], p["kutu"], p["ara"]), isler))
        print(f"ara kare: {len(isler)} çekim, {__import__('time').time() - t_ara:.0f} sn")

    def kareleri_yukle(p):
        if p["ara"]:      # already cropped; frame n = original second bas + n*hiz/FPS
            p["frames"] = _oku({"dosya": p["ara"], "ofset": 0.0, "ilk": 0.0, "bitis": 0.0,
                                "w": p["kutu"][2], "h": p["kutu"][3]}, 0.0,
                               (p["sonsn"] - p["kn"]["bas"]) / p["hiz"] + 3.0 / FPS)
            p["kps"] = FPS / p["hiz"]
        else:
            p["frames"] = _oku(p["k"], p["kn"]["bas"], p["sonsn"] - p["kn"]["bas"] + 2.5 / p["k"]["fps"], p["kutu"])
            p["kps"] = p["k"]["fps"]

    rapor = {"cumleler": [], "kelimeler": kel, "sure": round(son, 3), "ilk_kelime": kel[0][0]["a"]}
    for i, c in enumerate(cs):
        rapor["cumleler"].append({"metin": c["metin"], "t0": round(sinir[i], 3), "t1": round(sinir[i + 1], 3),
                                  "kanit": [{"kaynak": p["kn"]["kaynak"], "ne": p["kn"]["ne"], "kare": 0,
                                             "min_kisa_kenar": 1e9, "min_alan_orani": 1.0} for p in paneller[i]],
                                  "yazi_y": None, "kare": 0, "donuk_kare": 0, "madde": bool(c.get("madde")),
                                  "sayac": c.get("sayac", "")})
        czi = cizimler[i]
        if czi is not None:          # the gate (kapi.py 1 KANIT, 9 CIZIM) reads this
            rapor["cumleler"][i]["cizim"] = {"kip": czi["kip"], "tarif": c["cizim"].get("tarif") if isinstance(c["cizim"].get("tarif"), str) else "satir ici",
                                             "kare": 0, "beklenen": czi["beklenen"], "bas_sn": round(czi["t0"], 3),
                                             "kaynak": any(str(o.get("tur", "")).lower() in ("kaynak", "source", "kaynak_satiri")
                                                           for o in czi["T"].get("ogeler", []) if isinstance(o, dict)),
                                             "uyarilar": czi["mesaj"][:12]}

    sessiz = cikti + ".video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                            "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", sessiz], stdin=subprocess.PIPE)
    etiket_cache, kel_cache = {}, {}
    onceki_cumle = None; onceki_img = None
    for f in range(nkare):
        t = f / FPS
        i = max(q for q in range(len(cs)) if sinir[q] <= t + 1e-9) if t >= 0 else 0
        i = min(i, len(cs) - 1); c = cs[i]; u = (t - sinir[i]) / max(1e-6, sinir[i + 1] - sinir[i])
        img = Image.new("RGB", (W, H), (14, 14, 16)); d = ImageDraw.Draw(img)
        kutular, engel = [], []     # proof boxes, label boxes: the caption avoids both
        if i != onceki_cumle:          # load this sentence's frames, free the previous sentence's
            for q in (paneller[onceki_cumle] if onceki_cumle is not None else []): q["frames"] = None
            for q in paneller[i]: kareleri_yukle(q)
            onceki_cumle = i
            czi = cizimler[i]
            if czi is not None and czi["oto"] and paneller[i] and czi["icerik"]:
                ust_sinir = SERIT_ALT if any(kart_bicimi(plan, c, p["kn"]["alinti"]) == "serit" for p in paneller[i]
                                             if p["kn"].get("alinti")) else 0.17
                alt_sinir = min(0.66, (c.get("yazi_y") or 0.70) - 0.045)
                czi["yer"] = bos_yer(czi, paneller[i], ust_sinir, alt_sinir)
                y_ = czi["T"]["yerlesim"]; y_["bolge"] = czi["yer"]
                czi["kutular"] = [k["kutu"] for k in cizim.kutular(czi["T"])]
                rapor["cumleler"][i]["cizim"]["yer"] = [round(v, 3) for v in czi["yer"]]
        for j, p in enumerate(paneller[i]):
            n = min(f - p["f0"], len(p["kar"]) - 1); n = max(0, n)
            x0, y0, cw, ch = p["kar"][n]; s = p["src"][n]; k = p["k"]
            # every output frame takes exactly one stored frame: normal speed = the next real frame, slowed =
            # the next generated in-between frame. No blending, no repeats (old engine repeated frames below
            # 1x, which judders). The +1e-6 keeps float noise from flipping floor() and skipping/doubling.
            pos = (s - p["kn"]["bas"]) * p["kps"]; F = p["frames"]
            a = min(max(0, int(math.floor(pos + 1e-6))), len(F) - 1); src = F[a]
            if p["onceki"] is not None and a == p["onceki"] and not p["don"][n]:
                p["tekrar"] += 1; p.setdefault("tekrar_yer", []).append(f"{t:.2f} sn (kare {a}/{len(F)})")
            p["onceki"] = a
            pil = Image.fromarray(src).resize((p["PW"], p["PH"]), Image.LANCZOS,
                                              box=(x0 - p["ux"], y0 - p["uy"], x0 - p["ux"] + cw, y0 - p["uy"] + ch))
            kr = p["kn"].get("karart", 0)
            if kr: pil = Image.blend(pil, Image.new("RGB", pil.size, "black"), kr)
            img.paste(pil, (0, p["oy"]))
            sc = p["PW"] / cw; R = p["R"][n]
            box = [(R[0] - x0) * sc, (R[1] - y0) * sc + p["oy"], (R[2] - x0) * sc, (R[3] - y0) * sc + p["oy"]]
            vb = [max(0, box[0]), max(p["oy"], box[1]), min(W, box[2]), min(p["oy"] + p["PH"], box[3])]
            kutular.append(vb)
            kr_ = rapor["cumleler"][i]["kanit"][j]; vw, vh = max(0, vb[2] - vb[0]), max(0, vb[3] - vb[1])
            kr_["kare"] += 1; kr_["min_kisa_kenar"] = round(min(kr_["min_kisa_kenar"], min(vw, vh)), 1)
            kr_["min_alan_orani"] = round(min(kr_["min_alan_orani"], vw * vh / (W * H)), 4)
            et = p["kn"].get("etiket", k["etiket"]) if c.get("duzen") == "bolunmus" else p["kn"].get("etiket", "")
            if et:
                if et not in etiket_cache: etiket_cache[et] = yazi(et, 72, BEYAZ, 7)
                L = etiket_cache[et]; img.paste(L, (36, p["oy"] + 30), L)
                engel.append([36, p["oy"] + 30, 36 + L.width, p["oy"] + 30 + L.height])
            for m in c.get("isaretler", []):
                if m.get("panel", 0) != j: continue
                bx = lambda xr: box[0] + xr * (box[2] - box[0]); by = lambda yr: box[1] + yr * (box[3] - box[1])
                if m["tur"] == "cerceve": engel.append([bx(m["kutu"][0]) - 8, by(m["kutu"][1]) - 8, bx(m["kutu"][2]) + 8, by(m["kutu"][3]) + 8])
                elif m["tur"] == "ok":
                    ux, uy = {"ust": (0, -1), "alt": (0, 1), "sol": (-1, 0), "sag": (1, 0)}[m.get("yon", "ust")]
                    tx, ty = bx(m["x"]), by(m["y"]); ex, ey = tx + ux * 290, ty + uy * 290
                    engel.append([min(tx, ex) - 45, min(ty, ey) - 45, max(tx, ex) + 45, max(ty, ey) + 45])
                elif m["tur"] == "halka":
                    r = m["r"] * (box[2] - box[0]) * 1.5; engel.append([bx(m["x"]) - r, by(m["y"]) - r, bx(m["x"]) + r, by(m["y"]) + r])
                tm = t - sinir[i] - m.get("t0", 0.25)
                if tm < 0: continue
                e = smooth(tm / 0.25)
                if m["tur"] == "halka":
                    cx, cy = bx(m["x"]), by(m["y"]); r = m["r"] * (box[2] - box[0]) * (1.5 - 0.5 * e)
                    d.ellipse([cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5], outline="black", width=20)
                    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=VURGU, width=11)
                elif m["tur"] == "cerceve":
                    q = m["kutu"]; g = 14 * (1 - e)
                    xa, ya, xb, yb = bx(q[0]) - g, by(q[1]) - g, bx(q[2]) + g, by(q[3]) + g
                    d.rounded_rectangle([xa - 5, ya - 5, xb + 5, yb + 5], 14, outline="black", width=19)
                    d.rounded_rectangle([xa, ya, xb, yb], 12, outline=VURGU, width=10)
                    # the framed detail is what the sentence names: the gate checks its size too
                    isr = rapor["cumleler"][i].setdefault("isaret", {})
                    ad = f"cerceve{c['isaretler'].index(m) + 1}"; kk = min(bx(q[2]) - bx(q[0]), by(q[3]) - by(q[1]))
                    isr[ad] = round(min(isr.get(ad, 1e9), kk), 1)
                elif m["tur"] == "ok":
                    ok_ciz(d, bx(m["x"]), by(m["y"]), m.get("yon", "ust"), e)
        czi = cizimler[i]                       # sketch: on the footage (ust / giris / kose) or instead of it (ara)
        if paneller[i] and i + 1 < len(cs) and cizimler[i + 1] is not None and cizimler[i + 1]["kip"] == "ara":
            onceki_img = img.copy()             # footage only (no quote card, no caption): what an 'ara' board may blur
        if czi is not None and f >= czi["f0"]:
            if czi["kip"] == "ara" and czi["zemin"].replace("_", "-") == "oyun-kisik" and czi["zk"] is None and onceki_img is not None:
                czi["zk"] = np.asarray(onceki_img)          # the last shot of the sentence before, dimmed and blurred under the board
            img = cizim.sahne_karesi(img, czi["T"], f - czi["f0"], FPS, kelimeler=czi["kel"], zemin_kare=czi["zk"])
            d = ImageDraw.Draw(img); engel += czi["kutular"]
            rapor["cumleler"][i]["cizim"]["kare"] += 1
        for j, p in enumerate(paneller[i]):     # quote card on top of the (moving) footage
            a = p["kn"].get("alinti")
            if not a: continue
            if "kart" not in p:
                bc = kart_bicimi(plan, c, a)
                p["kart"] = {"kart": alinti_kart, "kisa": alinti_kart_kisa, "serit": kaynak_serit}[bc](a); p["bicim"] = bc
            K, km = p["kart"]
            if p["bicim"] == "serit": kx = SAFE_L; ky = p["oy"] + int(a.get("serit_y", SERIT_Y) * p["PH"])
            else: kx = (W - K.width) // 2; ky = p["oy"] + int(a.get("y", 0.16) * p["PH"])
            img.paste(K, (kx, ky), K); kb = [kx, ky, kx + K.width, ky + K.height]; engel.append(kb)
            ar = rapor["cumleler"][i]["kanit"][j].setdefault("alinti", dict(km, kare=0, kutu=kb))
            ar["kare"] += 1
            ar["ekranda"] = ar.get("ekranda", True) and kb[0] >= 0 and kb[1] >= 0 and kb[2] <= W and kb[3] <= H
        # caption: the word being spoken, centred, never on top of a proof region
        cur = None
        for ci, ws in enumerate(kel):
            for wi, w in enumerate(ws):
                nxt = ws[wi + 1]["a"] if wi + 1 < len(ws) else (kel[ci + 1][0]["a"] if ci + 1 < len(kel) else son)
                if w["a"] - 0.02 <= t < max(nxt, w["a"] + 0.12): cur = (ci, wi, w)
        if cur:
            ci, wi, w = cur
            vur = {norm(v) for v in cs[ci].get("vurgu", [])}
            renk = VURGU if norm(w["w"]) in vur else BEYAZ
            key = (w["w"], renk)
            if key not in kel_cache:
                ust_ = w["w"].replace("i", "İ").replace("ı", "I").upper()                 # Turkish upper case
                L = yazi(ust_, 132, renk); q = 1.0
                if L.width > W - SAFE_L - SAFE_R:
                    q = (W - SAFE_L - SAFE_R) / L.width; L = L.resize((int(L.width * q), int(L.height * q)), Image.LANCZOS)
                kel_cache[key] = (L, yazi_taban(ust_, 132) * q)
            if "#H" not in kel_cache: kel_cache["#H"] = (yazi("H", 132, BEYAZ).height, yazi_taban("H", 132))
            (L, taban), (hH, tabanH) = kel_cache[key], kel_cache["#H"]
            e = smooth((t - w["a"]) / 0.08); sc = 0.86 + 0.14 * e
            L2 = L.resize((max(1, int(L.width * sc)), max(1, int(L.height * sc))), Image.LANCZOS)
            yc = rapor["cumleler"][ci]["yazi_y"] or cs[ci].get("yazi_y")   # plan may fix the caption height
            if yc is None:
                for cand in (0.5, 0.42, 0.58, 0.32, 0.68, 0.24, 0.75, 0.14):
                    ya, yb = cand * H - L.height / 2, cand * H + L.height / 2
                    if all(yb < kb[1] - 10 or ya > kb[3] + 10 for kb in kutular + engel): yc = cand; break
                yc = yc or 0.75; rapor["cumleler"][ci]["yazi_y"] = yc
            # on the baseline (17.11 v3): the image is cropped to the ink, so a word with Ç, Ş, Ğ, a comma or dotted
            # capitals used to sit higher or lower than the word before it. A plain-capitals word lands where it did.
            y_taban = yc * H - hH * sc / 2 + tabanH * sc
            img.paste(L2, (SAFE_L + (W - SAFE_L - SAFE_R - L2.width) // 2, int(round(y_taban - taban * sc))), L2)
            if "ilk_yazi" not in rapor: rapor["ilk_yazi"] = round(t, 3)
        rapor["cumleler"][i]["kare"] += 1
        if paneller[i] and all(p["don"][max(0, min(f - p["f0"], len(p["don"]) - 1))] for p in paneller[i]): rapor["cumleler"][i]["donuk_kare"] += 1
        sy = c.get("sayac")      # running list number, e.g. "2/5", top left
        if sy:
            if ("#say", sy) not in etiket_cache:
                T = yazi(sy, 100, (0, 0, 0), 1); B = Image.new("RGBA", (T.width + 24, T.height + 4), VURGU + (255,))
                B.paste(T, (12, 2), T); etiket_cache[("#say", sy)] = B
            B = etiket_cache[("#say", sy)]; img.paste(B, (44, 150), B)
        enc.stdin.write(np.asarray(img, np.uint8).tobytes())
    enc.stdin.close(); enc.wait()

    # ---- sound: voice + quiet bed, nothing from the sources
    import muzik
    ses = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", yol(plan["ses"]), "-f", "s16le", "-ac", "1",
                                        "-ar", str(SR), "-"], capture_output=True, check=True).stdout, np.int16).astype(np.float32) / 32768
    N = int(son * SR); ses = np.pad(ses, (0, max(0, N - len(ses))))[:N]
    mz = plan.get("muzik", {})
    if mz.get("acik", True):
        bed = muzik.yatak(son, SR)
        w_ = int(0.02 * SR); env = np.sqrt(np.convolve(ses ** 2, np.ones(w_) / w_, "same"))
        aktif = env > 10 ** (-35 / 20)
        v_rms = np.sqrt((ses[aktif] ** 2).mean()) if aktif.any() else 0.1
        bed = bed / (np.sqrt((bed ** 2).mean()) + 1e-9) * v_rms * 10 ** (mz.get("db", -20) / 20)
        duck = np.convolve(aktif.astype(np.float32), np.ones(int(0.25 * SR)) / int(0.25 * SR), "same")
        bed = bed * (1 - 0.45 * np.clip(duck, 0, 1))
        tail = int(0.25 * SR); bed[-tail:] *= np.linspace(1, 0, tail)
    else: bed = np.zeros(N, np.float32)
    bed = np.pad(bed, (0, max(0, N - len(bed))))[:N]
    if any(cizimler):        # sketch sound effects (cizim_ses: chalk, pops, thuds) go into the bed, ~15 dB under the voice
        w_ = int(0.02 * SR); env_ = np.sqrt(np.convolve(ses ** 2, np.ones(w_) / w_, "same")); akt = env_ > 10 ** (-35 / 20)
        vr = np.sqrt((ses[akt] ** 2).mean()) if akt.any() else 0.1
        for i, czi in enumerate(cizimler):
            if czi is None: continue
            iz = cizim_ses.ses_izi(cizim.olaylar(czi["T"], FPS, kelimeler=czi["kel"]), sinir[i + 1] - czi["t0"], FPS, 0)
            dolu = np.abs(iz) > 1e-4
            if not dolu.any(): continue
            iz = iz / np.sqrt((iz[dolu] ** 2).mean()) * vr * 10 ** (-15 / 20)
            a = int(czi["t0"] * SR); b = min(N, a + len(iz)); bed[a:b] += iz[: b - a].astype(np.float32)
    mix = ses + bed
    # loudness: aim at about -14 LUFS (Shorts), soft-limit peaks above -1 dBFS; stems get the same gain
    tmp = cikti + ".olcum.wav"
    with wave.open(tmp, "wb") as wv:
        wv.setnchannels(1); wv.setsampwidth(2); wv.setframerate(SR)
        wv.writeframes((np.clip(mix / (np.abs(mix).max() + 1e-9) * 0.5, -1, 1) * 32767).astype("<i2").tobytes())
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", e)
    g = 0.5 / (np.abs(mix).max() + 1e-9) * (10 ** ((-14 - float(m[-1])) / 20) if m else 1)
    tavan = 10 ** (-1 / 20)
    def sinirla(x):
        y = x.copy(); a = np.abs(y) > 0.8 * tavan
        y[a] = np.sign(y[a]) * (0.8 * tavan + 0.2 * tavan * np.tanh((np.abs(y[a]) - 0.8 * tavan) / (0.2 * tavan)))
        return y
    ses, bed = ses * g, bed * g; mix = sinirla(ses + bed); g = 1.0
    for ad, x in (("ses", ses * g), ("muzik", bed * g), ("mix", mix * g)):
        with wave.open(f"{cikti}.{ad}.wav", "wb") as wv:
            wv.setnchannels(1); wv.setsampwidth(2); wv.setframerate(SR)
            wv.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", sessiz, "-i", f"{cikti}.mix.wav", "-map", "0:v", "-map", "1:a",
                           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-shortest", "-movflags", "+faststart", cikti])
    for i, lst in enumerate(paneller):      # how each shot moved: the gate reads this (kapi.py 8 HIZ)
        for j, p in enumerate(lst):
            rapor["cumleler"][i]["kanit"][j].update(hiz=p["hiz"], yontem=p["yontem"], tekrar_kare=p["tekrar"], tekrar_yer=p.get("tekrar_yer", [])[:10],
                                                    ara_kare_planda=bool(p["kn"].get("ara_kare")))
    rapor["kaynaklar"] = {a: {"dosya": v["dosya"], "ofset": v["ofset"], "alan": v["alan"]} for a, v in kaynaklar.items()}
    rapor["stemler"] = {a: f"{cikti}.{a}.wav" for a in ("ses", "muzik", "mix")}
    json.dump(rapor, open(cikti + ".rapor.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"TAMAM {cikti}  {son:.2f} sn, {nkare} kare")


if __name__ == "__main__":
    sys.path.insert(0, KOK)
    main(sys.argv[1], sys.argv[2])
