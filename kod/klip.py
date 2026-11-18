"""klip.py - Klip style: vertical clips cut out of ONE long recording that already has speech in it (17.11.2026).

    python klip.py <klip_plan.json> <out_dir>            -> <out_dir>/<ad>.mp4 for every clip + klipler.json
    python klip.py <klip_plan.json> <out_dir> --sadece klip-2      (render one clip again)
    python klip.py <klip_plan.json> <out_dir> --onizle klip-2 [sn]  one frame of the layout (game crop, caption
                         place, a sample caption) -> <out_dir>/klip-2-onizleme.jpg, in a second; nothing else is written.
                         Try "odak" / "oyun" / "yazi_yer" here before building the clip.
    python klip.py <klip_plan.json> --sozler [klip-2]     the clip's words as they will be captioned, the ones Whisper
                         was unsure of in [brackets] with their probability: write the fixes in "yazim" first.

Unlike the other three styles the soundtrack is the recording's OWN audio (the streamer's voice and the game),
cut at the same seconds as the picture. No slow motion, no frozen frames, no music bed: every output frame is
the next real frame of the recording. A clip starts on its first spoken word and ends after its last word.

Plan (times in the recording's own seconds = the seconds in yazi.json / bak.py; rectangles 0-1 of the full frame):
{
  "tarz": "klip",
  "kaynak": "C:/.../yayin.mp4",            # absolute, or relative to the plan file. Read in place, never copied.
  "ses_izi": 0,                           # audio track of the recording (OBS: 0 = everything)
  "yazi": "yazi/yazi.json",               # from: python kod/ses_yazi.py --uzun <recording> <dir>
  "duzen": "kamera" | "doldur" | "sigdir",
        # kamera = the recording has a streamer camera box: camera band on top, game band below (layout A)
        # doldur = no camera: the picture fills the 9:16 screen (cropped, `odak` picks where)          (layout B)
        # sigdir = no camera and a crop would make the content unreadable (text, a web page): the picture full
        #          width in the middle, above and below a blurred copy of the same picture (never black)  (layout B)
        # ("tek", the v1 name, still reads: doldur if the kadraj is tall, else sigdir)
  "kamera": [x0, y0, x1, y1],             # kamera: the camera box in the recording (kod/kamera_bul.py, checked by Claude)
  "yuz":    [x0, y0, x1, y1],             # kamera, optional: the face inside it -> the band is cropped around the face
  "oyun":   [x0, y0, x1, y1],             # kamera, optional: the game area (default the whole frame). Cutting its top
                                          # (e.g. [0, 0.12, 1, 1]) keeps a scoreboard row out of the clip
  "kadraj": [x0, y0, x1, y1],             # doldur/sigdir, optional: the part of the frame to use (default whole frame)
  "odak": 0.5,                            # across the game area / kadraj: where the crop sits. 0-1 (centre of the
                                          # crop) or "sol" | "orta" | "sag" (left edge, middle, right edge). Only ~46 %
                                          # of a 16:9 game shows: "orta" = the crosshair, "sag" = kill feed (top right),
                                          # "sol" = game messages / chat bottom left. Leave it out and the crop keeps
                                          # clear of the camera box and the chat box. Per clip like every field here.
  "yazi_yer": "oyun_ust",                 # captions: kamera layout default "oyun_ust" = a quarter down the game band
                                          # (under the HUD row of most games, above the crosshair); "dikis" = on the
                                          # seam; "alt" = 0.70 of the screen; or a number 0-1 (centre height). Never
                                          # over the face (the gate checks). doldur 0.72, sigdir under the picture.
  "sohbet_kutu": [x0, y0, x1, y1],        # optional: kept out of the game crop when odak is automatic
  "altyazi": true,                        # captions: a job opens with altyazi true (is_ac.js; --altyazisiz = false) and
                                          # the plan copies the job's value; only a plan WITHOUT this field gets none
  "kurgu": "sade" | "editli",             # sade (default) = straight cut. editli = the model's beats per clip
                                          # ("vuruslar": zum, sarsinti, parlama, yavas, tekrar, baslik, ses), see kod/klip_edit.py
  "kesmeler": [17.43, 36.8],              # optional: scene cuts of the recording (s); no clip shows frames across one
  "klipler": [
    {"ad": "klip-1", "bas": 812.4, "son": 846.0,          # rough range; snapped to the words inside it
     "puan": 8,                                            # 1-10: how well the moment stands alone (panel sorts by it)
     "neden": "one plain Turkish sentence: why this moment stands alone",
     "baslik": "title suggestion",
     "yazim": {"Fabl": "Fable", "ölüm günü": "doğum günü", "min valleri": "M4A1"},
                             # misheard words -> spelling on screen. A key of several words matches those words in a
                             # row; the fix may have more or fewer words (timing: the span of the words it replaces)
     "on_pay": 2.0,          # optional: seconds of picture before the first word (default 0.10, at most 3.0): the
                             # silent event before a reaction. Never starts inside the previous word.
     "odak": "sag", "oyun": [..], "yazi_yer": "dikis", "altyazi": true, "kamera": [..],   # optional per-clip overrides
     "kullanici": {"tur": "aralik", "satir": "12:30-13:05"}}   # only when the USER gave this moment (klip_bul --anlar):
                                                           # "aralik" = cut as given (snapped to sentences; outside
                                                           # 15-60 s the gate warns instead of failing), "nokta" = the
                                                           # model built the window around the user's second
  ]
}
The clip runs from (first word fully inside bas..son) - on_pay (0.10 s unless given) to (last word) + up to 0.30 s,
never into the next word. A caption cue closes at a sentence end of the transcript. Sound: the recording's own audio
raised toward -14 LUFS, but never so far that the limiter has to take more than 6 dB off the loudest peak (a quiet clip
stays a little quieter instead of having its gunshots squashed). Layout sizes come from our measurement of much-watched streamer clip Shorts: camera band 0-614 px (0.32 H), or
0-778 px (0.405 H) for a 4:3-like camera box; the face (forehead-chin) ~46 % of the band; game band below it, the
16:9 game scaled to the band height and cropped across (~46 % of its width shows). No line or gap at the seam, no
black bars, no blurred fill in layout A. The report holds the rectangles actually used, the face share, the
seam, the words drawn, frame counts and the audio range; kod/klip_kapi.py checks them.
"""
import json, math, os, re, subprocess, sys, wave
import numpy as np
from PIL import Image

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)
from motor import yazi, smooth, norm, BEYAZ, VURGU, SAFE_L, SAFE_R, ARA_KARE_VF  # noqa: E402
import klip_edit, klip_ses  # noqa: E402

