# -*- coding: utf-8 -*-
"""ses.py - sound with code only (no samples, no music): make short sounds, mix them under the voice, measure, attach.

  uret   one sound into a wav, to try it:       py -3 alet/ses.py uret vuus deneme.wav --sure 0.6 --db -20
  miks   voice + your cue list -> mastered wav:  py -3 alet/ses.py miks is/zaman/ses.wav isaretler.json is/ses-final.wav
  olc    loudness of any audio/video:            py -3 alet/ses.py olc is/klip.mp4
  ekle   put the final sound on the rendered picture (video copied, not re-encoded):
                                                 py -3 alet/ses.py ekle render/goruntu.mp4 is/ses-final.wav is/klip.mp4
         second round (new render or new mix): the same command + --ustune-yaz replaces an output ekle wrote before
         (never a file it did not write). It records its inputs, so kontrol.py hepsi fails on an output older than them.

Sound kinds (all synthesized, every parameter optional):
  tik   short clock click           (f0 = pitch, default 1650 Hz)
  vuus  whoosh, filtered noise sweep (sure; f0 -> f1 = sweep, e.g. 500 -> 3500 up, 3000 -> 400 down)
  gum   soft low thump              (f0 default 70 Hz, sure)
  darbe big impact: sub boom + crack + tail
  flas  bright noise burst + thin high ring (f0 = ring pitch, default 3400 Hz)
  dusus falling tone, "time slows" (f0 -> f1, default 320 -> 45 Hz)
  suzul fast short swish            (sure default 0.22)
Cue list (isaretler.json): [{"t": 9.13, "tur": "darbe", "db": -6}, {"t": 7.1, "tur": "vuus", "db": -25, "sure": 0.7,
  "f0": 400, "f1": 3000}, ...]   t = the second on the edit timeline where the sound should be HEARD to land
  (whoosh: its loudest point; impacts: their attack). db = peak level in dBFS before mastering.
miks: the voice is first set to --ses-hedef LUFS (default -16), the cues are added, then the whole mix is mastered to
about -14 LUFS / -1.5 dBTP. It prints the cue sheet and the voice, effects and final loudness. If the true peak is still
over the ceiling, a 4x-oversampled limiter brings it under (printed). Holding the peak ceiling can leave a short, punchy
mix a little under the target (measured -14.1 to -14.9); a gap over 0.5 LU is printed as a NOT line.
Info Short with a bed (soft pad that dips under the voice, chord changes on your seconds):
     py -3 alet/ses.py miks ses.wav isaretler.json ses-final.wav --yatak -27 --akorlar 4.45,7.1,8.85,10.55
"""
import argparse, json, os, re, subprocess, sys
import numpy as np
from scipy import signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortak import ses_oku, wav_yaz, loudness, SR, run, alet_yazdi_mi, yazildi, gecici_ad

rng = np.random.default_rng(1117)


def db(x):
    return 10 ** (x / 20)


def _t(n):
    return np.arange(n) / SR


def _bp(x, lo, hi, o=2):
    return signal.sosfilt(signal.butter(o, [lo, hi], btype='band', fs=SR, output='sos'), x)


def _lp(x, f, o=2):
    return signal.sosfilt(signal.butter(o, f, btype='low', fs=SR, output='sos'), x)


def _hp(x, f, o=2):
    return signal.sosfilt(signal.butter(o, f, btype='high', fs=SR, output='sos'), x)


def _n(x):
    return x / (np.max(np.abs(x)) + 1e-12)


def tik(f0=1650, **_):
    n = int(0.06 * SR); t = _t(n)
    b = np.sin(2 * np.pi * f0 * t) * np.exp(-t / 0.012) + 0.5 * np.sin(4 * np.pi * f0 * t) * np.exp(-t / 0.006)
    return _n(b + 0.6 * _hp(rng.standard_normal(n), 2500) * np.exp(-t / 0.0025)), 0.0


