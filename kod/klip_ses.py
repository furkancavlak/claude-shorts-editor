"""klip_ses.py - effect sounds for the Klip style's "Editli" cut (17.11.2026). Code-made sounds only, no sample files.

    carpma  impact: low thump (falling pitch) + a short crunch
    vin     whoosh (this engine's kod/sfx.py)
    pit     small pop (kod/sfx.py)

The crunch comes from kod/cizim_ses.py `citirti` (imported, that file is not changed). Every sound is seeded, so the
same plan gives the same sound. iz(vuruslar, sure, tohum) -> float32 stereo array at 48 kHz, peak ~ -9 dBFS, to be
added on top of the clip's own (already -14 LUFS) voice track.
"""
import os, sys, zlib
import numpy as np

KOK = os.path.dirname(os.path.abspath(__file__))
if KOK not in sys.path: sys.path.insert(0, KOK)
import sfx                                       # pop, whoosh (the engine's own generators)
try:
    import cizim_ses                             # the drawing scene's sounds; only imported
except Exception:                                # pragma: no cover - the drawing module is optional here
    cizim_ses = None

SR = 48000
TEPE = 10 ** (-9 / 20)                           # effect peak: -9 dBFS, under the voice's loud parts
TURLER = ("carpma", "vin", "pit")


def _tohum(*p): return zlib.crc32("|".join(str(x) for x in p).encode("utf-8"))


def carpma(rng):
    n = int(0.42 * SR); t = np.arange(n) / SR
    f = 95 * np.exp(-t * 9) + 38                                   # thump: pitch falls
    govde = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.13) * np.minimum(1, t / 0.003)
    gurul = rng.standard_normal(n) * np.exp(-t / 0.035) * 0.35     # the hit itself
    k = np.ones(24) / 24; gurul = np.convolve(gurul, k, mode="same")   # darker noise
    x = govde + gurul
    if cizim_ses is not None:
        try:
            c = np.asarray(cizim_ses.citirti(rng), np.float64)[: n]
            x[: len(c)] += c * 0.25
        except Exception:
            pass
    return x


def vin(rng): return np.asarray(sfx.whoosh(rng), np.float64)
def pit(rng): return np.asarray(sfx.pop(rng), np.float64)


def ses(tur, tohum):
    if tur not in TURLER: raise SystemExit(f"RED: bilinmeyen ses '{tur}' (carpma, vin, pit)")
    rng = np.random.default_rng(_tohum(tur, tohum))
    x = {"carpma": carpma, "vin": vin, "pit": pit}[tur](rng)
    return x / (np.abs(x).max() + 1e-9) * TEPE


def iz(olaylar, sure, tohum=0):
    """olaylar: [{"t": seconds in the OUTPUT clip, "ses": "carpma"|"vin"|"pit"}] -> (n, 2) float32."""
    n = int(round(sure * SR)); y = np.zeros(n)
    for i, o in enumerate(olaylar):
        x = ses(o["ses"], f"{tohum}-{i}")
        a = int(round(o["t"] * SR))
        if o["ses"] == "vin": a -= int(0.30 * SR)                  # a whoosh peaks in its middle: lead it in
        a = max(0, a); b = min(n, a + len(x))
        if b > a: y[a:b] += x[: b - a]
    return np.stack([y, y], axis=1).astype(np.float32)