W, H, SR = 1080, 1920, 48000
ON_PAY, SON_PAY = 0.10, 0.30          # pre-roll before word 1, tail after the last word
ON_PAY_EN_COK = 3.0                    # "on_pay" of a clip: at most this much silent picture before word 1
HEDEF_LUFS, SINIR_DB, SINIRLA_EN_COK = -14.0, -1.0, 6.0   # loudness target; limiter ceiling (0.89); most dB it may take
ODAK_AD = {"sol": 0.0, "orta": 0.5, "sag": 1.0}
KAMERA_H, KAMERA_H_43 = 614, 778       # camera band height: 0.32 H; 0.405 H when the camera box is 4:3-like
DORT_UC = 1.55                         # camera box wider than this (w/h) = 16:9-like, else 4:3-like
YUZ_PAY, YUZ_MERKEZ = 0.46, 0.50       # face height share of the camera band, face centre at this height of the band
YAZI_BOY = 0.05                        # caption capital-letter height as a share of H
ICERI = 4                              # camera crop stays this many source px inside the box (its frame line never shows)


def kaynak_bilgi(dosya):
    j = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
        "stream=index,codec_type,width,height,r_frame_rate,avg_frame_rate:format=duration", "-of", "json", dosya], text=True))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    n, d = v["r_frame_rate"].split("/")
    return {"w": int(v["width"]), "h": int(v["height"]), "fps": float(n) / float(d), "sure": float(j["format"]["duration"]),
            "ses_akisi": sum(1 for s in j["streams"] if s["codec_type"] == "audio")}


def birlestir(kel):
    """Whisper splits numbers: '5' '.2' "'yi", '1' '.58', '%' '20'. On screen they are one word ("5.2'yi", '1.58', '%20');
    timing = from the first part's start to the last part's end. The gate applies the same rule."""
    out = []
    for k in kel:
        k = list(k)
        if out and (re.match(r"^[.,]\d", k[0]) or re.match(r"^['’]\w", k[0]) or (out[-1][0] == "%" and re.match(r"^\d", k[0]))):
            out[-1] = [out[-1][0] + k[0], out[-1][1], k[2]] + out[-1][3:]
        else: out.append(k)
    return out


def yazim_uygula(kel, yazim):
    """Spelling fixes on [word, start, end, ...] (after birlestir) -> [[shown word, start, end, heard word], ...].
    A key may be several words ("ölüm günü"): it matches those words in a row (compared with norm()). The fix may
    have another number of words: the same number keeps every word's timing; fewer -> the last shown word spans the
    rest; more -> the last heard word's time is shared evenly. One rule, used by klip.py and the gate (klip_kapi)."""
    kural = sorted(((tuple(norm(x) for x in a.split()), b.split()) for a, b in (yazim or {}).items() if a.split() and b.split()),
                   key=lambda r: -len(r[0]))                                 # the longest key wins
    out, i = [], 0
    while i < len(kel):
        es = next(((k, y) for k, y in kural if tuple(norm(w[0]) for w in kel[i: i + len(k)]) == k), None)
        if not es: out.append([kel[i][0], kel[i][1], kel[i][2], kel[i][0]]); i += 1; continue
        k, y = es; parca = kel[i: i + len(k)]
        if len(y) <= len(parca):
            for j, w in enumerate(y[:-1]): out.append([w, parca[j][1], parca[j][2], parca[j][0]])
            out.append([y[-1], parca[len(y) - 1][1], parca[-1][2], " ".join(w[0] for w in parca[len(y) - 1:])])
        else:
            for j, w in enumerate(parca[:-1]): out.append([y[j], w[1], w[2], w[0]])
            a, b = parca[-1][1], parca[-1][2]; kalan = y[len(parca) - 1:]; d = (b - a) / len(kalan)
            for j, w in enumerate(kalan): out.append([w, round(a + j * d, 3), round(a + (j + 1) * d, 3), parca[-1][0] if j == 0 else ""])
        i += len(k)
    return out


def kelime_araligi(kel, bas, son):
    """Indices of the words fully inside bas..son (a word that starts before bas or ends after son is left out:
    the clip never starts or ends inside a word)."""
    ix = [i for i, k in enumerate(kel) if k[1] >= bas - 0.05 and k[2] <= son + 0.05]
    if not ix: raise SystemExit(f"RED: {bas}-{son} sn arasında kelime yok")
    return ix[0], ix[-1]


