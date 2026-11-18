"""klip_bul.py - Klip style, step 2: candidate moments for the model to read (it does NOT choose the clips).

    py -3 kod/klip_bul.py <yazi_klasoru> [adet] [--anlar anlar.txt] [--sohbet sohbet.txt|.json] [--kutu x0,y0,x1,y1]
                          [--kamera x0,y0,x1,y1 | --kamera yok]
    py -3 kod/klip_bul.py --help
      (yazi_klasoru = where ses_yazi.py --uzun wrote yazi.json, enerji.json)
      -> <yazi_klasoru>/adaylar.md      user moments (if given), candidates best first with WHY, map of the recording
      -> <yazi_klasoru>/adaylar.json    the candidates as data (best first)
      -> <yazi_klasoru>/isaretler.json  {"anlar": [...], "ses_tepesi": [...], "sohbet_tepesi": [...], "gunluk": [...]}
      -> <yazi_klasoru>/yazi.txt        the whole transcript, one Whisper sentence per line with its seconds

--anlar   the user's own moments, one per line: "12:30-13:05" (a range: cut exactly that, only snapped to the
          nearest sentence boundaries) or "12:30" (a point: the model builds a 15-45 s window that contains it).
          With moments given the model does NOT choose moments. Times: h:mm:ss, mm:ss or seconds.
--sohbet  chat file (see sohbet.py): its peaks are listed as "sohbet tepesi" and lift the candidate before them.
--kutu    chat box visible in the recording (0-1 of the frame): its change peaks are listed as "sohbet tepesi (ekran)".
--kamera  the streamer camera box (0-1). Not given: ../kamera/kamera.json next to the yazi folder, else the box is
          found here (kamera_bul.bul, nothing written). "--kamera yok" = no camera: the face check is skipped.

How a candidate is made (v2, 18.11.2026; v1 ranked by loudness alone and put the channel intro second):
every window of whole Whisper sentences 15-45 s long is scored, then the best windows that do not overlap are kept.
  ses      how much louder the loudest 2 s are than the recording's usual level around it (2-minute rolling
           median): (dB - 6) / 3, at most 6 points
  icerik   what is SAID (word lists below, one place): reaction words (lan, oha, noldu, yok artik, elongated
           "laaan"), laughter, a question answered within 4 s, oath/emphasis (yemin ederim, vallahi), story
           markers (bir sey soyleyecegim, fark ettim, cunku, mesela), talking to chat (chat, goruyor musunuz),
           long sentences (8+ words), a phrase repeated (biz seni hak etmedik x3). Diminishing: 8 * (1 - e^(-x/8)),
           thinned for windows over 30 s; plus up to 2 for dense talk (words per second over 1.2).
  yapi     the peak (loudest / most reactive sentence) 25-85 % into the window: +1 (the cause comes BEFORE the
           reaction, so the window grows back toward it); a window that opens ON a loud reaction: -0.8, unless a
           pause comes before it (then the silent event can be taken with the clip's on_pay, see klip.py).
  ceza     call to action or channel greeting (abone ol, begenmeyi unutma, merhabalar, kanalimdan): -3 each;
           in the first 90 s, or 2+ of them = the channel intro/outro, dropped. Long silence (talk under 35 %
           of the window), mostly short lines with no signal, shorter than 20 s / longer than 40 s, a dangling
           start (ve, ama, cunku...): small minus. No face in the camera box in most sampled frames (empty
           chair): -5, flagged.
  sohbet   a chat peak 3-12 s after the window starts and before it ends + 12 s: +2.
Language (yazi.json "dil", from ses_yazi.py --dil; missing = tr): the word lists and the Turkish rules (tepki/yemin/
anlati/hitap/cagri lists, dangling start, Turkish question words and endings, filler, 2-word repeats) are for Turkish
only. In any other language they are OFF, not guessed: what stays is ses, yapi, sohbet, the face check and the signs
that need no language (! and ?, stretched letters, laughter like haha/lol, 8+ word sentences, words per second, the
same short line twice). No intro/call is dropped then. adaylar.md says so at the top.
A window must end where the next word starts >= 0.1 s later (else the gate fails "KELIME ICINDE KESIYOR").
Number of candidates grows with the recording: max(9, 4 x adet, minutes / 3), at most 60.
Scores are hints: the model reads the text and keeps only moments that stand alone.
"""
import json, math, os, re, sys
import numpy as np

KOK = os.path.dirname(os.path.abspath(__file__))
MIN_SN, MAX_SN, HEDEF_SN = 15.0, 45.0, 30.0
ONCE_MIN, ONCE_MAX, SONRA_MIN, SONRA_MAX = 20.0, 25.0, 8.0, 10.0   # chat window around the peak
BIRLESIK_SN = 20.0                                                  # loud sentence and chat peak this close = same moment
GIRIS_SN = 90.0                                                     # a greeting / call in the first 90 s = channel intro
YUZ_CEZA = 5.0                                                      # no face in any sampled frame of the camera box
SUPHELI_P = 0.45                                                    # Whisper word probability under this = listed as doubtful
_PENCERELER = None                                                  # last scored windows (for a diagnosis by hand)

