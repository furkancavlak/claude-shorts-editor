# -*- coding: utf-8 -*-
"""Shared helpers for the alet/ tools (ffprobe, audio read/write, loudness). Not a tool itself."""
import json, os, re, subprocess, sys, wave
import numpy as np

SR = 48000


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def fps_val(s):
    if not s or s == '0/0':
        return 0.0
    a, b = (s.split('/') + ['1'])[:2]
    return float(a) / float(b)


def bilgi(path):
    """dict: sure, video{w,h,fps,fps_str,bas,kare}, ses{sr,kanal,bas} or None"""
    if not os.path.exists(path):
        sys.exit('dosya yok: %s' % path)
    r = run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path])
    d = json.loads(r.stdout or '{}')
    out = {'dosya': path, 'sure': float(d.get('format', {}).get('duration', 0) or 0), 'video': None, 'ses': None}
    for s in d.get('streams', []):
        if s.get('codec_type') == 'video' and out['video'] is None and s.get('disposition', {}).get('attached_pic', 0) == 0:
            out['video'] = {'w': int(s['width']), 'h': int(s['height']), 'fps': fps_val(s.get('r_frame_rate')),
                            'fps_ort': fps_val(s.get('avg_frame_rate')), 'fps_str': s.get('r_frame_rate'),
                            'bas': float(s.get('start_time', 0) or 0), 'kare': int(s.get('nb_frames', 0) or 0),
                            'codec': s.get('codec_name')}
        if s.get('codec_type') == 'audio' and out['ses'] is None:
            out['ses'] = {'sr': int(s.get('sample_rate', 0)), 'kanal': int(s.get('channels', 0)),
                          'bas': float(s.get('start_time', 0) or 0), 'codec': s.get('codec_name')}
    return out


def ses_oku(path, bas=None, sure=None, sr=SR, kanal=2):
    """float64 array (n, kanal); sample 0 = time `bas` (or file start) on the audio timeline"""
    cmd = ['ffmpeg', '-v', 'error']
    if bas is not None:
        cmd += ['-ss', '%.6f' % bas]
    cmd += ['-i', path]
    if sure is not None:
        cmd += ['-t', '%.6f' % sure]
    cmd += ['-vn', '-ac', str(kanal), '-ar', str(sr), '-f', 'f32le', '-']
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64).reshape(-1, kanal)


def wav_yaz(path, x, sr=SR):
    x = np.clip(np.asarray(x, dtype=np.float64), -1, 1)
    if x.ndim == 1:
        x = x[:, None]
    w = wave.open(path, 'wb')
    w.setnchannels(x.shape[1]); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((x * 32767).astype(np.int16).tobytes()); w.close()


def loudness(path):
    """{'I': LUFS, 'TP': dBTP, 'LRA': LU} measured by ffmpeg loudnorm (EBU R128)"""
    r = run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-vn', '-af',
             'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'])
    js = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr)
    if not js:
        return None
    m = json.loads(js[-1])
    return {'I': float(m['input_i']), 'TP': float(m['input_tp']), 'LRA': float(m['input_lra']), 'ham': m}


# ---- outputs the kit wrote: a small manifest per folder, so --ustune-yaz can never replace a user's own file ----
MANIFEST = '.alet-yazdi.json'


def _man(d):
    try:
        return json.load(open(os.path.join(d, MANIFEST), encoding='utf-8'))
    except Exception:
        return {}


def alet_listesi(d):
    """names the kit recorded as written inside folder d"""
    return list(_man(d)) if os.path.isdir(d) else []


def alet_yazdi_mi(path):
    d, ad = os.path.split(os.path.abspath(path))
    return ad in _man(d)


def yazma_izni(path, ustune):
    """exit unless `path` is free, or --ustune-yaz was given AND a kit tool wrote `path` before"""
    if not os.path.exists(path):
        return
    if alet_yazdi_mi(path):
        if ustune:
            return
        sys.exit('cikti zaten var: %s (aletler yazmisti; ustune yazmak icin --ustune-yaz ekle)' % path)
    sys.exit('cikti zaten var ve aletler yazmadi: %s (senin dosyan olabilir; baska bir ad ver)' % path)


def yazildi(path, arac, girdiler=None):
    """record that `arac` wrote `path` (file or folder). girdiler = {"goruntu": path, "ses": path}: the files this
    output was made from, so alet/kontrol.py can tell when one of them is newer than the output (a stale output)."""
    d, ad = os.path.split(os.path.abspath(path))
    m = _man(d)
    m[ad] = {'arac': arac, 'girdiler': {k: os.path.abspath(v) for k, v in girdiler.items() if v}} if girdiler else arac
    tmp = os.path.join(d, MANIFEST + '.%d.yari' % os.getpid())
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(d, MANIFEST))


def alet_kaydi(path):
    """what the kit recorded about `path`: {"arac": ..., "girdiler": {...}} (girdiler may be empty), or None"""
    d, ad = os.path.split(os.path.abspath(path))
    k = _man(d).get(ad)
    if k is None:
        return None
    return k if isinstance(k, dict) else {'arac': k, 'girdiler': {}}


def gecici_ad(path):
    """a sibling name for writing first; os.replace onto `path` only after success, so no half-written file stays"""
    kok, uz = os.path.splitext(path)
    return kok + '.yari' + uz