def vuus(sure=0.6, f0=500, f1=3500, tepe=0.55, **_):
    n = int(sure * SR); u = np.linspace(0, 1, n); x = rng.standard_normal(n); out = np.zeros(n)
    for i in range(0, n, 1024):
        fc = f0 * (f1 / f0) ** u[min(i, n - 1)]
        y = _bp(x[max(0, i - 2048):i + 1024], max(60, fc * 0.45), min(SR / 2 - 100, fc * 1.6), 1)
        out[i:i + 1024] = y[-len(out[i:i + 1024]):]
    env = np.where(u < tepe, (u / tepe) ** 2, ((1 - u) / (1 - tepe)) ** 1.6)
    return _n(out * env), tepe * sure


def gum(f0=70, sure=0.35, **_):
    n = int(sure * SR); t = _t(n)
    ph = 2 * np.pi * np.cumsum(f0 * (1 + 0.8 * np.exp(-t / 0.03))) / SR
    return _n(np.sin(ph) * np.exp(-t / (sure / 4)) + 0.3 * _lp(rng.standard_normal(n), 3000) * np.exp(-t / 0.004)), 0.004


def darbe(**_):
    n = int(1.4 * SR); t = _t(n)
    ph = 2 * np.pi * np.cumsum(38 + 70 * np.exp(-t / 0.08)) / SR
    x = np.sin(ph) * np.exp(-t / 0.42) + 0.55 * _bp(rng.standard_normal(n), 900, 7000) * np.exp(-t / 0.03)
    return _n(x + 0.25 * _lp(rng.standard_normal(n), 900) * np.exp(-t / 0.35)), 0.003


def flas(f0=3400, **_):
    n = int(1.1 * SR); t = _t(n)
    burst = _n(_hp(rng.standard_normal(n), 2200) * np.exp(-t / 0.07) * (1 - np.exp(-t / 0.004)))
    ring = np.sin(2 * np.pi * f0 * t) * np.exp(-t / 0.35) * (1 - np.exp(-t / 0.02))
    return _n(burst + db(-14) * ring), 0.004


def dusus(f0=320, f1=45, sure=0.55, **_):
    n = max(2, int(sure * SR)); t = _t(n)
    ph = 2 * np.pi * np.cumsum(f0 * (f1 / f0) ** (t / t[-1])) / SR
    # sin(pi * 1.0) can come out a hair below 0 for some lengths; a negative number to the power 0.7 is NaN and the
    # whole sound went silent: clip to 0 first
    x = np.sin(ph) * np.clip(np.sin(np.pi * t / t[-1]), 0, None) ** 0.7 + 0.3 * _bp(rng.standard_normal(n), 150, 1200) * np.exp(-t / 0.15)
    return _n(x), 0.02


def suzul(sure=0.22, **_):
    x, _ = vuus(sure, 900, 5000, 0.7)
    return x, 0.7 * sure


TURLER = {'tik': tik, 'vuus': vuus, 'gum': gum, 'darbe': darbe, 'flas': flas, 'dusus': dusus, 'suzul': suzul}


def yatak(n, akorlar, kok=53):
    """soft synthesized pad (no samples): minor-key chords i, VI, III, VII in turn, one change at each given second,
    a low sine root under it, slow pulse. (n, 2) array, peak about 1."""
    sira = [[0, 3, 7, 12], [-4, 0, 3, 8], [3, 7, 10, 15], [-2, 2, 5, 10]]
    t = _t(n)
    out = np.zeros((n, 2))
    ak = sorted(set([0.0] + [float(z) for z in akorlar]))
    for ci, t0 in enumerate(ak):
        t1 = ak[ci + 1] if ci + 1 < len(ak) else n / SR + 0.5
        i0, i1 = int(t0 * SR), min(n, int((t1 + 0.25) * SR))
        if i1 <= i0:
            continue
        seg = t[i0:i1] - t0
        w = np.minimum(1, seg / 0.06) * np.where(seg > t1 - t0, np.clip(1 - (seg - (t1 - t0)) / 0.25, 0, 1), 1)
        notes = [kok + z for z in sira[ci % len(sira)]]
        for side, det in ((0, -0.35), (1, 0.35)):
            s = np.zeros(i1 - i0)
            for j, m in enumerate(notes):
                ph = (440 * 2 ** ((m - 69) / 12) + det * (1 + j * 0.3)) * seg
                s += (2 * (ph % 1) - 1) / (1 + 0.4 * j)
            out[i0:i1, side] += _lp(s, 1100) * w * 0.16
        root = 440 * 2 ** ((notes[0] - 12 - 69) / 12)
        out[i0:i1] += (np.sin(2 * np.pi * root * seg) * w * (0.55 + 0.45 * np.exp(-seg / 0.4)) * 0.2)[:, None]
    return _n(out * (0.86 + 0.14 * np.cos(2 * np.pi * (100 / 60 * 2) * t) ** 2)[:, None])