# ---- what is said: the ONLY place these lists live (lower case, Turkish letters; matched on one sentence) ----
TEPKI = [r"\blan\b", r"\boha+\b", r"\bvay\b", r"\bvo+v\b", r"yok art[ıi]k", r"nas[ıi]l ya\b", r"\bn[ae]? ?oldu\b",
         r"\bolamaz\b", r"inan[ıi]lm[ıi]yor|inan[ıi]lmaz", r"\bhelal\b", r"\ballah[ıi]m\b", r"\bşaka m[ıi]", r"ciddi m[ıi]",
         r"\bwtf\b", r"\bomg\b", r"\befsane\b", r"\bnas[ıi]l (?:yani|olur|olabilir)", r"\bne(?:\s+ya)?\s*\?", r"\bay+\b"]
KAHKAHA = [r"\b(?:a?ha){2,}h?\b", r"\b(?:he){3,}\b", r"\bkahkaha", r"(?:sj|js|ks|kd){3,}", r"\bx+d+\b", r"\blo+l\b"]
YEMIN = [r"yemin eder", r"\bvallah", r"\bbillah", r"\bharbi(?:den)?\b", r"ciddi anlamda", r"\bger[çc]ekten\b", r"\bciddiyim\b"]
ANLATI = [r"bir şey (?:söyle|diy|anlat|fark)", r"fark ett", r"biliyor mu(?:sun|sunuz)?\b", r"düşün(?:sene|ün)\b", r"\bhikaye",
          r"anlatay[ıi]m", r"\bo y[üu]zden\b", r"\bçünkü\b", r"\bmesela\b", r"\basl[ıi]nda\b", r"\bbence\b",
          r"\bilk (?:defa|kez)\b", r"hayat[ıi]mda", r"geçen (?:gün|hafta|sefer)", r"bir keresinde", r"\bdedi(?:m)? ki\b"]
HITAP = [r"\bchat\b", r"\bçet\b", r"görüyor mu(?:sunuz|sun)?\b", r"görüyor(?:sunuz|sun) mu\b", r"gördünüz m[üu]", r"\bbak[ıi]n\b", r"\bizleyin\b", r"\bbeyler\b"]
CAGRI = [r"abone (?:ol|değil)", r"beğen(?:meyi|iniz|ip|in)\b", r"\blike\b", r"dislike", r"yorum (?:at|yap|yaz)", r"takip (?:et|edin)",
         r"\bkanal(?:ıma|ımıza|ımdan|ından)\b", r"bildirim", r"\bunutma(?:y[ıi]n)?\b", r"karşınızday", r"merhabalar",
         r"hoş ?geldiniz", r"\bkick\b|kik\.com|twitch\.tv|\bslash\b"]
SARKIK = re.compile(r"^(?:ve|ama|da|de|yani|çünkü|o yüzden|onun için|zaten)\b")       # a start that hangs on the line before
SORU_SON = re.compile(r"(?:\?|\bm[ıiuü](?:s[ıiuü]n(?:[ıiuü]z)?|y[ıiuü][mz])?)\s*[.!…]*$")
SORU_BAS = re.compile(r"^(?:ne|neden|niye|nas[ıi]l|kim|nerede|nereye|hangi|noldu|napt[ıi]n|nap[ıi]yorsun)\b")
UZAT = re.compile(r"([a-zçğıöşü])\1\1")                                              # "laaaan", "oooo"
DOLGU = set("şey kanka yani şimdi abi bir bu şu o ben sen biz siz ya da de ne mi mı mu mü var yok değil gibi daha çok "
            "için olum oğlum lan ve ama bak hadi tamam evet hayır kadar diye gel git".split())
_R = {ad: [re.compile(x) for x in L] for ad, L in
      (("tepki", TEPKI), ("kahkaha", KAHKAHA), ("yemin", YEMIN), ("anlati", ANLATI), ("hitap", HITAP), ("cagri", CAGRI))}
AGIRLIK = {"tepki": 1.0, "kahkaha": 1.5, "soru_cevap": 0.8, "yemin": 0.8, "anlati": 1.0, "hitap": 0.8, "uzun": 0.5, "tekrar": 0.7}
TAVAN = {"tepki": 4, "kahkaha": 2, "soru_cevap": 3, "yemin": 2, "anlati": 3, "hitap": 2, "uzun": 4, "tekrar": 3}
ADLAR = {"tepki": "tepki", "kahkaha": "kahkaha", "soru_cevap": "soru-cevap", "yemin": "yemin/vurgu", "anlati": "anlatı",
         "hitap": "sohbete hitap", "uzun": "uzun cümle", "tekrar": "tekrar"}


def mmss(t): t = int(t); return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def kucuk(t): return t.replace("İ", "i").replace("I", "ı").lower()


_SOZCUK = {True: re.compile(r"[0-9a-zçğıöşü]+"), False: re.compile(r"[^\W_]+")}


def sozcukler(t, tr=True): return _SOZCUK[tr].findall(kucuk(t) if tr else t.lower())


def turkce_mi(yz): return (yz.get("dil") or "tr") == "tr"      # an old yazi.json has no "dil": Turkish, as before


