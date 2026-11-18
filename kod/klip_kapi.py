"""klip_kapi.py - the gate for the Klip style (clips cut from one long recording with speech).

    python kod/kapi.py <klip_plan.json> <klasor>      (kapi.py sends Klip plans here)
    python kod/klip_kapi.py <klip_plan.json> <klasor>
    exit 0 = GECTI, 1 = KALDI. Every line covers all clips of the plan; one failing clip fails the line.
    A clip without "puan" (1-10) in the plan prints a separate "UYARI:" line; it is not a check.

Checks (each clip needs <klasor>/<ad>.mp4 and <ad>.mp4.rapor.json from klip.py). Length and frame count are
measured on the DELIVERED mp4 (ffprobe), not taken from the report (18.11.2026: a clip had 469 frames, its report 472).
 1. BASLANGIC  the first spoken word starts within 0.5 s of the clip start (with captions on: its caption is on
               screen within 0.5 s), and the clip does not open inside the previous word. A clip with "on_pay" in
               the plan (silent picture before word 1, at most 3 s): within its on_pay + 0.1 s.
 2. BITIS      ends on a sentence boundary: the last word closes a sentence (. ? ! ... in the transcript, or a
               transcript sentence ends there) and the clip ends after that word and before the next one.
 3. ALTYAZI    captions are off by default ("altyazi": true turns them on): off = no caption was drawn. On =
               captions match the transcript: same words in the same order (only the planned spelling fixes
               "yazim" may differ, one or several words: klip.yazim_uygula) and every word was lit on screen; no
               caption pixel over the face (kamera layout with a face box).
 4. SURE       15-60 s. A range the user typed ("kullanici": {"tur": "aralik"} in the plan) outside 15-60 s only
               WARNS (line passes, starts with "UYARI:"): the user chose it.
 5. KADRAJ     measured on output frames: no flat black bar >= 2 % of the frame at the top, bottom or sides.
               Layout kamera: the seam between the camera band and the game band is where the layout says
               (614 px, or 778 px for a 4:3-like camera box) and shows in the frames there. Every rectangle used
               lies inside the recording's frame with >= 160 px on its short side (camera crop: >= 120 px).
               A face share of the camera band under 0.30 only WARNS ("UYARI:"), as does a game crop that still
               covers the camera / chat box.
 6. HIZ        no repeated frames: output fps <= recording fps and the number of output frames equals the
               recording frames in that time span, and the delivered mp4 holds exactly those frames. Editli cut ("kurgu": "editli", kod/klip_edit.py): the slowed part
               must be made of in-between frames (measured on the output: no two identical frames in a row in the
               game band), and no beat (slow part, replay) cuts a spoken word.
 7. SES        THIS STYLE ONLY: the soundtrack IS the recording's own audio at the same seconds (correlation
               >= 0.97 with the recording within +-20 ms, nothing else mixed in). The moments the limiter worked on
               (the recording raised by the clip's gain goes over the ceiling, + 150 ms release) are left out of the
               comparison: there the sound is the recording's own, only made quieter (18.11.2026: a quiet clip
               raised 9 dB fell to 0.960 on squashed gunshots and a valid clip was dropped). A different audio
               track or other seconds still fail (correlation near 0). Editli: every played segment is
               checked on its own (effect sounds masked out), and the shift after a slowed part must equal the
               shift before it (difference <= 1 ms: the voice comes back in sync). The other styles' check "4 KAYNAK SESI"
               (source audio must be absent) does not apply to Klip, by design, and is not run.
"""
import json, os, re, subprocess, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor import norm  # noqa: E402
from klip import birlestir, yazim_uygula, ON_PAY_EN_COK, SINIR_DB  # noqa: E402

BAS_SN, SURE_MIN, SURE_MAX, KISA_PX, KOR, KAYMA_MS = 0.5, 15.0, 60.0, 160, 0.97, 20
KAMERA_KISA_PX, SIYAH_PAY, YUZ_UYARI, DIKIS_TOL = 120, 0.02, 0.30, 4
SR = 16000


SOZ_KILIT = 0.15


def pcm(yol, ss=None, t=None, iz=None):
    a = ["ffmpeg", "-v", "error"] + (["-ss", f"{ss:.3f}"] if ss is not None else []) + ["-i", yol] + \
        (["-t", f"{t:.3f}"] if t is not None else []) + (["-map", f"0:a:{iz}"] if iz is not None else []) + \
        ["-vn", "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"]
    return np.frombuffer(subprocess.run(a, capture_output=True, check=True).stdout, np.int16).astype(np.float32) / 32768