def egilim(v, derin=0.5, sal=0.12):
    """gain that dips the bed under the voice: 1 in silence, 1-derin while speaking; fast attack, `sal` s release"""
    e = signal.lfilter([1 - np.exp(-1 / (SR * 0.06))], [1, -np.exp(-1 / (SR * 0.06))], np.abs(v))
    ref = np.percentile(e, 95) + 1e-9
    g = 1 - derin * np.clip(e / ref, 0, 1) ** 0.5
    a = np.exp(-1 / (SR * sal))
    out = np.empty_like(g); cur = 1.0
    for i, x in enumerate(g):            # follow dips at once, come back slowly
        cur = x if x < cur else x + (cur - x) * a
        out[i] = cur
    return out


def sinirla(x, tavan):
    """look-ahead limiter on the 4x-oversampled (true) peak: no true peak passes `tavan` (linear). x: (n, kanal)"""
    up = np.stack([signal.resample_poly(x[:, c], 4, 1) for c in range(x.shape[1])])
    pk = np.abs(up).max(0)[: 4 * len(x)].reshape(-1, 4).max(1)[: len(x)]
    need = np.minimum(1.0, tavan / np.maximum(pk, 1e-9))
    la = int(0.002 * SR)
    from numpy.lib.stride_tricks import sliding_window_view
    gmin = sliding_window_view(np.concatenate([need, np.ones(la)]), la + 1).min(1)[: len(need)]
    a = np.exp(-1 / (SR * 0.08))
    g = np.empty_like(gmin); cur = 1.0
    for i, z in enumerate(gmin):         # instant attack, 80 ms release
        cur = z if z < cur else z + (cur - z) * a
        g[i] = cur
    gs = np.convolve(np.concatenate([np.ones(la), g]), np.ones(la) / la, mode='valid')[: len(g)]
    return x * gs[:, None]


def yap(c):
    tur = c.get('tur')
    if tur not in TURLER:
        sys.exit('bilinmeyen ses turu %r; olanlar: %s' % (tur, ', '.join(TURLER)))
    sig, off = TURLER[tur](**{k: v for k, v in c.items() if k in ('sure', 'f0', 'f1', 'tepe')})
    return sig * db(float(c.get('db', -20))), off


def cmd_uret(a):
    c = {'tur': a.tur, 'db': a.db}
    for k in ('sure', 'f0', 'f1'):
        if getattr(a, k) is not None:
            c[k] = getattr(a, k)
    sig, off = yap(c)
    wav_yaz(a.cikti, np.repeat(sig[:, None], 2, 1))
    print('%s  %s  %.3f sn, duyulan an +%.3f sn, tepe %.1f dBFS' % (a.cikti, a.tur, len(sig) / SR, off,
                                                                   20 * np.log10(np.max(np.abs(sig)) + 1e-12)))


def lufs_of(x, tmp):
    wav_yaz(tmp, x)
    L = loudness(tmp)
    return L['I'] if L else None