def cumle_sinyal(metin, tr=True):
    """One Whisper sentence -> counts of the content signals (see the word lists above). tr=False: only the signs
    that need no language (! ?, stretched letters, laughter, long sentence); the Turkish lists count 0."""
    k = (kucuk(metin) if tr else metin.lower()).strip(); say = lambda ad: sum(1 for r in _R[ad] if r.search(k)) if tr or ad == "kahkaha" else 0
    return {"tepki": min(2, say("tepki") + (1 if UZAT.search(k) else 0) + (1 if "!" in metin else 0)),
            "kahkaha": 1 if say("kahkaha") else 0, "yemin": 1 if say("yemin") else 0, "anlati": min(2, say("anlati")),
            "hitap": 1 if say("hitap") else 0, "cagri": 1 if say("cagri") else 0,
            "soru": 1 if ((SORU_SON.search(k) or SORU_BAS.search(k)) if tr else "?" in metin) else 0,
            "sarkik": 1 if tr and SARKIK.search(k) else 0,
            "uzun": 1 if len(metin.split()) >= 8 else 0}


def supheli_kelimeler(kel, a, b, en_cok=8, tr=True):
    """Words Whisper was least sure of between a and b (probability < SUPHELI_P), least sure first. Filler, 1-2 letter
    words, laughter and stretched reactions are left out: what remains is where names and game words go wrong."""
    out = {}
    for k in kel:
        if k[1] < a - 0.01 or k[2] > b + 0.01 or len(k) < 4 or k[3] >= SUPHELI_P: continue
        w = sozcukler(k[0], tr)
        if not w or len(w[0]) < 3 or w[0] in DOLGU or UZAT.search(w[0]) or any(r.search(w[0]) for r in _R["kahkaha"]): continue
        if any(r.search(w[0]) for r in _R["tepki"]): continue
        out[k[0]] = min(out.get(k[0], 1.0), k[3])
    return [w for w, _ in sorted(out.items(), key=lambda x: x[1])][:en_cok]


