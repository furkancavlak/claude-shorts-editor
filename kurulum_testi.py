# -*- coding: utf-8 -*-
"""kurulum_testi.py - self-test after installing: does the whole chain work on this computer?

Needs no footage from the user. It makes everything itself, locally:
  a few seconds of synthetic video (ffmpeg test picture) and one spoken Turkish test sentence (the Windows placeholder
  voice; a tone instead when that voice is missing), opens a real Short job with them through the chat entry
  (node panel/is_ac.js, jobs folder inside the test folder: panel/isler/ is never touched), which transcribes it
  (local Whisper); then runs the look tools, the camera finder, a shot cut, a tiny HyperFrames + GSAP stage render,
  the sound mix and the technical check.

    py -3 kurulum_testi.py                 output in kurulum-testi/<date-time>/ (git ignores it)
    py -3 kurulum_testi.py --klasor <dir>  output in a new or empty folder of your choice

Safe to run again: every run writes a NEW folder; nothing is deleted or overwritten, nothing is downloaded.
If HyperFrames' Chrome is missing the render step is skipped (rendering would download Chrome by itself).
Prints one line per part: GECTI / KALDI / ATLANDI + a plain Turkish reason, then "SONUC: GECTI | KALDI | EKSIK".
Writes <folder>/sonuc.json (the same, for an agent) and <folder>/gunluk/*.txt (full output of every command).
Exit code: 0 = GECTI, 1 = KALDI or EKSIK.
"""
import argparse, json, os, re, shutil, subprocess, sys, time

KOK = os.path.dirname(os.path.abspath(__file__))
WIN = os.name == "nt"
GIZLI = 0x08000000 if WIN else 0
PY = sys.executable
CUMLE = "Bu bir kurulum denemesidir. Motor sesi yazıya döküyor ve sonucu kontrol ediyor."
FPS = 30

ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", HYPERFRAMES_NO_TELEMETRY="1",
           HF_HUB_OFFLINE="1")
parcalar = []          # [{"id", "baslik", "durum", "neden", "sure_sn", "gunluk"}]


def kaydet(id, baslik, durum, neden, t0=None, gunluk=""):
    p = {"id": id, "baslik": baslik, "durum": durum, "neden": neden,
         "sure_sn": round(time.time() - t0, 1) if t0 else 0, "gunluk": gunluk}
    parcalar.append(p)
    etiket = {"GECTI": "GECTI  ", "KALDI": "KALDI  ", "ATLANDI": "ATLANDI"}[durum]
    print("%s %s%s - %s" % (etiket, baslik, (" (%.0f sn)" % p["sure_sn"]) if p["sure_sn"] >= 1 else "", neden), flush=True)
    return durum == "GECTI"


def calis(klasor, ad, komut, sure=600):
    """run one command from the engine root without a window; full output goes to gunluk/<ad>.txt"""
    gunluk = os.path.join(klasor, "gunluk", ad + ".txt")
    try:
        r = subprocess.run(komut, cwd=KOK, capture_output=True, timeout=sure, env=ENV, creationflags=GIZLI)
        cikti, kod = (r.stdout + r.stderr).decode("utf-8", "replace"), r.returncode
    except subprocess.TimeoutExpired:
        cikti, kod = "ZAMAN ASIMI: %d sn icinde bitmedi" % sure, -1
    except Exception as e:
        cikti, kod = "%s: %s" % (type(e).__name__, e), -1
    with open(gunluk, "w", encoding="utf-8") as f:
        f.write("$ " + " ".join('"%s"' % k if " " in k else k for k in komut) + "\n\n" + cikti)
    return kod, cikti, gunluk


def son_satir(cikti):
    s = [x.strip() for x in cikti.strip().splitlines() if x.strip()]
    return s[-1][:200] if s else "(cikti yok)"


