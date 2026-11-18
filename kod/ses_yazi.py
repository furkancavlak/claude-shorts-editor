"""ses_yazi.py - voice file -> trimmed voice wav + word timings (local faster-whisper, no downloads).

    python ses_yazi.py <voice.(wav|m4a|mp3)> <out_dir>
    python ses_yazi.py --uzun <long recording> <out_dir> [audio track]   Klip style: see uzun() below
    python ses_yazi.py --cihaz        which device transcription will use, where the GPU libraries were found (no model load)
      -> <out_dir>/ses.wav    48 kHz mono, leading silence cut so speech starts at 0.03 s,
                               trailing silence cut to 0.35 s, peak-normalised to -3 dBFS
      -> <out_dir>/ses.json   {"sure", "model", "kelimeler": [[word, start, end, prob], ...]}

Model: WHISPER_MODEL env (default large-v3-turbo, then medium) from the local Hugging Face cache only
(local_files_only=True: a missing model is an error, never a download).
GPU (18.11.2026): CTranslate2 needs the CUDA 12 cuBLAS + cuDNN 9 dlls listed in CUDA_DLL (~1.5 GB, not shipped
with it). They are looked for, in this order, and may come from several folders together:
  1. WHISPER_CUDA_DLL: one or more folders the user names (';'-separated on Windows, ':' elsewhere)
  2. this Python's own packages: nvidia/cublas/bin, nvidia/cudnn/bin, nvidia/cuda_runtime/bin (pip
     nvidia-cublas-cu12 / nvidia-cudnn-cu12), torch/lib (a CUDA build of PyTorch ships them)
  3. CUDA_PATH and CUDA_PATH_V12_* (\\bin), the standard CUDA 12 and cuDNN 9 install folders under Program Files
  4. every folder on PATH
Other Python environments (a venv of another program) are NOT searched: name such a folder in WHISPER_CUDA_DLL.
Found -> GPU (float16). Not found -> CPU int8, and a loud "UYARI: EKRAN KARTI KULLANILMIYOR" line with the measured
cost (one hour of recording: 649 s on the processor, 108 s on the graphics card; Ryzen 5 7500F / RTX 4060 Ti).
`py -3 kur_kontrol.py` reports the same.
"""
import glob, json, os, re, subprocess, sys, time
import numpy as np

SR = 48000
# measured 18.11.2026 on one hour of a stream recording (large-v3-turbo): seconds of work per hour of audio
SANIYE_SAAT = {"cpu": 649, "cuda": 108}


def oku(yol, sr):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", yol, "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0


def kirp(x, sr, esik_db=-42, bas_pay=0.03, son_pay=0.35):
    """Cut leading/trailing silence (20 ms RMS windows below esik_db)."""
    w = int(0.02 * sr); n = len(x) // w
    rms = np.sqrt((x[: n * w].reshape(n, w) ** 2).mean(1) + 1e-12)
    ses = np.where(20 * np.log10(rms) > esik_db)[0]
    if not len(ses): return x, 0.0
    a = max(0, ses[0] * w - int(bas_pay * sr)); b = min(len(x), (ses[-1] + 1) * w + int(son_pay * sr))
    return x[a:b], a / sr


# CUDA 12 cuBLAS + cuDNN 9 libraries CTranslate2 4.x loads on Windows (it ships only the small cudnn64_9.dll loader).
# About 1.5 GB together.
CUDA_DLL = ["cublas64_12.dll", "cublasLt64_12.dll", "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll", "cudnn_graph64_9.dll",
            "cudnn_adv64_9.dll", "cudnn_heuristic64_9.dll", "cudnn_engines_precompiled64_9.dll",
            "cudnn_engines_runtime_compiled64_9.dll"]


