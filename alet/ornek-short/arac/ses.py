"""Sound for short-wow-1: voice + a light synth bed + one designed sound per visual event.

Everything is synthesized here with numpy (seeded), nothing is downloaded. The cue times are the
same numbers the picture uses in index.html (numeral landings, the dive, the whip, the spray...).
Output: ../assets/audio/<name>.wav, 48 kHz stereo 16-bit, mastered to about -14 LUFS, true peak <= -1.2 dBTP.

    py -3 ses.py master-v1
"""
import os, sys, wave
import numpy as np
from scipy.signal import butter, sosfilt, lfilter, resample_poly

SR = 48000
END = 433 / 30
N = int(round(END * SR))
HERE = os.path.dirname(os.path.abspath(__file__))
VOICE = os.path.join(HERE, "..", "assets", "audio", "ses.wav")
OUTDIR = os.path.join(HERE, "..", "assets", "audio")
RNG = np.random.default_rng(6)
FXDB, BEDDB = -8.5, -12.0  # voice leads: fx about 6 dB under it, bed about 11 dB under


def read_wav(p):
    w = wave.open(p)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    x = x.reshape(-1, w.getnchannels()).mean(1)
    if w.getframerate() != SR:
        x = resample_poly(x, SR, w.getframerate())
    return x


def t_(n):
    return np.arange(n) / SR


def lp(x, fc, order=2):
    return sosfilt(butter(order, fc, "low", fs=SR, output="sos"), x)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x)


def bp(x, f0, f1, order=2):
    return sosfilt(butter(order, [f0, f1], "band", fs=SR, output="sos"), x)


def svf_sweep(x, fc, q=0.8):
    """Band-pass state-variable filter with a per-sample cutoff (array)."""
    low = band = 0.0
    out = np.empty_like(x)
    f = 2 * np.sin(np.pi * np.minimum(fc, SR / 6) / SR)
    for k in range(len(x)):
        low += f[k] * band
        high = x[k] - low - q * band
        band += f[k] * high
        out[k] = band
    return out


def whoosh(dur, f0, f1, peak=0.6, q=0.7, seed=1):
    n = int(dur * SR)
    noise = np.random.default_rng(seed).uniform(-1, 1, n)
    u = np.arange(n) / n
    fc = f0 * (f1 / f0) ** u
    y = svf_sweep(noise, fc, q)
    p = np.log(0.5) / np.log(peak)
    env = np.sin(np.pi * u ** p) ** 2
    return y * env * 1.8


def thock(f0=120, dur=0.32, click=0.6, seed=2):
    n = int(dur * SR); tt = t_(n)
    f = f0 * (1 + 1.2 * np.exp(-tt / 0.018))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-tt / 0.085)
    body += 0.35 * np.sin(2 * ph) * np.exp(-tt / 0.04)
    nz = np.random.default_rng(seed).uniform(-1, 1, n)
    cl = hp(nz, 2500) * np.exp(-tt / 0.004) * click
    return np.tanh(1.4 * (body + cl))


def sub_hit(dur=1.0, seed=3):
    n = int(dur * SR); tt = t_(n)
    f = 36 + 52 * np.exp(-tt / 0.08)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-tt / 0.42)
    nz = lp(np.random.default_rng(seed).uniform(-1, 1, n), 900) * np.exp(-tt / 0.05) * 2.5
    return np.tanh(1.5 * (s + nz))


def splash(dur=0.55, seed=4):
    n = int(dur * SR); tt = t_(n)
    nz = np.random.default_rng(seed).uniform(-1, 1, n)
    y = bp(nz, 900, 7500)
    grains = lp(np.abs(np.random.default_rng(seed + 1).normal(0, 1, n)), 40)
    env = (1 - np.exp(-tt / 0.025)) * np.exp(-tt / 0.22) * (0.6 + 0.8 * grains / (grains.max() + 1e-9))
    return y * env * 1.3


def swipe(dur=0.09, seed=5):
    n = int(dur * SR); tt = t_(n)
    nz = hp(np.random.default_rng(seed).uniform(-1, 1, n), 3500)
    env = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 1.5
    return nz * env * 0.8


