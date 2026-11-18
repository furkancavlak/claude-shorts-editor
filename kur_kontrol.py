# -*- coding: utf-8 -*-
"""kur_kontrol.py - what does the engine need on this computer, and what is already here?

Only LOOKS. Nothing is downloaded, installed or started; the only programs it runs are version/list commands
(python, node, npm, ffmpeg, nvidia-smi, PowerShell voice list). It never runs `hyperframes browser path`,
`hyperframes doctor` or `hyperframes render`, because those download Chrome when it is missing.

    py -3 kur_kontrol.py              plain Turkish list for the user
    py -3 kur_kontrol.py --json       one JSON object for an agent (KURULUM-AJAN.md reads it first and last)

Every item has: id, baslik, sart (required?), durum ("var" | "yok" | "eski" | "bilinmiyor"), surum, denenen
(the version the engine was tested with), adim (step number in KURULUM-AJAN.md), not (plain Turkish), yol.
Top level: hazir (every required item is "var"; the GPU is optional and NOT in it), eksik_sart, eksik_istege_bagli,
yazma_cihazi ("cuda" | "cpu": where transcription will run), uyarilar (a list; the GPU sentence with the measured cost
when it is "cpu": one hour of recording 649 s on the processor, 108 s on the graphics card), gpu (NVIDIA card, where
the CUDA libraries were found: same search as kod/ses_yazi.py cuda_ara, WHISPER_CUDA_DLL first). In the plain list a
GPU that will not be used is printed between lines of "!" and repeated on the SONUC line.
Exit code: 0 = ready, 1 = something required is missing (the report is printed either way).
Syntax kept simple on purpose, so an old Python can still report itself as too old.
"""
import json, os, platform, re, shutil, subprocess, sys, time

KOK = os.path.dirname(os.path.abspath(__file__))
WIN = os.name == "nt"
GIZLI = 0x08000000 if WIN else 0          # CREATE_NO_WINDOW: no console window flashes on Windows
os.environ["HF_HUB_OFFLINE"] = "1"         # the Whisper model lookup must never reach the internet
ENV = dict(os.environ, HYPERFRAMES_NO_TELEMETRY="1", PYTHONIOENCODING="utf-8")

PY_MIN = (3, 11)
NODE_MIN = 22
HF_DENENEN = "0.8.140"
CHROME_SURUM = {"0.8.140": "152.0.7977.30"}   # the Chrome build HyperFrames itself looks for (from its own code)
MODELLER = [("large-v3-turbo", 1617884929), ("medium", 1527906378)]   # same order as kod/ses_yazi.py; model.bin bytes
MODUL = {"numpy": "numpy", "Pillow": "PIL", "scipy": "scipy", "opencv-python": "cv2", "faster-whisper": "faster_whisper"}
FILTRELER = ["drawtext", "minterpolate", "loudnorm", "ebur128", "alimiter", "boxblur", "unsharp", "median", "threshold",
             "tile", "cropdetect", "volumedetect", "drawbox", "eq", "afade", "atrim", "aresample", "select", "setpts",
             "scale", "crop", "pad", "fps", "concat", "split", "trim", "fade", "format", "testsrc2", "sine"]
KODLAYICI = ["libx264", "aac", "pcm_s16le"]
WINF = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
SAHNE_FONT = [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts\Oswald-Bold.ttf"),
              os.path.join(WINF, "bahnschrift.ttf"), os.path.join(WINF, "segoeuib.ttf"), os.path.join(WINF, "arialbd.ttf")]
try:                                        # one list of CUDA libraries and ONE search, shared with the transcriber
    sys.path.insert(0, os.path.join(KOK, "kod"))
    from ses_yazi import CUDA_DLL, cuda_ara, SANIYE_SAAT
except Exception:
    cuda_ara = None
    SANIYE_SAAT = {"cpu": 649, "cuda": 108}
    CUDA_DLL = ["cublas64_12.dll", "cublasLt64_12.dll", "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll", "cudnn_graph64_9.dll",
                "cudnn_adv64_9.dll", "cudnn_heuristic64_9.dll", "cudnn_engines_precompiled64_9.dll",
                "cudnn_engines_runtime_compiled64_9.dll"]

ogeler = []


def oge(id, baslik, sart, durum, adim, surum="", denenen="", not_="", yol=""):
    ogeler.append({"id": id, "baslik": baslik, "sart": sart, "durum": durum, "surum": surum, "denenen": denenen,
                   "adim": adim, "not": not_, "yol": yol})