def _arama_yerleri():
    """[(folder, where it came from)] in search order (see the module text). Only folders that exist."""
    yer = []
    for k in (os.environ.get("WHISPER_CUDA_DLL") or "").split(os.pathsep):
        if k.strip(): yer.append((k.strip().strip('"'), "WHISPER_CUDA_DLL"))
    try:
        import site
        siteler = list(site.getsitepackages()) + [site.getusersitepackages()]
    except Exception:
        siteler = []
    for s in siteler:
        for alt in ("cublas", "cudnn", "cuda_runtime"):
            yer.append((os.path.join(s, "nvidia", alt, "bin"), "Python paketi nvidia-" + alt))
        yer.append((os.path.join(s, "torch", "lib"), "Python paketi torch"))
    for ad, v in sorted(os.environ.items()):
        if ad.upper() == "CUDA_PATH" or ad.upper().startswith("CUDA_PATH_V12"):
            yer.append((os.path.join(v, "bin"), ad))
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        for k in sorted(glob.glob(os.path.join(pf, "NVIDIA GPU Computing Toolkit", "CUDA", "v12*", "bin")), reverse=True):
            yer.append((k, "CUDA 12 kurulumu"))
        for k in sorted(glob.glob(os.path.join(pf, "NVIDIA", "CUDNN", "v9*", "bin", "12*")) +
                        glob.glob(os.path.join(pf, "NVIDIA", "CUDNN", "v9*", "bin")), reverse=True):
            yer.append((k, "cuDNN 9 kurulumu"))
    for k in os.environ.get("PATH", "").split(os.pathsep):
        if k.strip(): yer.append((k.strip().strip('"'), "PATH"))
    gor, out = set(), []
    for k, nereden in yer:
        anahtar = os.path.normcase(os.path.abspath(k))
        if anahtar in gor or not os.path.isdir(k): continue
        gor.add(anahtar); out.append((k, nereden))
    return out


def cuda_ara():
    """Where are the GPU libraries? -> {"klasorler": [folders that hold them, search order], "nereden": {folder:
    source}, "eksik": [dll names found nowhere], "gpu_kutuphane": all found}. Non-Windows: CTranslate2 finds its
    libraries itself, nothing to look for here (eksik = [])."""
    if os.name != "nt": return {"klasorler": [], "nereden": {}, "eksik": [], "gpu_kutuphane": True}
    yerler = _arama_yerleri(); secilen, nereden, eksik = [], {}, []
    for d in CUDA_DLL:
        bul = next(((k, n) for k, n in yerler if os.path.isfile(os.path.join(k, d))), None)
        if not bul: eksik.append(d); continue
        if bul[0] not in secilen: secilen.append(bul[0]); nereden[bul[0]] = bul[1]
    return {"klasorler": secilen, "nereden": nereden, "eksik": eksik, "gpu_kutuphane": not eksik}


def cuda_klasorleri():
    """(folders, missing dll names): kept for callers of the 17.11 version."""
    c = cuda_ara(); return c["klasorler"], c["eksik"]


def sure_tahmini(sure_sn, cihaz):
    """Expected transcription time (s) for this much audio on 'cpu' or 'cuda' (measured, see SANIYE_SAAT)."""
    return sure_sn / 3600 * SANIYE_SAAT["cuda" if cihaz == "cuda" else "cpu"]


def dk(sn): return f"{sn / 60:.0f} dk" if sn >= 90 else f"{sn:.0f} sn"


def gpu_uyarisi(c, sure_sn=None):
    """The loud line when transcription runs on the processor."""
    neden = (f"ekran kartı kütüphaneleri bulunamadı ({len(c['eksik'])}/{len(CUDA_DLL)} dosya eksik: "
             f"{', '.join(c['eksik'][:3])}{' ...' if len(c['eksik']) > 3 else ''})" if c["eksik"] else "ekran kartı açılamadı")
    ne = f"Bu kayıt ({dk(sure_sn)} ses)" if sure_sn else "1 saatlik kayıt"
    sure_sn = sure_sn or 3600
    return (f"UYARI: EKRAN KARTI KULLANILMIYOR, yazıya dökme işlemcide: {neden}. {ne} işlemcide "
            f"~{dk(sure_tahmini(sure_sn, 'cpu'))}, ekran kartıyla ~{dk(sure_tahmini(sure_sn, 'cuda'))} sürer (ölçülen: 1 saatlik kayıt "
            f"{SANIYE_SAAT['cpu']} sn / {SANIYE_SAAT['cuda']} sn). Kütüphaneler başka bir klasördeyse WHISPER_CUDA_DLL ile göster; "
            "yoksa KURULUM-AJAN.md adım 9 (~1,5 GB). `py -3 kur_kontrol.py` ayrıntıyı yazar.")