def vroom(dur=0.6):
    n = int(dur * SR); tt = t_(n); u = tt / dur
    f = 52 * (2.3 ** u)
    ph = np.cumsum(f) / SR
    saw = 2 * (ph % 1) - 1
    y = lp(saw, 700, 4) + 0.4 * lp(2 * ((2 * ph) % 1) - 1, 900, 2)
    env = np.sin(np.pi * u) ** 0.8
    return y * env


def chime(freqs, dur=0.5, tau=0.16):
    n = int(dur * SR); tt = t_(n)
    y = np.zeros(n)
    for j, f in enumerate(freqs):
        g = 1 / (1 + 0.5 * j)
        y += g * (np.sin(2 * np.pi * f * tt) + 0.15 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt / 0.06))
    return y * np.minimum(1, tt / 0.003) * np.exp(-tt / tau)


def ting(f=1480, dur=0.4):
    n = int(dur * SR); tt = t_(n)
    parts = [(1.0, 1.0), (2.71, 0.5), (4.13, 0.3), (5.4, 0.18)]
    y = sum(a * np.sin(2 * np.pi * f * r * tt) * np.exp(-tt / (0.12 / r ** 0.5)) for r, a in parts)
    return y * np.minimum(1, tt / 0.002)


def stamp():
    a = 0.7 * thock(70, 0.25, click=1.2, seed=9)
    s = swipe(0.04, 10)
    a[:len(s)] += 0.3 * s
    return a