def calis(komut, sure=30):
    """run a short command without a window; returns (exit code, stdout+stderr) or (None, reason)"""
    try:
        r = subprocess.run(komut, capture_output=True, timeout=sure, env=ENV, creationflags=GIZLI)
        return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def surum_sayi(s):
    return tuple(int(x) for x in re.findall(r"\d+", s)[:3])


def boyut_mb(yol):
    try:
        return os.path.getsize(yol) / 1e6
    except OSError:
        return 0.0


# ---------------------------------------------------------------- system
def sistem():
    ad = platform.system()
    s = {"sistem": ad, "surum": platform.release() + " " + platform.version(), "makine": platform.machine(),
         "denenen": ad == "Windows"}
    oge("isletim", "İşletim sistemi", False, "var", 0, ad + " " + platform.release(), "Windows 10 (x64)",
        "" if ad == "Windows" else "Bu sistemde denenmedi: motor Windows'ta denendi. Mac/Linux'ta yazı tipi yolları ve "
        "yer tutucu ses çalışmaz; KURULUM-AJAN.md 'Windows dışı' bölümüne bak.")
    try:
        bos = shutil.disk_usage(KOK).free / 1e9
        oge("disk", "Boş disk alanı", False, "var" if bos >= 10 else "eski", 0, "%.1f GB" % bos, "en az 10 GB",
            "" if bos >= 10 else "Yer az: kurulum ~4 GB, her iş birkaç GB tutabilir.", KOK)
    except Exception:
        pass
    return s


# ---------------------------------------------------------------- python and packages
def python_kontrol():
    v = sys.version_info
    ok = (v[0], v[1]) >= PY_MIN
    oge("python", "Python", True, "var" if ok else "eski", 1, "%d.%d.%d" % tuple(v[:3]), "3.14.5 (en az 3.11)",
        "" if ok else "Bu Python çok eski; 3.11 ya da yenisi gerekir.", sys.executable)
    if WIN:
        py = shutil.which("py")
        if not py:
            oge("py_baslatici", "py başlatıcısı", True, "yok", 1, "", "Python ile gelir",
                "Panel Python'u 'py -3' ile açar; py başlatıcısı yok.")
        else:
            kod, cikti = calis([py, "-3", "-c", "import sys;print(sys.executable)"])
            hedef = cikti.strip().splitlines()[-1] if kod == 0 and cikti.strip() else ""
            ayni = bool(hedef) and os.path.normcase(os.path.realpath(hedef)) == os.path.normcase(os.path.realpath(sys.executable))
            oge("py_baslatici", "py başlatıcısı", True, "var" if ayni else "bilinmiyor", 1, "py -3 = " + (hedef or "?"), "",
                "" if ayni else "Panel 'py -3' ile bu Python'u değil başkasını açıyor. Paketleri o Python'a kur "
                "(py -3 -m pip ...) ve bu kontrolü 'py -3 kur_kontrol.py' ile çalıştır.", hedef)
    return ok


def gerekenler():
    pin = {}
    try:
        for satir in open(os.path.join(KOK, "requirements.txt"), encoding="utf-8"):
            satir = satir.split("#")[0].strip()
            if "==" in satir:
                ad, s = satir.split("==", 1); pin[ad.strip()] = s.strip()
    except OSError:
        pass
    return pin


def paketler():
    try:
        from importlib import metadata
    except Exception:
        metadata = None
    for dist, s in gerekenler().items():
        mod = MODUL.get(dist, dist.replace("-", "_"))
        surum, durum, not_ = "", "yok", ""
        try:
            m = __import__(mod)
            durum = "var"
            if metadata:
                try:
                    surum = metadata.version(dist)
                except Exception:
                    pass
            surum = surum or getattr(m, "__version__", "")
            if mod == "cv2" and not hasattr(m, "FaceDetectorYN"):
                durum, not_ = "eski", "Bu OpenCV yüz bulucuyu (FaceDetectorYN) içermiyor; 4.5.4 ya da yenisi gerekir."
        except Exception as e:
            not_ = "Yüklenemedi (%s)." % type(e).__name__
        if durum == "var" and surum and surum.split("+")[0] != s and not not_:
            not_ = "Denenen sürüm %s; bu sürüm denenmedi ama büyük ihtimalle çalışır." % s
        oge("paket_" + mod, "Python paketi " + dist, True, durum, 2, str(surum), s, not_)
    try:
        import ctranslate2
        oge("paket_ctranslate2", "Python paketi ctranslate2 (faster-whisper ile gelir)", True, "var", 2,
            ctranslate2.__version__, "4.8.5")
    except Exception:
        oge("paket_ctranslate2", "Python paketi ctranslate2 (faster-whisper ile gelir)", True, "yok", 2, "", "4.8.5")