def kapla(r, k, pw, ph):
    """Cover-fit rectangle r (0-1) to aspect pw:ph by trimming around its centre -> pixel box (x, y, w, h), even."""
    x0, y0, x1, y1 = r[0] * k["w"], r[1] * k["h"], r[2] * k["w"], r[3] * k["h"]
    w, h = x1 - x0, y1 - y0
    if w / h > pw / ph: nw, nh = h * pw / ph, h
    else: nw, nh = w, w * ph / pw
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bx, by = int(round(cx - nw / 2)) // 2 * 2, int(round(cy - nh / 2)) // 2 * 2
    return [max(0, bx), max(0, by), int(nw) // 2 * 2, int(nh) // 2 * 2]


def cift(v): return int(round(v)) // 2 * 2


def kamera_kirp(kut, yuz, k, oran):
    """Camera band crop (pixels of the recording) of aspect `oran` (W / band height) inside the camera box.
    With a face: the face takes YUZ_PAY of the band height, centred across, its centre at YUZ_MERKEZ of the band;
    the crop never leaves the box (if that is too small, the face gets a smaller share). Without: cover-fit of the box.
    Returns (pixel box, face share of the band or None)."""
    bx0, by0, bx1, by1 = kut[0] * k["w"] + ICERI, kut[1] * k["h"] + ICERI, kut[2] * k["w"] - ICERI, kut[3] * k["h"] - ICERI
    bw, bh = bx1 - bx0, by1 - by0
    if not yuz:
        return kapla([bx0 / k["w"], by0 / k["h"], bx1 / k["w"], by1 / k["h"]], k, oran, 1), None
    fx0, fy0, fx1, fy1 = yuz[0] * k["w"], yuz[1] * k["h"], yuz[2] * k["w"], yuz[3] * k["h"]
    ch = (fy1 - fy0) / YUZ_PAY; cw = ch * oran
    if cw > bw: cw = bw; ch = cw / oran                        # the box is the limit
    if ch > bh: ch = bh; cw = ch * oran
    x0 = min(max((fx0 + fx1) / 2 - cw / 2, bx0), bx1 - cw)
    y0 = min(max((fy0 + fy1) / 2 - YUZ_MERKEZ * ch, by0), by1 - ch)
    b = [cift(x0), cift(y0), cift(cw), cift(ch)]
    return b, round((fy1 - fy0) / b[3], 3)


def kes_alan(a, b):
    """Overlap area of a pixel box (x, y, w, h) and a pixel rectangle (x0, y0, x1, y1)."""
    w = min(a[0] + a[2], b[2]) - max(a[0], b[0]); h = min(a[1] + a[3], b[3]) - max(a[1], b[1])
    return max(0, w) * max(0, h)


def yatay_kirp(alan, k, oran, odak, kacin):
    """Crop of aspect `oran` (w/h) out of `alan` (0-1): full height when the area is wide enough, across at `odak`
    (0-1). odak None = automatic: as near the middle as possible while keeping clear of the boxes in `kacin` (0-1
    rects: the camera box, the chat box). Returns (pixel box, odak used, share of the crop those boxes cover)."""
    if isinstance(odak, str):
        if odak not in ODAK_AD: raise SystemExit(f"RED: odak '{odak}' (sol, orta, sag ya da 0-1 arası sayı)")
        odak = ODAK_AD[odak]
    ax0, ay0, ax1, ay1 = alan[0] * k["w"], alan[1] * k["h"], alan[2] * k["w"], alan[3] * k["h"]
    aw, ah = ax1 - ax0, ay1 - ay0
    ch = ah; cw = ch * oran
    if cw > aw: cw = aw; ch = cw / oran
    y0 = ay0 + (ah - ch) / 2
    # boxes drawn by hand are rough: keep 2 % of the frame clear around them
    kp = [[(r[0] - 0.02) * k["w"], (r[1] - 0.02) * k["h"], (r[2] + 0.02) * k["w"], (r[3] + 0.02) * k["h"]] for r in kacin if r]
    def kutu(o): return [cift(min(max(ax0 + o * aw - cw / 2, ax0), ax1 - cw)), cift(y0), cift(cw), cift(ch)]
    gercek = [[r[0] * k["w"], r[1] * k["h"], r[2] * k["w"], r[3] * k["h"]] for r in kacin if r]
    def ortu(b, kutular=kp): return sum(kes_alan(b, r) for r in kutular) / (b[2] * b[3])
    if odak is None:
        odak = min((i / 100 for i in range(101)), key=lambda o: ortu(kutu(o)) * 4 + abs(o - 0.5))
    b = kutu(odak)
    return b, round(odak, 2), round(ortu(b, gercek), 3)      # reported: the share the boxes themselves cover


def filtre(plan, kl, k):
    """ffmpeg filter graph -> one 1080x1920 picture. Returns (graph, layout facts for the report)."""
    al = lambda a, d=None: kl.get(a, plan.get(a, d))
    duzen = al("duzen", "doldur")
    if duzen == "tek":                                                  # v1 plans
        r = al("kadraj", [0, 0, 1, 1]); ar = (r[2] - r[0]) * k["w"] / ((r[3] - r[1]) * k["h"])
        duzen = "doldur" if ar <= W / H * 1.02 else "sigdir"
    dz = {"duzen": duzen, "kaynak_px": [k["w"], k["h"]], "odak_plan": al("odak")}
    if duzen == "kamera":
        kut = al("kamera"); yuz = al("yuz"); oyun = al("oyun", [0, 0, 1, 1])
        kw_, kh_ = (kut[2] - kut[0]) * k["w"], (kut[3] - kut[1]) * k["h"]
        ht = KAMERA_H if kw_ / kh_ > DORT_UC else KAMERA_H_43; hb = H - ht
        kam, yuz_pay = kamera_kirp(kut, yuz, k, W / ht)
        oy, odak, ortu = yatay_kirp(oyun, k, W / hb, al("odak"), [kut, al("sohbet_kutu")])
        g = (f"[0:v]split=2[a][b];[a]crop={kam[2]}:{kam[3]}:{kam[0]}:{kam[1]},scale={W}:{ht}:flags=lanczos,setsar=1[ust];"
             f"[b]crop={oy[2]}:{oy[3]}:{oy[0]}:{oy[1]},scale={W}:{hb}:flags=lanczos,setsar=1[alt];[ust][alt]vstack=2,format=rgb24[v]")
        # captions (18.11.2026): they used to sit just under the seam, i.e. on the game's top HUD row (CS2 scoreboard)
        yer = al("yazi_yer", "oyun_ust")
        if isinstance(yer, (int, float)) and not isinstance(yer, bool): yazi_y = float(yer)
        elif yer == "oyun_ust": yazi_y = (ht + 0.25 * hb) / H          # a quarter down the game band
        elif yer == "dikis": yazi_y = ht / H
        elif yer == "alt": yazi_y = 0.70
        else: raise SystemExit(f"RED: yazi_yer '{yer}' (oyun_ust, dikis, alt ya da 0-1 arası sayı)")
        yuz_cikti = None
        if yuz:                                                         # the face in output pixels: captions stay off it
            sx, sy = W / kam[2], ht / kam[3]
            yuz_cikti = [round(max(0, (yuz[0] * k["w"] - kam[0]) * sx)), round(max(0, (yuz[1] * k["h"] - kam[1]) * sy)),
                         round(min(W, (yuz[2] * k["w"] - kam[0]) * sx)), round(min(ht, (yuz[3] * k["h"] - kam[1]) * sy))]
        aw = (oyun[2] - oyun[0]) * k["w"]
        dz.update(kamera_px=kam, oyun_px=oy, plan_kamera=kut, plan_yuz=yuz, plan_oyun=oyun, dikis_px=ht,
                  kamera_43=ht == KAMERA_H_43, yuz_pay=yuz_pay, odak=odak, ortusme=ortu,
                  paneller=[[0, 0, W, ht], [0, ht, W, H]], yazi_y=round(yazi_y, 4), yazi_yer=yer, yuz_cikti=yuz_cikti,
                  buyutme=round(max(W / kam[2], W / oy[2]), 2), oyun_gorunen=round(oy[2] / aw, 3),
                  oyun_gorunen_x=[round((oy[0] - oyun[0] * k["w"]) / aw, 3), round((oy[0] + oy[2] - oyun[0] * k["w"]) / aw, 3)])
        return g, dz
    r = al("kadraj", [0, 0, 1, 1])
    if duzen == "doldur":
        kb, odak, ortu = yatay_kirp(r, k, W / H, al("odak"), [al("sohbet_kutu")])
        g = f"[0:v]crop={kb[2]}:{kb[3]}:{kb[0]}:{kb[1]},scale={W}:{H}:flags=lanczos,setsar=1,format=rgb24[v]"
        yer = al("yazi_yer")
        dz.update(kadraj_px=kb, plan_kadraj=r, odak=odak, ortusme=ortu, paneller=[[0, 0, W, H]],
                  yazi_y=float(yer) if isinstance(yer, (int, float)) and not isinstance(yer, bool) else 0.72,
                  buyutme=round(W / kb[2], 2), oyun_gorunen=round(kb[2] / ((r[2] - r[0]) * k["w"]), 3))
        return g, dz
    if duzen != "sigdir": raise SystemExit(f"RED: bilinmeyen duzen '{duzen}' (kamera, doldur ya da sigdir)")
    x0, y0 = cift(r[0] * k["w"]), cift(r[1] * k["h"])
    cw, ch = cift((r[2] - r[0]) * k["w"]), cift((r[3] - r[1]) * k["h"])
    fh = cift(W * ch / cw)
    if fh >= H: raise SystemExit("RED: sigdir icin kadraj fazla dik; doldur kullan")
    fy = cift((H - fh) / 2)                                             # vertically centred
    g = (f"[0:v]crop={cw}:{ch}:{x0}:{y0},split=2[a][b];"
         # the fill is the blurred MIDDLE of the picture (page headers and menu bars are often near-black and
         # would read as black bars above and below); lifted a little so a dark page never fills as black
         f"[a]crop=iw*0.4:ih*0.4:iw*0.3:ih*0.3,scale=-2:{H},crop={W}:{H},boxblur=30:2,eq=brightness=0.10:saturation=1.1,setsar=1[bg];"
         f"[b]scale={W}:{fh}:flags=lanczos,setsar=1[fg];[bg][fg]overlay=0:{fy},format=rgb24[v]")
    yer = al("yazi_yer")
    dz.update(kadraj_px=[x0, y0, cw, ch], plan_kadraj=r, paneller=[[0, fy, W, fy + fh]],
              yazi_y=float(yer) if isinstance(yer, (int, float)) and not isinstance(yer, bool) else round(min(0.86, (fy + fh) / H + 0.06), 4),
              buyutme=round(W / cw, 2))
    return g, dz


# Caption cues of 2-3 words. Grouping rule after chunk_words() in helpers/render.py of the video-use project
# (MIT License, Copyright (c) 2026 Browser Use); rewritten here for our word lists.
KUME, KUME_EN_COK, KUME_MIN_SN, KUME_ARA_SN = 2, 3, 0.35, 0.3


def kumele(ws):
    """ws: words with w (text), a (start), b (end), optional cumle_sonu. A cue closes on punctuation, at the end of a
    transcript sentence (cumle_sonu: Whisper often leaves the period out, 18.11.2026) or a pause before the next word;
    otherwise at 2 words, unless it would flash (< 0.35 s), then up to 3. Returns lists of word indices."""
    out, cur = [], []
    for i, w in enumerate(ws):
        cur.append(i)
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        ara = (nxt["a"] - w["b"]) if nxt else 0.0
        sure = w["b"] - ws[cur[0]]["a"]
        if (nxt is None or w["w"][-1:] in ".,!?;:" or w.get("cumle_sonu") or ara >= KUME_ARA_SN or len(cur) >= KUME_EN_COK
                or (len(cur) >= KUME and sure >= KUME_MIN_SN)):
            out.append(cur); cur = []
    return out


_TR_HARF = True     # captions in capitals the Turkish way (i -> İ); False when yazi.json "dil" is not tr (it -> IT)


def buyuk(t): return t.replace("i", "İ").replace("ı", "I").upper() if _TR_HARF else t.upper()


def dil_ayarla(yz):
    global _TR_HARF; _TR_HARF = (yz.get("dil") or "tr") == "tr"


_YAZI_PX = None
def yazi_px():
    """Font size whose capital letters are YAZI_BOY of the screen height."""
    global _YAZI_PX
    if _YAZI_PX is None:
        from motor import font
        bb = font(200).getbbox("H"); _YAZI_PX = int(round(200 * YAZI_BOY * H / (bb[3] - bb[1])))
    return _YAZI_PX


def kume_ciz(kelimeler, etkin):
    """One cue as an RGBA image: the word being said in #FFD43B, the others white, dark outline; shrunk to fit."""
    px = yazi_px(); parca = [yazi(buyuk(w), px, VURGU if i == etkin else BEYAZ) for i, w in enumerate(kelimeler)]
    bosluk = int(px * 0.24) - 20                                     # yazi() pads 10 px on each side
    # align on the baseline: a word with ink below it (Ç, Ş, a comma) is a taller image and used to sit higher
    alt = [klip_edit.alt_tasma(buyuk(w), px) for w in kelimeler]
    ust = max(p.height - a for p, a in zip(parca, alt)); yuk = ust + max(alt)
    gen = sum(p.width for p in parca) + bosluk * (len(parca) - 1)
    img = Image.new("RGBA", (gen, yuk), (0, 0, 0, 0)); x = 0
    for p, a in zip(parca, alt): img.paste(p, (x, ust - (p.height - a)), p); x += p.width + bosluk
    sinir = W - SAFE_L - SAFE_R
    if img.width > sinir:
        q = sinir / img.width; img = img.resize((int(img.width * q), int(img.height * q)), Image.LANCZOS)
    return img


def kazanc(ham):
    """Gain (dB) for a cut: toward HEDEF_LUFS, but the loudest peak may go at most SINIRLA_EN_COK dB over the limiter
    ceiling. 18.11.2026: a quiet clip (-23 LUFS) got +9 dB and the limiter squashed its gunshots; the gate's 7 SES
    then failed a valid clip (correlation 0.960). Returns (gain, loudness before, peak before)."""
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", ham, "-af", "ebur128=peak=sample", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", e); lufs = float(m[-1]) if m else -20.0
    p = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", e); tepe = float(p[-1]) if p and p[-1] != "-inf" else -20.0
    kaz = min(HEDEF_LUFS - lufs, SINIR_DB + SINIRLA_EN_COK - tepe)
    return max(-12.0, min(18.0, kaz)), lufs, tepe