def teslim(yol):
    """The delivered mp4 itself: video frames (packets), video and audio length. None where ffprobe cannot tell."""
    try:
        j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-show_entries",
                                       "stream=codec_type,nb_read_packets,duration", "-of", "json", yol],
                                      capture_output=True, text=True, check=True).stdout)
    except (subprocess.CalledProcessError, ValueError):
        return {"kare": None, "sure": None, "ses_sure": None}
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), {})
    f = lambda x: float(x) if x not in (None, "N/A") else None
    return {"kare": int(v["nb_read_packets"]) if v.get("nb_read_packets") else None, "sure": f(v.get("duration")),
            "ses_sure": f(a.get("duration"))}


def ses_esle(c, k, kazanc_db):
    """Best correlation of the clip's sound c with the recording k (same seconds) within +-KAYMA_MS, leaving out the
    moments the limiter worked on: where the recording raised by the clip's gain goes over 0.8 x the ceiling (mono
    16 kHz hides some stereo peaks, hence the margin), from 10 ms before to 150 ms after (limiter release).
    Returns (correlation, shift in samples, share left out)."""
    n = min(len(c), len(k)); c, k = c[:n], k[:n]
    tavan = 10 ** (SINIR_DB / 20) * 0.8 / 10 ** (kazanc_db / 20)          # in the recording's own level
    blok = int(0.005 * SR); nb = n // blok
    asan = np.zeros(nb + 1, bool)
    if nb: asan[:nb] = np.abs(k[: nb * blok]).reshape(nb, blok).max(1) > tavan
    tut = np.ones(nb + 1, bool)
    for i in np.flatnonzero(asan): tut[max(0, i - 2): i + 31] = False       # 10 ms before, 150 ms after
    m = np.repeat(tut, blok)[:n].astype(np.float32)
    if m.sum() < SR: m[:] = 1.0                                              # under 1 s left: compare everything
    kor, kay = 0.0, 0
    for L in range(-KAYMA_MS * SR // 1000, KAYMA_MS * SR // 1000 + 1, 2):
        a = c[max(0, L): n + min(0, L)]; b = k[max(0, -L): n - max(0, L)]; mm = m[max(0, -L): n - max(0, L)]
        a = a * mm; b = b * mm
        q = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        if q > kor: kor, kay = q, L
    return kor, kay, round(1 - float(m.mean()), 3)


def kareler(yol, sure, n=6):
    """n grey frames (full size) spread over the clip."""
    out = []
    for i in range(n):
        t = sure * (i + 0.5) / n
        b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", yol, "-frames:v", "1", "-f", "rawvideo",
                            "-pix_fmt", "gray", "-"], capture_output=True).stdout
        if len(b) == 1080 * 1920: out.append(np.frombuffer(b, np.uint8).reshape(1920, 1080).astype(np.float32))
    return out


def siyah_bant(g):
    """Share of the frame taken by a flat black bar at each edge (rows/columns with mean < 18 and max < 40)."""
    def say(satirlar):
        n = 0
        for r in satirlar:
            if r.mean() < 18 and r.max() < 40: n += 1
            else: break
        return n
    return {"ust": say(g) / g.shape[0], "alt": say(g[::-1]) / g.shape[0],
            "sol": say(g.T) / g.shape[1], "sag": say(g.T[::-1]) / g.shape[1]}


def dikis_bul(g, bek, ara=24):
    """Row (near the expected seam) where the picture changes most from one row to the next."""
    # measured on the left 50 px only: captions (on) sit over the seam but never start before x = 60
    d = np.abs(np.diff(g[bek - ara: bek + ara + 1, :50], axis=0)).mean(axis=1)
    # 4th value: the strongest edge within the tolerance of the expected row. A game HUD bar just under the seam
    # (CS2 scoreboard, 22 px lower) can be the strongest edge of the window while the seam is still exactly in place.
    tol = d[ara - 1 - DIKIS_TOL: ara + DIKIS_TOL]
    return bek - ara + 1 + int(np.argmax(d)), float(d.max()), float(np.median(d)), float(tol.max())


