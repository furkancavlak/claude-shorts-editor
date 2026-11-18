# -*- coding: utf-8 -*-
"""zaman.py - ONE time map drives picture and sound together: pieces of the source, each at its own speed,
eased speed changes, jumps between pieces (internal cuts). Writes the retimed video, the retimed audio and every
word/event time on the new timeline. Stops with an error if any output frame would repeat a source frame
(that would be fake slow motion).

Map file (JSON, source seconds):
  {"kaynak": "kayit.mp4",                      (or give --kaynak / --is)
   "fps": 30,
   "parcalar": [
     {"bas": 12.30, "son": 20.40, "hiz": 1.0},
     {"bas": 20.40, "son": 20.93, "hiz": 0.5, "yumusat": 0.12},   speed eases from the previous piece over 0.12 s
     {"bas": 20.93, "son": 23.95, "hiz": 1.0, "yumusat": 0.14},
     {"bas": 24.85, "son": 28.54, "hiz": 1.0}],                    a gap = a cut (20 ms audio crossfade)
   "olaylar": {"olum": 20.95}}                  optional named source moments you found with kare_bak.py
Pieces must go forward in source time. A piece touching the previous one (bas == previous son) continues it.

Example:  py -3 alet/zaman.py harita.json --cikti is/zaman --is panel/isler/<is-id> --yuz
          (changed the map? run again with --ustune-yaz: replaces only what zaman.py wrote there)
          py -3 alet/zaman.py harita.json --cikti is/zaman --kelimeler yazi.json --ek "yakin=crop=640:360:640:360,scale=1920:1080"
"""
import argparse, json, os, shutil, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortak import bilgi, ses_oku, wav_yaz, SR, alet_yazdi_mi, alet_listesi, yazildi
from kelime import hizala_liste

DS = 1e-4


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def kos_kur(parcalar):
    """group touching pieces into runs; each run: S grid and T grid (relative to run start)"""
    kos, cur = [], []
    for i, p in enumerate(parcalar):
        if i and p['bas'] < parcalar[i - 1]['son'] - 1e-6:
            sys.exit('parcalar kaynakta ileri gitmeli: %s' % p)
        if cur and abs(p['bas'] - cur[-1]['son']) < 1e-6:
            cur.append(p)
        else:
            if cur:
                kos.append(cur)
            cur = [p]
    kos.append(cur)
    out = []
    for run in kos:
        S = np.arange(run[0]['bas'], run[-1]['son'] + DS / 2, DS)
        v = np.ones_like(S)
        prev = None
        for p in run:
            h = float(p.get('hiz', 1.0))
            if h <= 0:
                sys.exit('hiz 0 dan buyuk olmali')
            m = (S >= p['bas'] - 1e-9) & (S <= p['son'] + 1e-9)
            y = float(p.get('yumusat', 0) or 0)
            if prev is not None and y > 0:
                w = smooth((S[m] - p['bas']) / y)
                v[m] = prev + (h - prev) * w
            else:
                v[m] = h
            prev = h
        T = np.concatenate([[0], np.cumsum(DS / v[:-1])])
        out.append({'S': S, 'T': T, 'bas': run[0]['bas'], 'son': run[-1]['son']})
    t0 = 0.0
    for r in out:
        r['T0'] = t0
        t0 += r['T'][-1]
    return out, t0


def s_of_t(kos, T):
    """source second for an output second (scalar)"""
    for r in kos:
        if T <= r['T0'] + r['T'][-1] + 1e-9:
            return float(np.interp(T - r['T0'], r['T'], r['S'])), r
    r = kos[-1]
    return float(r['S'][-1]), r


def t_of_s(kos, S):
    for r in kos:
        if r['bas'] - 1e-9 <= S <= r['son'] + 1e-9:
            return round(r['T0'] + float(np.interp(S, r['S'], r['T'])), 4)
    return None