# ---------------------------------------------------------------- ffmpeg
def ffmpeg():
    for ad in ("ffmpeg", "ffprobe"):
        yol = shutil.which(ad)
        if not yol:
            oge(ad, ad, True, "yok", 3, "", "8.1.1 (gyan.dev full)", "PATH'te yok.")
            continue
        kod, cikti = calis([yol, "-hide_banner", "-version"])
        ilk = cikti.splitlines()[0] if cikti else ""
        m = re.search(r"version\s+(\S+)", ilk)
        oge(ad, ad, True, "var" if kod == 0 else "bilinmiyor", 3, m.group(1) if m else ilk[:40], "8.1.1 (gyan.dev full)",
            "", yol)
    yol = shutil.which("ffmpeg")
    if not yol:
        return
    kod, cikti = calis([yol, "-hide_banner", "-filters"])
    var = set()
    for satir in cikti.splitlines():
        p = satir.split()
        if len(p) >= 3 and re.match(r"^[TSC.]{2,3}$", p[0]):
            var.add(p[1])
    eksik = [f for f in FILTRELER if f not in var]
    oge("ffmpeg_filtre", "ffmpeg filtreleri", True, "var" if not eksik else "yok", 3,
        "%d/%d" % (len(FILTRELER) - len(eksik), len(FILTRELER)), "hepsi",
        "" if not eksik else "Bu ffmpeg şunları içermiyor: %s. 'Tam' (full) bir ffmpeg derlemesi gerekir." % ", ".join(eksik))
    kod, cikti = calis([yol, "-hide_banner", "-encoders"])
    eksik = [k for k in KODLAYICI if not re.search(r"\s%s\s" % re.escape(k), cikti)]
    oge("ffmpeg_kodlayici", "ffmpeg kodlayıcıları (libx264, aac)", True, "var" if not eksik else "yok", 3,
        "%d/%d" % (len(KODLAYICI) - len(eksik), len(KODLAYICI)), "hepsi",
        "" if not eksik else "Eksik kodlayıcı: %s." % ", ".join(eksik))


# ---------------------------------------------------------------- node, hyperframes, chrome
def node():
    yol = shutil.which("node")
    if not yol:
        oge("node", "Node.js", True, "yok", 4, "", "24.15.0 (en az 22)", "PATH'te yok.")
    else:
        kod, cikti = calis([yol, "--version"])
        s = cikti.strip().lstrip("v")
        ok = kod == 0 and surum_sayi(s)[:1] >= (NODE_MIN,)
        oge("node", "Node.js", True, "var" if ok else "eski", 4, s, "24.15.0 (en az 22)",
            "" if ok else "HyperFrames en az Node 22 ister.", yol)
    npm = shutil.which("npm")
    if not npm:
        oge("npm", "npm", True, "yok", 4, "", "Node ile gelir", "PATH'te yok (Node ile birlikte kurulur).")
    else:
        kod, cikti = calis([npm, "--version"])
        oge("npm", "npm", True, "var" if kod == 0 else "bilinmiyor", 4, cikti.strip()[:20], "Node ile gelir", "", npm)


def hyperframes_surum(yol):
    """version from the installed package.json (does not run HyperFrames)"""
    adaylar = [os.path.join(os.path.dirname(yol), "node_modules", "hyperframes", "package.json")]
    d = os.path.dirname(os.path.realpath(yol))
    for _ in range(6):
        adaylar.append(os.path.join(d, "package.json")); d = os.path.dirname(d)
    for p in adaylar:
        try:
            j = json.load(open(p, encoding="utf-8"))
            if j.get("name") == "hyperframes":
                return j.get("version", "")
        except Exception:
            pass
    return ""


