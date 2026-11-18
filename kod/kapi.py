"""kapi.py - gate: a Short that fails any check does not go out.

    python kapi.py <plan.json> <short.mp4>        (needs <short.mp4>.rapor.json and stems from motor.py)
    exit 0 = GECTI, 1 = KALDI

Checks
 1. KANIT     every sentence has a proof entry (source, seconds, region, what it shows) and the proof was on
              screen for every frame of that sentence.
 2. BUYUKLUK  the proof region, as displayed, is big enough on a phone. Threshold: shorter side >= 100 px
              of the 1080x1920 frame (on a ~6.5 cm wide phone screen that is ~6 mm) AND area >= 2.5 % of the
              frame, at the smallest moment of the sentence. For a quote-card proof ("alinti") the size is the
              type: quote >= 52 px, source line >= 40 px; the card must carry a source line (check 1) and be
              fully on screen for every frame of the sentence. In a sentence with a sketch on the footage the
              card is a one-line source strip (motor.kart_bicimi): the sketch tells the fact, the strip says where
              it is from; it counts as proof only with that sketch (check 1) and its line must be >= 46 px.
 3. SON       the last sentence is neither a call to action nor generic praise; no sentence is a call to action.
 4. KAYNAK SESI  (Karşılaştırma / Liste / Tek bilgi only; a Klip plan - "tarz": "klip" - goes to klip_kapi.py,
              where the recording's own audio is the soundtrack) sources contribute no sound: the Short's audio must match the engine's own mix
              (voice + self-made bed) - correlation >= 0.97 - and the engine never maps a source audio stream.
              Stem levels (ffmpeg volumedetect) are printed.
 5. KANCA     speech starts within 0.5 s (word timing and measured audio energy), the first caption is on
              screen within 0.5 s and the first frame is not black.
 6. DONUK     frozen picture (no panel advancing in its source) is at most 15 % of the runtime.
 7. MADDE     every list item (sentence with "madde": true) shows at least 1.5 s of moving picture.
 8. HIZ       no judder: a shot slower than normal (0 < hiz < 1) must say "ara_kare": true in the plan AND the
              render must have used in-between frames (report "yontem": "ara_kare"); no moving shot may show the
              same source frame twice in a row (report "tekrar_kare" = 0). hiz 0 is a still (check 6 counts it).
              A render made before 17.11 has no "yontem" in its report: it repeated frames, so it fails here.
 9. CIZIM     (only when the plan has sketches, "cizim" in a sentence) every sketch was drawn on every frame from its
              start to the end of its sentence; its recipe passes cizim.dogrula without HATA; a sketch that replaces
              the footage ("kip": "ara") carries a source line (that line is the proof, check 1 counts it); the hook
              sketch ("giris") sits in sentence 1 only. No sketch in the plan = passes ("kontrol uygulanmadi").
"""
import json, os, re, subprocess, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor import kanit_hatalari, norm  # noqa: E402

KISA_KENAR, ALAN = 100, 0.025
ALINTI_PX, KAYNAK_PX = 52, 40   # quote card font sizes (px of 1080 wide): ~3 mm / ~2.4 mm on a 6.5 cm wide phone
SERIT_PX = 46                    # source strip next to a sketch: it is the only text of the proof, so bigger (17.11 v3)
DONUK_ORAN, MADDE_SN = 0.15, 1.5
CAGRI = r"(abone|beğen|begen|like|subscribe|yorum|comment|takip|follow|paylaş|paylas|share|kaydet|zil|bildirim|link|" \
        r"profil|kanal[ıi]ma|unutma|izlemeye devam|part ?2|devam[ıi] gel|sonraki b[oö]l[uü]m)"
OVGU = r"(inan[ıi]lmaz|m[uü]kemmel|harika|efsane|[cç]ılg[ıi]n|olay|muhte[sş]em|detayc[ıi]|d[uü][sş][uü]nm[uü][sş]|" \
       r"bayıl|şaheser|saheser|amazing|insane|incredible|crazy|masterpiece|rockstar yine)"
SR = 16000


def pcm(yol):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", yol, "-vn", "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def volumedetect(yol):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", yol, "-af", "volumedetect", "-vn", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: ([-\d.]+) dB", e); x = re.search(r"max_volume: ([-\d.]+) dB", e)
    return (float(m.group(1)) if m else None, float(x.group(1)) if x else None)