def eslestir(c, k):
    """Best correlation of c with k within +-KAYMA_MS -> (correlation, shift in samples)."""
    n = min(len(c), len(k)); kor, kay = 0.0, 0
    for L in range(-KAYMA_MS * SR // 1000, KAYMA_MS * SR // 1000 + 1, 1):
        a = c[max(0, L): n + min(0, L)]; b = k[max(0, -L): n - max(0, L)]
        q = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        if q > kor: kor, kay = q, L
    return kor, kay


def ses_editli(r, klasor):
    """Editli: each played segment against the recording at its own seconds, effect sounds masked (+-0.6 s)."""
    c = pcm(os.path.join(klasor, r["ad"] + ".mp4"))
    efekt = [v["ot"] for v in r["edit"]["vuruslar"] if v["tur"] == "ses"]
    sonuc, kaymalar, ok = [], [], True
    for g in r["edit"]["segmentler"]:
        if g["tur"] == "yavas": sonuc.append(f"yavas {g['oa']:.2f}-{g['ob']:.2f} sessiz"); continue
        if g["ob"] - g["oa"] < 0.5: continue
        a = c[int(g["oa"] * SR): int(g["ob"] * SR)].copy()
        k = pcm(r["kaynak"], r["t0"] + g["a"], g["ob"] - g["oa"], r["ses"].get("iz", 0))
        for t in efekt:
            if g["oa"] - 0.6 <= t <= g["ob"] + 0.6:
                i0, i1 = max(0, int((t - 0.6 - g["oa"]) * SR)), max(0, int((t + 0.6 - g["oa"]) * SR))
                a[i0:i1] = 0; k[i0:i1] = 0
        if float(np.sqrt(np.mean(k ** 2))) < 1e-3:              # the recording is silent there: nothing to match
            ok &= float(np.sqrt(np.mean(a ** 2))) < 3e-3
            sonuc.append(f"{g['tur']} {g['oa']:.2f}-{g['ob']:.2f} sn kayitta da sessiz"); continue
        kor, kay = eslestir(a, k); ms = kay * 1000 / SR
        kaymalar.append(ms); ok &= kor >= KOR
        sonuc.append(f"{g['tur']} {g['oa']:.2f}-{g['ob']:.2f} sn korelasyon {kor:.4f} kayma {ms:+.2f} ms")
    fark = (max(kaymalar) - min(kaymalar)) if len(kaymalar) > 1 else 0.0
    ok &= fark <= 1.0
    return ok, f"{r['ad']} editli: " + ", ".join(sonuc) + f"; parcalar arasi kayma farki {fark:.2f} ms" + ("" if fark <= 1.0 else " (SES KAYDI)")


def main(plan_yolu, klasor):
    plan = json.load(open(plan_yolu, encoding="utf-8"))
    rp, eksik = [], []
    for kl in plan["klipler"]:
        y = os.path.join(klasor, kl["ad"] + ".mp4")
        if os.path.isfile(y + ".rapor.json") and os.path.isfile(y): rp.append(json.load(open(y + ".rapor.json", encoding="utf-8")))
        else: eksik.append(kl["ad"])
    sonuc = []

    def yaz(ad, ok, ayrinti): sonuc.append(ok); print(f"[{'GECTI' if ok else 'KALDI'}] {ad}: {ayrinti}")

    if eksik: print(f"[KALDI] 0 KLIP: render edilmemiş klip: {', '.join(eksik)}"); sonuc.append(False)
    v = lambda x: f"{x:.2f}"
    for r in rp:                                            # the delivered file, measured (not the report)
        r["_teslim"] = teslim(os.path.join(klasor, r["ad"] + ".mp4"))
        if not r.get("edit") and r["_teslim"]["sure"]: r["sure"] = round(r["_teslim"]["sure"], 3)
    on_plan = {kl["ad"]: kl.get("on_pay") for kl in plan["klipler"]}

    # 1 start on the first spoken word (or within the clip's planned on_pay: the silent event before a reaction)
    s, ok = [], True
    for r in rp:
        acik = r.get("altyazi", True)                       # v1 reports had captions always on
        op = on_plan.get(r["ad"])
        esik = BAS_SN if not op else max(BAS_SN, min(ON_PAY_EN_COK, float(op)) + 0.1)
        iyi = r["ilk_kelime"] <= esik and (not acik or (r["ilk_yazi"] is not None and r["ilk_yazi"] <= esik))
        ok &= iyi; s.append(f"{r['ad']} ilk kelime {v(r['ilk_kelime'])} sn" + (f" (on_pay {float(op):g}, esik {esik:.2f})" if op else "")
                            + (f", ilk yazi {v(r['ilk_yazi'] or 99)} sn" if acik else ", altyazi kapali") + ("" if iyi else " (GEC)"))
    yaz("1 BASLANGIC", ok, f"[esik {BAS_SN} sn; planda on_pay varsa en cok {ON_PAY_EN_COK:g} sn] " + "; ".join(s))

    # 2 ends on a sentence boundary, not inside a word
    s, ok = [], True
    for r in rp:
        nokta = bool(re.search(r"[.?!…]$", r["son_kelime"]))
        cumle_sonu = any(abs(c - (r["t0"] + r["son_kelime_bitis"])) < 0.05 for c in r.get("cumle_sonlari", []))
        gs = r.get("govde_kaynak_sure", r["sure"])      # editli: the body of the clip (before a replay), recording time
        if not r.get("edit"): gs = min(gs, r["sure"])   # Sade: the delivered file may be shorter than the report
        kelime_ici = gs < r["son_kelime_bitis"] + 0.02 or gs > r["sonraki_kelime_bas"] + 0.02
        iyi = (nokta or cumle_sonu) and not kelime_ici; ok &= iyi
        s.append(f"{r['ad']} son kelime '{r['son_kelime']}' {v(r['son_kelime_bitis'])} sn, klip sonu {v(gs)} sn, "
                 f"sonraki kelime {v(r['sonraki_kelime_bas'])} sn" + ("" if nokta or cumle_sonu else " (CUMLE BITMIYOR)")
                 + (" (KELIME ICINDE KESIYOR)" if kelime_ici else ""))
    yaz("2 BITIS", ok, "; ".join(s))

    # 3 captions = transcript
    s, ok = [], True
    for r in rp:
        if not r.get("altyazi", True):
            cizilen = sum(w["kare"] for w in r["kelimeler"])
            ok &= cizilen == 0; s.append(f"{r['ad']} altyazi kapali (varsayilan)" + (f" ama {cizilen} karede yazi var" if cizilen else ""))
            continue
        yazim = r.get("yazim", {}) or {}
        # '1' '.58' -> '1.58', then the same spelling rule klip.py used (one or several words)
        bek = [w[0] for w in yazim_uygula(birlestir([[w, 0, 0] for w in r["yazi_kelimeleri"]]), yazim)]
        cizilen = [w["w"] for w in r["kelimeler"]]
        fark = [f"'{a}'≠'{b}'" for a, b in zip(bek, cizilen) if norm(a) != norm(b)]
        gorunmeyen = [w["w"] for w in r["kelimeler"] if w["kare"] == 0]
        # never over the face: the area the cues covered against the face box (kamera layout, both in output pixels)
        yk, yb = r.get("yazi_kutu"), (r.get("duzen") or {}).get("yuz_cikti")
        yuzde = bool(yk and yb and min(yk[2], yb[2]) > max(yk[0], yb[0]) and min(yk[3], yb[3]) > max(yk[1], yb[1]))
        iyi = len(bek) == len(cizilen) and not fark and not gorunmeyen and not yuzde; ok &= iyi
        s.append(f"{r['ad']} {len(cizilen)} kelime" + (f", fark {fark[:3]}" if fark else "")
                 + (f", ekrana cikmayan {gorunmeyen[:3]}" if gorunmeyen else "") + (f", yazim {len(yazim)}" if yazim else "")
                 + (f", yazi y {yk[1]}-{yk[3]} px" if yk else "") + (" (YAZI YUZUN USTUNDE: yazi_yer'i degistir)" if yuzde else ""))
    yaz("3 ALTYAZI", ok, "; ".join(s))

    # 4 length
    # a range the USER gave ("kullanici": {"tur": "aralik"}) is cut as given: outside 15-60 s is a warning, not a
    # failure - the user decided. Moments the model chose (or built around a user's point) must be 15-60 s.
    kul = {kl["ad"]: (kl.get("kullanici") or {}).get("tur") for kl in plan["klipler"]}
    s, ok, uyari = [], True, []
    for r in rp:
        icinde = SURE_MIN <= r["sure"] <= SURE_MAX
        if not icinde and kul.get(r["ad"]) == "aralik": uyari.append(f"{r['ad']} {v(r['sure'])} sn (kullanicinin araligi)")
        elif not icinde: ok = False
        s.append(f"{r['ad']} {v(r['sure'])} sn" + (" (kullanici araligi)" if kul.get(r["ad"]) == "aralik" else ""))
    yaz("4 SURE", ok, (f"UYARI: 15-60 sn disinda ama kullanicinin verdigi aralik, karar kullanicinin: {', '.join(uyari)}; " if uyari else "")
        + f"[{SURE_MIN:g}-{SURE_MAX:g} sn] " + ", ".join(s))

    # 5 layout: no black bars (measured on the output), the seam where the layout says, rectangles inside the frame
    s, ok, uyari = [], True, []
    for r in rp:
        d = r["duzen"]; kw, kh = d["kaynak_px"]; ad = r["ad"]
        if d["duzen"] == "kamera":
            kut = {"kamera": d.get("kamera_px"), "oyun": d.get("oyun_px")}; plan_k = [d.get("plan_kamera"), d.get("plan_oyun")]
        else:
            kut = {"kadraj": d.get("kadraj_px")}; plan_k = [d.get("plan_kadraj")]
        for kad, b_ in kut.items():
            en_az = KAMERA_KISA_PX if kad == "kamera" else KISA_PX
            ic = b_ and b_[0] >= 0 and b_[1] >= 0 and b_[0] + b_[2] <= kw and b_[1] + b_[3] <= kh and min(b_[2], b_[3]) >= en_az
            ok &= bool(ic)
            if not ic: s.append(f"{ad}/{kad} {b_} kayit karesinin DISINDA ya da KUCUK (kisa kenar >= {en_az} px)")
        for p in plan_k:
            if not (p and 0 <= p[0] < p[2] <= 1 and 0 <= p[1] < p[3] <= 1): ok = False; s.append(f"{ad} plan dikdortgeni gecersiz {p}")
        G = kareler(os.path.join(klasor, ad + ".mp4"), r["sure"])
        if not G: ok = False; s.append(f"{ad} cikti karesi okunamadi"); continue
        # a letterbox bar is in EVERY frame; a dark game moment (death screen, black loading frame) is in one or two.
        # So a bar counts when at least half of the sampled frames have it (median), not when one frame is dark.
        bant = {k: float(np.median([siyah_bant(g)[k] for g in G])) for k in ("ust", "alt", "sol", "sag")}
        kotu = {k: v_ for k, v_ in bant.items() if v_ >= SIYAH_PAY}
        ok &= not kotu
        parca = [f"{ad} {d['duzen']}: siyah bant " + (", ".join(f"{k} %{v_ * 100:.1f}" for k, v_ in kotu.items()) + " (SIYAH BANT)" if kotu else "yok")]
        if d["duzen"] == "kamera":
            bek = d.get("dikis_px")
            beklenen_ok = bek in (614, 778) and d["paneller"][0][3] == bek == d["paneller"][1][1]
            olc = [dikis_bul(g, bek) for g in G] if bek else []
            # a frame where both sides of the seam are equally dark (game HUD under a dark room) shows no edge at all:
            # it is not counted. Of the frames that do show an edge, at least half must have it at the expected row.
            net = [(y, mx, md, yb) for y, mx, md, yb in olc if mx > 2 * md + 2]
            yerinde = sum(1 for y, mx, md, yb in net if abs(y - bek) <= DIKIS_TOL or yb > 2 * md + 2)
            iyi = beklenen_ok and (yerinde >= len(net) / 2 if net else True)
            ok &= iyi
            parca.append(f"dikis {bek} px ({'4:3 kamera' if d.get('kamera_43') else '16:9 kamera'}), karelerde {yerinde}/{len(net)} yerinde"
                         + (f" ({len(olc) - len(net)} karede kenar secilmedi)" if len(net) < len(olc) else "") + ("" if iyi else " (DIKIS YANLIS)"))
            yp = d.get("yuz_pay")
            parca.append(f"yuz payi {yp:.2f}" if yp is not None else "yuz yok (kutu ortadan kirpildi)")
            if yp is not None and yp < YUZ_UYARI: uyari.append(f"{ad} yuz kamera bandinin yalniz %{yp * 100:.0f}'i (< %{YUZ_UYARI * 100:.0f})")
            parca.append(f"oyun odak {d.get('odak')}, gorunen %{(d.get('oyun_gorunen') or 0) * 100:.0f}")
            if (d.get("ortusme") or 0) > 0.005: uyari.append(f"{ad} oyun kirpmasinin %{d['ortusme'] * 100:.1f}'ini kamera/sohbet kutusu kapliyor")
        elif d["duzen"] == "doldur":
            parca.append(f"odak {d.get('odak')}, gorunen %{(d.get('oyun_gorunen') or 0) * 100:.0f}")
        s.append(", ".join(parca))
    yaz("5 KADRAJ", ok, (f"UYARI: {'; '.join(uyari)}; " if uyari else "") +
        f"[siyah bant < %{SIYAH_PAY * 100:g}, dikis +-{DIKIS_TOL} px, kayit karesi icinde] " + "; ".join(s))

    # 6 speed: real frames only (editli: the slowed part made of in-between frames, no beat cuts a word)
    s, ok = [], True
    for r in rp:
        ed = r.get("edit")
        if not ed:
            tk = r["_teslim"]["kare"]
            iyi = (r["hiz"] == 1.0 and r["fps_cikti"] <= r["fps_kaynak"] + 0.01 and r["kare_cikti"] == r["kare_kaynak_beklenen"]
                   and tk == r["kare_cikti"])
            ok &= iyi; s.append(f"{r['ad']} 1x, {r['fps_kaynak']:g}->{r['fps_cikti']:g} fps, {r['kare_cikti']} kare (kayitta {r['kare_kaynak_beklenen']}, "
                                f"teslim dosyasinda {tk if tk is not None else '?'})" + ("" if tk == r["kare_cikti"] else " (TESLIM DOSYASI EKSIK)")); continue
        yv = [g for g in ed["segmentler"] if g["tur"] == "yavas"]
        kare_ok = abs(r["kare_cikti"] - r["kare_kaynak_beklenen"]) <= len(yv) and r["fps_cikti"] <= r["fps_kaynak"] + 0.01
        parca = [f"{r['ad']} editli, {r['kare_cikti']} kare (plan {r['kare_kaynak_beklenen']})"]
        tekrar_kare = 0
        for g in yv:
            o = os.path.join(klasor, r["ad"] + ".mp4"); d = r["duzen"]; y0 = d.get("dikis_px") or 0
            b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{g['oa'] + 0.02:.3f}", "-i", o, "-t", f"{g['ob'] - g['oa'] - 0.05:.3f}",
                                "-vf", f"crop=1080:{1920 - y0}:0:{y0},scale=270:-2,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
            hh = (1920 - y0) * 270 // 1080 // 2 * 2
            F = np.frombuffer(b, np.uint8)[: len(b) // (270 * hh) * 270 * hh].reshape(-1, hh, 270).astype(np.float32)
            dif = np.abs(np.diff(F, axis=0)).mean(axis=(1, 2)) if len(F) > 1 else np.array([])
            tekrar_kare += int((dif < 0.3).sum())
            parca.append(f"yavas {g['a']:.2f}-{g['b']:.2f} sn x{g['kat']:g} {g.get('yavas_yontem') or 'ara kare'}, {len(F)} kare olculdu, tekrar eden kare {int((dif < 0.3).sum())}")
        kes = []
        kel = r["kelimeler"]
        for g in ed["segmentler"]:
            if g["tur"] == "yavas":
                kes += [w["w"] for w in kel if w["a_k"] < g["b"] - 0.01 and w["b_k"] > g["a"] + 0.01]
            if g["tur"] == "tekrar":
                kes += [w["w"] for w in kel if (w["a_k"] < g["a"] - 0.01 < w["b_k"]) or (w["a_k"] < g["b"] - 0.01 < w["b_k"] - 0.02)]
        iyi = kare_ok and tekrar_kare == 0 and not kes; ok &= iyi
        if kes: parca.append(f"vurus kelime kesiyor: {kes[:3]} (VURUS KELIME KESIYOR)")
        else: parca.append("vuruslar kelime kesmiyor")
        if tekrar_kare: parca.append("(KARE TEKRARI)")
        s.append(", ".join(parca))
    yaz("6 HIZ", ok, "[yavas cekim yalniz ara kareyle, kare tekrari yok] " + "; ".join(s))

    # 7 the recording's own audio, in sync, nothing added (Klip only; replaces 'source audio absent')
    s, ok = [], True
    for r in rp:
        if r.get("edit"):
            iyi, satir = ses_editli(r, klasor); ok &= iyi; s.append(satir); continue
        try:
            c = pcm(os.path.join(klasor, r["ad"] + ".mp4"))
            k = pcm(r["kaynak"], r["t0"], r["sure"], r["ses"].get("iz", 0))
            # decoding at a different sample rate shifts the audio by a few ms (resampler delay), and AAC adds
            # its own: search +-KAYMA_MS for the best match and report the shift. A shift under 20 ms (less than
            # one video frame) is in sync; beyond that the audio is out of sync and the check fails.
            kor, kay, maske = ses_esle(c, k, float(r["ses"].get("kazanc_db") or 0.0))
        except subprocess.CalledProcessError: kor, kay, maske = 0.0, 0, 0.0
        ok &= kor >= KOR; s.append(f"{r['ad']} korelasyon {kor:.4f} (kayma {kay * 1000 / SR:+.0f} ms"
                                   + (f", sinirlayici payi %{maske * 100:.0f} disarida" if maske else "") + ")")
    yaz("7 SES", ok, f"[Klip: ses kaydin kendi sesi, ayni saniyeler (kayma <= {KAYMA_MS} ms), esik {KOR}; diger tarzlardaki 'kaynak sesi yok' kontrolu "
        "bu tarzda uygulanmaz] " + "; ".join(s))

    # 8 overlays (Editli "cizim" + "soz"): below the camera band (never over the face), inside the 1080x1920 frame,
    # each said word turns yellow within SOZ_KILIT s of the moment it is heard (and the yellow is really on screen)
    s, ok = [], True
    for r in rp:
        ed = r.get("edit") or {}; dk = (r.get("duzen") or {}).get("dikis_px") or 0; fps = r.get("fps_cikti", 30)
        vs = [x for x in ed.get("vuruslar", []) if x["tur"] in ("cizim", "soz")]
        if not vs: s.append(f"{r['ad']} cizim/soz yok"); continue
        parca = []
        for x in vs:
            kut = [k_["kutu"] for k_ in x.get("kutular", [])] if x["tur"] == "cizim" else [x["kutu"]]
            kotu = [k_ for k_ in kut if k_[1] < dk or k_[0] < 0 or k_[2] > 1080 or k_[3] > 1920]
            if kotu: ok = False; parca.append(f"{x['tur']} @{x['ot']:.2f} {kotu[0]} kamera bandina ya da ekran disina tasiyor (TASMA)"); continue
            if x["tur"] == "cizim": parca.append(f"cizim @{x['ot']:.2f} {len(kut)} oge, hepsi y>={dk}"); continue
            sap, sari = [], 0
            for w in x["kel"]:
                es = [k_ for k_ in r["kelimeler"] if abs(k_["a_k"] - w["a"]) < 0.02]
                duy = es[0]["a"] if es else w["oa"]
                ilk = -(-round(w["oa"] * fps, 6) // 1) / fps          # first output frame that shows it yellow
                sap.append(max(abs(w["oa"] - duy), ilk - duy))
                o = os.path.join(klasor, r["ad"] + ".mp4"); x0, y0, x1, y1 = x["kutu"]
                b_ = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{(w['oa'] + w['ob']) / 2:.3f}", "-i", o, "-frames:v", "1",
                                     "-vf", f"crop={x1 - x0}:{y1 - y0}:{x0}:{y0}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
                F = np.frombuffer(b_, np.uint8).reshape(-1, 3).astype(int)
                sari += int(((F[:, 0] > 215) & (F[:, 1] > 175) & (F[:, 2] < 110)).sum() > 400)
            iyi = max(sap) <= SOZ_KILIT and sari == len(x["kel"]); ok &= iyi
            parca.append(f"soz '{x['metin']}' {len(x['kel'])} kelime, en buyuk kayma {max(sap):.3f} sn, sari gorulen {sari}/{len(x['kel'])}"
                         + ("" if iyi else " (KILIT YOK)"))
        s.append(f"{r['ad']} " + "; ".join(parca))
    yaz("8 BINDIRME", ok, f"[cizim/soz kamera bandinin altinda, ekran icinde; soz kelimesi duyuldugu andan <= {SOZ_KILIT} sn sonra sari] " + " | ".join(s))

    puansiz = [kl["ad"] for kl in plan["klipler"] if not isinstance(kl.get("puan"), (int, float))]
    if puansiz: print(f"UYARI: puan yok (1-10, panel klipleri puana gore siralar): {', '.join(puansiz)}")
    gec = bool(sonuc) and all(sonuc)
    print("SONUC:", "GECTI" if gec else "KALDI")
    return 0 if gec else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
