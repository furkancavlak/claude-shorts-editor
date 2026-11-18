"""sohbet.py - Klip style, second marker source: when the CHAT speeds up (17.11.2026).

Two ways in, both optional:
  a) a chat FILE with a time per message
       python kod/sohbet.py dosya <chat.txt|chat.json> [kayit_suresi_sn]
     - text: one message per line, starting with a time: "[01:02:03] ad: mesaj", "[12:30] ad: mesaj",
       "01:02:03 ad: mesaj" (brackets optional; h:mm:ss or mm:ss, decimals allowed)
     - JSON: a list of messages, or an object holding one ("comments", "messages", "chat", "data", ...).
       The time of a message is looked up in these fields (also one level down, e.g. TwitchDownloader's
       comments[].content_offset_seconds): content_offset_seconds, offset_seconds, offset, time_in_seconds,
       video_offset, seconds, saniye, time, timestamp, t, zaman. Numbers are seconds; "hh:mm:ss" text works.
       Nothing found -> a clear error naming the fields it looked for.
  b) chat VISIBLE in the recording: the chat box as a 0-1 rectangle of the frame
       python kod/sohbet.py ekran <kayit.mp4> x0,y0,x1,y1 [bas_sn sure_sn]
     ffmpeg crops that box (small, grey, 5 frames/s) and measures how much it changes each second; new lines
     scrolling in = change. Without a box this way does not run (the caller logs that and skips it).
     A chat that never stops scrolling cannot show a peak this way: three 2-minute samples are read first and, if
     they are saturated (doygun_mu), the whole recording is not read (bilgi["doygun"], bilgi["yontem"] says why).

Both give the same thing: a per-second activity curve, its 10-second window sum, the ratio ("kat") to the
recording's median 10-second window, and peaks (kat >= 2.5, at least 30 s apart).
Chat FILE only (we know the messages):
  - absolute floor: a peak needs at least ALT_5SN messages in some 5-second bucket inside it. A sparse chat
    (1 message per 10 s) makes "2.5 x the median" mean 3 messages, which is noise (17.11.2026: 105 fake peaks
    on a 1 h 54 min stream). If the chat never reaches the floor anywhere: no peaks, bilgi["seyrek"] = True.
  - reaction or not: the messages of the peak are sorted into "tepki" (KEKW, AHAHA, sjsj, oha, nasil ya, emoji
    rain, shouting, the same short message repeated) and "soru-istek" (abi, merhaba, gec, lutfen, questions,
    long and all different). puan = kat x 1.5 when most are reactions, x 0.5 when most are questions/requests.
    The word lists are TEPKI / ISTEK below, in one place. Check one message: python kod/sohbet.py tur "KEKW"
The screen way (b) has no message text or count: no floor, no reaction type (puan = kat). Output as JSON on stdout
with --json, otherwise a readable list. A chat peak shows the REACTION; the moment that caused it is usually
5-20 s before the peak.
"""
import json, re, subprocess, sys
import numpy as np

PENCERE, KAT_ESIK, ARA_SN = 10, 2.5, 30
ALT_5SN = 5                    # absolute floor: messages in one 5-second bucket (chat file only); change here

# ---- reaction vs question/request: the ONLY place these lists live (lower case, Turkish letters allowed) ----
TEPKI = [r"\bkekw\b", r"\blul\b", r"\bomegalul\b", r"\bpog", r"\blo+l\b", r"\bx+d+\b", r"\boha+\b", r"\bvay\b",
         r"yok art[ıi]k", r"nas[ıi]l ya", r"ne oldu", r"olamaz", r"efsane", r"g[üu]ld[üu]m", r"[şs]aka m[ıi]",
         r"ciddi m[ıi]", r"\bgg\b", r"\bwtf\b", r"(?:a?h[ae]){2,}", r"(?:he){3,}", r"helal", r"[öo]ld[üu]m",
         r"(?:sj){2,}", r"(?:ks){2,}", r"(?:kd){2,}", r"(?:hs){2,}", r"(?:js){2,}"]