# ---- speech energy and word-boundary snapping (Whisper word times can be off by 0.1-1 s) ----
HOP = 0.01


def konusma_db(x, sr=SR):
    """dB per 10 ms of the speech band (250-4000 Hz) of a mono or (n, ch) signal"""
    from scipy import signal
    m = x.mean(1) if x.ndim > 1 else x
    y = signal.sosfilt(signal.butter(4, [250, 4000], btype='band', fs=sr, output='sos'), m)
    h, w = int(HOP * sr), int(0.03 * sr)
    n = max(0, (len(y) - w) // h + 1)
    if n == 0:
        return np.zeros(0)
    idx = np.arange(w)[None, :] + h * np.arange(n)[:, None]
    return 10 * np.log10((y[idx] ** 2).mean(1) + 1e-12)


def kelime_hizala(e, t0, ws, we, alt=None, ust=None):
    """Snap one word to the energy of the speech band. e = konusma_db(), t0 = time of e[0].
    Looks for the loudest stretch inside Whisper's span widened by 0.4 s (but not past alt/ust, the neighbour words),
    then walks out from its peak while the level stays in the upper part between the local floor and the peak
    (gaps up to 80 ms are bridged). Returns (start, end, contrast_dB); contrast under 10 dB = not reliable."""
    def i_of(t):
        return int(round((t - t0) / HOP))
    lo = ws - 0.4 if alt is None else max(ws - 0.4, alt)
    hi = we + 0.4 if ust is None else min(we + 0.4, ust)
    a, b = max(0, i_of(lo)), min(len(e), i_of(hi))
    if b - a < 5:
        return ws, we, 0.0
    ctx = e[max(0, i_of(ws - 1.5)):min(len(e), i_of(we + 1.5))]
    floor = np.percentile(ctx, 15)
    seg = e[a:b]
    peak = np.percentile(seg, 97)
    if peak - floor < 6:
        return ws, we, float(peak - floor)
    thr = floor + 0.35 * (peak - floor)
    on = seg > thr
    gap = int(0.08 / HOP)
    # longest run of "on" frames with gaps <= 80 ms bridged
    runs, s, last = [], None, None
    for i, v in enumerate(on):
        if v:
            if s is None:
                s = i
            elif i - last > gap:
                runs.append((s, last)); s = i
            last = i
    if s is not None:
        runs.append((s, last))
    if not runs:
        return ws, we, float(peak - floor)
    # the run carrying most energy above the threshold
    best = max(runs, key=lambda r: float(np.sum(seg[r[0]:r[1] + 1] - thr)))
    s = t0 + (a + best[0]) * HOP
    t = t0 + (a + best[1] + 1) * HOP + 0.02          # +20 ms: the 30 ms window ends after the last loud frame
    if alt is not None:
        s = max(s, alt)
    if ust is not None:
        t = min(t, ust)                                # never into the next word
    return round(s, 3), round(max(t, s + 0.03), 3), float(peak - floor)


def konusma_sonu(a):
    """The end-of-speech measure alet/kontrol.py 'son' judges with. a = mono signal at SR.
    Returns (r, ref, t_last): r = level in dB per 20 ms, ref = its 95th percentile, t_last = end of the last 20 ms
    step louder than ref - 25 dB (0 when nothing is)."""
    win = int(0.02 * SR)
    nw = len(a) // win
    if nw == 0:
        return np.full(1, -180.0), -180.0, 0.0
    r = 20 * np.log10(np.sqrt((a[:nw * win].reshape(nw, win) ** 2).mean(1)) + 1e-9)
    ref = float(np.percentile(r, 95))
    above = np.where(r > ref - 25)[0]
    return r, ref, ((above[-1] + 1) * win / SR if len(above) else 0.0)


def son_80ms(r, dur):
    """loudest 20 ms step in the last 80 ms of a picture `dur` s long, without its final 20 ms (kontrol.py 'son')"""
    e = min(len(r), int(round(dur / 0.02)))
    return float(r[max(0, e - 4):max(1, e - 1)].max() if e > 4 else r.max())


def bitis_karesi(a, fps, pay=0.05):
    """Frame count of a picture that ends just after the last heard speech of `a` (mono, SR): 0 to 0.095 s after it
    (kontrol.py allows 0.10) with a quiet tail, as close to `pay` s after it as possible. Returns (frames, t_last)."""
    r, ref, t = konusma_sonu(a)
    en_iyi = None
    for k in range(max(1, int(t * fps)), int((t + 0.10) * fps) + 2):
        dur = k / fps
        gap = dur - t
        if 0.0 <= gap <= 0.095 and son_80ms(r, dur) <= ref - 6:
            if en_iyi is None or abs(gap - pay) < abs(en_iyi[1] - pay):
                en_iyi = (k, gap)
    return (en_iyi[0] if en_iyi else int(np.ceil((t + pay) * fps - 1e-9))), t


def font_esc(p):
    return p.replace('\\', '/').replace(':', '\\:')


ETIKET_FONT = font_esc(r'C:\Windows\Fonts\arialbd.ttf' if os.path.exists(r'C:\Windows\Fonts\arialbd.ttf')
                       else r'C:\Windows\Fonts\arial.ttf')