def kucuk(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def kelime_listesi(s):
    return re.findall(r"[a-zçğıöşü]+", kucuk(s))


def on_kontrol():
    """the readiness check, quietly; returns {id: durum}"""
    try:
        r = subprocess.run([PY, os.path.join(KOK, "kur_kontrol.py"), "--json"], cwd=KOK, capture_output=True,
                           timeout=180, env=ENV, creationflags=GIZLI)
        j = json.loads(r.stdout.decode("utf-8", "replace"))
        return {o["id"]: o["durum"] for o in j["ogeler"]}, j
    except Exception:
        return {}, None


def yeni_klasor(istenen):
    if istenen:
        k = os.path.abspath(istenen)
        if os.path.exists(k) and os.listdir(k):
            sys.exit("HATA: %s bos degil. Yeni ya da bos bir klasor ver (bu test hicbir seyi silmez, ustune yazmaz)." % k)
    else:
        k = os.path.join(KOK, "kurulum-testi", time.strftime("%Y%m%d-%H%M%S"))
        n = 2
        while os.path.exists(k):
            k = os.path.join(KOK, "kurulum-testi", time.strftime("%Y%m%d-%H%M%S") + "-%d" % n); n += 1
    for alt in ("gunluk", "bak", "v"):
        os.makedirs(os.path.join(k, alt))
    return k


def bitis_karesi(ses_wav):
    """picture length that ends on the last word, chosen with the same measure alet/kontrol.py 'son' uses"""
    sys.path.insert(0, os.path.join(KOK, "alet"))
    import numpy as np
    from _ortak import ses_oku, SR
    a = ses_oku(ses_wav).mean(1)
    win = int(0.02 * SR); nw = len(a) // win
    r = 20 * np.log10(np.sqrt((a[:nw * win].reshape(nw, win) ** 2).mean(1)) + 1e-9)
    ref = np.percentile(r, 95)
    above = np.where(r > ref - 25)[0]
    t_last = (above[-1] + 1) * win / SR if len(above) else len(a) / SR
    en_iyi = None
    for k in range(max(1, int((t_last - 0.05) * FPS)), int((t_last + 0.10) * FPS) + 2):
        dur = k / FPS; gap = dur - t_last
        e = min(nw, int(round(dur / 0.02)))
        tail = r[max(0, e - 4):max(1, e - 1)].max() if e > 4 else r.max()
        if -0.05 <= gap <= 0.095 and tail <= ref - 6:
            if en_iyi is None or abs(gap - 0.05) < abs(en_iyi[1] - 0.05):
                en_iyi = (k, gap)
    return (en_iyi[0] if en_iyi else int(round((t_last + 0.05) * FPS))), t_last


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--klasor", help="new or empty output folder (default: kurulum-testi/<date-time>/)")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    K = yeni_klasor(a.klasor)
    J = lambda *p: os.path.join(K, *p)
    print("Kurulum denemesi: %s" % K, flush=True)
    hazir, _ = on_kontrol()
    if not hazir:
        print("UYARI kur_kontrol.py calismadi; yine de deneniyor.", flush=True)
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"

    # 1 synthetic video: 8 s, 1920x1080, 30 fps, moving test picture + a 440 Hz tone as its sound
    t0 = time.time()
    kod, c, g = calis(K, "01-goruntu", [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=8",
                                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=8",
                                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", J("kaynak.mp4")], 120)
    video_ok = kaydet("goruntu", "Deneme görüntüsü üretme (ffmpeg)", "GECTI" if kod == 0 and os.path.isfile(J("kaynak.mp4")) else "KALDI",
                      "8 sn'lik deneme videosu yazıldı" if kod == 0 else "ffmpeg deneme videosunu yazamadı: " + son_satir(c), t0, g)

    # 2 spoken sentence: Windows placeholder voice (tr-TR); a tone pattern when it is missing
    t0 = time.time()
    open(J("cumle.txt"), "w", encoding="utf-8").write(CUMLE)
    konusma = False
    if WIN and hazir.get("turkce_ses") == "var":
        kod, c, g = calis(K, "02-ses", ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                                       os.path.join(KOK, "kod", "tts_tr.ps1"), J("cumle.txt"), J("konusma-ham.wav")], 120)
        konusma = kod == 0 and os.path.isfile(J("konusma-ham.wav"))
        if konusma:
            kaydet("ses", "Türkçe deneme cümlesi (Windows sesi)", "GECTI", "cümle seslendirildi", t0, g)
    if not konusma:
        denendi = os.path.isfile(J("gunluk", "02-ses.txt"))
        kod, c, g = calis(K, "02-ses-ton", [ffmpeg, "-v", "error", "-f", "lavfi", "-i",
                                           "aevalsrc=0.4*sin(2*PI*220*t)*gt(mod(t\\,0.5)\\,0.15):s=48000:d=3",
                                           J("konusma-ham.wav")], 60)
        kaydet("ses", "Türkçe deneme cümlesi (Windows sesi)", "ATLANDI",
               ("Windows sesi çalışmadı (gunluk/02-ses.txt)" if denendi else "Türkçe Windows sesi yok (şart değil)") +
               "; yerine ton kullanıldı, kelime kontrolü yapılmayacak", t0, g)

    # 3 a real job through the chat entry (node panel/is_ac.js): Short "Tek bilgi" with the synthetic video and the
    #   sentence (its own placeholder voice when the Windows voice works, else the tone), prepared = transcribed with the
    #   engine's own transcriber (local Whisper, never downloads). The job lives in <test folder>/isler, never in panel/isler.
    t0 = time.time()
    SES = J("ses")
    node = shutil.which("node")
    baslik = "İş açma ve yazıya dökme (node panel/is_ac.js)"
    if not video_ok:
        kaydet("yazi", baslik, "ATLANDI", "deneme görüntüsü yok")
    elif not node:
        kaydet("yazi", baslik, "ATLANDI", "Node.js kurulu değil (KURULUM-AJAN.md adım 4)")
    else:
        girdi = ["--metin-dosya", J("cumle.txt")] if konusma else ["--ses", J("konusma-ham.wav")]
        env_is = dict(ENV, PANEL_ISLER=J("isler"))
        try:
            r = subprocess.run([node, os.path.join(KOK, "panel", "is_ac.js"), "short", "tek_bilgi", "--video", J("kaynak.mp4")] + girdi,
                               cwd=KOK, capture_output=True, timeout=1800, env=env_is, creationflags=GIZLI)
            c, kod = (r.stdout + r.stderr).decode("utf-8", "replace"), r.returncode
        except Exception as e:
            c, kod = "%s: %s" % (type(e).__name__, e), -1
        g = J("gunluk", "03-is-ac.txt")
        open(g, "w", encoding="utf-8").write(c)
        m = re.search(r"^KLASOR (.+)$", c, re.M)
        if kod == 3:
            kaydet("yazi", baslik, "ATLANDI", "iş açılmadı, kurulum eksik: " + (re.search(r"KURULUM EKSIK: (.*)", c) or [None, "?"])[1], t0, g)
        elif kod == 0 and m and os.path.isfile(os.path.join(m.group(1).strip(), "ses", "ses.json")):
            SES = os.path.join(m.group(1).strip(), "ses")
            d = json.load(open(os.path.join(SES, "ses.json"), encoding="utf-8"))
            duyulan = " ".join(k[0] for k in d["kelimeler"])
            beklenen = kelime_listesi(CUMLE); bulunan = set(kelime_listesi(duyulan))
            oran = sum(1 for k in beklenen if k in bulunan) / float(len(beklenen))
            if not konusma:
                kaydet("yazi", baslik, "GECTI", "iş açıldı, model açıldı ve çalıştı (%s); konuşma olmadığı için kelimeler denetlenmedi"
                       % d["model"], t0, g)
            elif oran >= 0.6:
                kaydet("yazi", baslik, "GECTI", "iş açıldı; %s ile %%%d doğru: \"%s\"" % (d["model"], oran * 100, duyulan), t0, g)
            else:
                kaydet("yazi", baslik, "KALDI", "kelimelerin yalnız %%%d'i doğru duyuldu: \"%s\"" % (oran * 100, duyulan), t0, g)
        else:
            kaydet("yazi", baslik, "KALDI", "iş açılamadı ya da hazırlanamadı: " + son_satir(c), t0, g)
    if SES == J("ses"):                                    # no job: keep testing the rest with the raw sentence
        os.makedirs(SES)
    if not os.path.isfile(os.path.join(SES, "ses.wav")):
        calis(K, "03-yazi-yedek", [ffmpeg, "-v", "error", "-i", J("konusma-ham.wav"), "-ac", "1", "-ar", "48000", os.path.join(SES, "ses.wav")], 60)
    if not os.path.isfile(os.path.join(SES, "ses.json")):          # stand-in timings: one word over the whole sound
        t_son = bitis_karesi(os.path.join(SES, "ses.wav"))[1]
        json.dump({"sure": 0, "model": "yok (yer tutucu)", "kelimeler": [["deneme", 0.03, round(t_son, 3), 1.0]]},
                  open(os.path.join(SES, "ses.json"), "w", encoding="utf-8"))

    # 4-6 the look tools and the camera finder on the synthetic video
    if video_ok:
        t0 = time.time()
        kod, c, g = calis(K, "04-kaynak-bak", [PY, os.path.join(KOK, "alet", "kaynak_bak.py"), J("kaynak.mp4"), "--olc"], 120)
        kaydet("kaynak_bak", "Video bilgisi (alet/kaynak_bak.py)", "GECTI" if kod == 0 else "KALDI",
               "boyut, kare hızı ve ses okundu" if kod == 0 else son_satir(c), t0, g)
        t0 = time.time()
        kod, c, g = calis(K, "05-kare-bak", [PY, os.path.join(KOK, "alet", "kare_bak.py"), J("kaynak.mp4"), "--bas", "0",
                                            "--son", "4", "--hiz", "2", "--cikti", J("bak", "genel.jpg")], 120)
        jpg = [f for f in os.listdir(J("bak"))] if os.path.isdir(J("bak")) else []
        kaydet("kare_bak", "Kare kâğıdı (alet/kare_bak.py)", "GECTI" if kod == 0 and jpg else "KALDI",
               ("bak/" + jpg[0] + " yazıldı") if kod == 0 and jpg else son_satir(c), t0, g)
        t0 = time.time()
        kod, c, g = calis(K, "06-kamera", [PY, os.path.join(KOK, "kod", "kamera_bul.py"), J("kaynak.mp4"), J("kamera")], 300)
        ok = kod == 0 and os.path.isfile(J("kamera", "kamera.json"))
        yok = any(x.startswith("KAMERA YOK") for x in c.splitlines())
        kaydet("kamera", "Yayıncı kamerası bulma (OpenCV + YuNet)", "GECTI" if ok else "KALDI",
               ("çalıştı; deneme görüntüsünde yüz olmadığı için beklenen 'KAMERA YOK' cevabı geldi" if yok else
                "çalıştı (cevap: " + son_satir(c)[:80] + ")") if ok else son_satir(c), t0, g)
    else:
        for id, b in (("kaynak_bak", "Video bilgisi"), ("kare_bak", "Kare kâğıdı"), ("kamera", "Yayıncı kamerası bulma")):
            kaydet(id, b, "ATLANDI", "deneme görüntüsü yazılamadı")

    # 7 one shot cut to 9:16, as long as the sentence, plus the word timings in the shots folder
    t0 = time.time()
    cekim_ok = False
    if video_ok:
        kare, t_last = bitis_karesi(os.path.join(SES, "ses.wav"))
        if kare > 7 * FPS:
            kaydet("cekim", "Çekim kesme (alet/cekim.py)", "KALDI", "deneme cümlesi 7 sn'den uzun çıktı", t0)
        else:
            kod, c, g = calis(K, "07-cekim-kes", [PY, os.path.join(KOK, "alet", "cekim.py"), "kes", J("kaynak.mp4"), "--bas", "0",
                                                 "--kare", str(kare), "--cikti", J("v", "deneme.mp4")], 300)
            if kod == 0:
                kod, c2, g = calis(K, "07-cekim-zaman", [PY, os.path.join(KOK, "alet", "cekim.py"), "zaman", J("v"), "--kelimeler",
                                                         os.path.join(SES, "ses.json"), "--sure", "%.6f" % (kare / float(FPS))], 120)
                c = c2
            cekim_ok = kod == 0 and os.path.isfile(J("v", "zamanlar.json"))
            kaydet("cekim", "Çekim kesme (alet/cekim.py)", "GECTI" if cekim_ok else "KALDI",
                   ("%d kare (%.2f sn) dikey çekim ve kelime zamanları yazıldı" % (kare, kare / float(FPS))) if cekim_ok
                   else son_satir(c), t0, g)
    else:
        kaydet("cekim", "Çekim kesme (alet/cekim.py)", "ATLANDI", "deneme görüntüsü yok")

    # 8 an empty stage + one line of Turkish text animated with GSAP
    t0 = time.time()
    sahne_ok = False
    if cekim_ok:
        sure = json.load(open(J("v", "zamanlar.json"), encoding="utf-8"))
        json.dump([{"dosya": J("v", "deneme.mp4"), "bas": 0, "sure": round(sure["kare"] / float(sure["fps"]), 4)}],
                  open(J("cekimler.json"), "w", encoding="utf-8"))
        kod, c, g = calis(K, "08-sahne", [PY, os.path.join(KOK, "alet", "sahne_baslat.py"), J("sahne"), "--zaman", J("v"),
                                         "--cekimler", J("cekimler.json")], 120)
        ix = J("sahne", "index.html")
        if kod == 0 and os.path.isfile(ix):
            h = open(ix, encoding="utf-8").read()
            yazi = ('  <div id="deneme-yazi" style="position:absolute;left:0;top:760px;width:1080px;text-align:center;'
                    'font-size:120px;line-height:1.15;z-index:5;text-shadow:0 4px 18px #000">KURULUM<br>DENEMESİ ÇALIŞIYOR</div>\n')
            hareket = ("    st('#deneme-yazi', { opacity: 0 }, 0);\n"
                       "    ft('#deneme-yazi', { opacity: 0, y: 60 }, { opacity: 1, y: 0 }, 0.6, 'power3.out', 0.3);\n")
            h2 = h.replace('  <script src="gsap.min.js"></script>', yazi + '  <script src="gsap.min.js"></script>', 1)
            h2 = h2.replace("    window.__timelines = window.__timelines || {};", hareket + "    window.__timelines = window.__timelines || {};", 1)
            if h2.count("deneme-yazi") == 3:
                open(ix, "w", encoding="utf-8", newline="\n").write(h2)
                sahne_ok = kaydet("sahne", "Boş sahne kurma (alet/sahne_baslat.py)", "GECTI",
                                  "sahne kuruldu, içine bir satır hareketli yazı kondu", t0, g)
            else:
                kaydet("sahne", "Boş sahne kurma (alet/sahne_baslat.py)", "KALDI", "sahne dosyasının biçimi beklenenden farklı", t0, g)
        else:
            kaydet("sahne", "Boş sahne kurma (alet/sahne_baslat.py)", "KALDI", son_satir(c), t0, g)
    else:
        kaydet("sahne", "Boş sahne kurma (alet/sahne_baslat.py)", "ATLANDI", "çekim yok")

    # 9 render (only when HyperFrames' own Chrome is already here: otherwise render would download it)
    t0 = time.time()
    render_ok = False
    hf = shutil.which("hyperframes")
    if not sahne_ok:
        kaydet("render", "Sahneyi videoya çevirme (HyperFrames)", "ATLANDI", "sahne yok")
    elif not hf:
        kaydet("render", "Sahneyi videoya çevirme (HyperFrames)", "ATLANDI", "HyperFrames kurulu değil (adım 5)")
    elif hazir.get("chrome") != "var":
        kaydet("render", "Sahneyi videoya çevirme (HyperFrames)", "ATLANDI",
               "HyperFrames'in Chrome'u yok (adım 6); render onu kendisi indireceği için denenmedi")
    else:
        kod, c, g = calis(K, "09-render", [hf, "render", J("sahne"), "--output", J("render", "goruntu.mp4"), "--quality", "draft",
                                          "--workers", "1"], 900)
        render_ok = kod == 0 and os.path.isfile(J("render", "goruntu.mp4"))
        if render_ok:                   # a black or empty picture would also "render": look at the middle frame
            import numpy as np
            sure = json.load(open(J("v", "zamanlar.json"), encoding="utf-8"))
            raw = subprocess.run([ffmpeg, "-v", "error", "-ss", "%.3f" % (sure["kare"] / float(sure["fps"]) / 2), "-i",
                                  J("render", "goruntu.mp4"), "-frames:v", "1", "-vf", "scale=108:192,format=gray", "-f",
                                  "rawvideo", "-"], capture_output=True, creationflags=GIZLI).stdout
            kare = np.frombuffer(raw, np.uint8)
            render_ok = kare.size > 0 and float(kare.std()) > 10
            kaydet("render", "Sahneyi videoya çevirme (HyperFrames)", "GECTI" if render_ok else "KALDI",
                   "taslak video yazıldı ve görüntü dolu" if render_ok else "video yazıldı ama ortadaki kare boş/siyah", t0, g)
        else:
            kaydet("render", "Sahneyi videoya çevirme (HyperFrames)", "KALDI", son_satir(c), t0, g)

    # 10 sound: voice + one coded click, mastered; attached to the picture
    t0 = time.time()
    ses_ok = False
    json.dump([{"t": 0.3, "tur": "tik", "db": -20}], open(J("isaretler.json"), "w", encoding="utf-8"))
    kod, c, g = calis(K, "10-ses-miks", [PY, os.path.join(KOK, "alet", "ses.py"), "miks", os.path.join(SES, "ses.wav"), J("isaretler.json"),
                                        J("ses-final.wav")], 300)
    if kod == 0 and render_ok:
        kod, c, g = calis(K, "10-ses-ekle", [PY, os.path.join(KOK, "alet", "ses.py"), "ekle", J("render", "goruntu.mp4"),
                                            J("ses-final.wav"), J("deneme-short.mp4")], 120)
        ses_ok = kod == 0 and os.path.isfile(J("deneme-short.mp4"))
        kaydet("ses_miks", "Ses karıştırma ve ekleme (alet/ses.py)", "GECTI" if ses_ok else "KALDI",
               "ses -14 LUFS'a getirildi ve videoya eklendi" if ses_ok else son_satir(c), t0, g)
    elif kod == 0:
        kaydet("ses_miks", "Ses karıştırma ve ekleme (alet/ses.py)", "GECTI",
               "ses karıştırıldı (render olmadığı için videoya eklenmedi)", t0, g)
    else:
        kaydet("ses_miks", "Ses karıştırma ve ekleme (alet/ses.py)", "KALDI", son_satir(c), t0, g)

    # 11 the technical check the engine uses before every delivery
    t0 = time.time()
    if ses_ok:
        kod, c, g = calis(K, "11-kontrol", [PY, os.path.join(KOK, "alet", "kontrol.py"), "hepsi", J("deneme-short.mp4"), "--zaman",
                                           J("v"), "--ses", J("ses-final.wav"), "--konusma", os.path.join(SES, "ses.wav"), "--min", "1",
                                           "--max", "60"], 300)
        calis(K, "11-kareler", [PY, os.path.join(KOK, "alet", "kontrol.py"), "serit", J("deneme-short.mp4"), "--esit", "8",
                                "--sutun", "8", "--cikti", J("bak", "sonuc-kareler.jpg")], 120)
        gecti = "SONUC: GECTI" in son_satir(c)
        kaydet("kontrol", "Teknik kontrol (alet/kontrol.py hepsi)", "GECTI" if gecti else "KALDI",
               "boyut, kare hızı, kare kopyası, ses kayması ve bitiş doğru" if gecti else son_satir(c), t0, g)
    else:
        kaydet("kontrol", "Teknik kontrol (alet/kontrol.py hepsi)", "ATLANDI", "bitmiş deneme videosu yok")

    kalan = [p["id"] for p in parcalar if p["durum"] == "KALDI"]
    atlanan = [p["id"] for p in parcalar if p["durum"] == "ATLANDI" and p["id"] != "ses"]
    sonuc = "KALDI" if kalan else ("EKSIK" if atlanan else "GECTI")
    out = {"arac": "kurulum_testi", "surum": 1, "zaman": time.strftime("%Y-%m-%d %H:%M:%S"), "klasor": K, "sonuc": sonuc,
           "kalan": kalan, "atlanan": atlanan, "parcalar": parcalar,
           "video": J("deneme-short.mp4") if os.path.isfile(J("deneme-short.mp4")) else "",
           "kareler": J("bak", "sonuc-kareler.jpg") if os.path.isfile(J("bak", "sonuc-kareler.jpg")) else ""}
    json.dump(out, open(J("sonuc.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if out["video"]:
        print("VIDEO  %s" % out["video"])
    if out["kareler"]:
        print("KARELER %s" % out["kareler"])
    print("SONUC: %s%s" % (sonuc, (": " + ", ".join(kalan or atlanan)) if (kalan or atlanan) else ""))
    sys.exit(0 if sonuc == "GECTI" else 1)


if __name__ == "__main__":
    main()