ISTEK = [r"\babi\b", r"merhaba", r"\bselam", r"\bsa\b", r"\bslm\b", r"ho[şs] ?geldi", r"\bge[çc]\b", r"l[üu]tfen",
         r"\boyna", r"\bolsun\b", r"\bnaber\b", r"\?\s*$"]
UZUN_KELIME = 6                # a message this long (words) is talk, not a reaction
_TEPKI = [re.compile(x) for x in TEPKI]; _ISTEK = [re.compile(x) for x in ISTEK]


def mesaj_turu(m, ayni=1):
    """One chat message -> "tepki" | "soru-istek" | "": reaction words, emoji only, SHOUTING (all caps, short),
    keyboard mash (a long word with almost no vowels: sjsjsj, kdnskdnkd), or the same short message repeated
    in the window (ayni >= 2) count as a reaction; request words, a question, or a long message as talk."""
    t = (m or "").strip(); k = t.replace("İ", "i").replace("I", "ı").lower()
    if not t: return ""
    if any(r.search(k) for r in _TEPKI): return "tepki"
    harf = re.sub(r"[^a-zçğıöşü]", "", k)
    if not harf or re.fullmatch(r"(?::[a-z_\-]+:\s*)+", k): return "tepki"                 # emoji only / :shortcode:
    if any(len(w) >= 5 and sum(c in "aeıioöuü" for c in w) / len(w) < 0.2 for w in re.findall(r"[a-zçğıöşü]+", k)):
        return "tepki"                                                                     # keyboard mash
    kel = t.split()
    if len(kel) <= 3 and len(harf) >= 3 and t == t.upper() and t != t.lower(): return "tepki"   # SHOUTING
    if any(r.search(k) for r in _ISTEK): return "soru-istek"
    if ayni >= 2 and len(kel) <= 4: return "tepki"
    if len(kel) >= UZUN_KELIME: return "soru-istek"
    return ""


def patlama_turu(mesajlar):
    """Messages of one peak -> (tur, reaction ratio, question/request ratio, multiplier for puan)."""
    if not mesajlar: return "", 0.0, 0.0, 1.0
    nrm = [re.sub(r"\W+", " ", m.lower()).strip() for m in mesajlar]
    tur = [mesaj_turu(m, nrm.count(n)) for m, n in zip(mesajlar, nrm)]
    te, ist = tur.count("tepki") / len(tur), tur.count("soru-istek") / len(tur)
    if te >= 0.5: return "tepki", te, ist, 1.5
    if ist >= 0.5: return "soru-istek", te, ist, 0.5
    return "karisik", te, ist, 1.0
ZAMAN_ALANLARI = ["content_offset_seconds", "offset_seconds", "offset", "time_in_seconds", "video_offset",
                  "seconds", "saniye", "time", "timestamp", "t", "zaman"]
LISTE_ALANLARI = ["comments", "messages", "chat", "data", "mesajlar", "items"]


def saniye(x):
    """'1:02:03' / '12:30' / '750' / '750.5' / 750 -> seconds (float) or None."""
    if isinstance(x, (int, float)): return float(x)
    if not isinstance(x, str): return None
    s = x.strip().strip("[]()")
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{1,2}(?:[.,]\d+)?)", s)
    if m: return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + float(m.group(3).replace(",", "."))
    try: return float(s.replace(",", "."))
    except ValueError: return None


def _zaman_bul(msg):
    if not isinstance(msg, dict): return None
    for a in ZAMAN_ALANLARI:
        if a in msg and saniye(msg[a]) is not None and not isinstance(msg[a], bool):
            return saniye(msg[a])
    for v in msg.values():                         # one level down
        if isinstance(v, dict):
            for a in ZAMAN_ALANLARI:
                if a in v and saniye(v[a]) is not None: return saniye(v[a])
    return None