def model_ac(sure_sn=None):
    from faster_whisper import WhisperModel
    c = cuda_ara()
    gpu = c["gpu_kutuphane"]
    if gpu:
        for k in c["klasorler"]:
            if hasattr(os, "add_dll_directory"): os.add_dll_directory(k)
        os.environ["PATH"] = os.pathsep.join(c["klasorler"] + [os.environ.get("PATH", "")])
    try:
        import ctranslate2
        if gpu and ctranslate2.get_cuda_device_count() == 0: gpu = False; c["eksik"] = []      # no NVIDIA card
    except Exception:
        pass
    adlar = [os.environ["WHISPER_MODEL"]] if os.environ.get("WHISPER_MODEL") else ["large-v3-turbo", "medium"]
    for ad in adlar:
        for cihaz, tip in (("cuda", "float16"), ("cpu", "int8")):
            if cihaz == "cuda" and not gpu: continue
            try:
                m = WhisperModel(ad, device=cihaz, compute_type=tip, local_files_only=True)
                if cihaz == "cuda":     # a missing library only shows up on first use: try one second of silence
                    list(m.transcribe(np.zeros(16000, np.float32), language="tr", vad_filter=False)[0])
                if cihaz == "cpu": print(gpu_uyarisi(c, sure_sn), flush=True)
                else: print("CIHAZ ekran karti (cuda); kutuphaneler: " + "; ".join(f"{k} ({c['nereden'][k]})" for k in c["klasorler"]), flush=True)
                return m, f"{ad}/{cihaz}"
            except Exception as e:
                print(f"  {ad}/{cihaz} acilmadi: {str(e)[:90]}", flush=True)
    sys.exit("HATA: yerel Whisper modeli yok (indirme yapilmaz)")