def is_oku(is_dir):
    """files the motor already left in a panel job folder"""
    out = {}
    for rel in ['yazi/yazi.json', 'yazi.json']:
        p = os.path.join(is_dir, rel)
        if os.path.exists(p):
            out['kelimeler'] = p; break
    for rel in ['klip_plan.json', 'kamera/kamera.json']:
        p = os.path.join(is_dir, rel)
        if os.path.exists(p):
            d = json.load(open(p, encoding='utf-8'))
            if 'kamera' in d and d['kamera']:
                out.setdefault('kamera', d['kamera'])
            if rel == 'klip_plan.json' and d.get('kaynak'):
                k = d['kaynak']
                out.setdefault('kaynak', k if os.path.isabs(k) else os.path.normpath(os.path.join(is_dir, k)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('harita', help='map JSON (see above)')
    ap.add_argument('--cikti', required=True, help='output folder (new, or one zaman.py wrote before with --ustune-yaz)')
    ap.add_argument('--kaynak', help='source video (overrides the map / job)')
    ap.add_argument('--is', dest='is_dir', help='panel job folder: reads yazi/yazi.json, klip_plan.json (kaynak, kamera) if present')
    ap.add_argument('--kelimeler', help='word timings JSON {"kelimeler": [[word, start, end, p], ...]} in source seconds; '
                    'wins over the map\'s "kelimeler" and over --is (its yazi/yazi.json is then not read)')
    ap.add_argument('--yuz', action='store_true', help='also write yuz.mp4: the streamer camera box (from the job, or --kamera) 4x upscaled')
    ap.add_argument('--kamera', help='camera box x0,y0,x1,y1 as 0-1 of the frame (overrides the job)')
    ap.add_argument('--ek', action='append', default=[], help='extra video from the retimed one: "name=ffmpeg filter" (repeatable)')
    ap.add_argument('--yuz-ic', type=int, default=4, help='inset in source px for --yuz so the stream\'s own camera frame does not show (default 4)')
    ap.add_argument('--ustune-yaz', action='store_true', help='replace an output folder zaman.py wrote before (never a folder it did not write)')
    ap.add_argument('--crf', type=int, default=12)
    a = ap.parse_args()

    H = json.load(open(a.harita, encoding='utf-8'))
    job = is_oku(a.is_dir) if a.is_dir else {}
    kaynak = a.kaynak or H.get('kaynak') or job.get('kaynak')
    if kaynak and not os.path.isabs(kaynak) and not os.path.exists(kaynak):
        kaynak = os.path.join(os.path.dirname(os.path.abspath(a.harita)), kaynak)
    if not kaynak:
        sys.exit('kaynak video yok: haritaya "kaynak" yaz ya da --kaynak / --is ver')
    hedef = os.path.normpath(a.cikti)
    if os.path.exists(hedef) and os.listdir(hedef):
        if not alet_yazdi_mi(hedef):
            sys.exit('cikti klasoru bos degil ve aletler yazmadi: %s (yeni bir klasor ver)' % hedef)
        if not a.ustune_yaz:
            sys.exit('cikti klasoru zaten var: %s (zaman.py yazmisti; yenisiyle degistirmek icin --ustune-yaz ekle)' % hedef)
    # write into a sibling folder first; only a finished run replaces the old outputs, a failed one leaves nothing
    tmp = hedef + '.yari'
    if os.path.exists(tmp):
        sys.exit('yarim kalmis bir klasor var: %s (eski bir calismadan; icine bak, sonra sil ya da baska --cikti ver)' % tmp)
    os.makedirs(tmp)
    try:
        isle(a, H, job, kaynak, tmp)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    os.makedirs(hedef, exist_ok=True)
    eski = [f for f in alet_listesi(hedef) if os.path.exists(os.path.join(hedef, f))]
    for f in eski:                                     # only files zaman.py itself wrote there before
        os.remove(os.path.join(hedef, f))
    for f in os.listdir(tmp):
        os.replace(os.path.join(tmp, f), os.path.join(hedef, f))
        yazildi(os.path.join(hedef, f), 'zaman.py')
    os.rmdir(tmp)
    yazildi(hedef, 'zaman.py')
    print('CIKTI   %s  (video.mp4, ses.wav, zamanlar.json, zamanlar.js)%s' % (
        os.path.abspath(hedef), '  eskisinin yerine yazildi' if eski else ''))


def isle(a, H, job, kaynak, C):
    """everything the map produces, written into folder C"""
    fps = float(H.get('fps', 30))
    b = bilgi(kaynak)
    v = b['video']
    V0, SF, W, Hh = v['bas'], v['fps'], v['w'], v['h']
    parcalar = H['parcalar']
    for p in parcalar:
        if float(p.get('hiz', 1)) < fps / SF - 1e-9:
            sys.exit('HATA: %.2fx bu kaynakta kare kopyalar (kaynak %g fps, cikti %g fps; en dusuk %.2fx). '
                     'Daha yavas istiyorsan baska yol bul, kare kopyalama.' % (float(p['hiz']), SF, fps, fps / SF))
    kos, T_END = kos_kur(parcalar)
    N = int(round(T_END * fps))
    T_END_FR = N / fps
    Sf = np.array([s_of_t(kos, f / fps)[0] for f in range(N)])
    K = np.round((Sf - V0) * SF).astype(int)
    dup = np.where(np.diff(K) <= 0)[0]
    if len(dup):
        sys.exit('HATA: kare kopyasi/geri gidis, cikti kareleri %s (kaynak kare %s). Hizi ya da yumusatmayi degistir.'
                 % (dup[:10].tolist(), K[dup[:10]].tolist()))
    print('HARITA  %d parca, %d kesme, cikti %.3f sn = %d kare @ %g fps; kaynak kareleri %d..%d'
          % (len(parcalar), len(kos) - 1, T_END_FR, N, fps, K[0], K[-1]))

    # ---- picture: decode only the needed range, keep the mapped frames ----
    out_v = os.path.join(C, 'video.mp4')
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', kaynak, '-map', '0:v:0',
                            '-vf', 'select=between(n\\,%d\\,%d)' % (K[0], K[-1]), '-vsync', '0',
                            '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, Hh),
                            '-r', '%g' % fps, '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', str(a.crf), '-g', '10',
                            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out_v], stdin=subprocess.PIPE)
    want, fsz, k, yaz = set(K.tolist()), W * Hh * 3, int(K[0]), 0
    while k <= K[-1]:
        buf = dec.stdout.read(fsz)
        if len(buf) < fsz:
            break
        if k in want:
            enc.stdin.write(buf); yaz += 1
        k += 1
    enc.stdin.close(); enc.wait(); dec.stdout.close(); dec.wait()
    if yaz != N:
        sys.exit('HATA: %d kare yazildi, %d bekleniyordu (kaynak VFR olabilir; once sabit fps e cevir)' % (yaz, N))

    # ---- sound: same map, varispeed inside a run, 20 ms crossfade at cuts ----
    s_lo, s_hi = parcalar[0]['bas'] - 0.1, parcalar[-1]['son'] + 0.1
    x = ses_oku(kaynak, bas=max(0, s_lo), sure=s_hi - max(0, s_lo))
    a0 = max(0, s_lo)
    n = int(round(T_END_FR * SR))
    t = np.arange(n) / SR
    y = np.zeros((n, 2))
    XF = 0.02

    def samp(S):
        idx = (S - a0) * SR
        i0 = np.clip(np.floor(idx).astype(int), 0, len(x) - 2)
        fr = (idx - i0)[:, None]
        return x[i0] * (1 - fr) + x[i0 + 1] * fr
    for i, r in enumerate(kos):
        lo, hi = r['T0'], r['T0'] + r['T'][-1]
        m = (t >= lo - XF) & (t < hi + XF)
        tt = t[m] - r['T0']
        S = np.interp(tt, r['T'], r['S'], left=np.nan, right=np.nan)
        S = np.where(tt < 0, r['S'][0] + tt, S)
        S = np.where(tt > r['T'][-1], r['S'][-1] + (tt - r['T'][-1]), S)
        g = np.ones(m.sum())
        if i > 0:
            g *= smooth((t[m] - (lo - XF / 2)) / XF)
        if i < len(kos) - 1:
            g *= 1 - smooth((t[m] - (hi - XF / 2)) / XF)
        y[m] += samp(S) * g[:, None]
    fe = int(0.01 * SR)
    y[-fe:] *= np.linspace(1, 0, fe)[:, None]
    wav_yaz(os.path.join(C, 'ses.wav'), y)

    # ---- extra views (camera box, crops) from the retimed picture ----
    ek = list(a.ek)
    kam = [float(z) for z in a.kamera.split(',')] if a.kamera else job.get('kamera')
    if a.yuz:
        if not kam:
            sys.exit('--yuz icin kamera kutusu yok (--kamera x0,y0,x1,y1 ya da --is)')
        x0, y0, x1, y1 = [int(round(c * d)) for c, d in zip(kam, [W, Hh, W, Hh])]
        ic = max(0, int(a.yuz_ic))      # inset: the stream's own frame/border around the camera must not show
        x0, y0, x1, y1 = x0 + ic, y0 + ic, x1 - ic, y1 - ic
        cw, ch = (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2
        ek.append('yuz=crop=%d:%d:%d:%d,scale=%d:%d:flags=lanczos,unsharp=5:5:0.55' % (cw, ch, x0, y0, cw * 4, ch * 4))
    for e in ek:
        name, flt = e.split('=', 1)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', out_v, '-vf', flt, '-c:v', 'libx264', '-preset', 'medium',
                        '-crf', str(a.crf + 1), '-g', '10', '-pix_fmt', 'yuv420p', os.path.join(C, name + '.mp4')], check=True)
        print('EK      %s.mp4  (%s)' % (name, flt))

    # ---- times on the new timeline ----
    kel_path = a.kelimeler or H.get('kelimeler') or job.get('kelimeler')
    kel = []
    yarim_bas = []
    if kel_path:
        d = json.load(open(kel_path, encoding='utf-8'))
        src = d.get('kelimeler', [])
        # Whisper word times can be off by up to ~1 s; the words at piece edges decide "cut in half", so snap those
        # to the sound first (kelime.py does the same on demand). Skipped if the file is already snapped.
        if 'hizalama' not in d:
            kenar = [i for i, w in enumerate(src) for r in kos
                     if any(w[1] - 0.6 <= e <= w[2] + 0.6 for e in (r['bas'], r['son']))]
            kenar = sorted(set(kenar))
            if kenar:
                src, rapor = hizala_liste(kaynak, src, kenar)
                for i, w, s0, e0, s1, e1, c, ok in rapor:
                    if ok and (abs(s1 - s0) >= 0.05 or abs(e1 - e0) >= 0.05):
                        print('HIZALAMA %-14s Whisper %.2f-%.2f -> ses %.2f-%.2f' % (w[:14], s0, e0, s1, e1))
        for w in src:
            ts, te = t_of_s(kos, w[1]), t_of_s(kos, w[2])
            if ts is not None and te is None and t_of_s(kos, w[2] - 0.03) is not None:
                te = t_of_s(kos, w[2] - 0.03) + 0.03     # only the last 30 ms (breath/tail) are past the cut: not cut
            if ts is not None:
                # [word, start, end, source start, cut]  cut = the word goes on past the end of its piece
                kel.append([w[0], ts, te if te is not None else ts, round(w[1], 3), te is None])
            elif te is not None:
                yarim_bas.append(w[0])     # starts before its piece: only its tail is in the clip
    olay = {k_: t_of_s(kos, s) for k_, s in (H.get('olaylar') or {}).items()}
    kes = [round(float(r['T0']), 4) for r in kos[1:]]
    Z = {'fps': fps, 'sure': T_END_FR, 'kare': N, 'en': W, 'boy': Hh, 'kaynak': os.path.abspath(kaynak),
         'kesmeler': kes, 'parcalar': [{'bas': r['bas'], 'son': r['son'], 'T_bas': round(r['T0'], 4),
                                        'T_son': round(r['T0'] + r['T'][-1], 4)} for r in kos],
         'olaylar': olay, 'kelimeler': kel, 'kamera': kam,
         'kare_kaynak_sn': [round(float(s), 4) for s in Sf]}
    json.dump(Z, open(os.path.join(C, 'zamanlar.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(C, 'zamanlar.js'), 'w', encoding='utf-8').write('window.ZAMAN = ' + json.dumps(Z, ensure_ascii=False) + ';\n')
    print('KESMELER (cikti sn) %s' % kes)
    for k_, T in olay.items():
        print('OLAY    %-12s %s' % (k_, T if T is not None else 'kesilen kisimda (klipte yok)'))
    if kel:
        print('KELIMELER (cikti sn: kelime)')
        print('  ' + '  '.join('%.2f:%s' % (w[1], w[0]) for w in kel))
        print('  son kelime biter: %.3f sn (Whisper sonu; gercek bitisi kontrol.py son ile olc)' % kel[-1][2])
        kes_k = [w[0] for w in kel if w[4]]
        if kes_k:
            print('  UYARI: parca sonunda yarida kalan kelime(ler): %s' % ', '.join(kes_k))
        if yarim_bas:
            print('  UYARI: parca basinda yarim giren kelime(ler) (yazida yok): %s' % ', '.join(yarim_bas))


if __name__ == '__main__':
    main()
