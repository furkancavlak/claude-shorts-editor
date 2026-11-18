# -*- coding: utf-8 -*-
"""Retime the raw 60 fps stream moment into a 30 fps edit timeline.

Time map (source seconds S -> output seconds T):
  * normal speed (every 2nd 60 fps frame) for the setup,
  * eased ramp down to 0.5x (every real 60 fps frame, no duplicated frames)
    across the firefight, eased ramp back to 1x at the death,
  * one 0.9 s trim of a silent watching pause (23.95 -> 24.85),
  * ends on the last spoken word.
Audio is varispeed-resampled with the SAME map, so it stays in sync.
Outputs (all new files in kaynak/):
  oyun.mp4  1920x1080 30 fps retimed game+overlay frames
  yuz.mp4   streamer cam crop, 4x lanczos upscale, same timing
  ses-zaman.wav  retimed stream audio (48 kHz stereo)
  ../beats.js + kaynak/beats.json  every beat in output time
"""
import json, subprocess, wave, sys, os
import numpy as np

KOK = os.path.dirname(os.path.abspath(__file__))
# read-only illustration: the original 60 fps stream recording is not in this repo (placeholder path)
SRC = os.path.join(KOK, 'kaynak', 'ozgun-kayit.mp4')
OUT = os.path.join(KOK, 'kaynak')
os.makedirs(OUT, exist_ok=True)

V0 = 0.016016          # pts of source frame 0
SRC_FPS = 60
FPS = 30
S_START = 12.30        # 0.18 s before "Ben flash"
S_END = 28.54          # "kapatıyo" energy gone by ~28.50
CUT_A, CUT_B = 23.95, 24.85   # trimmed silent pause (room tone only, -33..-40 dB)

# speed curve v(S): source seconds per output second
R_DOWN = (20.40, 20.52)   # ease 1 -> 0.5 (after "tutuyorum")
R_UP = (20.93, 21.07)     # ease 0.5 -> 1 around the death frame (20.95)
SLOW = 0.5


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def speed(S):
    S = np.asarray(S, dtype=np.float64)
    v = np.ones_like(S)
    a, b = R_DOWN
    v = np.where((S >= a) & (S < b), 1 - (1 - SLOW) * smooth((S - a) / (b - a)), v)
    c, d = R_UP
    v = np.where((S >= b) & (S < c), SLOW, v)
    v = np.where((S >= c) & (S < d), SLOW + (1 - SLOW) * smooth((S - c) / (d - c)), v)
    return v


# T(S) on a fine grid, piece 1 = [S_START, CUT_A], piece 2 = [CUT_B, S_END]
DS = 1e-4
S1 = np.arange(S_START, CUT_A + DS / 2, DS)
T1 = np.concatenate([[0], np.cumsum(DS / speed(S1[:-1]))])
T_CUT = T1[-1]
S2 = np.arange(CUT_B, S_END + DS / 2, DS)
T2 = T_CUT + (S2 - CUT_B)
T_END = T2[-1]


def T_of(S):
    if S <= CUT_A:
        return float(np.interp(S, S1, T1))
    if S >= CUT_B:
        return float(T_CUT + (S - CUT_B))
    raise ValueError('time inside trimmed pause: %s' % S)


def S_of(T):
    T = np.asarray(T, dtype=np.float64)
    return np.where(T < T_CUT, np.interp(T, T1, S1), CUT_B + (T - T_CUT))


N_FRAMES = int(round(T_END * FPS))
T_END_FR = N_FRAMES / FPS