def main(girdi, klasor):
    os.makedirs(klasor, exist_ok=True)
    x = oku(girdi, SR)
    x, kesilen = kirp(x, SR)
    pk = np.abs(x).max()
    if pk > 0: x = x / pk * 10 ** (-3 / 20)
    wav = os.path.join(klasor, "ses.wav")
    import wave
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    model, ad = model_ac(len(x) / SR); t0 = time.time()
    x16 = oku(wav, 16000)
    segs, info = model.transcribe(x16, language="tr", word_timestamps=True, vad_filter=False,
                                  condition_on_previous_text=False, beam_size=5)
    kel = []
    for s in segs:
        for wd in s.words or []:
            kel.append([wd.word.strip(), round(wd.start, 3), round(wd.end, 3), round(wd.probability, 2)])
    json.dump({"sure": round(len(x) / SR, 3), "model": ad, "bastan_kesilen": round(kesilen, 3), "kelimeler": kel},
              open(os.path.join(klasor, "ses.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"TAMAM {wav}  {len(x) / SR:.2f} sn, {len(kel)} kelime, {ad}, {time.time() - t0:.0f} sn")
    print(" ".join(k[0] for k in kel))


# ---------------------------------------------------------------- long recordings (Klip style)
PARCA_SN = 300          # one Whisper call per ~5 minutes of audio
ARA_SN = 25             # each cut is moved to the quietest 0.4 s inside the last ARA_SN seconds (no word is split)
ENERJI_ADIM = 0.25      # loudness curve resolution, seconds
# Tried 18.11.2026 on 10 minutes of a stream (4 pieces of 150 s, GPU), punctuation share per piece:
#   no prompt (kept)                    0.98 0.66 0.70 0.03   688 words, longest sentence 19.6 s
#   previous piece's last sentences     0.64 0.76 0.94 0.04   693 words, longest 42.8 s (one sentence = 15 lines)
#   + player names as prompt            0.45 1.00 0.79 0.72   622 words (10 % lost), longest 57.7 s
#   condition_on_previous_text=True     1.00 0.93 1.00 0.15   807 words, but one phrase invented 4 times
#   no prompt, run again                0.98 1.00 0.76 0.03   709 words: the same setting differs run to run
# The drift is Whisper's own (piece 4 is unpunctuated in every run, piece 2 moves 0.66 -> 1.00 between two identical
# runs), not the cut between pieces, and no prompt fixes it without a worse side effect: pieces stay independent.
# What IS done: a Whisper
# segment that holds several sentences is split at its inner . ? ! (sentence = the unit the finder and the gate
# use), and yazi.json records each piece's punctuation share ("parca_noktalama") so a drift can be seen.


def cumlelere_bol(metin, ws):
    """One Whisper segment -> [[text, start, end]]: split after every word that ends a sentence (. ? ! ...) when more
    words follow. A segment without inner sentence ends stays as Whisper wrote it."""
    ic = [i for i, w in enumerate(ws[:-1]) if re.search(r"[.?!…]$", w[0])]
    if not ic: return [[metin, ws[0][1], ws[-1][2]]]
    out, a = [], 0
    for i in ic + [len(ws) - 1]:
        parca = ws[a: i + 1]; out.append([" ".join(w[0] for w in parca), parca[0][1], parca[-1][2]]); a = i + 1
    return out


def noktalama_orani(cumleler):
    """Share of Whisper sentences that end with . ? ! ... (a check of the style staying the same)."""
    return round(sum(1 for c in cumleler if re.search(r"[.?!…]\s*$", c[0])) / max(1, len(cumleler)), 2)


def uzun(girdi, klasor, iz=0, parca_sn=PARCA_SN):
    """A long recording (an hour or more) with speech in it -> word timings in the RECORDING's own seconds.
    Nothing is trimmed or normalised: the clips are cut from the recording itself, so times must match it.
      <klasor>/yazi.json    {"kaynak", "sure", "model", "parca", "parca_noktalama", "kelimeler": [[w, a, b, p]],
                             "cumleler": [[text, a, b]]}
      <klasor>/enerji.json  {"adim": 0.25, "db": [...]}   loudness (RMS dBFS) of every 0.25 s of the recording
    Progress lines on stdout: 'ILERLEME <done>/<total> parca %<p> ...' (the panel reads them)."""
    os.makedirs(klasor, exist_ok=True)
    sr = 16000; t_bas = time.time()
    print(f"ILERLEME ses okunuyor ({os.path.basename(girdi)}, ses izi {iz})", flush=True)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", girdi, "-map", f"0:a:{iz}", "-vn", "-f", "s16le", "-ac", "1",
                          "-ar", str(sr), "-"], stdout=subprocess.PIPE)
    bloklar = []
    while True:
        b = p.stdout.read(sr * 2 * 60)
        if not b: break
        bloklar.append(np.frombuffer(b, np.int16))
    p.wait()
    if p.returncode != 0 or not bloklar: sys.exit(f"HATA: kaydın sesi okunamadı (ses izi {iz} yok mu?)")
    x = np.concatenate(bloklar); del bloklar                      # int16: an hour is ~115 MB
    sure = len(x) / sr
    w = int(ENERJI_ADIM * sr); n = len(x) // w
    db = []
    for q in range(0, n, 14400):     # an hour at a time keeps memory small
        blok = x[q * w: min(n, q + 14400) * w].astype(np.float32).reshape(-1, w) / 32768
        db += [round(float(v), 1) for v in 20 * np.log10(np.sqrt((blok ** 2).mean(1)) + 1e-9)]
    json.dump({"adim": ENERJI_ADIM, "db": db}, open(os.path.join(klasor, "enerji.json"), "w", encoding="utf-8"))
    # cut points: every ~parca_sn, moved back to the quietest moment of the preceding ARA_SN seconds
    kes = [0.0]
    while kes[-1] + parca_sn < sure - 30:
        hedef = kes[-1] + parca_sn
        a, b = int((hedef - ARA_SN) / ENERJI_ADIM), int(hedef / ENERJI_ADIM)
        pen = np.convolve(np.array(db[a:b]), np.ones(2) / 2, "same")
        kes.append(round((a + int(np.argmin(pen))) * ENERJI_ADIM + ENERJI_ADIM, 2))
    kes.append(sure)
    model, ad = model_ac(sure)
    print(f"ILERLEME model hazir ({ad}); {sure / 60:.1f} dk ses, {len(kes) - 1} parca; tahmini ~{dk(sure_tahmini(sure, ad.split('/')[-1]))}",
          flush=True)
    kel, cum, oran = [], [], []
    for i, (a, b) in enumerate(zip(kes, kes[1:])):
        parca = x[int(a * sr): int(b * sr)].astype(np.float32) / 32768
        segs, _ = model.transcribe(parca, language="tr", word_timestamps=True, vad_filter=True,
                                   condition_on_previous_text=False, beam_size=5)
        bu = []
        for s in segs:
            ws = [[wd.word.strip(), round(a + wd.start, 3), round(a + wd.end, 3), round(wd.probability, 2)] for wd in (s.words or []) if wd.word.strip()]
            if not ws: continue
            kel.extend(ws); bu.extend(cumlelere_bol(s.text.strip(), ws))
        cum.extend(bu); oran.append(noktalama_orani(bu))
        gecen = time.time() - t_bas; o = b / sure
        print(f"ILERLEME {i + 1}/{len(kes) - 1} parca %{o * 100:.0f}  ({b / 60:.1f}/{sure / 60:.1f} dk ses, "
              f"{len(kel)} kelime, gecen {gecen:.0f} sn, kalan ~{gecen / o - gecen:.0f} sn)", flush=True)
    json.dump({"kaynak": os.path.abspath(girdi), "ses_izi": iz, "sure": round(sure, 3), "model": ad, "parca": kes,
               "parca_noktalama": oran,
               "sure_sn": round(time.time() - t_bas, 1), "kelimeler": kel, "cumleler": cum},
              open(os.path.join(klasor, "yazi.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"TAMAM {os.path.join(klasor, 'yazi.json')}  {sure / 60:.1f} dk, {len(kel)} kelime, {len(cum)} cumle, {ad}, "
          f"{time.time() - t_bas:.0f} sn")


def cihaz_raporu():
    """--cihaz: device and library folders, without loading a model (quick)."""
    c = cuda_ara()
    try:
        import ctranslate2; kart = ctranslate2.get_cuda_device_count()
    except Exception:
        kart = None
    if c["gpu_kutuphane"] and kart:
        print("CIHAZ cuda (ekran karti); kutuphaneler: " + "; ".join(f"{k} ({c['nereden'][k]})" for k in c["klasorler"]))
    elif not kart:
        print("CIHAZ cpu: NVIDIA ekran karti gorunmuyor. " + gpu_uyarisi({"eksik": []}))
    else:
        print("CIHAZ cpu. " + gpu_uyarisi(c))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--cihaz":
        cihaz_raporu()
    elif a and a[0] == "--uzun":
        # python ses_yazi.py --uzun <recording> <out_dir> [audio track index, default 0]
        uzun(a[1], a[2], int(a[3]) if len(a) > 3 else 0)
    elif len(a) >= 2:
        main(a[0], a[1])
    else:
        sys.exit(__doc__)