def ses_kes(kaynak, iz, t0, sure, hedef):
    """The recording's own audio, same seconds as the picture, toward -14 LUFS (see kazanc), 15 ms fades (no click)."""
    ham = hedef + ".ham.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-i", kaynak, "-t", f"{sure:.3f}", "-map", f"0:a:{iz}",
                    "-vn", "-ac", "2", "-ar", str(SR), ham], check=True)
    kaz, lufs, tepe = kazanc(ham)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", ham, "-af",
                    f"volume={kaz:.2f}dB,alimiter=limit=0.89:level=false,afade=t=in:d=0.015,afade=t=out:st={max(0, sure - 0.015):.3f}:d=0.015",
                    "-ar", str(SR), hedef], check=True)
    return {"lufs_once": lufs, "tepe_once_db": tepe, "kazanc_db": round(kaz, 2), "ham": ham}


def ses_kurgu(kaynak, iz, t0, ed, sure_cikti, hedef):
    """Editli: the recording's own audio cut by the same segments as the picture. The slowed part is silent (the
    voice never plays slowed; it comes back in sync after), the replay plays its own seconds again. 10 ms fades at
    every join. Then -14 LUFS like the Sade cut, then the effect sounds on top, then the limiter."""
    son = max(s_["b"] for s_ in ed.seg) + 0.1
    ham_b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-i", kaynak, "-t", f"{son:.3f}", "-map", f"0:a:{iz}",
                            "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(ham_b, np.float32).reshape(-1, 2)
    f = int(0.010 * SR); parca = []
    for s_ in ed.seg:
        m = int(round((s_["ob"] - s_["oa"]) * SR))
        if s_["tur"] == "yavas": y = np.zeros((m, 2), np.float32)
        else:
            a = int(round(s_["a"] * SR)); y = x[a: a + m].copy()
            if len(y) < m: y = np.concatenate([y, np.zeros((m - len(y), 2), np.float32)])
            r = np.linspace(0, 1, f, dtype=np.float32)[:, None]; y[:f] *= r; y[-f:] *= r[::-1]
        parca.append(y)
    y = np.concatenate(parca)[: int(round(sure_cikti * SR))]
    ham = hedef + ".ham.wav"; _wav_yaz(ham, y)
    kaz, lufs, _ = kazanc(ham)
    kon = hedef + ".konusma.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", ham, "-af", f"volume={kaz:.2f}dB,alimiter=limit=0.89:level=false", "-ar", str(SR), kon], check=True)
    olay = [{"t": v["ot"], "ses": v.get("ses", "pit")} for v in ed.vuruslar if v["tur"] == "ses"]
    if any(v["tur"] == "cizim" for v in ed.vuruslar):         # the drawings' own sounds (kit events), under the voice
        k_ = _wav_oku(kon); mix = hedef + ".cizim.wav"; _wav_yaz(mix, k_ + ed.cizim_sesi(len(k_), SR)); kon = mix
    if olay:
        k_ = _wav_oku(kon); fx = klip_ses.iz(olay, len(k_) / SR, ed.tohum)[: len(k_)]
        mix = hedef + ".mix.wav"; _wav_yaz(mix, k_ + fx)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mix, "-af", "alimiter=limit=0.89:level=false", "-ar", str(SR), hedef], check=True)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", kon, "-c", "copy", hedef], check=True)
    return {"lufs_once": lufs, "kazanc_db": round(kaz, 2), "ham": ham, "efekt": olay}