METIN_ALANLARI = ["mesaj", "message", "text", "body", "content", "msg", "icerik"]


def _metin_bul(msg):
    for a in METIN_ALANLARI:
        v = msg.get(a)
        if isinstance(v, str): return v
        if isinstance(v, dict):                      # TwitchDownloader: comments[].message.body
            for b in METIN_ALANLARI:
                if isinstance(v.get(b), str): return v[b]
    return ""


def dosya_oku(yol):
    """Chat file -> sorted list of message seconds. Raises ValueError with a plain message."""
    return [t for t, _ in dosya_mesajlar(yol)]


def dosya_mesajlar(yol):
    """Chat file -> sorted list of (second, message text). Raises ValueError with a plain message."""
    ham = open(yol, encoding="utf-8-sig", errors="replace").read()
    if ham.lstrip()[:1] in "[{":
        try: j = json.loads(ham)
        except json.JSONDecodeError: j = None
        if j is not None:
            liste = None
            if isinstance(j, list): liste = j
            else:
                for a in LISTE_ALANLARI:
                    if isinstance(j.get(a), list): liste = j[a]; break
                if liste is None:
                    liste = next((v for v in j.values() if isinstance(v, list) and v and isinstance(v[0], dict)), None)
            if not liste: raise ValueError("JSON'da mesaj listesi bulunamadı (aranan: " + ", ".join(LISTE_ALANLARI) + ")")
            t = [(z, _metin_bul(m) if isinstance(m, dict) else "") for m, z in ((m, _zaman_bul(m)) for m in liste) if z is not None]
            if not t:
                ornek = list(liste[0].keys())[:12] if isinstance(liste[0], dict) else type(liste[0]).__name__
                raise ValueError("JSON mesajlarında zaman alanı bulunamadı. Beklenen alanlardan biri: "
                                 + ", ".join(ZAMAN_ALANLARI) + f". İlk mesajdaki alanlar: {ornek}")
            return sorted(t, key=lambda x: x[0])
    t = []
    for satir in ham.splitlines():
        m = re.match(r"\s*\[?((?:\d+:)?\d{1,2}:\d{1,2}(?:[.,]\d+)?)\]?", satir)
        if m:
            geri = satir[m.end():].strip()
            ad_m = re.match(r"[^:\s][^:]{0,40}:\s?", geri)                  # "ad: mesaj" -> "mesaj"
            t.append((saniye(m.group(1)), geri[ad_m.end():] if ad_m else geri))
    if not t: raise ValueError("Sohbet dosyasında zamanlı satır yok. Beklenen: '[hh:mm:ss] ad: mesaj' ya da '[mm:ss] ad: mesaj', "
                               "veya mesaj başına zaman alanı olan JSON")
    return sorted(t, key=lambda x: x[0])