def main():
    # ---------- frame list ----------
    Tf = np.arange(N_FRAMES) / FPS
    Sf = S_of(Tf)
    K = np.round((Sf - V0) * SRC_FPS).astype(int)
    assert np.all(np.diff(K) > 0), 'duplicated source frame -> fake slow motion'
    k_first, k_last = int(K[0]), int(K[-1])
    print('frames', N_FRAMES, 'T_END', round(T_END, 3), 'T_CUT', round(T_CUT, 3), 'src frames', k_first, k_last)
    print('min step', int(np.diff(K).min()), 'max step', int(np.diff(K).max()))

    W, H = 1920, 1080
    dec = subprocess.Popen([
        'ffmpeg', '-v', 'error', '-i', SRC, '-map', '0:v:0',
        '-vf', 'select=between(n\\,%d\\,%d)' % (k_first, k_last), '-vsync', '0',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    enc = subprocess.Popen([
        'ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
        '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '12', '-g', '10',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', os.path.join(OUT, 'oyun.mp4')], stdin=subprocess.PIPE)
    want = set(K.tolist())
    fsz = W * H * 3
    k = k_first
    written = 0
    while k <= k_last:
        buf = dec.stdout.read(fsz)
        if len(buf) < fsz:
            break
        if k in want:
            enc.stdin.write(buf)
            written += 1
        k += 1
    enc.stdin.close(); enc.wait(); dec.stdout.close(); dec.wait()
    assert written == N_FRAMES, (written, N_FRAMES)

    # face cam: box from klip_plan.json kamera [0,0.113,0.231,0.343] of 1920x1080
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y', '-i', os.path.join(OUT, 'oyun.mp4'),
        '-vf', 'crop=443:248:0:122,scale=1772:992:flags=lanczos,unsharp=5:5:0.55:5:5:0.0',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '13', '-g', '10', '-pix_fmt', 'yuv420p',
        os.path.join(OUT, 'yuz.mp4')], check=True)

    # ---------- audio (varispeed, same map) ----------
    w = wave.open(os.path.join(OUT, 'ham-ses.wav'))
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(np.float64) / 32768
    n_out = int(round(T_END_FR * sr))
    t = np.arange(n_out) / sr
    XF = 0.02  # crossfade at the trim
    # piece 1 continued a little past the cut, piece 2 started a little before
    s_a = np.where(t < T_CUT, np.interp(t, T1, S1), CUT_A + (t - T_CUT))
    s_b = CUT_B + (t - T_CUT)
    def samp(s):
        idx = s * sr
        i0 = np.clip(np.floor(idx).astype(int), 0, len(x) - 2)
        f = (idx - i0)[:, None]
        return x[i0] * (1 - f) + x[i0 + 1] * f
    ga = 1 - smooth((t - (T_CUT - XF / 2)) / XF)
    y = samp(s_a) * ga[:, None] + samp(s_b) * (1 - ga)[:, None]
    y = np.clip(y, -1, 1)
    wo = wave.open(os.path.join(OUT, 'ses-zaman.wav'), 'wb')
    wo.setnchannels(2); wo.setsampwidth(2); wo.setframerate(sr)
    wo.writeframes((y * 32767).astype(np.int16).tobytes()); wo.close()

    # ---------- beats in output time ----------
    words = {
        'ben': 12.48, 'flash1': 12.85, 'aticam': 13.57, 'kanka': 15.89, 'zaten': 16.53,
        'giremiyorum': 17.29, 'ki': 17.81, 'hatta': 19.07, 'smoku': 19.67, 'tutuyorum': 20.21,
        'oglum': 21.57, 'kor1': 22.17, 'vuruyor': 22.63, 'lan1': 23.23,
        'kor2': 25.65, 'lan2': 26.05, 'eliyle': 26.31, 'gozunu': 26.85, 'kapatiyo': 27.59,
    }
    events = {
        'ak': 18.70, 'peek': 19.35, 'ring': 20.20, 'hp99': 20.20, 'hp72': 20.60, 'yayinciAtes': 20.70,
        'hp45': 20.80, 'hp19': 20.83, 'hudGone': 20.90, 'death': 20.95, 'redFull': 21.05,
        'black': 22.80, 'armUp': 25.75, 'armCross': 26.20, 'armOff': 27.65,
        'slowIn': R_DOWN[0], 'slowFull': R_DOWN[1], 'slowOut0': R_UP[0], 'slowOut1': R_UP[1],
    }
    beats = {'fps': FPS, 'duration': T_END_FR, 'frames': N_FRAMES, 'cut': T_CUT,
             'sStart': S_START, 'sDeath': 20.95}
    for k_, s in list(words.items()) + list(events.items()):
        beats[k_] = round(T_of(s), 4)
    # countdown samples: remaining game time to the death, per output frame
    beats['countdown'] = [round(max(0.0, 20.95 - float(s)), 3) if s <= 20.95 else 0.0 for s in Sf]
    with open(os.path.join(OUT, 'beats.json'), 'w', encoding='utf-8') as f:
        json.dump(beats, f, ensure_ascii=False, indent=1)
    with open(os.path.join(KOK, 'beats.js'), 'w', encoding='utf-8') as f:
        f.write('window.BEATS = ' + json.dumps(beats, ensure_ascii=False) + ';\n')
    print(json.dumps({k_: v for k_, v in beats.items() if k_ != 'countdown'}, indent=0))


if __name__ == '__main__':
    main()
