"""klip_edit.py - the "Editli" cut of the Klip style (17.11.2026): beats ("vuruslar") chosen by the model, applied here.

The default stays "Sade" (a straight cut: the much-watched streamer clips we measured are cut straight). With
"kurgu": "editli" the plan carries, per clip, a list of beats. Nothing is guessed here: no automatic effect, only
what the plan says. Times "t", "bas", "son" are seconds inside the clip as the Sade cut shows them (0 = clip start).

  {"tur": "zum",      "t": 13.1, "neden": "..."}   quick push-in on the face (camera band) and a slight one on the
                                                     game band at the crop centre; 0.15 s in, ~0.8 s hold, 0.35 s out
  {"tur": "sarsinti", "t": 12.9, "neden": "..."}   0.25 s shake + one white flash frame, game band only
  {"tur": "parlama",  "t": 12.9, "neden": "..."}   one white flash frame, game band only
  {"tur": "yavas",    "bas": 11.2, "son": 12.4, "neden": "..."}
                                                     1-1.5 s at half speed; in-between frames by ffmpeg minterpolate
                                                     (never a repeated frame); the sound is cut there and comes back in
                                                     sync. No spoken word may lie inside it.
  {"tur": "tekrar",   "bas": 12.6, "son": 14.2, "neden": "..."}
                                                     1-2 s replay of the best moment, closer, after the clip's end; it
                                                     may not cut a word in two
  {"tur": "baslik",   "metin": "SÖZ VERDİ, 15 SN SONRA…", "vurgu": ["SÖZ"], "neden": "..."}
                                                     hook box for the first ~2.4 s, under the seam, then fades
  {"tur": "ses",      "t": 13.0, "ses": "carpma"|"vin"|"pit", "neden": "..."}
                                                     code-made effect sound (kod/klip_ses.py) on top of the voice
  {"tur": "cizim",    "t": 17.4, "sure": 2.8, "tarif": "cizim/bicak.json" | {...}, "bolge": [x0, y0, x1, y1],
                      "kisma": 0.3, "neden": "..."}
                                                     a hand-drawn scene (kod/cizim.py recipe, written by the model for
                                                     what is SAID or HAPPENS right then) drawn on the game band as a
                                                     transparent layer; bolge = shares of the 1080x1920 frame and must
                                                     stay under the camera band (never on the face). At most 2 a clip.
  {"tur": "soz",      "metin": "SENİN KELEBEĞİNDEN DAHA İYİ", "t": 19.4, "neden": "..."}
                                                     the punch line of the joke/event, 2-4 words exactly as spoken
                                                     (found in the transcript near t), big Anton under the seam while it
                                                     is said: the word being said is yellow, the next ones are dim; gone
                                                     0.35 s after the last word. Not a caption. At most 2 a clip.

Forbidden by design (the creator rejected it): freeze frame + text + ring. There is no freeze here at all.
All motion comes from the frame number and a seed (the clip name): the same plan renders the same clip.
"""
import math, zlib
import numpy as np
from PIL import Image, ImageDraw

W, H = 1080, 1920