def cmd_miks(a):
    v = ses_oku(a.ses)
    n = len(v)
    cues = json.load(open(a.isaretler, encoding='utf-8'))
    base = os.path.splitext(a.cikti)[0]
    vI = lufs_of(v, base + '.ses-ham.wav')
    g = a.ses_hedef - vI if vI is not None and vI > -70 else 0.0
    sfx = np.zeros(n)
    print('ISARETLER (cikti sn, tur, dB)')
    for c in sorted(cues, key=lambda c: c['t']):
        sig, off = yap(c)
        s0 = int(round((c['t'] - off) * SR))
        lo, hi = max(0, s0), min(n, s0 + len(sig))
        if hi > lo:
            sfx[lo:hi] += sig[lo - s0:hi - s0]
        print('  %7.3f  %-6s %6.1f%s' % (c['t'], c['tur'], float(c.get('db', -20)), '' if hi > lo else '  (klibin disinda!)'))
    mix = v * db(g) + sfx[:, None]
    bed_txt = None
    if a.yatak is not None:
        bed = yatak(n, [z for z in (a.akorlar or '').split(',') if z.strip()], a.yatak_kok)
        bI = lufs_of(bed, base + '.yatak.wav')
        bed = bed * db(a.yatak - bI) * egilim(v.mean(1), a.yatak_egilim)[:, None]
        wav_yaz(base + '.yatak.wav', bed)
        mix = mix + bed
        bed_txt = 'YATAK         %.1f LUFS (konusmada %.0f dB alcalir), akor degisimleri %s' % (
            a.yatak, 20 * np.log10(1 - a.yatak_egilim), a.akorlar or '0')
    pk = np.max(np.abs(mix))
    if pk > 0.97:
        mix *= 0.97 / pk
    wav_yaz(base + '.efekt.wav', np.repeat(sfx[:, None], 2, 1))
    wav_yaz(base + '.miks.wav', mix)
    L = loudness(base + '.miks.wav')
    m = L['ham']
    af = ('loudnorm=I=%g:TP=%g:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true'
          % (a.master, a.tepe, m['input_i'], m['input_tp'], m['input_lra'], m['input_thresh'], m['target_offset']))
    r = run(['ffmpeg', '-v', 'error', '-y', '-i', base + '.miks.wav', '-af', af + ',aresample=48000', '-ar', '48000',
             '-c:a', 'pcm_s16le', a.cikti])
    if r.returncode:
        sys.exit(r.stderr[-800:])
    F = loudness(a.cikti)
    lim = ''
    if F['TP'] > a.tepe + 0.05:
        # loudnorm can miss the true-peak ceiling on short, punchy mixes; a 4x-oversampled limiter fixes it
        once = F['TP']
        wav_yaz(a.cikti, sinirla(ses_oku(a.cikti), db(a.tepe - 0.2)))
        F = loudness(a.cikti)
        lim = '  (sinirlayici: tepe %.1f dBTP idi)' % once
    E = loudness(base + '.efekt.wav')
    print('SES (konusma) %.1f LUFS -> %+.1f dB ile %.1f LUFS' % (vI, g, a.ses_hedef))
    print('EFEKT         %s LUFS (sadece efektler)' % ('%.1f' % E['I'] if E and E['I'] > -70 else 'sessiz'))
    if bed_txt:
        print(bed_txt)
    print('SON           %.1f LUFS, tepe %.1f dBTP  -> %s%s' % (F['I'], F['TP'], a.cikti, lim))
    if F['TP'] > a.tepe + 0.1:
        print('UYARI         tepe hala %.1f dBTP (hedef %.1f)' % (F['TP'], a.tepe))
    if abs(F['I'] - a.master) > 0.5:
        print('NOT           hedef %.1f LUFS idi, %.1f LUFS cikti: tepe siniri (%.1f dBTP) korunurken kisa ve vurgulu bir '
              'karisim hedefin biraz altinda kalabilir. 1 LU icindeki fark Shorts icin sorun degil; daha fazlasinda en '
              'yuksek efektin dB degerini dusur.' % (a.master, F['I'], a.tepe))
    print('ARA DOSYALAR  %s.ses-ham.wav  %s.efekt.wav  %s.miks.wav%s' % (base, base, base,
                                                                      '  %s.yatak.wav' % base if bed_txt else ''))


def cmd_olc(a):
    L = loudness(a.dosya)
    if not L:
        sys.exit('ses yok ya da olculemedi')
    print('%s: %.1f LUFS, tepe %.1f dBTP, LRA %.1f' % (a.dosya, L['I'], L['TP'], L['LRA']))