def _wav_yaz(yol, y):
    with wave.open(yol, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())


def _wav_oku(yol):
    with wave.open(yol, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, w.getnchannels()).astype(np.float32) / 32768


def tek_klip(plan, kl, kok, cikti_kl):
    yol = lambda p: p if os.path.isabs(p) else os.path.join(kok, p)
    kaynak = yol(plan["kaynak"]); k = kaynak_bilgi(kaynak)
    yz = json.load(open(yol(plan["yazi"]), encoding="utf-8")); kel = yz["kelimeler"]; dil_ayarla(yz)
    i0, i1 = kelime_araligi(kel, kl["bas"], kl["son"])
    # on_pay (18.11.2026): the silent event before a reaction may open the clip, up to ON_PAY_EN_COK before word 1
    on_pay = min(ON_PAY_EN_COK, max(ON_PAY, float(kl.get("on_pay") or ON_PAY)))
    t0 = max(0.0, kel[i0][1] - on_pay)
    if i0 > 0: t0 = max(t0, kel[i0 - 1][2])             # never start on the end of the previous word
    sonraki = kel[i1 + 1][1] if i1 + 1 < len(kel) else k["sure"]
    t1 = min(kel[i1][2] + SON_PAY, sonraki - 0.03, k["sure"])
    # real recordings (several people talking over each other): Whisper often gives the next word the same start as
    # the last word's end. Then the clip ends on that shared boundary (+0.02), never inside the last word.
    t1 = min(max(t1, kel[i1][2] + 0.02), k["sure"])
    # scene cuts of the recording ("kesmeler", seconds): a clip never shows a frame of the scene before or after its own
    kes = sorted(float(c) for c in kl.get("kesmeler", plan.get("kesmeler", [])))
    kare = 1.0 / (k["fps"] if k["fps"] <= 30.5 else 30.0)
    once_k = [c for c in kes if c <= kel[i0][1]]; sonra_k = [c for c in kes if c > kel[i0][1]]
    if once_k: t0 = max(t0, once_k[-1])
    if sonra_k and sonra_k[0] < t1:
        if sonra_k[0] < kel[i1][2]: raise SystemExit(f"RED: {kl['ad']} {sonra_k[0]} sn'deki sahne kesmesinin üstünden geçiyor (son kelime {kel[i1][2]:.2f} sn)")
        t1 = sonra_k[0] - kare
    sure = t1 - t0
    os.makedirs(os.path.dirname(cikti_kl) or ".", exist_ok=True)

    # caption words: Whisper's words in order; yazim only changes spelling ("Fabl" -> "Fable", "ölüm günü" ->
    # "doğum günü"), the timing of the words it replaces stays. A word that ends a transcript sentence closes its cue.
    ws = []
    sonlar = np.array(sorted(c[2] for c in yz.get("cumleler", [])) or [-1.0])
    for w_, a_, b_, duy in yazim_uygula(birlestir(kel[i0: i1 + 1]), kl.get("yazim", {})):
        ws.append({"w": w_, "duyulan": duy, "a": round(a_ - t0, 3), "b": round(b_ - t0, 3), "kare": 0,
                   "cumle_sonu": bool(np.abs(sonlar - b_).min() < 0.02)})
    altyazi = bool(kl.get("altyazi", plan.get("altyazi", False)))
    fps_cikti = k["fps"] if k["fps"] <= 30.5 else 30.0      # 60 fps recordings: every other frame, never a repeat
    kurgu = kl.get("kurgu", plan.get("kurgu", "sade"))
    if kurgu not in ("sade", "editli"): raise SystemExit(f"RED: kurgu '{kurgu}' (sade ya da editli)")
    ed = klip_edit.Kurgu(kl, sure, fps_cikti, ws, [c - t0 for c in kes], kok) if kurgu == "editli" and kl.get("vuruslar") else None
    for w in ws: w["a_k"], w["b_k"] = w["a"], w["b"]          # source-relative times (the gate checks the cut on these)
    # on-screen start of every word: Whisper sometimes gives a word no length ('Bu' 10.80-10.80, next word also
    # at 10.80); such a word would never be lit. Each word gets at least 2 frames, starts never go backwards.
    if ed:                                                    # words move with the timeline (slow part pushes them later)
        for w in ws: w["a"], w["b"] = round(ed.cikti(w["a_k"]), 3), round(ed.cikti(w["b_k"]), 3)
    once = -1.0
    for w in ws:
        w["g"] = max(w["a"] - 0.02, once + 2.0 / fps_cikti); once = w["g"]

    g, dz = filtre(plan, kl, k)
    if ed: g = ed.filtre_on(ARA_KARE_VF, k["fps"]) + ";" + g.replace("[0:v]", "[kurgu]", 1)   # editli: fps per segment
    elif k["fps"] > 30.5: g = g.replace("[0:v]", f"[0:v]fps={fps_cikti},", 1)
    bimg = ed.baslik_ciz(yazi, None, BEYAZ, VURGU) if ed else None
    if ed: ed.hazirla(yazi, BEYAZ, VURGU, dz, bimg)            # drawings under the camera band, punch lines laid out
    govde = ed.govde_sure if ed else sure
    # -t as an INPUT option: it limits the recording read, not the output (an edited clip is longer than its source span)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{sure + (0.2 if ed else 0):.3f}", "-i", kaynak, "-an",
                            "-filter_complex", g, "-map", "[v]", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    sessiz = cikti_kl + ".video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", f"{fps_cikti:g}",
                            "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", sessiz], stdin=subprocess.PIPE)
    kumeler = kumele(ws) if altyazi else []
    for ki, ku in enumerate(kumeler):                                  # a cue stays until the next one (or a pause)
        son_w = ws[ku[-1]]; nxt = ws[kumeler[ki + 1][0]]["g"] if ki + 1 < len(kumeler) else govde
        son_w["kume_bitis"] = min(nxt, max(son_w["b"] + 0.6, son_w["g"] + 0.12))
    cache = {}; n = 0; boyut = W * H * 3; ilk_yazi = None; ki = 0; yazi_kutu = None
    while True:
        buf = dec.stdout.read(boyut)
        if len(buf) < boyut: break
        t = n / fps_cikti
        if ed:
            buf = np.ascontiguousarray(ed.uygula(np.frombuffer(buf, np.uint8).reshape(H, W, 3), t, dz, k, bimg)).tobytes()
        while altyazi and ki < len(kumeler) and t >= ws[kumeler[ki][-1]]["kume_bitis"]: ki += 1
        if altyazi and ki < len(kumeler) and ws[kumeler[ki][0]]["g"] <= t:
            ku = kumeler[ki]; etkin = max(j for j, i in enumerate(ku) if ws[i]["g"] <= t)
            key = (ki, etkin)
            if key not in cache: cache = {key: kume_ciz([ws[i]["w"] for i in ku], etkin)}
            L = cache[key]
            img = Image.frombuffer("RGB", (W, H), buf, "raw", "RGB", 0, 1).copy()
            yy = dz["yazi_y"] + (0.10 if bimg is not None and t < klip_edit.BASLIK_SN + klip_edit.BASLIK_SOLMA else 0)
            x_, y_ = SAFE_L + (W - SAFE_L - SAFE_R - L.width) // 2, int(yy * H - L.height / 2)
            img.paste(L, (x_, y_), L)
            # the area any cue covered (the gate keeps it off the face): ink of the cue image, not its padding
            bb = L.getchannel("A").getbbox() or (0, 0, L.width, L.height)
            r_ = [x_ + bb[0], y_ + bb[1], x_ + bb[2], y_ + bb[3]]
            yazi_kutu = r_ if yazi_kutu is None else [min(yazi_kutu[0], r_[0]), min(yazi_kutu[1], r_[1]),
                                                      max(yazi_kutu[2], r_[2]), max(yazi_kutu[3], r_[3])]
            ws[ku[etkin]]["kare"] += 1                                  # frames in which this word is the lit one
            if ilk_yazi is None: ilk_yazi = round(t, 3)
            buf = img.tobytes()
        enc.stdin.write(buf); n += 1
    dec.wait(); enc.stdin.close(); enc.wait()
    if n == 0: raise SystemExit(f"HATA: {kaynak} {t0:.2f} sn'den kare okunamadı")

    ses = cikti_kl + ".ses.wav"
    s_bilgi = ses_kurgu(kaynak, plan.get("ses_izi", 0), t0, ed, n / fps_cikti, ses) if ed else ses_kes(kaynak, plan.get("ses_izi", 0), t0, n / fps_cikti, ses)
    # no -shortest: it dropped the last 3 frames of a clip (469 of 472, 18.11.2026). The sound is exactly as long as
    # the picture; -t cuts both at the picture's length.
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", sessiz, "-i", ses, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                           "-c:a", "aac", "-b:a", "192k", "-t", f"{n / fps_cikti:.6f}", "-movflags", "+faststart", cikti_kl])
    son_k = kel[i1][0]
    rapor = {"ad": kl["ad"], "kaynak": kaynak, "t0": round(t0, 3), "t1": round(t0 + n / fps_cikti, 3), "sure": round(n / fps_cikti, 3),
             "fps_kaynak": k["fps"], "fps_cikti": fps_cikti, "hiz": 1.0,
             "kare_cikti": n, "kare_kaynak_beklenen": sum(s_["kare"] for s_ in ed.seg) if ed else int(round(n / fps_cikti * min(k["fps"], fps_cikti))),
             "ilk_kelime": ws[0]["a"], "ilk_yazi": ilk_yazi, "son_kelime_bitis": ws[-1]["b_k"], "son_kelime": son_k,
             "on_pay": round(kel[i0][1] - t0, 3), "on_pay_plan": kl.get("on_pay"), "yazi_kutu": yazi_kutu,
             "govde_kaynak_sure": round(ed.govde_kaynak if ed else n / fps_cikti, 3), "edit": ed.rapor() if ed else None,
             "sonraki_kelime_bas": round(sonraki - t0, 3), "sonraki_kelime": kel[i1 + 1][0] if i1 + 1 < len(kel) else None,
             "altyazi": altyazi, "kelimeler": ws, "yazi_kelimeleri": [k_[0] for k_ in kel[i0: i1 + 1]], "yazim": kl.get("yazim", {}),
             "cumle_sonlari": [round(c[2], 3) for c in yz.get("cumleler", []) if t0 - 1 <= c[2] <= t0 + sure + 1],
             "duzen": dz, "ses": {"dosya": ses, **s_bilgi, "iz": plan.get("ses_izi", 0)},
             "neden": kl.get("neden", ""), "baslik": kl.get("baslik", ""), "puan": kl.get("puan"), "bas_plan": kl["bas"], "son_plan": kl["son"]}
    json.dump(rapor, open(cikti_kl + ".rapor.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # four frames + an 8-frame strip, for the eye check and the panel
    kd = os.path.splitext(cikti_kl)[0] + "-kareler"; os.makedirs(kd, exist_ok=True)
    for q, u in enumerate((0.08, 0.36, 0.64, 0.94), 1):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{u * rapor['sure']:.2f}", "-i", cikti_kl, "-frames:v", "1",
                        "-vf", "scale=540:-2", "-q:v", "3", os.path.join(kd, f"kare{q}.jpg")], check=True)
    subprocess.run([sys.executable, os.path.join(KOK, "serit.py"), cikti_kl, os.path.join(kd, "serit.jpg"), "8"],
                   capture_output=True)
    print(f"TAMAM {cikti_kl}  {kl['ad']}: {t0:.2f}-{t0 + rapor['sure']:.2f} sn kayıtta, {rapor['sure']:.2f} sn, {n} kare, "
          f"{len(ws)} kelime", flush=True)
    return rapor


