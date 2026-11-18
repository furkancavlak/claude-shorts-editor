"""sfx.py - self-synthesised sound effects (no samples, no music).
yaz(events, duration, wav_path); events = [{"t": sec, "tur": "whoosh"|"pop"|"riser"|"tik", "gain": 1.0}]
"""
import wave
import numpy as np

SR = 48000


def _env(n, atk, dec):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(atk, 1e-4)) * np.exp(-np.maximum(0, t - atk) / dec)


def whoosh(rng):
    n = int(0.55 * SR); x = rng.standard_normal(n)
    # sweeping one-pole low-pass: cutoff rises then falls
    cut = np.sin(np.linspace(0, np.pi, n)) ** 2 * 0.25 + 0.02
    y = np.zeros(n); s = 0.0
    for i in range(n): s += cut[i] * (x[i] - s); y[i] = s
    return y * np.sin(np.linspace(0, np.pi, n)) ** 1.5 * 2.2


def pop(rng):
    n = int(0.18 * SR); t = np.arange(n) / SR
    f = 900 * np.exp(-t * 25) + 300
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.045) * 0.8


def tik(rng):
    n = int(0.05 * SR); return rng.standard_normal(n) * _env(n, 0.0005, 0.006) * 0.5


def riser(rng):
    n = int(1.2 * SR); t = np.arange(n) / SR
    f = 200 * 2 ** (t * 2.2)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / t[-1]) ** 2 * 0.25


TURLER = {"whoosh": whoosh, "pop": pop, "tik": tik, "riser": riser}


def yaz(olaylar, sure, yol):
    rng = np.random.default_rng(7)
    out = np.zeros(int((sure + 0.5) * SR))
    for o in olaylar:
        s = TURLER[o["tur"]](rng) * o.get("gain", 1.0)
        i = int(o["t"] * SR); j = min(len(out), i + len(s)); out[i:j] += s[: j - i]
    pk = np.abs(out).max()
    if pk > 0: out = out / pk * 0.5          # about -6 dBFS peak
    pcm = (np.clip(out, -1, 1) * 32767).astype("<i2")
    with wave.open(yol, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