def pan(x, p):
    """p in [-1, 1]; equal power."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)])


def put(bus, x, at, gain_db=0.0, p=0.0):
    i0 = int(round(at * SR))
    if i0 < 0:
        x = x[-i0:] if x.ndim == 1 else x[:, -i0:]
        i0 = 0
    st = pan(x, p) if x.ndim == 1 else x
    n = min(st.shape[1], bus.shape[1] - i0)
    if n > 0:
        bus[:, i0:i0 + n] += st[:, :n] * 10 ** (gain_db / 20)


# ------------------------------------------------------------------ music bed
def note(m):
    return 440 * 2 ** ((m - 69) / 12)


def bed():
    """Soft sunset pad in F minor, chord change on each item, a low root under it."""
    chords = [  # (start s, midi notes)
        (0.00, [53, 56, 60, 65]),   # Fm
        (4.45, [49, 53, 56, 61]),   # Db
        (7.10, [56, 60, 63, 68]),   # Ab
        (8.85, [51, 55, 58, 63]),   # Eb
        (10.55, [53, 56, 60, 65, 68]),  # Fm(add)
    ]
    out = np.zeros((2, N))
    tt = t_(N)
    for ci, (t0, ms) in enumerate(chords):
        t1 = chords[ci + 1][0] if ci + 1 < len(chords) else END + 0.5
        i0, i1 = int(t0 * SR), min(N, int((t1 + 0.25) * SR))
        seg = tt[i0:i1] - t0
        w = np.minimum(1, seg / 0.06) * np.where(seg > (t1 - t0), np.clip(1 - (seg - (t1 - t0)) / 0.25, 0, 1), 1)
        for side, det in ((0, -0.35), (1, 0.35)):
            s = np.zeros(i1 - i0)
            for j, m in enumerate(ms):
                f = note(m) + det * (1 + j * 0.3)
                ph = f * seg
                s += (2 * (ph % 1) - 1) / (1 + 0.4 * j)
            s = lp(s, 1100, 2)
            out[side, i0:i1] += s * w * 0.16
        root = note(ms[0] - 12)
        sub = np.sin(2 * np.pi * root * seg) * w * np.minimum(1, seg / 0.02) * (0.55 + 0.45 * np.exp(-seg / 0.4))
        out[:, i0:i1] += sub * 0.20
    # gentle tremolo pulse at 100 BPM eighths for life
    puls = 0.86 + 0.14 * np.cos(2 * np.pi * (100 / 60 * 2) * tt) ** 2
    return out * puls


def env_follow(x, ms=60):
    a = np.exp(-1 / (SR * ms / 1000))
    y = lfilter([1 - a], [1, -a], np.abs(x))
    return y


# ------------------------------------------------------------------ loudness (BS.1770-4)
SHELF = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585])
HIPASS = ([1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621])


def lufs(st):
    k = [lfilter(*HIPASS, lfilter(*SHELF, ch)) for ch in st]
    p = k[0] ** 2 + k[1] ** 2
    cs = np.concatenate([[0], np.cumsum(p)])
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    z = np.array([(cs[i + blk] - cs[i]) / blk for i in range(0, len(p) - blk + 1, hop)])
    L = lambda v: -0.691 + 10 * np.log10(v)
    z = z[(z > 0)]
    z = z[L(z) > -70]
    rel = L(z.mean()) - 10
    return L(z[L(z) > rel].mean())


def true_peak(st):
    up = np.stack([resample_poly(ch, 4, 1) for ch in st])
    return np.abs(up).max()


def limit(st, ceil, look_ms=2.0, rel_ms=80.0):
    """Look-ahead peak limiter on the 4x-oversampled peak: gain never lets a true peak pass the ceiling."""
    up = np.stack([resample_poly(ch, 4, 1) for ch in st])
    pk = np.abs(up).max(0).reshape(-1, 4).max(1)[: st.shape[1]]
    need = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    la = int(look_ms / 1000 * SR)
    # running minimum over the look-ahead window (so gain is down before the peak arrives)
    padded = np.concatenate([need, np.ones(la)])
    from numpy.lib.stride_tricks import sliding_window_view
    gmin = sliding_window_view(padded, la + 1).min(1)[: len(need)]
    a = np.exp(-1 / (SR * rel_ms / 1000))
    g = np.empty_like(gmin); cur = 1.0
    for i, x in enumerate(gmin):  # instant attack, smooth release
        cur = x if x < cur else x + (cur - x) * a
        g[i] = cur
    # smooth the attack step: gs[i] = mean(g[i-la .. i-1]); every g in that window is already <= need[i]
    k = np.ones(la) / la
    gs = np.convolve(np.concatenate([np.ones(la), g]), k, mode="valid")[: len(g)]
    return st * gs


def main(name):
    bus = np.zeros((2, N))
    v = read_wav(VOICE)
    v = hp(v, 70)
    v = v[:N] if len(v) >= N else np.pad(v, (0, N - len(v)))
    vbus = np.stack([v, v])

    fx = np.zeros((2, N))
    # frame 0 is already moving: tail of an incoming whoosh under the first letters
    put(fx, whoosh(0.55, 500, 3200, peak=0.35, seed=11)[int(0.20 * SR):], 0.0, -10)
    # IV lands on the beach: I, V-left, V-right
    for k, (tm, f, p) in enumerate([(0.70, 92, -0.25), (0.756, 104, 0.1), (0.786, 117, 0.3)]):
        put(fx, thock(f, seed=20 + k), tm, -6, p)
    # dive through the I
    put(fx, whoosh(0.48, 300, 5200, peak=0.85, seed=12), 1.04, -5)
    put(fx, sub_hit(0.9, seed=13), 1.50, -9)
    # stamp
    put(fx, stamp(), 2.02, -9, -0.3)
    # key-word slabs (quiet)
    for k, tm in enumerate([0.60, 2.00, 3.02, 6.12, 8.08, 9.90, 11.38, 13.60]):
        put(fx, swipe(0.09, 30 + k), tm, -17, -0.4)
    # item 1: I falls, lands, snaps open
    put(fx, whoosh(0.22, 4200, 380, peak=0.7, seed=14), 4.20, -8)
    put(fx, thock(84, seed=40), 4.405, -5)
    put(fx, whoosh(0.16, 700, 4800, peak=0.5, seed=15), 4.60, -9)
    put(fx, thock(300, 0.12, click=0.8, seed=41), 4.52, -18, -0.7)  # HUD tick
    # punch-in on "pervaneli" and the cut into the helicopter
    put(fx, whoosh(0.46, 250, 2400, peak=0.9, seed=16), 5.88, -14)
    put(fx, thock(140, 0.18, click=1.0, seed=42), 6.333, -14)
    # item 2: whip out left, II rides in from the right
    put(fx, whoosh(0.30, 600, 6500, peak=0.75, seed=17), 6.95, -5, -0.6)
    put(fx, thock(118, seed=43), 7.06, -7, 0.35)
    put(fx, thock(132, seed=44), 7.09, -7, 0.5)
    put(fx, whoosh(0.18, 900, 5200, peak=0.5, seed=18), 7.29, -11)
    put(fx, thock(300, 0.12, click=0.8, seed=45), 7.18, -18, -0.7)
    # jet ski spray hits the lens
    put(fx, splash(0.6, seed=19), 8.66, -6, 0.1)
    # item 3: III shoots up, three rising notes
    for k, (tm, f) in enumerate([(8.85, 132), (8.88, 148), (8.91, 166)]):
        put(fx, thock(f, seed=50 + k), tm, -7, -0.3 + 0.3 * k)
    put(fx, whoosh(0.18, 900, 5200, peak=0.5, seed=21), 9.10, -11)
    put(fx, thock(300, 0.12, click=0.8, seed=46), 8.98, -18, -0.7)
    # speed surge of the drift
    put(fx, vroom(0.62), 9.32, -10, 0.2)
    # item 4: IV chases in from the left, roll-dive, the one big hit
    put(fx, whoosh(0.16, 500, 3800, peak=0.6, seed=22), 10.36, -9, -0.5)
    for k, (tm, f) in enumerate([(10.475, 88), (10.48, 99), (10.51, 78)]):
        put(fx, thock(f, seed=60 + k), tm, -6, -0.4 + 0.3 * k)
    put(fx, whoosh(0.34, 250, 6000, peak=0.9, seed=23), 10.66, -5)
    put(fx, sub_hit(1.2, seed=24), 10.965, -4)
    put(fx, ting(1397, 0.4), 11.40, -20, 0.4)
    # last word: IV -> VI
    put(fx, chime([note(77), note(84)], 0.30, 0.10), 14.20, -16, 0.2)
    put(fx, swipe(0.12, 70), 14.12, -20, -0.2)

    b = bed()
    # duck the bed under the voice and under the two big hits
    ve = env_follow(v, 80)
    duck = 1 - 0.55 * np.clip(ve / (np.percentile(ve, 95) + 1e-9), 0, 1)
    for at in (1.50, 10.965):
        i0 = int(at * SR); n = int(0.5 * SR)
        duck[i0:i0 + n] *= 1 - 0.5 * np.exp(-np.arange(n) / (0.18 * SR))
    b = b * duck

    bus = vbus * 1.0 + fx * 10 ** (FXDB / 20) + b * 10 ** (BEDDB / 20)
    # tail: the Short stops on the last word; 12 ms fade so it doesn't click
    nf = int(0.012 * SR)
    bus[:, -nf:] *= np.linspace(1, 0, nf)

    target, ceil = -14.0, 10 ** (-1.5 / 20)
    pre = bus.copy()
    for _ in range(4):  # gain to target, then a 4x-oversampled look-ahead limiter; repeat until it settles
        g = 10 ** ((target - lufs(bus)) / 20)
        bus = limit(bus * g, ceil)
    gv = 10 ** ((lufs(bus) - lufs(pre)) / 20)
    for nm, s in (("voice", vbus), ("fx", fx * 10 ** (FXDB / 20)), ("bed", b * 10 ** (BEDDB / 20))):
        print(f"  {nm:5s} in the mix: {lufs(s * gv):6.1f} LUFS")
    print(f"{name}: {N / SR:.4f} s, {lufs(bus):.2f} LUFS, true peak {20 * np.log10(true_peak(bus)):.2f} dBTP")
    out = os.path.join(OUTDIR, name + ".wav")
    if os.path.exists(out):
        raise SystemExit(f"{out} exists; pick a new name")
    pcm = (np.clip(bus.T, -1, 1) * 32767).astype(np.int16)
    w = wave.open(out, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes()); w.close()
    # stems for checking sync by eye
    for nm, s in (("fx", fx), ("bed", b)):
        p = os.path.join(OUTDIR, f"{name}-{nm}.wav")
        if not os.path.exists(p):
            pk = np.abs(s).max() + 1e-9
            w = wave.open(p, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(s.T / pk * 0.9, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "master-v1")