def hyperframes():
    yol = shutil.which("hyperframes")
    if not yol:
        oge("hyperframes", "HyperFrames", True, "yok", 5, "", HF_DENENEN, "PATH'te yok.")
        s = ""
    else:
        s = hyperframes_surum(yol)
        oge("hyperframes", "HyperFrames", True, "var" if s else "bilinmiyor", 5, s, HF_DENENEN,
            "" if s == HF_DENENEN else ("Sürüm okunamadı." if not s else
                                        "Denenen sürüm %s; bu sürüm denenmedi." % HF_DENENEN), yol)
    # HyperFrames' own lookup for rendering: env var, else its cache with exactly its Chrome build, else it DOWNLOADS.
    env = os.environ.get("HYPERFRAMES_BROWSER_PATH") or os.environ.get("PRODUCER_HEADLESS_SHELL_PATH")
    if env and os.path.isfile(env):
        oge("chrome", "HyperFrames'in Chrome'u", True, "var", 6, "ortam değişkeni", "", "", env)
        return
    kok = os.path.join(os.path.expanduser("~"), ".cache", "hyperframes", "chrome", "chrome-headless-shell")
    bulunan = []
    if os.path.isdir(kok):
        for klasor in sorted(os.listdir(kok)):
            for alt in ("chrome-headless-shell-win64", "chrome-headless-shell-linux64", "chrome-headless-shell-mac-arm64",
                        "chrome-headless-shell-mac-x64", "chrome-headless-shell-win32"):
                for exe in ("chrome-headless-shell.exe", "chrome-headless-shell"):
                    p = os.path.join(kok, klasor, alt, exe)
                    if os.path.isfile(p):
                        bulunan.append((klasor.split("-", 1)[-1], p))
    beklenen = CHROME_SURUM.get(s)
    uyan = [b for b in bulunan if b[0] == beklenen]
    if uyan:
        oge("chrome", "HyperFrames'in Chrome'u", True, "var", 6, uyan[0][0], beklenen, "", uyan[0][1])
    elif bulunan and not beklenen:
        oge("chrome", "HyperFrames'in Chrome'u", True, "bilinmiyor", 6, ", ".join(b[0] for b in bulunan), "",
            "Bu HyperFrames sürümünün hangi Chrome'u istediği bilinmiyor; render ederken kendisi indirebilir.", bulunan[-1][1])
    else:
        oge("chrome", "HyperFrames'in Chrome'u", True, "yok", 6, ", ".join(b[0] for b in bulunan), beklenen or "",
            "Yok. Dikkat: 'hyperframes render', 'browser path' ve 'browser ensure' bu durumda Chrome'u kendisi indirir "
            "(denenen bilgisayarda kurulu hâli ~270 MB). Önce kullanıcıya sor.", kok)


# ---------------------------------------------------------------- whisper model
def whisper():
    try:
        from faster_whisper import download_model
    except Exception:
        oge("whisper_model", "Yazıya dökme modeli (Whisper)", True, "bilinmiyor", 7, "", "large-v3-turbo",
            "Önce faster-whisper paketi kurulmalı.")
        return
    adlar = [(os.environ["WHISPER_MODEL"], 0)] if os.environ.get("WHISPER_MODEL") else MODELLER
    for ad, bayt in adlar:
        try:
            yol = download_model(ad, local_files_only=True)
        except Exception:
            continue
        mb = boyut_mb(os.path.join(yol, "model.bin"))
        tam = not bayt or abs(mb * 1e6 - bayt) < 1e6
        oge("whisper_model", "Yazıya dökme modeli (Whisper)", True, "var" if tam else "bilinmiyor", 7,
            "%s (%.0f MB)" % (ad, mb), "large-v3-turbo",
            "" if tam else "model.bin beklenen boyutta değil (yarım inmiş olabilir).", yol)
        return
    oge("whisper_model", "Yazıya dökme modeli (Whisper)", True, "yok", 7, "", "large-v3-turbo",
        "Bu bilgisayarda yok. Bir kez indirilir (~1,6 GB); motor kendisi indirmez.")


# ---------------------------------------------------------------- voice, fonts, repo files, claude
def turkce_ses():
    if not WIN:
        oge("turkce_ses", "Türkçe yer tutucu ses (Windows)", False, "yok", 8, "", "Microsoft Tolga",
            "Yalnız Windows'ta var. Şart değil: gerçek ses kullanıcının kendi kaydı.")
        return
    ps = ("Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
          "$null=[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]; "
          "[Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Language -eq 'tr-TR' } | "
          "ForEach-Object { $_.DisplayName }")
    kod, cikti = calis(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], 60)
    adlar = [s.strip() for s in (cikti or "").splitlines() if s.strip() and kod == 0]
    oge("turkce_ses", "Türkçe yer tutucu ses (Windows)", False, "var" if adlar else "yok", 8, ", ".join(adlar),
        "Microsoft Tolga", "" if adlar else "Şart değil: yalnız deneme sesi için. Gerçek ses kullanıcının kendi kaydı.")