def _plan_ac(plan_yolu):
    plan = json.load(open(plan_yolu, encoding="utf-8"))
    if plan.get("tarz") != "klip": sys.exit("RED: bu plan Klip planı değil (\"tarz\": \"klip\" yok)")
    kok = os.path.dirname(os.path.abspath(plan_yolu))
    return plan, kok, (lambda p: p if os.path.isabs(p) else os.path.join(kok, p))


def _klip_al(plan, ad):
    kl = next((x for x in plan["klipler"] if x["ad"] == ad), None)
    if kl is None: sys.exit(f"RED: planda '{ad}' adlı klip yok ({', '.join(x['ad'] for x in plan['klipler'])})")
    return kl


def onizle(plan_yolu, klasor, ad, sn=None):
    """One frame of the layout at second `sn` of the recording (default: the clip's middle) with a sample caption
    at its place and the face box outline: check the game crop (odak, oyun) and the caption place before building."""
    plan, kok, yol = _plan_ac(plan_yolu); kl = _klip_al(plan, ad)
    kaynak = yol(plan["kaynak"]); k = kaynak_bilgi(kaynak)
    t = float(sn) if sn is not None else (kl["bas"] + kl["son"]) / 2
    g, dz = filtre(plan, kl, k)
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", kaynak, "-frames:v", "1", "-an", "-filter_complex", g,
                        "-map", "[v]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(b) != W * H * 3: sys.exit(f"HATA: {t:.2f} sn'den kare okunamadı")
    img = Image.frombuffer("RGB", (W, H), b, "raw", "RGB", 0, 1).copy()
    yz = json.load(open(yol(plan["yazi"]), encoding="utf-8")); dil_ayarla(yz)
    # the sample caption as the clip will show it: the clip's yazim applied (a key may start a word or two earlier)
    kel = yz["kelimeler"]; j = next((i for i, w in enumerate(kel) if w[1] >= t), len(kel))
    yakin = yazim_uygula(birlestir(kel[max(0, j - 3): j + 8]), kl.get("yazim", {}))
    ornek = [w[0] for w in yakin if w[1] >= t - 0.001][:2] or ["ÖRNEK", "YAZI"]
    L = kume_ciz(ornek, 0)
    img.paste(L, (SAFE_L + (W - SAFE_L - SAFE_R - L.width) // 2, int(dz["yazi_y"] * H - L.height / 2)), L)
    from PIL import ImageDraw
    if dz.get("yuz_cikti"): ImageDraw.Draw(img).rectangle(dz["yuz_cikti"], outline=(60, 220, 90), width=4)
    os.makedirs(klasor, exist_ok=True); cikti = os.path.join(klasor, f"{ad}-onizleme.jpg")
    img.resize((540, 960), Image.LANCZOS).save(cikti, quality=90)
    gx = dz.get("oyun_gorunen_x")
    print(f"ONIZLEME {cikti}  {t:.2f} sn; düzen {dz['duzen']}, odak {dz.get('odak')}"
          + (f", oyunun görünen kısmı soldan %{gx[0] * 100:.0f}–%{gx[1] * 100:.0f}" if gx else "")
          + f", yazı yeri {dz.get('yazi_yer', '')} (ekran yüksekliğinin %{dz['yazi_y'] * 100:.0f}'i)"
          + ("; yeşil çerçeve = yüz (yazı oraya gelmez)" if dz.get("yuz_cikti") else ""))


def sozler(plan_yolu, ad=None, esik=0.45):
    """The words each clip will caption (after yazim), the ones Whisper was unsure of in [brackets] with their
    probability. Read it before building: names and game words are where Whisper goes wrong."""
    plan, kok, yol = _plan_ac(plan_yolu)
    kel = json.load(open(yol(plan["yazi"]), encoding="utf-8"))["kelimeler"]
    for kl in plan["klipler"]:
        if ad and kl["ad"] != ad: continue
        i0, i1 = kelime_araligi(kel, kl["bas"], kl["son"])
        olas = {}
        for w in kel[i0: i1 + 1]: olas[w[0]] = min(olas.get(w[0], 1.0), w[3] if len(w) > 3 else 1.0)
        parca = []
        for w_, a_, b_, duy in yazim_uygula(birlestir(kel[i0: i1 + 1]), kl.get("yazim", {})):
            p = olas.get(duy, 1.0)
            parca.append(f"[{w_} {p:.2f}]" if w_ == duy and p < esik else (f"{w_}(<-{duy})" if w_ != duy else w_))
        sup = sum(1 for x in parca if x.startswith("["))
        print(f"{kl['ad']} ({kl['bas']}-{kl['son']} sn, {len(parca)} kelime, {sup} şüpheli): " + " ".join(parca))


def main(plan_yolu, klasor, sadece=None):
    plan = json.load(open(plan_yolu, encoding="utf-8"))
    if plan.get("tarz") != "klip": sys.exit("RED: bu plan Klip planı değil (\"tarz\": \"klip\" yok)")
    kok = os.path.dirname(os.path.abspath(plan_yolu)); os.makedirs(klasor, exist_ok=True)
    liste_yol = os.path.join(klasor, "klipler.json")
    eski = {x["ad"]: x for x in json.load(open(liste_yol, encoding="utf-8"))} if os.path.isfile(liste_yol) else {}
    adlar = [kl["ad"] for kl in plan["klipler"]]
    if len(set(adlar)) != len(adlar): sys.exit("RED: iki klibin adı aynı")
    for kl in plan["klipler"]:
        if sadece and kl["ad"] != sadece: continue
        r = tek_klip(plan, kl, kok, os.path.join(klasor, kl["ad"] + ".mp4"))
        eski[kl["ad"]] = {"ad": kl["ad"], "video": kl["ad"] + ".mp4", "kareler": kl["ad"] + "-kareler", "bas": r["t0"], "son": r["t1"],
                          "sure": r["sure"], "neden": r["neden"], "baslik": r["baslik"], "puan": kl.get("puan"), "kullanici": kl.get("kullanici"),
                          "boyut": os.path.getsize(os.path.join(klasor, kl["ad"] + ".mp4"))}
    # best first: the panel lists the clips by score (a clip without a score goes last, in plan order)
    liste = sorted([eski[a] for a in adlar if a in eski], key=lambda x: -(x.get("puan") or 0))
    json.dump(liste, open(liste_yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): print(__doc__); sys.exit(0)
    if "--sozler" in a:
        i = a.index("--sozler"); sozler(a[0], a[i + 1] if i + 1 < len(a) else None)
    elif "--onizle" in a:
        i = a.index("--onizle"); onizle(a[0], a[1], a[i + 1], a[i + 2] if i + 2 < len(a) else None)
    else:
        s = a[a.index("--sadece") + 1] if "--sadece" in a else None
        main(a[0], a[1], s)
