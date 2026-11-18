"""hazir_mi.py - is everything the engine needs on this computer? Prints one JSON object. Only LOOKS:
nothing is downloaded, installed or started (the speech model is looked up in the local cache only).

    py -3 panel/hazir_mi.py
"""
import importlib, json, os, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KOD = os.path.join(KOK, "kod")
PAKETLER = [("numpy", "numpy"), ("PIL", "Pillow"), ("cv2", "opencv-python"), ("scipy", "scipy"), ("faster_whisper", "faster-whisper")]

out = {"python": sys.version.split()[0], "paketler": {}, "model": None, "dosyalar": {}}
for mod, pip_ad in PAKETLER:
    try:
        importlib.import_module(mod); out["paketler"][mod] = {"var": True, "pip": pip_ad}
    except Exception as e:
        out["paketler"][mod] = {"var": False, "pip": pip_ad, "neden": type(e).__name__}

if out["paketler"]["faster_whisper"]["var"]:
    from faster_whisper import download_model
    adlar = [os.environ["WHISPER_MODEL"]] if os.environ.get("WHISPER_MODEL") else ["large-v3-turbo", "medium"]
    for ad in adlar:                                  # same order as kod/ses_yazi.py
        try:
            download_model(ad, local_files_only=True); out["model"] = ad; break
        except Exception:
            pass

for ad, yol in (("yazi_tipi", os.path.join(KOD, "font", "Anton.ttf")), ("yuz_modeli", os.path.join(KOD, "model", "yunet.onnx"))):
    out["dosyalar"][ad] = os.path.isfile(yol)

print(json.dumps(out))