def dosyalar():
    for id, baslik, yol in (("font_anton", "Yazı tipi Anton (depoda)", os.path.join(KOK, "kod", "font", "Anton.ttf")),
                            ("yuz_modeli", "Yüz bulma modeli YuNet (depoda)", os.path.join(KOK, "kod", "model", "yunet.onnx")),
                            ("gsap", "GSAP (depoda)", os.path.join(KOK, "alet", "vendor", "gsap.min.js"))):
        var = os.path.isfile(yol)
        oge(id, baslik, True, "var" if var else "yok", 0, "%.2f MB" % boyut_mb(yol) if var else "", "",
            "" if var else "Depo eksik indirilmiş: bu dosyayı depodan yeniden al.", yol)
    a = [p for p in (os.path.join(WINF, "arialbd.ttf"), os.path.join(WINF, "arial.ttf")) if os.path.isfile(p)]
    oge("font_arial", "Yazı tipi Arial Bold (etiketler)", True, "var" if a else "yok", 0, os.path.basename(a[0]) if a else "",
        "Windows ile gelir", "" if a else "Kare kâğıtlarının etiketleri için Windows yazı tipi gerekir (Windows dışı denenmedi).",
        a[0] if a else "")
    s = [p for p in SAHNE_FONT if os.path.isfile(p)]
    oge("font_sahne", "Sahne yazı tipi", True, "var" if s else "yok", 0, os.path.basename(s[0]) if s else "",
        "Windows ile gelir", "" if s else "sahne_baslat.py için kurulu bir .ttf gerekir (--font ile de verilir).",
        s[0] if s else "")
    c = shutil.which("claude")
    oge("claude", "Claude Code", False, "var" if c else "bilinmiyor", 0, "", "",
        "" if c else "PATH'te görünmedi (başka bir kodlama ajanıyla da çalışır).", c or "")


