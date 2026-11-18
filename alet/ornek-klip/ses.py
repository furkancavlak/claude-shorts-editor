# -*- coding: utf-8 -*-
"""Sound design for klip-wow-1, all synthesized here (no samples, no music).

Input : kaynak/ses-zaman.wav (the stream's own audio, already retimed with the picture)
        kaynak/beats.json     (every visual beat in output seconds)
Output: kaynak/sfx.wav (stem), kaynak/ses-mix.wav, kaynak/ses-final.wav (-14 LUFS, -1.5 dBTP)
Cue sheet printed so every cue can be checked against the picture.
"""
import json, os, subprocess, wave, re
import numpy as np
from scipy import signal

KOK = os.path.dirname(os.path.abspath(__file__))
K = os.path.join(KOK, 'kaynak')
SR = 48000
rng = np.random.default_rng(20261117)
B = json.load(open(os.path.join(K, 'beats.json'), encoding='utf-8'))
N = int(round(B['frames'] / B['fps'] * SR))
T_AB, T_BC, T_CD = 6.70, 9.36, 11.95


def db(x):
    return 10 ** (x / 20)


def t_(n):
    return np.arange(n) / SR


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype='band', fs=SR, output='sos')
    return signal.sosfilt(sos, x)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype='low', fs=SR, output='sos'), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype='high', fs=SR, output='sos'), x)


def norm(x):
    m = np.max(np.abs(x)) + 1e-12
    return x / m


# ---------------- generators ----------------
def tick(level):
    n = int(0.06 * SR); t = t_(n)
    body = np.sin(2 * np.pi * 1650 * t) * np.exp(-t / 0.012) + 0.5 * np.sin(2 * np.pi * 3300 * t) * np.exp(-t / 0.006)
    click = hp(rng.standard_normal(n), 2500) * np.exp(-t / 0.0025)
    return norm(body + 0.6 * click) * db(level), 0.0


def whoosh(dur, level, f0=500, f1=3500, peak=0.55):
    """filtered-noise swish; cutoff sweeps f0->f1, loudness peaks at `peak` of its length"""
    n = int(dur * SR); t = np.linspace(0, 1, n)
    x = rng.standard_normal(n)
    out = np.zeros(n)
    hop = 1024
    for i in range(0, n, hop):
        seg = x[max(0, i - 2048):i + hop]
        fc = f0 * (f1 / f0) ** t[min(i, n - 1)]
        y = bp(seg, max(60, fc * 0.45), min(SR / 2 - 100, fc * 1.6), 1)
        out[i:i + hop] = y[-len(out[i:i + hop]):]
    env = np.where(t < peak, (t / peak) ** 2, ((1 - t) / (1 - peak)) ** 1.6)
    return norm(out * env) * db(level), peak * dur


def thump(level, f=70, dur=0.35, click=0.25):
    n = int(dur * SR); t = t_(n)
    freq = f * (1 + 0.8 * np.exp(-t / 0.03))
    ph = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(ph) * np.exp(-t / (dur / 4))
    c = lp(rng.standard_normal(n), 3000) * np.exp(-t / 0.004)
    return norm(body + click * c) * db(level), 0.004


def impact(level):
    n = int(1.4 * SR); t = t_(n)
    freq = 38 + 70 * np.exp(-t / 0.08)
    ph = 2 * np.pi * np.cumsum(freq) / SR
    boom = np.sin(ph) * np.exp(-t / 0.42)
    crack = bp(rng.standard_normal(n), 900, 7000) * np.exp(-t / 0.03)
    tail = lp(rng.standard_normal(n), 900) * np.exp(-t / 0.35) * 0.25
    return norm(boom + 0.55 * crack + tail) * db(level), 0.003


def time_drop(level):
    n = int(0.55 * SR); t = t_(n)
    freq = 320 * (45 / 320) ** (t / t[-1])
    ph = 2 * np.pi * np.cumsum(freq) / SR
    x = np.sin(ph) * np.sin(np.pi * np.clip(t / t[-1], 0, 1)) ** 0.7
    air = bp(rng.standard_normal(n), 150, 1200) * np.exp(-t / 0.15) * 0.3
    return norm(x + air) * db(level), 0.02


def flashbang(level, ring_level):
    """bright blow-out burst + the thin ear ring every CS player knows"""
    n = int(1.1 * SR); t = t_(n)
    burst = hp(rng.standard_normal(n), 2200) * (np.exp(-t / 0.07) * (1 - np.exp(-t / 0.004)))
    ring = np.sin(2 * np.pi * 3400 * t) * np.exp(-t / 0.35) * (1 - np.exp(-t / 0.02))
    return norm(burst) * db(level) + ring * db(ring_level), 0.004


def swipe(level):
    x, _ = whoosh(0.22, 0, 900, 5000, 0.7)
    return x * db(level), 0.15


# ---------------- cue sheet ----------------
cues = []  # (name, time of the audible landing, (signal, offset_of_landing_in_signal))


def cue(name, at, gen):
    cues.append((name, at, gen))