def ekran_olc(kayit, kutu, bas=None, sure=None, fps=5):
    """Chat box visible in the recording -> per-second change of that box (mean abs grey difference of
    consecutive frames, summed over the second). Returns (curve, start second)."""
    w, h = (int(x) for x in subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                                    "stream=width,height", "-of", "csv=p=0", kayit], text=True).strip().split(",")[:2])
    x0, y0 = int(kutu[0] * w) // 2 * 2, int(kutu[1] * h) // 2 * 2
    cw, ch = int((kutu[2] - kutu[0]) * w) // 2 * 2, int((kutu[3] - kutu[1]) * h) // 2 * 2
    ow = 96; oh = max(8, int(ow * ch / cw) // 2 * 2)
    a = ["ffmpeg", "-v", "error"] + (["-ss", f"{bas:.3f}"] if bas is not None else []) + ["-i", kayit] + \
        (["-t", f"{sure:.3f}"] if sure is not None else []) + \
        ["-an", "-vf", f"crop={cw}:{ch}:{x0}:{y0},fps={fps},scale={ow}:{oh},format=gray", "-f", "rawvideo", "-"]
    p = subprocess.Popen(a, stdout=subprocess.PIPE); n = ow * oh; onceki = None; fark = []
    while True:
        b = p.stdout.read(n)
        if len(b) < n: break
        f = np.frombuffer(b, np.uint8).astype(np.int16)
        fark.append(0.0 if onceki is None else float(np.abs(f - onceki).mean())); onceki = f
    p.wait()
    fark = np.array(fark); s = len(fark) // fps
    egri = fark[: s * fps].reshape(s, fps).sum(1)
    return egri, (bas or 0.0)


def tepeler(egri, bas=0.0, pencere=PENCERE, esik=KAT_ESIK, ara=ARA_SN, olcek=1.0):
    """Per-second activity -> peaks. Window sum over the NEXT `pencere` seconds is centred on its middle;
    kat = window / median window. A peak is the highest window in its +-ara neighbourhood with kat >= esik.
    Returns [{"t": second (recording time, middle of the busiest window), "kat", "deger"}], highest first."""
    egri = np.asarray(egri, float)
    if len(egri) < pencere * 2: return [], 0.0
    pen = np.convolve(egri, np.ones(pencere), "valid")          # pen[i] = sum of seconds i .. i+pencere-1
    med = float(np.median(pen)); taban = med if med > 0 else max(1e-9, float(pen.mean()) or 1.0)
    kat = pen / taban
    out = []
    for i in np.argsort(kat)[::-1]:
        if kat[i] < esik: break
        t = bas + i + pencere / 2
        if any(abs(t - o["t"]) < ara for o in out): continue
        out.append({"t": round(float(t), 1), "kat": round(float(kat[i]), 1), "deger": round(float(pen[i] * olcek), 1)})
    return out, taban


def dosya_tepeleri(yol, sure=None, alt=ALT_5SN):
    """Chat file -> peaks that pass the absolute floor, each with its reaction type and puan (highest puan first).
    bilgi["seyrek"] = True (and no peaks) when no 5-second bucket of the whole chat reaches `alt` messages."""
    ms = dosya_mesajlar(yol); t = [x[0] for x in ms]
    son = int(np.ceil(max(sure or 0, t[-1] + 1)))
    egri = np.bincount(np.clip(np.array(t, int), 0, son - 1), minlength=son).astype(float)
    bes = np.convolve(egri, np.ones(5), "valid") if len(egri) >= 5 else np.array([egri.sum()])   # 5-second buckets
    en5 = int(bes.max())
    tp, taban = tepeler(egri)
    bilgi = {"mesaj": len(t), "ortanca_10sn": round(taban, 1), "sure": son, "en_cok_5sn": en5, "alt_5sn": alt,
             "seyrek": en5 < alt, "ham_tepe": len(tp)}
    if bilgi["seyrek"]: return [], bilgi
    out = []
    for x in tp:
        i0 = max(0, int(round(x["t"] - PENCERE / 2)))              # the peak's 10-second window: seconds i0 .. i0+9
        m5 = int(bes[i0: i0 + PENCERE - 4].max(initial=0))
        if m5 < alt: continue
        x["mesaj"] = int(x.pop("deger")); x["en_cok_5sn"] = m5
        metin = [m for z, m in ms if i0 <= z < i0 + PENCERE]
        x["tur"], te, ist, carp = patlama_turu(metin)
        x["tepki_orani"], x["istek_orani"] = round(te, 2), round(ist, 2)
        x["puan"] = round(x["kat"] * carp, 1)
        x["ornek"] = [m.strip() for m in metin if m.strip()][:6]
        out.append(x)
    out.sort(key=lambda y: -y["puan"])
    return out, bilgi


DOYGUN_KAT, DOYGUN_SESSIZ, ORNEK_SN = 2.2, 0.15, 120   # a quiet chat is NOT saturated: it has many still seconds


def doygun_mu(kayit, kutu, sure):
    """A chat that scrolls all the time (or a moving overlay inside the box) changes every second: the screen way
    cannot tell a reaction from the usual flow (18.11.2026: 60 min read, 44 s of work, 0 peaks; the busiest 10 s were
    only 1.4-1.9x the median, and 0-6 % of the seconds were still). Three 2-minute samples (start, middle, end) decide first:
    saturated = in every sample the busiest window < DOYGUN_KAT x the median AND under DOYGUN_SESSIZ of its seconds
    are still. Returns (saturated?, the samples' numbers)."""
    ornek = []
    for bas in (0.05 * sure, 0.5 * sure - ORNEK_SN / 2, 0.95 * sure - ORNEK_SN):
        e, _ = ekran_olc(kayit, kutu, max(0.0, bas), ORNEK_SN)
        if len(e) < PENCERE * 2: return False, ornek
        pen = np.convolve(e, np.ones(PENCERE), "valid"); med = float(np.median(pen)) or 1e-9
        ornek.append({"bas": round(max(0.0, bas)), "en_yogun_kat": round(float(pen.max()) / med, 2),
                      "durgun_pay": round(float((e < 0.05 * np.percentile(e, 90)).mean()), 3)})
    return all(o["en_yogun_kat"] < DOYGUN_KAT and o["durgun_pay"] < DOYGUN_SESSIZ for o in ornek), ornek


def ekran_tepeleri(kayit, kutu, bas=None, sure=None):
    if bas is None and sure is None:                 # the whole recording: first ask whether the box can tell anything
        uzunluk = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                                 kayit], text=True).strip() or 0)
        if uzunluk >= 3 * ORNEK_SN * 2:
            doygun, ornek = doygun_mu(kayit, kutu, uzunluk)
            if doygun:
                return [], {"saniye": 3 * ORNEK_SN, "ortanca_10sn": None, "doygun": True, "ornek": ornek,
                            "yontem": "sohbet hep akıyor, ekrandan tepki ayırt edilemiyor: 3 örnekte en yoğun an olağanın "
                                      f"en çok {max(o['en_yogun_kat'] for o in ornek):.1f} katı; kaydın tamamı ölçülmedi. "
                                      "Tepki için sohbet dosyası ver"}
    egri, b = ekran_olc(kayit, kutu, bas, sure)
    tp, taban = tepeler(egri, b)
    for x in tp: x["degisim"] = x.pop("deger"); x["puan"] = x["kat"]
    return tp, {"saniye": len(egri), "ortanca_10sn": round(taban, 2)}


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--json"]; js = "--json" in sys.argv
    try:
        if a[0] == "dosya": tp, bilgi = dosya_tepeleri(a[1], float(a[2]) if len(a) > 2 else None)
        elif a[0] == "tur":                                      # one message: python kod/sohbet.py tur "KEKW"
            print(mesaj_turu(" ".join(a[1:])) or "(tarafsiz)"); sys.exit(0)
        elif a[0] == "ekran":
            tp, bilgi = ekran_tepeleri(a[1], [float(v) for v in a[2].split(",")],
                                       float(a[3]) if len(a) > 3 else None, float(a[4]) if len(a) > 4 else None)
        else: raise IndexError
    except IndexError: sys.exit(__doc__)
    except ValueError as e: sys.exit("HATA: " + str(e))
    if js: print(json.dumps({"tepeler": tp, "bilgi": bilgi}, ensure_ascii=False))
    else:
        print(f"bilgi: {bilgi}")
        if bilgi.get("seyrek"): print(f"  sohbet seyrek: 5 sn'de en cok {bilgi['en_cok_5sn']} mesaj (< {bilgi['alt_5sn']}), isaret kullanilmadi")
        for x in tp: print(f"  sohbet tepesi {int(x['t']) // 60}:{int(x['t']) % 60:02d} ({x['t']} sn)  kat {x['kat']}  "
                           + ", ".join(f"{k} {v}" for k, v in x.items() if k not in ("t", "kat", "ornek")))