def main(plan_yolu, video):
    plan = json.load(open(plan_yolu, encoding="utf-8"))
    if plan.get("tarz") == "klip":
        # Klip style: the soundtrack IS the recording's own audio, so check 4 (source audio absent) does not apply;
        # its own gate (klip_kapi.py) checks start/end on speech, captions vs transcript, length, rectangles, speed
        # and that the audio is the recording's, in sync. Second argument = the folder holding the clips.
        import klip_kapi
        return klip_kapi.main(plan_yolu, video)
    rp = json.load(open(video + ".rapor.json", encoding="utf-8"))
    plan["_kok"] = os.path.dirname(os.path.abspath(plan_yolu))      # sketch recipes are relative to the plan
    sonuc = []

    def yaz(ad, ok, ayrinti): sonuc.append((ad, ok)); print(f"[{'GECTI' if ok else 'KALDI'}] {ad}: {ayrinti}")

    # 1 proof per sentence, on screen the whole sentence (a sketch that replaces the footage: its source line, every frame)
    err = kanit_hatalari(plan)
    ara = lambda i: i < len(plan["cumleler"]) and (plan["cumleler"][i].get("cizim") or {}).get("kip") == "ara"
    eksik = [f"cumle {i + 1}" for i, c in enumerate(rp["cumleler"]) if not ara(i) and (any(k["kare"] < c["kare"] for k in c["kanit"]) or not c["kanit"])]
    eksik += [f"cumle {i + 1} cizim+kaynak satiri" for i, c in enumerate(rp["cumleler"])
              if ara(i) and (c.get("cizim", {}).get("kare", 0) < c["kare"] or not c.get("cizim", {}).get("kaynak"))]
    # a quote card is only proof together with where it was said: source line in the plan AND drawn every frame
    for i, (pc, rc) in enumerate(zip(plan["cumleler"], rp["cumleler"])):
        for j, kn in enumerate([] if ara(i) else pc.get("kanit", [])):      # footage replaced by a sketch: no card drawn
            if not kn.get("alinti"): continue
            ra = rc["kanit"][j].get("alinti") if j < len(rc["kanit"]) else None
            if not ra or ra["kare"] < rc["kare"] or not ra.get("ekranda"): eksik.append(f"cumle {i + 1} alinti karti")
            elif ra.get("kaynak_satiri", "").strip() != str(kn["alinti"].get("kaynak_satiri", "")).strip():
                err.append(f"cumle {i + 1}: kartta cizilen kaynak satiri plandakiyle ayni degil")
            # a source strip (one line instead of the card) is proof only together with the sketch that tells the fact
            elif ra.get("bicim") == "serit" and not (rc.get("cizim") or {}).get("kare"):
                err.append(f"cumle {i + 1}: kaynak seridi var ama cumlede cizim yok (serit yalniz cizimle kanit sayilir)")
    if len(rp["cumleler"]) != len(plan["cumleler"]): err.append("rapor ile plan cumle sayisi farkli (eski render?)")
    yaz("1 KANIT", not err and not eksik, "; ".join(err + [f"{e}: kanit her karede yok" for e in eksik]) or
        f"{len(plan['cumleler'])} cumlenin hepsinde kanit var ve cumle boyunca ekranda")

    # 2 size on a phone
    kotu, satir = [], []
    for i, c in enumerate(rp["cumleler"]):
        for k in c["kanit"]:
            if k.get("alinti", {}).get("bicim") == "serit":   # sketch + one source line: the line must be readable
                a = k["alinti"]
                satir.append(f"c{i + 1}/kaynak seridi {a['kaynak_px']}px (H {a['kaynak_buyuk_harf_px']}px), {a['satir']['kaynak']} satir")
                if a["kaynak_px"] < SERIT_PX: kotu.append(satir[-1])
                continue
            if k.get("alinti"):   # proof = the typeset quote; the footage behind it is background, not proof
                a = k["alinti"]
                satir.append(f"c{i + 1}/alinti yazi {a['metin_px']}px (H {a['metin_buyuk_harf_px']}px), "
                             f"kaynak satiri {a['kaynak_px']}px (H {a['kaynak_buyuk_harf_px']}px)")
                if a["metin_px"] < ALINTI_PX or a["kaynak_px"] < KAYNAK_PX: kotu.append(satir[-1])
                continue
            satir.append(f"c{i + 1}/{k['kaynak']} {k['min_kisa_kenar']:.0f}px %{k['min_alan_orani'] * 100:.1f}")
            if k["min_kisa_kenar"] < KISA_KENAR or k["min_alan_orani"] < ALAN: kotu.append(satir[-1])
        for ad, kk in c.get("isaret", {}).items():   # a framed detail inside the proof: same short-side threshold
            satir.append(f"c{i + 1}/{ad} {kk:.0f}px")
            if kk < KISA_KENAR: kotu.append(satir[-1])
    yaz("2 BUYUKLUK", not kotu, (f"kucuk: {', '.join(kotu)}" if kotu else "hepsi esigin ustunde")
        + f"  [esik kisa kenar>={KISA_KENAR}px ve alan>=%{ALAN * 100:.1f}; alinti>={ALINTI_PX}px, kaynak>={KAYNAK_PX}px, kaynak seridi>={SERIT_PX}px]  "
        + " | ".join(satir))

    # 3 ending
    son = plan["cumleler"][-1]["metin"]
    cagri = [c["metin"] for c in plan["cumleler"] if re.search(CAGRI, c["metin"].lower())]
    ovgu = re.search(OVGU, son.lower())
    yaz("3 SON", not cagri and not ovgu,
        (f"cagri: {cagri} " if cagri else "") + (f"son cumlede genel ovgu: '{ovgu.group(0)}' " if ovgu else "")
        + f"son cumle: '{son}'")

    # 4 no source audio
    # stems are written next to the Short; the path in the report is relative to where motor.py ran, so fall back
    # to the Short's own folder when kapi.py runs from somewhere else
    st = {a: (y if os.path.isfile(y) else os.path.join(os.path.dirname(os.path.abspath(video)), os.path.basename(y)))
          for a, y in rp["stemler"].items()}
    cikis = pcm(video); mix = pcm(st["mix"])
    n = min(len(cikis), len(mix)); a, b = cikis[:n], mix[:n]
    kor = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    fark_db = 20 * np.log10(np.sqrt(((a - b) ** 2).mean()) / (np.sqrt((b ** 2).mean()) + 1e-12) + 1e-12)
    kaynak_ses = []
    for ad, k in rp["kaynaklar"].items():
        o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
                            k["dosya"]], capture_output=True, text=True).stdout.split()
        kaynak_ses.append(f"{ad}: {len(o)} ses akisi (motor okumaz, -an)")
    vd = {ad: volumedetect(st[ad]) for ad in ("ses", "muzik", "mix")}
    yaz("4 KAYNAK SESI", kor >= 0.97,
        f"cikti sesi = motorun kendi karisimi: korelasyon {kor:.4f}, fark {fark_db:.1f} dB (AAC kaybi); "
        + "; ".join(kaynak_ses) + "; volumedetect ortalama/tepe dB: "
        + ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in vd.items()))

    # 5 hook in the first half second
    w = int(0.02 * SR); x = cikis[: SR]; nn = len(x) // w
    rms = 20 * np.log10(np.sqrt((x[: nn * w].reshape(nn, w) ** 2).mean(1)) + 1e-9)
    ses_on = st["ses"]; v = pcm(ses_on)[: SR]; vr = 20 * np.log10(np.sqrt((v[: nn * w].reshape(nn, w) ** 2).mean(1)) + 1e-9)
    ses_bas = next((i * 0.02 for i, r in enumerate(vr) if r > -35), 9)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-frames:v", "1", "-vf", "scale=108:192", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True).stdout
    parlak = float(np.frombuffer(raw, np.uint8).mean())
    ilk_yazi = rp.get("ilk_yazi", 9)
    ok = rp["ilk_kelime"] <= 0.5 and ses_bas <= 0.5 and ilk_yazi <= 0.5 and parlak > 20
    yaz("5 KANCA", ok, f"ilk kelime {rp['ilk_kelime']:.2f} sn, ses enerjisi {ses_bas:.2f} sn, ilk yazi {ilk_yazi:.2f} sn, "
        f"ilk kare parlaklik {parlak:.0f}/255")

    # 6 frozen picture: share of runtime where no panel advances (fail above 15 %); every list item >= 1.5 s in motion
    FPS = 30
    toplam = sum(c["kare"] for c in rp["cumleler"]); donuk = sum(c.get("donuk_kare", 0) for c in rp["cumleler"])
    oran = donuk / max(1, toplam)
    yaz("6 DONUK", oran <= DONUK_ORAN, f"donuk kare payi %{oran * 100:.1f} (esik %{DONUK_ORAN * 100:.0f}); " +
        ", ".join(f"c{i + 1} {c.get('donuk_kare', 0) / FPS:.2f} sn" for i, c in enumerate(rp["cumleler"]) if c.get("donuk_kare")))
    kisa = []
    for i, c in enumerate(rp["cumleler"]):
        if c.get("madde"):
            hs = (c["kare"] - c.get("donuk_kare", 0)) / FPS
            if hs < MADDE_SN: kisa.append(f"c{i + 1} {hs:.2f} sn")
    maddeler = [f"c{i + 1} {(c['kare'] - c.get('donuk_kare', 0)) / FPS:.2f} sn" for i, c in enumerate(rp["cumleler"]) if c.get("madde")]
    yaz("7 MADDE HAREKETI", not kisa, (f"kisa: {kisa} " if kisa else "") + f"[esik {MADDE_SN} sn hareketli] " + ", ".join(maddeler)
        if maddeler else "liste maddesi yok (kontrol uygulanmadi)")

    # 8 speed: slowed shots only with generated in-between frames, never repeated frames
    hata, satir = [], []
    for i, (pc, rc) in enumerate(zip(plan["cumleler"], rp["cumleler"])):
        for j, kn in enumerate([] if ara(i) else pc.get("kanit", [])):
            hiz = kn.get("hiz", 1.0); r = rc["kanit"][j] if j < len(rc["kanit"]) else {}
            yon = r.get("yontem")
            satir.append(f"c{i + 1} {hiz:g}x {yon or 'eski render'}" + (f" tekrar {r['tekrar_kare']}" if r.get("tekrar_kare") else ""))
            if 0 < hiz < 1 and not kn.get("ara_kare"):
                hata.append(f"c{i + 1}: hiz {hiz:g} normalden yavas ama planda \"ara_kare\": true yok")
            if 0 < hiz < 1 and yon != "ara_kare":
                hata.append(f"c{i + 1}: yavas cekim ara kare uretilmeden render edilmis ({yon or 'eski motor: kare tekrari'})")
            if r.get("tekrar_kare", 0) > 0:
                hata.append(f"c{i + 1}: {r['tekrar_kare']} kare tekrari (ayni kaynak karesi art arda)")
    yaz("8 HIZ", not hata, ("; ".join(hata) + "  ") * bool(hata) + "[yavas = ara kare zorunlu, kare tekrari yok] " + ", ".join(satir))

    # 9 sketches: drawn every frame from their start to the end of the sentence, recipe clean, right mode in the right place
    from motor import cizim_hatalari
    hata, satir = list(cizim_hatalari(plan)), []
    for i, (pc, rc) in enumerate(zip(plan["cumleler"], rp["cumleler"])):
        if not pc.get("cizim"): continue
        r = rc.get("cizim")
        if not r: hata.append(f"c{i + 1}: planda cizim var, raporda yok (eski motor?)"); continue
        satir.append(f"c{i + 1} {r['kip']} {r['kare']}/{r['beklenen']} kare" + (" kaynak satiri var" if r.get("kaynak") else ""))
        if r["kare"] < r["beklenen"]: hata.append(f"c{i + 1}: cizim {r['beklenen']} karenin {r['kare']}'inde var")
    yaz("9 CIZIM", not hata, (("; ".join(hata) + "  ") if hata else "") + (", ".join(satir) if satir else "cizim yok (kontrol uygulanmadi)"))

    gec = all(o for _, o in sonuc)
    print("SONUC:", "GECTI" if gec else "KALDI")
    return 0 if gec else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