# hook: the countdown pill lands at frame 0
cue('hook-thump', 0.02, thump(-17, 62, 0.45, 0.35))
cue('hook-air', 0.10, whoosh(0.45, -27, 2500, 700, 0.2))
# dock swish (pill flies to the seam)
cue('dock', 1.27, whoosh(0.55, -29, 700, 3200, 0.5))
# countdown ticks at every whole second of game time left (8..1), from the real clock
cd = np.array(B['countdown']); fr = np.arange(len(cd)) / B['fps']
for k in range(8, 0, -1):
    i = np.where(cd <= k)[0][0]
    if i == 0:
        continue
    tk = fr[i - 1] + (cd[i - 1] - k) / (cd[i - 1] - cd[i]) * (fr[i] - fr[i - 1])
    cue('tick-%d' % k, tk, tick(-33 + (8 - k) * 1.2))
# layout move A->B (the peek)
cue('peek-whoosh', T_AB + 0.42, whoosh(0.7, -25, 400, 3000, 0.6))
# entering slow motion
cue('time-drop', B['slowIn'] + 0.02, time_drop(-22))
# the three hits he takes (HP 99->72, 72->45, 45->19)
cue('hit-72', B['hp72'], thump(-18, 95, 0.18, 0.6))
cue('hit-45', B['hp45'], thump(-17, 90, 0.18, 0.6))
cue('hit-19', B['hp19'], thump(-16, 85, 0.2, 0.6))
# death frame
cue('death', B['death'], impact(-6))
# face grows, game sinks
cue('react-whoosh', T_BC + 0.36, whoosh(0.62, -27, 2800, 500, 0.55))
# KÖR = flashbang
cue('kor-flash', B['kor1'] - 0.02, flashbang(-17, -31))
cue('vur-thud', B['vuruyor'] + 0.01, thump(-24, 75, 0.25, 0.3))
# C -> D move, hides the trim
cue('sink-whoosh', T_CD + 0.33, whoosh(0.62, -26, 3000, 350, 0.5))
cue('goz-thud', B['gozunu'] + 0.01, thump(-25, 80, 0.25, 0.3))
cue('kap-swipe', B['kapatiyo'] + 0.07, swipe(-22))
cue('kap-hit', B['kapatiyo'] + 0.16, thump(-19, 70, 0.3, 0.5))

sfx = np.zeros(N)
print('CUE SHEET (output seconds)')
for name, at, (sig, off) in sorted(cues, key=lambda c: c[1]):
    s0 = int(round((at - off) * SR))
    a, b = max(0, s0), min(N, s0 + len(sig))
    if b > a:
        sfx[a:b] += sig[a - s0:b - s0]
    print('  %6.3f  %s' % (at, name))

# ---------------- mix ----------------
w = wave.open(os.path.join(K, 'ses-zaman.wav'))
v = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(np.float64) / 32768
v = v[:N]
if len(v) < N:
    v = np.vstack([v, np.zeros((N - len(v), 2))])
# light duck of the stream bed under the death impact only (voice is silent there)
duck = np.ones(N)
d0 = int(B['death'] * SR)
duck[d0:d0 + int(0.5 * SR)] = np.linspace(0.6, 1.0, int(0.5 * SR))
# the stream audio arrives brick-walled at about -6 LUFS; bring it to about -16 LUFS first so the
# designed sounds (written in dBFS above) sit 8-14 dB under the speech peaks and the master has headroom
VOICE_GAIN_DB = -10.0
mix = v * db(VOICE_GAIN_DB) * duck[:, None] + sfx[:, None]
# 12 ms fade at the very end so the last syllable does not click
fe = int(0.012 * SR)
mix[-fe:] *= np.linspace(1, 0, fe)[:, None]


def wr(path, x):
    x = np.clip(x, -1, 1)
    o = wave.open(path, 'wb'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(SR)
    o.writeframes((x * 32767).astype(np.int16).tobytes()); o.close()


wr(os.path.join(K, 'sfx.wav'), np.repeat(sfx[:, None], 2, 1))
pk = np.max(np.abs(mix))
wr(os.path.join(K, 'ses-mix.wav'), mix / max(1.0, pk / 0.97))

# ---------------- master: two-pass loudnorm to -14 LUFS / -1.5 dBTP ----------------
src = os.path.join(K, 'ses-mix.wav')
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', src, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json',
                    '-f', 'null', '-'], capture_output=True, text=True)
m = json.loads(re.findall(r'\{[^{}]*\}', r.stderr)[-1])
af = ('loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:'
      'offset=%s:linear=true' % (m['input_i'], m['input_tp'], m['input_lra'], m['input_thresh'], m['target_offset']))
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-af', af + ',aresample=48000', '-ar', '48000',
                '-c:a', 'pcm_s16le', os.path.join(K, 'ses-final.wav')], check=True)
r2 = subprocess.run(['ffmpeg', '-hide_banner', '-i', os.path.join(K, 'ses-final.wav'), '-af',
                     'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, text=True)
m2 = json.loads(re.findall(r'\{[^{}]*\}', r2.stderr)[-1])
print('mix in : I %s LUFS, TP %s dBTP' % (m['input_i'], m['input_tp']))
print('final  : I %s LUFS, TP %s dBTP' % (m2['input_i'], m2['input_tp']))