def cmd_ekle(a):
    # an existing output is replaced only with --ustune-yaz and only when ses.py ekle wrote it (manifest, _ortak.py)
    ustune = os.path.exists(a.cikti)
    if ustune and not alet_yazdi_mi(a.cikti):
        sys.exit('cikti zaten var ve aletler yazdigi kayitli degil: %s (senin dosyan olabilir; ses.py ekle\'nin eski surumu '
                 'de kayit tutmuyordu). Sesi yeni bir ada ekle; teslim adi sartsa o yeni dosyayi kendi eski mp4\'unun '
                 'ustune tasi.' % a.cikti)
    if ustune and not a.ustune_yaz:
        sys.exit('cikti zaten var: %s (ses.py ekle yazmisti; ikinci turda ayni komuta --ustune-yaz ekle)' % a.cikti)
    if os.path.abspath(a.cikti) in (os.path.abspath(a.goruntu), os.path.abspath(a.ses)):
        sys.exit('cikti, girdilerden biriyle ayni dosya: %s' % a.cikti)
    # the sound is cut to the picture (frames / fps) so the mp4 never runs past its last frame
    n = run(['ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries',
             'stream=nb_read_packets,r_frame_rate', '-of', 'json', a.goruntu])
    st = json.loads(n.stdout)['streams'][0]
    fa, fb = (st['r_frame_rate'].split('/') + ['1'])[:2]
    dur = int(st['nb_read_packets']) / (float(fa) / float(fb))
    af = [] if a.kirpma else ['-af', 'atrim=end=%.6f' % dur]
    # written under a temporary name first and moved onto the output only when complete: no half-written mp4 stays
    tmp = gecici_ad(a.cikti)
    if os.path.exists(tmp):
        os.remove(tmp)                      # this tool's own leftover from a run that was stopped
    r = run(['ffmpeg', '-v', 'error', '-y', '-i', a.goruntu, '-i', a.ses, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy']
            + af + ['-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-movflags', '+faststart', tmp])
    if r.returncode:
        if os.path.exists(tmp):
            os.remove(tmp)
        sys.exit(r.stderr[-800:])
    os.replace(tmp, a.cikti)
    yazildi(a.cikti, 'ses.py ekle', {'goruntu': a.goruntu, 'ses': a.ses})
    sl = ses_oku(a.ses).shape[0] / SR
    print('BIRLESTI %s%s  (goruntu kopyalandi, ses AAC 256k; goruntu %.3f sn, ses %.3f sn%s)' % (
        a.cikti, ' (eskisinin ustune yazildi)' if ustune else '', dur, sl,
        '' if a.kirpma else (', ses goruntuye kesildi' if sl > dur + 0.001 else '')))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='komut', required=True)
    p = sp.add_parser('uret', help='make one sound'); p.add_argument('tur', choices=list(TURLER)); p.add_argument('cikti')
    p.add_argument('--db', type=float, default=-20); p.add_argument('--sure', type=float); p.add_argument('--f0', type=float)
    p.add_argument('--f1', type=float); p.set_defaults(f=cmd_uret)
    p = sp.add_parser('miks', help='voice + cue list -> mastered wav'); p.add_argument('ses'); p.add_argument('isaretler')
    p.add_argument('cikti'); p.add_argument('--ses-hedef', type=float, default=-16.0, help='voice LUFS before effects (default -16)')
    p.add_argument('--master', type=float, default=-14.0, help='final LUFS (default -14)')
    p.add_argument('--tepe', type=float, default=-1.5, help='final true peak dBTP (default -1.5)')
    p.add_argument('--yatak', type=float, help='add a soft synthesized pad under everything at this LUFS before mastering '
                   '(e.g. -27 = about 11 LU under the voice); off when not given')
    p.add_argument('--akorlar', help='seconds where the pad changes chord, e.g. "4.45,7.1,8.85" (list items, sections)')
    p.add_argument('--yatak-kok', type=int, default=53, help='pad key as a MIDI note of a minor root (default 53 = F)')
    p.add_argument('--yatak-egilim', type=float, default=0.5, help='how far the pad dips under the voice, 0-0.9 (default 0.5 = -6 dB)')
    p.set_defaults(f=cmd_miks)
    p = sp.add_parser('olc', help='measure loudness'); p.add_argument('dosya'); p.set_defaults(f=cmd_olc)
    p = sp.add_parser('ekle', help='attach sound to rendered picture (sound cut to the picture length)'); p.add_argument('goruntu'); p.add_argument('ses')
    p.add_argument('cikti'); p.add_argument('--kirpma', action='store_true', help='keep the whole sound even past the last frame')
    p.add_argument('--ustune-yaz', action='store_true', help='replace an output ses.py ekle wrote before (never a file it did not write)')
    p.set_defaults(f=cmd_ekle)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