def alt_tasma(metin, px, kontur=None):
    """Pixels a word's ink reaches below the baseline of its font (Ç, Ş, comma, semicolon); 0 for plain capitals.
    motor.yazi() crops a word image to its ink, so words in one line must be aligned on the baseline."""
    from motor import font
    f = font(px); st = kontur or max(6, px // 11)
    return max(0, f.getbbox(metin, stroke_width=st)[3] - f.getbbox("H", stroke_width=st)[3])
YAVAS_KAT = 2.0                      # half speed
ZUM_GIR, ZUM_KAL, ZUM_CIK = 0.15, 0.80, 0.35
ZUM_KAMERA, ZUM_OYUN = 1.32, 1.10
SARS_SN, SARS_PX, SARS_ZUM = 0.26, 22, 1.07
BASLIK_SN, BASLIK_SOLMA = 2.4, 0.3
TEKRAR_KAMERA, TEKRAR_OYUN = 1.22, 1.30
TURLER = ("zum", "sarsinti", "parlama", "yavas", "tekrar", "baslik", "ses", "cizim", "soz")
EN_COK = 4                           # picture beats per clip (zum, sarsinti, parlama, yavas, tekrar); hook text and sounds aside
CIZIM_EN_COK, SOZ_EN_COK = 2, 2      # drawings and punch lines per clip (counted on their own)
SOZ_PX, SOZ_KALAN = 104, 0.35        # punch line font size; how long it stays after the last word
SOZ_ZEMIN = (10, 10, 12, 175)          # plate behind the words
SOZ_SOLUK = 0.42                     # alpha of the words not said yet


def _yumusak(a): a = max(0.0, min(1.0, a)); return a * a * (3 - 2 * a)


class Kurgu:
    """Timeline of one clip: segments of the recording (source time, relative to the clip start) -> output time."""

    def __init__(self, kl, sure, fps, kelimeler, kesmeler_rel, kok=None):
        self.fps = fps; self.ad = kl["ad"]; self.tohum = zlib.crc32(kl["ad"].encode("utf-8"))
        vs = kl.get("vuruslar") or []
        gorsel = [v for v in vs if v.get("tur") not in ("ses", "baslik", "cizim", "soz")]
        if sum(1 for v in vs if v.get("tur") == "cizim") > CIZIM_EN_COK: raise SystemExit(f"RED: {self.ad} en cok {CIZIM_EN_COK} cizim")
        if sum(1 for v in vs if v.get("tur") == "soz") > SOZ_EN_COK: raise SystemExit(f"RED: {self.ad} en cok {SOZ_EN_COK} vurgu sozu")
        if len(gorsel) > EN_COK: raise SystemExit(f"RED: {self.ad} {len(gorsel)} goruntu vurusu; en cok {EN_COK} (baslik ve ses haric)")
        if sum(1 for v in vs if v.get("tur") == "ses") > EN_COK: raise SystemExit(f"RED: {self.ad} en cok {EN_COK} efekt sesi")
        for v in vs:
            if v.get("tur") not in TURLER: raise SystemExit(f"RED: {self.ad} bilinmeyen vurus turu '{v.get('tur')}' ({', '.join(TURLER)})")
            if not str(v.get("neden", "")).strip(): raise SystemExit(f"RED: {self.ad} '{v['tur']}' vurusunun nedeni yok")
            for a in ("t", "bas", "son"):
                if a in v and not (0 <= float(v[a]) <= sure + 1e-6): raise SystemExit(f"RED: {self.ad} '{v['tur']}' {a}={v[a]} klibin disinda (0-{sure:.2f})")
        kare = 1.0 / fps
        q = lambda x: round(round(float(x) / kare) * kare, 6)            # snap to the output frame grid
        kelime_ici = lambda a, b: [w for w in kelimeler if w["a"] < b - 0.01 and w["b"] > a + 0.01]
        son = round(math.ceil(sure * fps - 1e-6) / fps, 6)               # body end: whole frames, never before the last word
        yv = [v for v in vs if v["tur"] == "yavas"]; tk = [v for v in vs if v["tur"] == "tekrar"]
        if len(yv) > 1 or len(tk) > 1: raise SystemExit(f"RED: {self.ad} en cok bir yavas ve bir tekrar")
        self.seg = []
        if yv:
            a, b = q(yv[0]["bas"]), q(yv[0]["son"])
            if not 0.8 <= b - a <= 1.6: raise SystemExit(f"RED: {self.ad} yavas {b - a:.2f} sn; 1-1,5 sn olmali")
            ic = kelime_ici(a, b)
            if ic: raise SystemExit(f"RED: {self.ad} yavas {a:.2f}-{b:.2f} sn konusmanin ustune dusuyor ('{ic[0]['w']}' {ic[0]['a']:.2f}-{ic[0]['b']:.2f}); ses orada kesilir, kelime kesilmez: araligi kaydir")
            if any(a < c < b for c in kesmeler_rel): raise SystemExit(f"RED: {self.ad} yavas aralik bir sahne kesmesini iceriyor")
            if a > 0: self.seg.append({"tur": "normal", "a": 0.0, "b": a, "kat": 1.0})
            self.seg.append({"tur": "yavas", "a": a, "b": b, "kat": YAVAS_KAT})
            self.seg.append({"tur": "normal", "a": b, "b": son, "kat": 1.0})
        else:
            self.seg.append({"tur": "normal", "a": 0.0, "b": son, "kat": 1.0})
        if tk:
            a, b = q(tk[0]["bas"]), q(tk[0]["son"])
            if not 0.8 <= b - a <= 2.2: raise SystemExit(f"RED: {self.ad} tekrar {b - a:.2f} sn; 1-2 sn olmali")
            yarim = [w for w in kelimeler if (w["a"] < a - 0.01 < w["b"]) or (w["a"] < b - 0.01 < w["b"] - 0.02)]
            if yarim: raise SystemExit(f"RED: {self.ad} tekrar bir kelimeyi ikiye boluyor ('{yarim[0]['w']}' {yarim[0]['a']:.2f}-{yarim[0]['b']:.2f})")
            if any(a < c < b for c in kesmeler_rel): raise SystemExit(f"RED: {self.ad} tekrar bir sahne kesmesini iceriyor")
            self.seg.append({"tur": "tekrar", "a": a, "b": b, "kat": 1.0})
        o = 0.0
        for s in self.seg:
            s["kare"] = int(round((s["b"] - s["a"]) * s["kat"] * fps)); s["oa"] = round(o, 6); o += s["kare"] / fps; s["ob"] = round(o, 6)
        self.toplam = o
        govde = [s for s in self.seg if s["tur"] != "tekrar"]
        self.govde_sure = govde[-1]["ob"]; self.govde_kaynak = govde[-1]["b"]
        self.vuruslar = []
        for v in vs:
            d = dict(v)
            if v["tur"] == "cizim": d.update(self._cizim_hazirla(v, sure, kok))
            if v["tur"] == "soz": d.update(self._soz_bul(v, kelimeler))
            if "t" in v: d["ot"] = round(self.cikti(float(v["t"])), 3)
            if "bas" in v: d["oa"] = round(self.cikti(float(v["bas"])), 3) if v["tur"] != "tekrar" else self.seg[-1]["oa"]
            if "son" in v: d["ob"] = round(self.cikti(float(v["son"])), 3) if v["tur"] != "tekrar" else self.seg[-1]["ob"]
            self.vuruslar.append(d)
        self.baslik = next((v for v in vs if v["tur"] == "baslik"), None)
        for d in self.vuruslar:
            if d["tur"] == "soz":
                for w in d["kel"]: w["oa"], w["ob"] = round(self.cikti(w["a"]), 3), round(self.cikti(w["b"]), 3)
                d["oa"], d["ob"] = d["kel"][0]["oa"], d["kel"][-1]["ob"]
        self._soz_img = {}

    # ------------------------------------------------------------------ drawing ("cizim") and punch line ("soz")
    def _cizim_hazirla(self, v, sure, kok):
        """Load the recipe, place it ('ust' on the given region, no push-in, no chalk stick), check it with the kit."""
        import json, os, cizim
        if "t" not in v: raise SystemExit(f"RED: {self.ad} cizim vurusunun 't'si yok")
        sn = float(v.get("sure", 0))
        if not 1.5 <= sn <= 3.5: raise SystemExit(f"RED: {self.ad} cizim {sn} sn; 1,5-3,5 sn olmali")
        if float(v["t"]) + sn > sure + 0.01: raise SystemExit(f"RED: {self.ad} cizim klibin sonunu asiyor")
        tr = v.get("tarif")
        if isinstance(tr, str):
            yol = tr if os.path.isabs(tr) or not kok else os.path.join(kok, tr)
            T = json.load(open(yol, encoding="utf-8"))
        elif isinstance(tr, dict): T = json.loads(json.dumps(tr))
        else: raise SystemExit(f"RED: {self.ad} cizim vurusunun 'tarif'i yok (dosya yolu ya da gomulu tarif)")
        b = v.get("bolge")
        if not (isinstance(b, list) and len(b) == 4 and 0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1):
            raise SystemExit(f"RED: {self.ad} cizim 'bolge' [x0, y0, x1, y1] (karenin orani) olmali")
        T["zemin"] = "saydam"; T["itme"] = 0; T["sure"] = sn; T["tebesir"] = bool(T.get("tebesir", False))
        T["yerlesim"] = {"kip": "ust", "bolge": b, "kisma": float(v.get("kisma", 0.3))}
        hata = [m for m in cizim.dogrula(T) if m.startswith("HATA")]
        if hata: raise SystemExit(f"RED: {self.ad} cizim tarifi: {hata[0]}")
        return {"T": T, "kutular": cizim.kutular(T), "uyarilar": [m for m in cizim.dogrula(T) if m.startswith("UYARI")]}

    def _soz_bul(self, v, kelimeler):
        """The punch line's words in the transcript (2-4, consecutive, as spoken), nearest to v['t']."""
        import re
        nk = lambda w: re.sub(r"[^0-9a-zçğıöşü]", "", str(w).replace("İ", "i").replace("I", "ı").lower())
        # "duyulan": the words as the transcript has them, when Whisper misheard one ("elimden" for "evimden");
        # "metin" is what is shown. Same number of words.
        hedef = [nk(x) for x in str(v.get("duyulan") or v.get("metin", "")).split() if nk(x)]
        if not 2 <= len(hedef) <= 4: raise SystemExit(f"RED: {self.ad} vurgu sozu 2-4 kelime olmali ('{v.get('metin')}')")
        ws = [w for w in kelimeler]; aday = []
        for i in range(len(ws) - len(hedef) + 1):
            if all(nk(ws[i + j]["w"]) == hedef[j] for j in range(len(hedef))): aday.append(i)
        if not aday: raise SystemExit(f"RED: {self.ad} vurgu sozu '{v.get('metin')}' dokumde bu sirayla yok; kelimeleri dokumdeki gibi yaz")
        i = min(aday, key=lambda i: abs(ws[i]["a"] - float(v.get("t", ws[i]["a"]))))
        yaz = [x for x in str(v["metin"]).split() if nk(x)]
        if len(yaz) != len(hedef): raise SystemExit(f"RED: {self.ad} vurgu sozu 'metin' ile 'duyulan' ayni sayida kelime olmali")
        return {"kel": [{"w": yaz[j], "a": ws[i + j]["a"], "b": ws[i + j]["b"]} for j in range(len(hedef))]}

    def hazirla(self, yazi_fn, beyaz, vurgu_renk, dz, baslik_img):
        """After the layout is known: drawings must stay under the camera band; punch lines are laid out."""
        ht = dz.get("dikis_px") or 0
        for d in self.vuruslar:
            if d["tur"] == "cizim":
                y0 = d["bolge"][1] * H
                if y0 < ht + 40: raise SystemExit(f"RED: {self.ad} cizim bolgesi kamera bandina giriyor (y0 {y0:.0f} px, dikis {ht} px): yuzun ustune cizim yok")
                for k in d["kutular"]:
                    x0, y0_, x1, y1 = k["kutu"]
                    if y0_ < ht or x0 < 0 or y1 > H or x1 > W: raise SystemExit(f"RED: {self.ad} cizim ogesi '{k['id']}' {k['kutu']} kamera bandina ya da ekran disina tasiyor")
            if d["tur"] == "soz": self._soz_dizgi(d, yazi_fn, beyaz, vurgu_renk, ht, baslik_img)

    def _soz_dizgi(self, d, yazi_fn, beyaz, vurgu_renk, ht, baslik_img):
        buyuk = lambda s: s.replace("i", "İ").replace("ı", "I").upper().strip(".,!?…")
        px = SOZ_PX; sinir = W - 2 * 80
        while True:
            ak = [yazi_fn(buyuk(w["w"]), px, beyaz, max(6, px // 11)) for w in d["kel"]]
            sa = [yazi_fn(buyuk(w["w"]), px, vurgu_renk, max(6, px // 11)) for w in d["kel"]]
            alt = [alt_tasma(buyuk(w["w"]), px, max(6, px // 11)) for w in d["kel"]]
            bos = int(px * 0.22); satir, cur, gen = [], [], 0
            for i, p in enumerate(ak):
                if cur and gen + bos + p.width > sinir: satir.append(cur); cur, gen = [], 0
                gen += (bos if cur else 0) + p.width; cur.append(i)
            if cur: satir.append(cur)
            if len(satir) <= 2 or px <= 70: break
            px -= 8
        bas_y = ht + 34
        if baslik_img is not None and d["oa"] < BASLIK_SN + BASLIK_SOLMA: bas_y = ht + 22 + baslik_img.height + 18
        yer, y = [], bas_y
        for s_ in satir:
            hh = max(ak[i].height - alt[i] for i in s_); x = (W - (sum(ak[i].width for i in s_) + bos * (len(s_) - 1))) // 2
            for i in s_: yer.append((i, x, y + hh - (ak[i].height - alt[i]))); x += ak[i].width + bos
            y += hh - 18
        d["kutu"] = [min(x for _, x, _ in yer), bas_y, max(x + ak[i].width for i, x, _ in yer), max(y_ + ak[i].height for i, _, y_ in yer)]
        # dark plate behind the words: the game HUD (score strip, kill banners) must not eat the grey not-said-yet words
        x0, y0, x1, y1 = d["kutu"]; pad = 22
        x0, y0, x1, y1 = max(0, x0 - pad), max(ht, y0 - pad + 6), min(W, x1 + pad), y1 + pad - 10
        zemin = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        ImageDraw.Draw(zemin).rounded_rectangle([0, 0, x1 - x0 - 1, y1 - y0 - 1], radius=22, fill=SOZ_ZEMIN)
        d["kutu"] = [x0, y0, x1, y1]
        self._soz_img[id(d)] = (ak, sa, yer, (zemin, x0, y0))

    def _soz_bindir(self, im, d, t):
        ak, sa, yer, (zemin, zx, zy) = self._soz_img[id(d)]
        im.paste(zemin, (zx, zy), zemin)
        for i, x, y in yer:
            w = d["kel"][i]
            if t < w["oa"]: L = ak[i].copy(); L.putalpha(Image.eval(L.getchannel("A"), lambda q: int(q * SOZ_SOLUK)))
            elif t < w["ob"] + 0.02 or (i == len(yer) - 1 and t < w["ob"] + SOZ_KALAN): L = sa[i]
            else: L = ak[i]
            im.paste(L, (x, y), L)
    def cikti(self, t):
        """Source time (clip-relative) -> output time, in the main body (not the replay)."""
        for s in self.seg:
            if s["tur"] == "tekrar": continue
            if s["a"] - 1e-6 <= t <= s["b"] + 1e-6: return s["oa"] + (t - s["a"]) * s["kat"]
        return self.govde_sure

    # ------------------------------------------------------------------ video: segments before the layout graph
    def filtre_on(self, ara_kare_vf, kaynak_fps=None):
        """'[0:v]...' graph part that cuts the clip into its segments, slows one, appends the replay -> [kurgu].
        kaynak_fps: the recording's frame rate. A 60 fps recording slowed 2x for a 30 fps clip needs no made-up frames:
        every real frame is shown once (setpts, then fps). Only when the recording has too few frames is
        ara_kare_vf (minterpolate) used. Normal parts are brought to the clip's fps here (every other frame of 60)."""
        n = len(self.seg); g = f"[0:v]split={n}" + "".join(f"[s{i}]" for i in range(n)) + ";" if n > 1 else ""
        parca = []
        kf = float(kaynak_fps or self.fps)
        for i, s in enumerate(self.seg):
            gir = f"[s{i}]" if n > 1 else "[0:v]"
            gercek = s["kat"] != 1.0 and kf >= s["kat"] * self.fps - 0.5      # enough real frames for this slow-down
            s["yavas_yontem"] = None if s["kat"] == 1.0 else ("gercek kare" if gercek else "ara kare")
            # a slowed part made with minterpolate reads 3 frames more: it needs the frame after the last one
            ek = 3.0 / self.fps if (s["kat"] != 1.0 and not gercek) else (2.0 / kf if gercek else 0)
            p = f"{gir}trim=start={s['a']:.6f}:end={s['b'] + ek:.6f},setpts=PTS-STARTPTS"
            if s["kat"] != 1.0 and gercek: p += f",setpts={s['kat']}*PTS,fps={self.fps:g}"
            elif s["kat"] != 1.0: p += f",setpts={s['kat']}*PTS," + ara_kare_vf.format(fps=f"{self.fps:g}")
            elif kf > self.fps + 0.5: p += f",fps={self.fps:g}"
            p += f",trim=end_frame={s['kare']},setpts=PTS-STARTPTS[p{i}]"
            parca.append(p)
        g += ";".join(parca) + ";" + "".join(f"[p{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[kurgu]"
        return g

    # ------------------------------------------------------------------ per-frame effects (output time t)
    def yuz_merkezi(self, dz, k):
        """Face centre in the camera band (output pixels); band centre without a face."""
        ht = dz.get("dikis_px")
        y = dz.get("plan_yuz"); kam = dz.get("kamera_px")
        if not ht: return None
        if not y or not kam: return (W / 2, ht / 2)
        fx, fy = (y[0] + y[2]) / 2 * k["w"], (y[1] + y[3]) / 2 * k["h"]
        return ((fx - kam[0]) / kam[2] * W, (fy - kam[1]) / kam[3] * ht)

    @staticmethod
    def _zum(bolge, z, mx, my):
        """Zoom a band (H x W x 3 array) by z around (mx, my), crop kept inside the band -> same size."""
        h, w = bolge.shape[:2]
        if z <= 1.001: return bolge
        cw, ch = w / z, h / z
        x0 = min(max(mx - cw / 2, 0), w - cw); y0 = min(max(my - ch / 2, 0), h - ch)
        im = Image.fromarray(bolge).resize((w, h), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
        return np.asarray(im)

    def uygula(self, a, t, dz, k, baslik_img):
        """a: H x W x 3 uint8 output frame (a copy may be returned). Applies the plan's beats at output time t."""
        ht = dz.get("dikis_px") or 0
        ust = (0, ht); alt = (ht, H)
        degisti = False
        zk, zo = 1.0, 1.0; kayx = kayy = 0.0; flas = 0.0
        tekrar = t >= self.govde_sure - 1e-6 and self.seg[-1]["tur"] == "tekrar"
        if tekrar:
            p = (t - self.seg[-1]["oa"]) / max(0.01, self.seg[-1]["ob"] - self.seg[-1]["oa"])
            zk, zo = TEKRAR_KAMERA + 0.04 * p, TEKRAR_OYUN + 0.06 * p
        for v in self.vuruslar:
            if v["tur"] == "zum" and not tekrar:
                d = t - v["ot"]
                if 0 <= d <= ZUM_GIR + ZUM_KAL + ZUM_CIK:
                    e = (1 - (1 - min(1, d / ZUM_GIR)) ** 3) if d < ZUM_GIR else (1.0 if d < ZUM_GIR + ZUM_KAL else 1 - _yumusak((d - ZUM_GIR - ZUM_KAL) / ZUM_CIK))
                    zk = max(zk, 1 + (ZUM_KAMERA - 1) * e); zo = max(zo, 1 + (ZUM_OYUN - 1) * e)
            elif v["tur"] == "sarsinti" and not tekrar:
                d = t - v["ot"]
                if 0 <= d < SARS_SN:
                    i = int(round(d * self.fps)); r = np.random.default_rng(self.tohum * 31 + i + int(v["ot"] * 1000))
                    guc = SARS_PX * (1 - d / SARS_SN)
                    kayx, kayy = r.uniform(-1, 1) * guc, r.uniform(-1, 1) * guc
                    zo = max(zo, SARS_ZUM)
                if -0.5 / self.fps <= d < 0.5 / self.fps: flas = max(flas, 0.75)   # exactly one frame
            elif v["tur"] == "parlama" and not tekrar:
                d = t - v["ot"]
                if -0.5 / self.fps <= d < 0.5 / self.fps: flas = max(flas, 0.75)   # exactly one frame
        if zk > 1.001 and ht:
            m = self.yuz_merkezi(dz, k)
            a = a.copy(); a[ust[0]:ust[1]] = self._zum(a[ust[0]:ust[1]], zk, m[0], m[1]); degisti = True
        if zo > 1.001 or kayx or kayy:
            if not degisti: a = a.copy(); degisti = True
            b = a[alt[0]:alt[1]]; hb = b.shape[0]
            z = max(zo, 1 + 2 * (abs(kayx) + abs(kayy)) / min(W, hb) + 0.01)   # zoomed enough that a shake never shows an edge
            a[alt[0]:alt[1]] = self._zum(b, z, W / 2 + kayx, hb / 2 + kayy)
        if flas:
            if not degisti: a = a.copy(); degisti = True
            b = a[alt[0]:alt[1]].astype(np.float32)
            a[alt[0]:alt[1]] = (b * (1 - flas) + 255 * flas).astype(np.uint8)
        tekrar_mi = t >= self.govde_sure - 1e-6 and self.seg[-1]["tur"] == "tekrar"
        for v in self.vuruslar:                  # drawings: transparent layer on the game band (kit dims under it)
            if v["tur"] == "cizim" and not tekrar_mi and v["ot"] <= t < v["ot"] + v["sure"]:
                import cizim
                n = int(round((t - v["ot"]) * self.fps))
                a = np.asarray(cizim.sahne_karesi(Image.fromarray(a), v["T"], n, fps=self.fps)); degisti = True
        sozler = [v for v in self.vuruslar if v["tur"] == "soz" and not tekrar_mi and v["oa"] - 0.04 <= t < v["ob"] + SOZ_KALAN]
        if sozler:
            im = Image.fromarray(a)
            for v in sozler: self._soz_bindir(im, v, t)
            a = np.asarray(im); degisti = True
        if baslik_img is not None and t < BASLIK_SN + BASLIK_SOLMA:
            al = 1.0 if t < BASLIK_SN else 1 - _yumusak((t - BASLIK_SN) / BASLIK_SOLMA)
            if al > 0.01:
                if not degisti: a = a.copy(); degisti = True
                im = Image.fromarray(a); L = baslik_img
                if al < 0.999:
                    L = L.copy(); L.putalpha(Image.eval(L.getchannel("A"), lambda x: int(x * al)))
                y = (ht + 22) if ht else int(0.12 * H)
                im.paste(L, ((W - L.width) // 2, y), L); a = np.asarray(im)
        return a

    def baslik_ciz(self, yazi_fn, font_fn, beyaz, vurgu_renk):
        return self._baslik_ciz(yazi_fn, beyaz, vurgu_renk)

    def _baslik_ciz(self, yazi_fn, beyaz, vurgu_renk):
        """Hook box: Anton, white + #FFD43B for the plan's 'vurgu' words, dark rounded box. Fits 1080 - margins."""
        if not self.baslik: return None
        metin = str(self.baslik.get("metin", "")).strip()
        if not metin: raise SystemExit(f"RED: {self.ad} baslik vurusunun metni yok")
        tem = lambda w: w.strip(".,!?:…'\"’").replace("i", "İ").replace("ı", "I").upper()
        vur = {tem(x) for x in self.baslik.get("vurgu", [])}
        buyuk = lambda s: s.replace("i", "İ").replace("ı", "I").upper()
        kelimeler = buyuk(metin).split()
        px = 74; sinir = W - 2 * 70
        while True:
            parca = [yazi_fn(w, px, vurgu_renk if tem(w) in vur else beyaz, max(4, px // 14)) for w in kelimeler]
            # yazi() crops each word to its ink. A word with ink below the baseline (Ç, Ş, a comma) is a taller
            # image, so bottom-aligning lifted it above its neighbours ("BIÇAK", "DÜŞTÜ,"). Align on the baseline.
            for p, w in zip(parca, kelimeler): p.info["alt"] = alt_tasma(w, px, max(4, px // 14))
            bos = int(px * 0.26) - 20
            satirlar, cur, gen = [], [], 0
            for p in parca:
                if cur and gen + bos + p.width > sinir: satirlar.append(cur); cur, gen = [], 0
                gen += (bos if cur else 0) + p.width; cur.append(p)
            if cur: satirlar.append(cur)
            if len(satirlar) <= 2 or px <= 48: break
            px -= 6
        sw = [sum(p.width for p in s) + bos * (len(s) - 1) for s in satirlar]
        sh = [max(p.height - p.info["alt"] for p in s) for s in satirlar]   # line height = above-baseline part only
        pad = 26; bw = max(sw) + 2 * pad; bh = sum(sh) - 14 * (len(sh) - 1) + 2 * pad - 20
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=18, fill=(10, 10, 12, 242))   # near-opaque: HUD text under it never mixes in
        y = pad - 10
        for s, w_, h_ in zip(satirlar, sw, sh):
            x = (bw - w_) // 2
            for p in s: img.alpha_composite(p, (x, y + h_ - (p.height - p.info["alt"]))); x += p.width + bos
            y += h_ - 14
        return img

    def rapor(self):
        vr = []
        for v in self.vuruslar:
            d = {k: x for k, x in v.items() if k != "T"}
            if v["tur"] == "cizim": d["tarif"] = v["T"].get("ad") or (v["tarif"] if isinstance(v["tarif"], str) else "gomulu")
            vr.append(d)
        return {"kurgu": "editli", "segmentler": self.seg, "toplam": round(self.toplam, 3), "govde_sure": round(self.govde_sure, 3),
                "vuruslar": vr}

    def cizim_sesi(self, n_ornek, sr):
        """Stereo float32 track of the drawings' own sounds (kod/cizim_ses.py from the kit's frame events), placed at their
        output time, peak ~ -16 dBFS so they stay under the voice."""
        import cizim, cizim_ses
        y = np.zeros(n_ornek)
        for i, v in enumerate(v for v in self.vuruslar if v["tur"] == "cizim"):
            s = cizim_ses.ses_izi(cizim.olaylar(v["T"], self.fps), v["sure"], self.fps, self.tohum + i)
            m = np.abs(s).max()
            if m > 0: s = s / m * 10 ** (-16 / 20)
            a = int(round(v["ot"] * sr)); b = min(n_ornek, a + len(s))
            if b > a: y[a:b] += s[: b - a]
        return np.stack([y, y], axis=1).astype(np.float32)