# ---------------------------------------------------------------- gpu
def gpu():
    """Will transcription run on the graphics card? Same search as kod/ses_yazi.py (cuda_ara): WHISPER_CUDA_DLL,
    this Python's nvidia-*/torch packages, CUDA_PATH and the standard CUDA 12 / cuDNN 9 folders, PATH."""
    g = {"nvidia": False, "kart": "", "surucu": "", "bellek_mb": "", "ct2_cuda_aygit": None,
         "whisper_cuda_dll": os.environ.get("WHISPER_CUDA_DLL", ""), "bulunan_klasorler": [], "eksik_dll": [],
         "onerilen_whisper_cuda_dll": "",    # kept empty since 18.11.2026: libraries found in standard places are used as they are
         "hazir": False, "cihaz": "cpu", "oneri": "",
         "yazma_suresi": {"islemci_sn_saat": SANIYE_SAAT["cpu"], "ekran_karti_sn_saat": SANIYE_SAAT["cuda"],
                          "olcum": "18.11.2026, 60 dk yayın kaydı, large-v3-turbo; Ryzen 5 7500F / RTX 4060 Ti"}}
    smi = shutil.which("nvidia-smi") or (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "nvidia-smi.exe")
                                         if WIN else None)
    if smi and os.path.isfile(smi):
        kod, cikti = calis([smi, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"])
        if kod == 0 and cikti.strip():
            p = [x.strip() for x in cikti.strip().splitlines()[0].split(",")]
            g.update(nvidia=True, kart=p[0], surucu=p[1] if len(p) > 1 else "", bellek_mb=p[2] if len(p) > 2 else "")
    try:
        import ctranslate2
        g["ct2_cuda_aygit"] = ctranslate2.get_cuda_device_count()
    except Exception:
        pass
    if cuda_ara:
        c = cuda_ara()
        g["bulunan_klasorler"] = [{"klasor": k, "nereden": c["nereden"][k]} for k in c["klasorler"]]
        g["eksik_dll"] = c["eksik"]
    else:                                    # the transcriber did not load (a package is missing): only the env var
        kl = [k.strip().strip('"') for k in g["whisper_cuda_dll"].split(os.pathsep) if k.strip()]
        g["eksik_dll"] = [d for d in CUDA_DLL if not any(os.path.isfile(os.path.join(k, d)) for k in kl)] if WIN else []
    saat = "1 saatlik kayıt işlemcide ~%d dk, ekran kartıyla ~%d dk (3 saat: ~%d dk / ~%d dk)" % (
        round(SANIYE_SAAT["cpu"] / 60), round(SANIYE_SAAT["cuda"] / 60), round(3 * SANIYE_SAAT["cpu"] / 60), round(3 * SANIYE_SAAT["cuda"] / 60))
    if g["nvidia"] and not g["eksik_dll"] and (g["ct2_cuda_aygit"] or 0) > 0:
        g.update(hazir=True, cihaz="cuda")
        g["oneri"] = "GPU hazır: yazıya dökme ekran kartında çalışır (%s)." % saat
    elif not g["nvidia"]:
        g["oneri"] = ("EKRAN KARTI KULLANILMAYACAK: NVIDIA ekran kartı görünmüyor, yazıya dökme işlemcide çalışır: %s. "
                      "Kurulacak bir şey yok; uzun kayıtta işi açmadan önce kullanıcıya süreyi söyle." % saat)
    else:
        g["oneri"] = ("EKRAN KARTI KULLANILMAYACAK: NVIDIA kart var (%s) ama CUDA 12 cuBLAS + cuDNN 9 dosyalarından %d/%d tanesi "
                      "bulunamadı (%s). Yazıya dökme işlemcide çalışır: %s. Dosyalar başka bir klasördeyse (başka bir programın "
                      "Python ortamı, ör. ...\\venv\\Lib\\site-packages\\torch\\lib) kullanıcının onayıyla WHISPER_CUDA_DLL o klasörü "
                      "göstersin; yoksa KURULUM-AJAN.md adım 9 (~1,5 GB indirme, kullanıcı onaylarsa). Kısa seslendirmeli "
                      "Short'ta fark küçük; uzun yayın kaydında büyük." % (g["kart"], len(g["eksik_dll"]), len(CUDA_DLL),
                                                                          ", ".join(g["eksik_dll"][:3]) + (" ..." if len(g["eksik_dll"]) > 3 else ""), saat))
    return g


def main():
    js = "--json" in sys.argv[1:]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    s = sistem()
    if python_kontrol():
        paketler()
    ffmpeg(); node(); hyperframes(); whisper(); turkce_ses(); dosyalar()
    g = gpu()
    eksik = [o["id"] for o in ogeler if o["sart"] and o["durum"] != "var"]
    istege = [o["id"] for o in ogeler if not o["sart"] and o["durum"] not in ("var",) and o["id"] not in ("isletim",)]
    uyarilar = [] if g["hazir"] else [g["oneri"]]
    out = {"arac": "kur_kontrol", "surum": 2, "zaman": time.strftime("%Y-%m-%d %H:%M:%S"), "kok": KOK,
           "isletim": s, "hazir": not eksik, "eksik_sart": eksik, "eksik_istege_bagli": istege,
           # 'hazir' covers the required items only; the GPU is optional, so its state is spelled out here as well
           "yazma_cihazi": g["cihaz"], "uyarilar": uyarilar, "ogeler": ogeler, "gpu": g}
    if js:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("Short motoru kurulum kontrolü (%s, %s)" % (s["sistem"], out["zaman"]))
        for o in ogeler:
            etiket = {"var": "VAR ", "yok": "YOK ", "eski": "ESKİ", "bilinmiyor": "?   "}.get(o["durum"], o["durum"])
            satir = "[%s] %s%s" % (etiket, o["baslik"], (" " + o["surum"]) if o["surum"] else "")
            if not o["sart"]:
                satir += " (isteğe bağlı)"
            if o["not"]:
                satir += " - " + o["not"]
            print(satir)
        if g["hazir"]:
            print("[GPU ] " + g["oneri"])
        else:
            cizgi = "!" * 78
            print(cizgi)
            print("!!! " + g["oneri"])
            print(cizgi)
        sonuc = "SONUC: HAZIR" if not eksik else "SONUC: EKSIK: " + ", ".join(eksik)
        print(sonuc + ("" if g["hazir"] else " (UYARI: ekran kartı kullanılmayacak, uzun kayıt yavaş yazıya dökülür)"))
    sys.exit(0 if not eksik else 1)


if __name__ == "__main__":
    main()