def yukseklik(en):
    """enerji.json -> dB above the usual level (2-second loudness minus a 2-minute rolling median), per step."""
    adim = en["adim"]; db = np.array(en["db"])
    k2 = max(1, int(2 / adim))
    yuk = np.convolve(db, np.ones(k2) / k2, "same")
    pen = int(120 / adim); med = np.empty_like(yuk)
    for i in range(0, len(yuk), int(5 / adim)):                          # rolling median, every 5 s
        a, b = max(0, i - pen // 2), min(len(yuk), i + pen // 2)
        med[i: i + int(5 / adim)] = np.median(yuk[a:b])
    return yuk - med, adim


def kamera_kutusu(klasor, yz, kamera_arg, gunluk):
    """The camera box for the face check: --kamera, else ../kamera/kamera.json, else found here (nothing written)."""
    if kamera_arg == "yok": gunluk.append("kamera yok dendi: yüz kontrolü yapılmadı"); return None
    if kamera_arg: return [float(v) for v in kamera_arg.split(",")]
    kj = os.path.join(os.path.dirname(os.path.abspath(klasor)), "kamera", "kamera.json")
    if os.path.isfile(kj):
        k = json.load(open(kj, encoding="utf-8")).get("kamera")
        if k: return k
        gunluk.append("kamera/kamera.json kutu bulamamış: yüz kontrolü yapılmadı"); return None
    try:
        import kamera_bul
        k = kamera_bul.bul(yz["kaynak"])[0].get("kamera")
        gunluk.append("kamera kutusu bu adımda önerildi (doğrulanmadı)" if k else "kamera kutusu bulunamadı: yüz kontrolü yapılmadı")
        return k
    except Exception as e:                                               # never stop the job for the face check
        gunluk.append(f"kamera aranamadı ({type(e).__name__}): yüz kontrolü yapılmadı"); return None


def aday_sayisi(sure_sn, adet): return int(min(60, max(9, 4 * adet, round(sure_sn / 60 / 3))))


def adaylari_bul(yz, hey, adim, adet, sohbet_t=(), kamera=None, gunluk=None):
    """Score every 15-45 s window of whole sentences, keep the best that do not overlap. Returns (candidates, dropped)."""
    cum = [c for c in yz["cumleler"] if c[2] > c[1] or c[0].strip()]
    kel = yz["kelimeler"]; n = len(cum); tr = turkce_mi(yz)
    A = np.array([c[1] for c in cum]); B = np.array([c[2] for c in cum])
    sig = [cumle_sinyal(c[0], tr) for c in cum]
    tepe = np.zeros(n)
    for i, c in enumerate(cum):
        a, b = int(c[1] / adim), max(int(c[1] / adim) + 1, int(c[2] / adim))
        tepe[i] = float(hey[a:b].max()) if b <= len(hey) and a < b else 0.0
    ses_p = np.clip((tepe - 6) / 3, 0, 6)
    # gap to the word before / after each sentence (a clean start or end needs a pause)
    kb = np.array([k[1] for k in kel]); ke = np.array([k[2] for k in kel])
    j_son = np.searchsorted(kb, B - 1e-3, side="right")                  # first word starting at/after the sentence end
    sonra_bosluk = np.where(j_son < len(kb), kb[np.minimum(j_son, len(kb) - 1)] - B, 99.0)
    j_bas = np.searchsorted(ke, A + 1e-3, side="left") - 1               # last word ending at/before the sentence start
    once_bosluk = np.where(j_bas >= 0, A - ke[np.maximum(j_bas, 0)], 99.0)
    # prefix sums of the additive signals
    def onek(v): return np.concatenate([[0.0], np.cumsum(v)])
    P = {ad: onek([s[ad] for s in sig]) for ad in ("tepki", "kahkaha", "yemin", "anlati", "hitap", "cagri", "uzun")}
    sc = [1 if sig[i]["soru"] and i + 1 < n and not sig[i + 1]["soru"] and A[i + 1] - B[i] < 4 else 0 for i in range(n)]
    P["soru_cevap"] = onek(sc)
    P["konusma"] = onek(B - A)
    bos = [1 if len(cum[i][0].split()) <= 3 and not (sig[i]["tepki"] or sig[i]["kahkaha"] or sig[i]["soru"]) else 0 for i in range(n)]
    P["bos"] = onek(bos)
    tepe_puan = ses_p + np.array([s["tepki"] + 1.5 * s["kahkaha"] for s in sig])
    soz = [sozcukler(c[0], tr) for c in cum]
    # 2-word repeats need the Turkish filler list (else "of the", "you know" would count): off in another language
    ikili = [set(bg for bg in zip(w, w[1:]) if not all(x in DOLGU for x in bg)) if tr else set() for w in soz]
    P["kelime"] = onek([len(w) for w in soz])
    sohbet_t = sorted(sohbet_t)

    def tekrar(i, j):
        """Phrases said again inside the window: a 2-word phrase (not only filler) in 2+ sentences, or the same
        short line twice in a row (Noldu / Noldu)."""
        gor, say = {}, 0
        for k in range(i, j + 1):
            for bg in ikili[k]: gor[bg] = gor.get(bg, 0) + 1
            if k > i and soz[k] and soz[k] == soz[k - 1] and len(soz[k]) <= 3: say += 1
        return say + sum(1 for v in gor.values() if v >= 2)

    def puanla(i, j):
        a, b = A[i], B[j]; L = b - a
        top = lambda ad: P[ad][j + 1] - P[ad][i]
        say = {ad: top(ad) for ad in ("tepki", "kahkaha", "yemin", "anlati", "hitap", "uzun")}
        say["soru_cevap"] = P["soru_cevap"][j] - P["soru_cevap"][i]          # the answer must be inside too
        say["tekrar"] = tekrar(i, j)
        ham = sum(AGIRLIK[ad] * min(TAVAN[ad], v) for ad, v in say.items()) * min(1.0, 30.0 / L) ** 0.5
        icerik = 8 * (1 - math.exp(-ham / 8))
        hiz = top("kelime") / L                                           # words per second: a Sade clip is talk
        icerik += float(np.clip((hiz - 1.2) * 2, 0, 2))
        ses = float(ses_p[i: j + 1].max())
        pk = i + int(np.argmax(tepe_puan[i: j + 1])); konum = (A[pk] - a) / L
        # a window that opens ON a loud reaction lost its cause; unless a pause comes before it: then the silent
        # picture before the first word (the event itself) is taken with on_pay (klip.py, up to 3 s)
        yapi = 1.0 if 0.25 <= konum <= 0.85 else (-0.8 if konum < 0.1 and ses_p[pk] >= 3 and once_bosluk[i] < 1.5 else 0.0)
        bas = (-0.7 if sig[i]["sarkik"] else 0.0) + (0.3 if once_bosluk[i] >= 0.8 else 0.0)
        kapsama = top("konusma") / L; bos_oran = top("bos") / (j - i + 1)
        ceza = 0.15 * max(0, 18 - L) + 0.12 * max(0, L - 35)
        ceza += 3 * max(0, 0.35 - kapsama) / 0.35 + 2 * max(0, bos_oran - 0.5) / 0.5
        cagri = int(top("cagri")); ceza += 3 * cagri
        sohbet = 2.0 if any(a + 3 <= t <= b + 12 for t in sohbet_t) else 0.0
        toplam = ses + icerik + yapi + bas + sohbet - ceza
        return {"puan": round(toplam, 2), "ses_db": round(float(tepe[i: j + 1].max()), 1), "ses_p": round(ses, 2), "hiz": round(hiz, 2),
                "icerik_p": round(icerik, 2), "sinyal": {ad: int(v) for ad, v in say.items() if v},
                "yapi": yapi, "tepe_i": pk, "tepe_konum": round(konum, 2), "kapsama": round(kapsama, 2),
                "cagri": cagri, "sohbet": sohbet > 0, "ceza": round(ceza, 2)}

    pencereler, elenen = [], {}
    for i in range(n):
        for j in range(i, n):
            L = B[j] - A[i]
            if L > MAX_SN: break
            if L < MIN_SN or sonra_bosluk[j] < 0.1: continue
            r = puanla(i, j); r["i"], r["j"] = i, j
            if r["cagri"] and (A[i] < GIRIS_SN or r["cagri"] >= 2):           # the channel intro / an announcement
                elenen.setdefault(round(A[i] // 30), (A[i], B[j], "giriş anonsu" if A[i] < GIRIS_SN else "anons/çağrı", cum[i][0]))
                continue
            pencereler.append(r)
    pencereler.sort(key=lambda r: -r["puan"])
    global _PENCERELER; _PENCERELER = (pencereler, A, B)                  # for a diagnosis by hand
    N = aday_sayisi(yz["sure"], adet)
    secilen = []
    for r in pencereler:                                                   # greedy: best first, no overlap
        a, b = A[r["i"]], B[r["j"]]
        if any(a < y - 0.5 and b > x + 0.5 for x, y in ((A[s["i"]], B[s["j"]]) for s in secilen)): continue
        secilen.append(r)
        if len(secilen) >= 2 * N: break
    # the streamer's chair: a moment with no face in the camera box is weak (talk over an empty chair)
    if kamera:
        try:
            import kamera_bul
            for r in secilen:
                a, b = A[r["i"]], B[r["j"]]
                yz_ = kamera_bul.yuz_var_mi(yz["kaynak"], kamera, [a + (b - a) * q for q in (0.15, 0.4, 0.65, 0.9)])
                r["yuz"] = sum(1 for _, s in yz_ if s > 0); r["yuz_kare"] = len(yz_)
                eksik = round(YUZ_CEZA * (1 - r["yuz"] / max(1, len(yz_))) ** 1.5, 2)    # 0/4 -> 5, 2/4 -> 1.8, 3/4 -> 0.6
                r["puan"] = round(r["puan"] - eksik, 2); r["ceza"] = round(r["ceza"] + eksik, 2)
        except Exception as e:
            if gunluk is not None: gunluk.append(f"yüz kontrolü yapılamadı ({type(e).__name__})")
    secilen.sort(key=lambda r: -r["puan"]); secilen = secilen[:N]
    adaylar = []
    for no, r in enumerate(secilen, 1):
        i, j, pk = r["i"], r["j"], r["tepe_i"]
        supheli = supheli_kelimeler(kel, A[i], B[j], tr=tr)
        adaylar.append({"no": no, "bas": round(float(A[i]), 2), "son": round(float(B[j]), 2), "sure": round(float(B[j] - A[i]), 1),
                        "puan": r["puan"], "tepe_cumle": cum[pk][0], "tepe_t": round(float(A[pk]), 2), "tepe_konum": r["tepe_konum"],
                        "ses_db": r["ses_db"], "sinyal": r["sinyal"], "ses_p": r["ses_p"], "icerik_p": r["icerik_p"],
                        "ceza": r["ceza"], "kapsama": r["kapsama"], "sohbet": r["sohbet"],
                        "yuz": r.get("yuz"), "yuz_kare": r.get("yuz_kare"),
                        "once_sessiz": round(float(min(once_bosluk[i], 99.0)), 2),
                        "supheli": supheli[:10],
                        "cumleler": [[round(c[1], 2), round(c[2], 2), c[0]] for c in cum[i: j + 1]],
                        "once": cum[i - 1][0] if i > 0 else "", "sonra": cum[j + 1][0] if j + 1 < n else ""})
    dusen = [{"bas": round(float(a), 2), "son": round(float(b), 2), "neden": ne, "ilk_cumle": c} for a, b, ne, c in sorted(elenen.values())]
    return adaylar, dusen


def harita(yz, adaylar, blok=600):
    """A 10-minute map of a long recording: where the talk, the reactions and the best candidates are."""
    sure = yz["sure"]; satir = []; tr = turkce_mi(yz)
    for b0 in np.arange(0, sure - 30, blok):
        b1 = min(sure, b0 + blok)
        cs = [c for c in yz["cumleler"] if b0 <= c[1] < b1]
        nk = sum(len(c[0].split()) for c in cs)
        tep = sum(cumle_sinyal(c[0], tr)["tepki"] + cumle_sinyal(c[0], tr)["kahkaha"] for c in cs)
        ad = [x for x in adaylar if b0 <= x["bas"] < b1]
        en = max(ad, key=lambda x: x["puan"]) if ad else None
        satir.append(f"| {mmss(b0)}–{mmss(b1)} | {nk / max(1, (b1 - b0) / 60):.0f} | {tep} | {len(ad)} | "
                     + (f"aday {en['no']} ({mmss(en['bas'])}, puan {en['puan']})" if en else "—") + " |")
    return satir


def main(klasor, adet=3, anlar=None, sohbet_dosya=None, kutu=None, kamera_arg=None):
    sys.path.insert(0, KOK)
    import sohbet as _s
    yz = json.load(open(os.path.join(klasor, "yazi.json"), encoding="utf-8"))
    en = json.load(open(os.path.join(klasor, "enerji.json"), encoding="utf-8"))
    hey, adim = yukseklik(en)
    cum = yz["cumleler"]; kel = yz["kelimeler"]
    with open(os.path.join(klasor, "yazi.txt"), "w", encoding="utf-8") as f:
        blok = -1
        for c in cum:
            if yz["sure"] >= 1200 and int(c[1] // 600) != blok:          # long recording: a marker every 10 minutes
                blok = int(c[1] // 600); f.write(f"----- {mmss(blok * 600)} -----\n")
            f.write(f"[{mmss(c[1])} | {c[1]:.2f}-{c[2]:.2f}] {c[0]}\n")

    # sentence boundaries: a Whisper segment ending in . ? ! ... closes a sentence; the next segment opens one
    nokta = lambda s: bool(re.search(r"[.?!…]\s*$", s))
    baslar = [cum[0][1]] + [cum[i][1] for i in range(1, len(cum)) if nokta(cum[i - 1][0])]
    sonlar = [c[2] for c in cum if nokta(c[0])] or [cum[-1][2]]
    yakin = lambda L, t: min(L, key=lambda x: abs(x - t))

    def metin(a, b): return [[round(c[1], 2), round(c[2], 2), c[0]] for c in cum if c[2] > a + 0.01 and c[1] < b - 0.01]

    def pencere(t, once=0.0):
        """Whole sentences around second t (centre moved back by `once`), ~HEDEF_SN, at most MAX_SN."""
        m = t - once
        a = max([x for x in baslar if x <= m] or [baslar[0]])
        b = min([x for x in sonlar if x >= max(m, a + 0.1)] or [sonlar[-1]])
        if once == 0: b = min([x for x in sonlar if x >= t] or [sonlar[-1]])     # a point must lie inside
        while b - a < HEDEF_SN:
            onc = [x for x in baslar if x < a]; snr = [x for x in sonlar if x > b]
            ga = max(onc) if onc else None; gb = min(snr) if snr else None
            if ga is not None and (gb is None or (m - ga) <= (gb - m)) and b - ga <= MAX_SN: a = ga
            elif gb is not None and gb - a <= MAX_SN: b = gb
            elif ga is not None and b - ga <= MAX_SN: a = ga
            else: break
        return round(a, 2), round(b, 2)

    def sohbet_penceresi(t):
        """Chat peak at t -> a sentence start ONCE_MIN-ONCE_MAX s before it, a sentence end SONRA_MIN-SONRA_MAX s
        after it (closest to the middle of each range; if none falls inside, the nearest one outside)."""
        hedef_a = t - (ONCE_MIN + ONCE_MAX) / 2; hedef_b = t + (SONRA_MIN + SONRA_MAX) / 2
        ic_a = [x for x in baslar if t - ONCE_MAX <= x <= t - ONCE_MIN]
        a = min(ic_a or [x for x in baslar if x <= t - ONCE_MIN] or [baslar[0]], key=lambda x: abs(x - hedef_a))
        ic_b = [x for x in sonlar if t + SONRA_MIN <= x <= t + SONRA_MAX]
        b = min(ic_b or [x for x in sonlar if x >= t + SONRA_MIN] or [sonlar[-1]], key=lambda x: abs(x - hedef_b))
        if b - a > MAX_SN: b = max([x for x in sonlar if a < x <= a + MAX_SN] or [b])
        return round(a, 2), round(b, 2)

    gunluk = []
    isaret = {"anlar": [], "ses_tepesi": [], "sohbet_tepesi": [], "gunluk": gunluk}
    if anlar:
        satirlar = [x.strip() for x in open(anlar, encoding="utf-8-sig").read().splitlines() if x.strip()]
        for n, satir in enumerate(satirlar, 1):
            parca = [x for x in re.split(r"\s*[-–—]\s*", satir) if x]
            ts = [_s.saniye(x) for x in parca]
            if not ts or any(x is None for x in ts) or len(ts) > 2:
                gunluk.append(f"an {n} okunamadı: '{satir}' (beklenen 12:30-13:05 ya da 12:30)"); continue
            if len(ts) == 2:
                a, b = sorted(ts); sa, sb = yakin(baslar, a), yakin(sonlar, b)
                if sb <= sa: sb = min([x for x in sonlar if x > sa] or [sonlar[-1]])
                uyar = "" if 15 <= sb - sa <= 60 else f"UYARI: {sb - sa:.1f} sn, 15–60 sn dışında (kapı düşürmez, karar kullanıcının)"
                isaret["anlar"].append({"no": n, "satir": satir, "tur": "aralik", "verilen": [a, b], "bas": round(sa, 2),
                                        "son": round(sb, 2), "sure": round(sb - sa, 1), "uyari": uyar, "cumleler": metin(sa, sb)})
            else:
                sa, sb = pencere(ts[0])
                isaret["anlar"].append({"no": n, "satir": satir, "tur": "nokta", "verilen": [ts[0]], "bas": sa, "son": sb,
                                        "sure": round(sb - sa, 1), "uyari": "", "cumleler": metin(sa, sb)})
    if sohbet_dosya:
        try:
            tp, bilgi = _s.dosya_tepeleri(sohbet_dosya, yz["sure"])
            if bilgi.get("seyrek"):
                gunluk.append(f"sohbet seyrek, işaret kullanılmadı: {bilgi['mesaj']} mesaj, 5 sn'de en çok {bilgi['en_cok_5sn']} "
                              f"mesaj (alt sınır {bilgi['alt_5sn']})")
            else:
                gunluk.append(f"sohbet dosyası: {bilgi['mesaj']} mesaj, 10 sn'de ortanca {bilgi['ortanca_10sn']}, "
                              f"{len(tp)} tepe (5 sn'de en az {bilgi['alt_5sn']} mesaj şartından önce {bilgi['ham_tepe']})")
            for x in tp: isaret["sohbet_tepesi"].append(dict(x, kaynak="dosya"))
        except (ValueError, OSError) as e: gunluk.append("sohbet dosyası okunamadı: " + str(e))
    else: gunluk.append("sohbet dosyası verilmedi")
    if kutu:
        tp, bilgi = _s.ekran_tepeleri(yz["kaynak"], kutu)
        gunluk.append(f"görünen sohbet (kutu {kutu}): {bilgi['saniye']} sn ölçüldü, {len(tp)} tepe"
                      + (f" ({bilgi['yontem']})" if bilgi.get("yontem") else ""))
        for x in tp: isaret["sohbet_tepesi"].append(dict(x, kaynak="ekran"))
    else: gunluk.append("sohbet kutusu verilmedi: görünen sohbet ölçülmedi")
    for x in isaret["sohbet_tepesi"]:          # the cause is usually 5-20 s BEFORE the chat peak
        x["bas"], x["son"] = sohbet_penceresi(x["t"])
        x["cumleler"] = metin(x["bas"], x["son"])

    kamera = kamera_kutusu(klasor, yz, kamera_arg, gunluk)
    tr = turkce_mi(yz)
    if not tr: gunluk.append(f"dil {yz.get('dil')}: Türkçe kelime listeleri kapalı, puan ses ve yapıdan")
    adaylar, dusen = adaylari_bul(yz, hey, adim, adet, [x["t"] for x in isaret["sohbet_tepesi"]], kamera, gunluk)
    yuzsuz = [a["no"] for a in adaylar if a.get("yuz") == 0]
    gunluk.append(f"{len(adaylar)} aday (kayıt {yz['sure'] / 60:.0f} dk)" + (f"; {len(dusen)} pencere giriş/anons diye elendi" if dusen else "")
                  + (f"; kamerada yüz yok: aday {', '.join(map(str, yuzsuz))}" if yuzsuz else "")
                  + ("" if kamera else "; yüz kontrolü yok"))
    # combined: a candidate and a chat peak within BIRLESIK_SN = one moment (the chat bonus is already in its score)
    birlesik, kullanilan = [], set()
    for x in sorted(isaret["sohbet_tepesi"], key=lambda y: -y.get("puan", y["kat"])):
        es = [c for c in adaylar if c["no"] not in kullanilan and abs(c["tepe_t"] - x["t"]) <= BIRLESIK_SN]
        if not es: continue
        c = max(es, key=lambda y: y["puan"]); kullanilan.add(c["no"]); x["birlesik"] = c["no"]
        birlesik.append({"no": len(birlesik) + 1, "isaret": "ikisi", "ses_aday": c["no"], "sohbet_t": x["t"],
                         "ses_t": c["tepe_t"], "bas": c["bas"], "son": c["son"], "sure": c["sure"],
                         "ses_puan": c["puan"], "sohbet_puan": x.get("puan", x["kat"]), "sohbet_tur": x.get("tur", "")})
    for c in adaylar: c["isaret"] = "ikisi" if c["no"] in kullanilan else "ses"
    isaret["birlesik"] = birlesik; isaret["elenen"] = dusen
    for c in adaylar: isaret["ses_tepesi"].append({"t": c["bas"], "bas": c["bas"], "son": c["son"], "puan": c["puan"], "isaret": c["isaret"]})
    json.dump(adaylar, open(os.path.join(klasor, "adaylar.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(isaret, open(os.path.join(klasor, "isaretler.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    with open(os.path.join(klasor, "adaylar.md"), "w", encoding="utf-8") as f:
        f.write(f"# Klip adayları\n\nKayıt: {yz['kaynak']}  ·  {yz['sure'] / 60:.1f} dk  ·  {len(kel)} kelime  ·  model {yz['model']}\n"
                "Bütün yazı: yazi.txt  ·  günlük: " + " · ".join(gunluk) + "\n\n")
        if not tr:
            f.write(f"**Kaydın dili: {yz.get('dil')}.** İçerik sinyali yalnız Türkçe için ayarlı; bu dilde adaylar ses ve yapı "
                    "puanına dayanıyor (söylenenlerden yalnız dilden bağımsız işaretler sayıldı: ! ve ?, uzatılmış harf, kahkaha, "
                    "uzun cümle, konuşma hızı). Kanal girişi ve çağrı (abone ol) bu dilde elenmez. Seçimi yazıyı (yazi.txt) "
                    "okuyarak yap.\n\n")
        if isaret["anlar"]:
            f.write(f"## KULLANICININ VERDİĞİ ANLAR ({len(isaret['anlar'])}) — an SEÇME, bunları kur\n\n")
            for x in isaret["anlar"]:
                ne = ("aralık: bu aralık kesilir, yalnız baş ve son en yakın cümle sınırına oturtuldu" if x["tur"] == "aralik"
                      else "tek nokta: bu saniyeyi içeren, tek başına anlaşılan 15–45 sn'lik pencereyi sen kur (öneri aşağıda)")
                f.write(f"### An {x['no']}: '{x['satir']}' — {ne}\n- öneri: {mmss(x['bas'])}–{mmss(x['son'])}  "
                        f"({x['bas']}–{x['son']} sn, {x['sure']} sn)" + (f"\n- **{x['uyari']}**" if x["uyari"] else "") + "\n")
                for s in x["cumleler"]: f.write(f"  - [{s[0]:.2f}–{s[1]:.2f}] {s[2]}\n")
                f.write("\n")
        f.write(f"## ADAYLAR ({len(adaylar)}, puan sırasıyla; istenen {adet} klip)\n\n"
                "Puan = ses (olağan düzeyin kaç dB üstü) + söylenenler ("
                + ("tepki, kahkaha, soru-cevap, anlatı, sohbete hitap, tekrar" if tr else "bu dilde yalnız dilden bağımsız işaretler") + ") "
                "+ yapı (tepe pencerenin ortasında: olayın nedeni önce) − ceza (çağrı/anons, uzun sessizlik, kamerada yüz yok). "
                "Puan yalnız ipucu: metni oku, tek başına anlaşılan anı seç. Sıra dışı bir an (sessiz geçen olay, sakin anlatı) "
                "listede olmayabilir; yazi.txt'ye de bak.\n\n")
        for c in adaylar:
            neden = [f"ses +{c['ses_db']:.0f} dB"] + [f"{ADLAR[k]} {v}" for k, v in sorted(c["sinyal"].items(), key=lambda kv: -kv[1])]
            if c["sohbet"]: neden.append("sohbet tepesi")
            yuz = ("" if c.get("yuz") is None else f" · kamerada yüz {c['yuz']}/{c['yuz_kare']} karede"
                   + (" (BOŞ SANDALYE: zayıf)" if c["yuz"] == 0 else ""))
            f.write(f"### Aday {c['no']} · {mmss(c['bas'])}–{mmss(c['son'])}  ({c['bas']}–{c['son']} sn, {c['sure']} sn)  ·  puan {c['puan']}"
                    f"  ·  işaret: {c['isaret']}{yuz}\n")
            f.write(f"- neden: {', '.join(neden)}; tepe {mmss(c['tepe_t'])} (pencere içinde %{c['tepe_konum'] * 100:.0f}): {c['tepe_cumle']}\n")
            if c["once_sessiz"] >= 1.0 and c["once_sessiz"] < 99:
                f.write(f"- ilk sözden önce {c['once_sessiz']:.1f} sn konuşma yok: olay oradaysa kareye bak; Sade'de klibin "
                        "`on_pay`'i ile ilk sözden en çok 3 sn önce başlar\n")
            if c["supheli"]: f.write(f"- Whisper'ın emin olmadığı kelimeler (doğrusunu ekrandan/bağlamdan bul, `yazim`'e yaz): {', '.join(c['supheli'])}\n")
            f.write(f"- öncesi: {c['once']}\n")
            for s in c["cumleler"]: f.write(f"  - [{s[0]:.2f}–{s[1]:.2f}] {s[2]}\n")
            f.write(f"- sonrası: {c['sonra']}\n\n")
        if dusen:
            f.write(f"## ELENEN ({len(dusen)}) — kanal girişi, anons, çağrı\n\n")
            for x in dusen: f.write(f"- {mmss(x['bas'])}: {x['neden']} ('{x['ilk_cumle'][:60]}')\n")
            f.write("\n")
        yalniz = [x for x in isaret["sohbet_tepesi"] if "birlesik" not in x]
        if yalniz:
            f.write(f"## SOHBET TEPELERİ, adayla eşleşmeyen ({len(yalniz)}) — işaret: sohbet. Tepki burada; onu doğuran an genelde "
                    f"5–20 sn ÖNCE (pencere {ONCE_MIN:g}–{ONCE_MAX:g} sn önce başlar, {SONRA_MIN:g}–{SONRA_MAX:g} sn sonra biter). "
                    "Puan = kat, tepki ağırlıklıysa ×1,5, soru/istek ağırlıklıysa ×0,5\n\n")
            for x in sorted(yalniz, key=lambda y: -y.get("puan", y["kat"])):
                tur = f" · {x['tur']} (tepki %{x['tepki_orani'] * 100:.0f}, soru/istek %{x['istek_orani'] * 100:.0f})" if x.get("tur") else ""
                f.write(f"### sohbet tepesi ({x['kaynak']}) · işaret: sohbet · {mmss(x['t'])} ({x['t']} sn) · olağanın {x['kat']} katı"
                        f" · puan {x.get('puan', x['kat'])}{tur}\n"
                        f"- önerilen pencere: {mmss(x['bas'])}–{mmss(x['son'])} ({x['bas']}–{x['son']} sn)\n")
                if x.get("ornek"): f.write("- sohbette: " + " | ".join(x["ornek"]) + "\n")
                for s in x["cumleler"]: f.write(f"  - [{s[0]:.2f}–{s[1]:.2f}] {s[2]}\n")
                f.write("\n")
        if yz["sure"] >= 1200:
            f.write("## KAYDIN HARİTASI (10 dakikalık bölümler)\n\nUzun kayıtta yazi.txt'nin tamamını oku ama tek seferde değil, "
                    "yazi.txt'deki `----- dk -----` işaretlerinden parça parça: önce adaylar, sonra tepkinin yoğun ya da adayı az olan bölümler, sonra kalanı.\n\n"
                    "| bölüm | kelime/dk | tepki+kahkaha | aday | en iyi aday |\n|---|---|---|---|---|\n")
            for s in harita(yz, adaylar): f.write(s + "\n")
    print(f"TAMAM {len(adaylar)} aday, {len(isaret['anlar'])} kullanıcı anı, {len(isaret['sohbet_tepesi'])} sohbet tepesi, "
          f"{len(birlesik)} birleşik, {len(dusen)} elenen -> {os.path.join(klasor, 'adaylar.md')}")
    for g in gunluk: print("  " + g)


if __name__ == "__main__":
    sys.path.insert(0, KOK)
    arg = sys.argv[1:]
    if not arg or arg[0] in ("-h", "--help", "/?"):
        print(__doc__); sys.exit(0)

    def al(ad):
        if ad in arg:
            i = arg.index(ad); v = arg[i + 1]; del arg[i:i + 2]; return v
        return None
    an, sd, ku, ka = al("--anlar"), al("--sohbet"), al("--kutu"), al("--kamera")
    main(arg[0], int(arg[1]) if len(arg) > 1 else 3, an, sd, [float(v) for v in ku.split(",")] if ku else None, ka)
