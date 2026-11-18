# -*- coding: utf-8 -*-
"""cekim.py - one shot of game/trailer footage -> a silent vertical clip (default 1080x1920, 30 fps) for a stage.
Exact source frames, black letterbox bars cut away, a 9:16 crop that can follow the subject, and speed changes that
never repeat a frame: faster = real frames skipped; slower than the source allows = only with --ara-kare
(motion interpolation). The source sound is not kept (trailer audio stays muted).

  bant  where is the real picture (letterbox bars?):
        py -3 alet/cekim.py bant fragman.mp4 --bas 34.6 --son 38.3
  kes   cut one shot:
        py -3 alet/cekim.py kes fragman.mp4 --bas 34.63 --son 38.33 --takip 34.63:0.46,36.9:0.61,38.33:0.71 --cikti is/v/pov.mp4
  zaman voice word timings -> zamanlar.json/js in the shots folder, then sahne_baslat.py --zaman is/v opens a stage:
        py -3 alet/cekim.py zaman is/v --kelimeler panel/isler/<id>/ses/ses.json
        Default length: ends just after the last HEARD speech of the voice (ses.wav next to the json, or --ses), measured
        the way kontrol.py 'son' measures it, so the last word is never cut; Whisper's last-word end can be early.
        --sure <s> sets another length (at most 0.10 s after the last word, or the check fails).

Times are SOURCE seconds, as kare_bak.py labels them. The shot starts on the source frame at --bas and holds every
frame up to --son (or --kare N source frames).
--takip s:x[:y],...  at source second s the crop centre sits at x (and y) as 0-1 of the real picture; smoothly eased
                     between keys, held before the first and after the last. No --takip = centre.
--yakin 1.3          crop 1.3x tighter than the widest 9:16 crop (then y in --takip matters too).
--alan oto|tam|w:h:x:y  real picture: oto = cropdetect over the shot (default), tam = whole frame.
Speed: --hiz 1 (default) = real speed. A 30 fps source then shows every source frame once; a 60 fps source shows
       every 2nd frame (the output is 30 fps), and --hiz 0.5 shows each of its frames once (half speed: the slowest
       real-frame speed, kaynak_bak.py says "en dusuk 0.50x").  --hiz 1.4 = skips real frames.
       --parcalar harita.json = a real-frame speed ramp, same "parcalar" list as zaman.py (bas, son, hiz, yumusat);
       --bas and --son are still needed with it (the first part's bas, the last part's son).
       --hiz 0.8 --ara-kare = slower than the source by motion interpolation; look at the result frame by frame
       (kare_bak.py --hiz kaynak): thin fast things (propellers, bars, hands) smear or double.
An existing output is refused; --ustune-yaz replaces it only if a kit tool wrote it (never your own file). A failed
run leaves no half-written file. Asking past the last frame of the file is clamped to the frames that exist.
It prints the source frames used and the frame count it wrote.
"""
import argparse, json, os, re, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortak import bilgi, run, yazma_izni, yazildi, gecici_ad, ses_oku, bitis_karesi
from zaman import kos_kur, s_of_t


def ss_of(V0, s):
    """-ss counts from the file's first frame; our seconds are the frame timestamps (what kare_bak.py prints).
    Seconds below the file's first timestamp are taken as already counted from the file start."""
    return max(0.0, s - V0 if V0 > 0 and s >= V0 - 0.02 else s)     # 25.39 for a first frame at 25.392 = that frame


def bant(video, bas, son):
    """real picture as (w, h, x, y) from cropdetect over bas..son (largest area seen)"""
    V0 = bilgi(video)['video']['bas']
    cmd = ['ffmpeg', '-hide_banner', '-nostats']
    ss = ss_of(V0, bas or 0)
    if ss > 0:
        cmd += ['-ss', '%.4f' % ss]
    cmd += ['-i', video, '-t', '%.4f' % max(0.2, son - (bas or 0)), '-an',
            '-vf', 'cropdetect=limit=0.09:round=2:reset=0', '-f', 'null', '-']
    r = run(cmd)
    m = re.findall(r'crop=(\d+):(\d+):(\d+):(\d+)', r.stderr)
    if not m:
        return None
    return tuple(int(z) for z in m[-1])


def anahtarlar(s):
    out = []
    for p in (s or '').split(','):
        if p.strip():
            z = [float(q) for q in p.split(':')]
            out.append((z[0], z[1], z[2] if len(z) > 2 else 0.5))
    return out


def ifade(pts):
    """ffmpeg expression of t: smoothstep between (t, value) keys, held at both ends"""
    if len(pts) == 1:
        return '%.1f' % pts[0][1]
    e = '%.1f' % pts[-1][1]
    for (ta, va), (tb, vb) in reversed(list(zip(pts[:-1], pts[1:]))):
        d = max(tb - ta, 1e-3)
        u = 'min(max((t-(%.4f))/%.4f,0),1)' % (ta, d)
        e = 'if(lt(t,%.4f),(%.1f+(%.1f)*(%s)*(%s)*(3-2*(%s))),%s)' % (tb, va, vb - va, u, u, u, e)
    return 'if(lt(t,%.4f),%.1f,%s)' % (pts[0][0], pts[0][1], e)


def cmd_bant(a):
    v = bilgi(a.video)['video']
    son = a.son if a.son is not None else (a.bas or 0) + 10
    b = bant(a.video, a.bas, son)
    if not b:
        sys.exit('cropdetect sonuc vermedi')
    w, h, x, y = b
    print('KAYNAK  %dx%d' % (v['w'], v['h']))
    print('GERCEK  %dx%d  x=%d y=%d   ->  --alan %d:%d:%d:%d' % (w, h, x, y, w, h, x, y))
    if (w, h) == (v['w'], v['h']):
        print('        bant yok')
    else:
        print('        siyah bant: ust %d, alt %d, sol %d, sag %d px. Karanlik sahnede cropdetect fazla kesebilir: '
              'kare_bak.py ile bak.' % (y, v['h'] - h - y, x, v['w'] - w - x))


def cmd_kes(a):
    yazma_izni(a.cikti, a.ustune_yaz)
    b = bilgi(a.video)
    v = b['video']
    V0, SF, W, H = v['bas'], v['fps'], v['w'], v['h']
    FPS = float(a.fps)
    K0 = int(round((a.bas - V0) * SF))
    if a.kare:
        n_src = int(a.kare)
    elif a.son is not None:
        n_src = int(round((a.son - V0) * SF)) - K0 + 1
    else:
        sys.exit('--son ya da --kare ver')
    s_first = V0 + K0 / SF
    son_k = kare_sayisi(a.video) - 1          # last frame that exists (a job's "bitis" is the end time, one frame later)
    if K0 < 0 or K0 > son_k:
        sys.exit('HATA: --bas %.3f dosyanin disinda (kareler %.3f-%.3f sn)' % (a.bas, V0, V0 + son_k / SF))
    if not a.parcalar and K0 + n_src - 1 > son_k:
        print('SINIR   istenen son kare k%d dosyada yok; son kare k%d (%.3f sn), %d kaynak karesi kullanilacak'
              % (K0 + n_src - 1, son_k, V0 + son_k / SF, son_k - K0 + 1))
        n_src = son_k - K0 + 1

    # ---- which source frame goes to which output frame ----
    interp = False
    if a.parcalar:
        P = json.load(open(a.parcalar, encoding='utf-8'))
        P = P['parcalar'] if isinstance(P, dict) else P
        kos, T_END = kos_kur(P)
        N = int(round(T_END * FPS))
        Ks = [int(round((s_of_t(kos, k / FPS)[0] - V0) * SF)) for k in range(N)]
        t_out = lambda s: next((r['T0'] + float(np.interp(s, r['S'], r['T']))
                                for r in kos if r['bas'] - 1e-9 <= s <= r['son'] + 1e-9),
                               0.0 if s < kos[0]['bas'] else T_END)
    else:
        hiz = hiz_t = float(a.hiz)
        oran = hiz * SF / FPS                      # source frames per output frame
        if 0.995 <= oran < 1 - 1e-9 and not a.ara_kare:
            # e.g. a 29.97 fps source at --hiz 1: every source frame once; the shot runs 0.1 % slow (not visible)
            hiz_t = SF / FPS
            N = n_src
            Ks = list(range(K0, K0 + n_src))
            print('NOT     kaynak %.3f fps, cikti %g fps: her kaynak karesi bir kez (%.2fx, fark gorunmez)' % (SF, FPS, hiz_t))
        elif oran < 1 - 1e-9:
            if not a.ara_kare:
                sys.exit('HATA: %.3fx bu kaynakta kare kopyalar (kaynak %.3f fps, cikti %g fps; gercek karelerle en dusuk %.3fx). '
                         'Ya hizi yukselt ya --ara-kare ile ara kare uret (sonra kare kare bak).' % (hiz, SF, FPS, FPS / SF))
            interp = True
            N = int(round(n_src / SF / hiz * FPS))
            Ks = list(range(K0, K0 + n_src))
        else:
            N = int((n_src - 1) / SF / hiz * FPS) + 1
            Ks = [K0 + int(round(k * hiz * SF / FPS)) for k in range(N)]
        t_out = lambda s: (s - s_first) / (1.0 if interp else hiz_t)
    if Ks[-1] > son_k:
        print('SINIR   parcalar dosyanin sonunu asiyor; son kare k%d (%.3f sn) sonrasi atildi' % (son_k, V0 + son_k / SF))
        Ks = [k for k in Ks if k <= son_k]
        N = len(Ks)
    if any(k2 <= k1 for k1, k2 in zip(Ks, Ks[1:])):
        sys.exit('HATA: kare kopyasi olurdu (kaynak kareleri %s...). Hizi degistir.' % Ks[:12])

    # ---- real picture and the 9:16 crop ----
    if a.alan == 'tam':
        aw, ah, ax, ay = W, H, 0, 0
    elif a.alan == 'oto':
        bb = bant(a.video, s_first, V0 + Ks[-1] / SF + 1 / SF)
        aw, ah, ax, ay = bb if bb else (W, H, 0, 0)
        if (aw, ah) != (W, H):
            print('BANT    gercek resim %dx%d x=%d y=%d (siyah bantlar kesildi; yanlissa --alan ver)' % (aw, ah, ax, ay))
    else:
        aw, ah, ax, ay = [int(z) for z in a.alan.split(':')]
    oran = a.en / a.boy
    ch = ah; cw = int(round(ch * oran / 2)) * 2
    if cw > aw:
        cw = aw // 2 * 2; ch = int(round(cw / oran / 2)) * 2
    cw = int(round(cw / a.yakin / 2)) * 2; ch = int(round(ch / a.yakin / 2)) * 2
    keys = anahtarlar(a.takip) or [(a.bas, 0.5, 0.5)]
    cl = lambda val, lo, span: min(max(val, lo), lo + span)
    xs = [(t_out(s), cl(ax + fx * aw - cw / 2, ax, aw - cw)) for s, fx, fy in keys]
    ys = [(t_out(s), cl(ay + fy * ah - ch / 2, ay, ah - ch)) for s, fx, fy in keys]
    crop = "crop=w=%d:h=%d:x='%s':y='%s',scale=%d:%d:flags=lanczos,setsar=1" % (cw, ch, ifade(xs), ifade(ys), a.en, a.boy)

    # ---- decode from a frame boundary half a frame before the first needed frame; select by index ----
    S0 = ss_of(V0, V0 + (Ks[0] - 0.5) / SF) if Ks[0] > 0 else 0.0
    if S0 == 0.0:      # no seek: timestamps start at the first frame, frame k sits at t = k / SF
        J0 = 0
        sel_t = 't*%.6f+0.5' % SF
    else:              # seek half a frame early: frame Ks[0] + m sits at t = (m + 0.5) / SF
        J0 = Ks[0]
        sel_t = 't*%.6f' % SF
    # minterpolate makes no frames after its last input frame, so it wrote 2-4 frames short: give it up to 4 source
    # frames past the shot (when the file has them); -frames:v N still stops at the asked length
    ek = max(0, min(4, son_k - Ks[-1])) if interp else 0
    vf = ("select='between(floor(%s),%d,%d)',setpts=N/%.6f/TB,%s,setpts=PTS/%.6f,"
          "minterpolate=fps=%g:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,setpts=N/%g/TB"
          % (sel_t, Ks[0] - J0, Ks[0] - J0 + n_src - 1 + ek, SF, crop, float(a.hiz), FPS, FPS)) if interp else None
    os.makedirs(os.path.dirname(os.path.abspath(a.cikti)), exist_ok=True)
    seek = ['-ss', '%.6f' % S0] if S0 > 0 else []
    tmp = gecici_ad(a.cikti)
    enc_opts = ['-frames:v', str(N), '-c:v', 'libx264', '-preset', 'medium', '-crf', str(a.crf), '-pix_fmt', 'yuv420p',
                '-g', '15', '-movflags', '+faststart', '-f', 'mp4', tmp]
    try:
        yaz_kes(a, interp, vf, seek, enc_opts, Ks, J0, sel_t, SF, W, H, FPS, crop, N)
        os.replace(tmp, a.cikti)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    yazildi(a.cikti, 'cekim.py')
    got = run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
               'stream=nb_read_frames', '-of', 'csv=p=0', a.cikti]).stdout.strip()
    print('KESIM   %s' % a.cikti)
    print('        kaynak kareleri %d..%d (%d kare, %.3f-%.3f sn), kirpma %dx%d -> %dx%d' % (
        Ks[0], Ks[-1], len(set(Ks)), V0 + Ks[0] / SF, V0 + Ks[-1] / SF, cw, ch, a.en, a.boy))
    print('        cikti %s kare @ %g fps = %.3f sn (beklenen %d kare)%s' % (
        got, FPS, int(got or 0) / FPS, N, '  ARA KARE: kare kare bak' if interp else ''))
    if got and int(got) != N:
        print('        UYARI: kare sayisi farkli; sahnede data-duration\'i yazilan kareye gore ver')


def kare_sayisi(video):
    r = run(['ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries',
             'stream=nb_read_packets', '-of', 'csv=p=0', video])
    # an MPEG-TS file (even one named .mp4) lists its stream twice (under the program and alone): first line only
    return int(r.stdout.strip().splitlines()[0].split(',')[0])


def yaz_kes(a, interp, vf, seek, enc_opts, Ks, J0, sel_t, SF, W, H, FPS, crop, N):
    if interp:
        r = run(['ffmpeg', '-v', 'error', '-y'] + seek + ['-i', a.video, '-an', '-vf', vf, '-r', '%g' % FPS] + enc_opts)
        if r.returncode:
            sys.exit(r.stderr[-1200:])
    else:
        # decode the needed range once, keep exactly the mapped frames (a select list of hundreds of frames is too long
        # for one ffmpeg expression), crop on the output timeline
        dec = subprocess.Popen(['ffmpeg', '-v', 'error'] + seek + ['-i', a.video, '-map', '0:v:0', '-vf',
                               "select='between(floor(%s),%d,%d)',setpts=N/%g/TB" % (sel_t, Ks[0] - J0, Ks[-1] - J0, SF),
                               '-vsync', '0',
                               '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-'], stdout=subprocess.PIPE)
        enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-s', '%dx%d' % (W, H),
                                '-r', '%g' % FPS, '-i', '-', '-vf', crop] + enc_opts, stdin=subprocess.PIPE)
        want, fsz, k, yaz = set(Ks), W * H * 3 // 2, Ks[0], 0
        while k <= Ks[-1]:
            buf = dec.stdout.read(fsz)
            if len(buf) < fsz:
                break
            if k in want:
                enc.stdin.write(buf); yaz += 1
            k += 1
        enc.stdin.close(); enc.wait(); dec.stdout.close(); dec.wait()
        if yaz != N:
            sys.exit('HATA: %d kare okundu, %d bekleniyordu (kaynak degisken kare hizli olabilir)' % (yaz, N))


def cmd_zaman(a):
    """voice word timings -> zamanlar.json/js in the shots folder, so sahne_baslat.py can open a stage on it"""
    for f in ('zamanlar.json', 'zamanlar.js'):
        yazma_izni(os.path.join(a.klasor, f), a.ustune_yaz)
    # Whisper writes sentence-first words 0.2-0.7 s early: when the motor (or you) made ses-hizali.json from this very
    # file with kelime.py hizala --hepsi, its word times are taken (--whisper keeps the given file)
    hz = os.path.join(os.path.dirname(os.path.abspath(a.kelimeler)), 'ses-hizali.json')
    if not a.whisper and os.path.basename(a.kelimeler) != 'ses-hizali.json' and os.path.exists(hz):
        try:
            hd = json.load(open(hz, encoding='utf-8'))
            if (os.path.normcase((hd.get('hizalama') or {}).get('kaynak') or '') == os.path.normcase(os.path.abspath(a.kelimeler))
                    and os.path.getmtime(hz) >= os.path.getmtime(a.kelimeler)):
                print('KELIME  hizalanmis zamanlar kullaniliyor: %s (Whisper zamani icin --whisper)' % hz)
                a.kelimeler = hz
        except (OSError, ValueError):
            pass
    kel = json.load(open(a.kelimeler, encoding='utf-8'))['kelimeler']
    duyulan, not_ = None, ''
    if a.sure:
        # a given length is a frame count written in seconds (16.1667 = 485 frames): round, like the stage and renderer
        N = int(round(a.sure * a.fps))
    else:
        # default: just after the last HEARD speech (Whisper's last-word end can be 0.1 s early and cut the word)
        sw = a.ses or os.path.join(os.path.dirname(os.path.abspath(a.kelimeler)), 'ses.wav')
        if os.path.exists(sw):
            N, duyulan = bitis_karesi(ses_oku(sw).mean(1), a.fps)
            not_ = 'son duyulan konusma %.3f sn (%s), ' % (duyulan, os.path.basename(sw))
        else:
            N = int(np.ceil(kel[-1][2] * a.fps - 0.05))
            not_ = 'ses dosyasi yok (%s): Whisper son kelime sonuna gore, ' % sw
    Z = {'fps': a.fps, 'sure': N / a.fps, 'kare': N, 'en': a.en, 'boy': a.boy, 'kaynak': os.path.abspath(a.kelimeler),
         'kesmeler': [], 'parcalar': [], 'olaylar': {}, 'kamera': None,
         'son_konusma': round(duyulan, 3) if duyulan is not None else None,     # what kontrol.py son measures
         'kelimeler': [[w[0], round(w[1], 3), round(w[2], 3), round(w[1], 3), False] for w in kel]}
    json.dump(Z, open(os.path.join(a.klasor, 'zamanlar.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(a.klasor, 'zamanlar.js'), 'w', encoding='utf-8').write('window.ZAMAN = ' + json.dumps(Z, ensure_ascii=False) + ';\n')
    yazildi(os.path.join(a.klasor, 'zamanlar.json'), 'cekim.py'); yazildi(os.path.join(a.klasor, 'zamanlar.js'), 'cekim.py')
    print('ZAMAN   %s  sure %.3f sn = %d kare (%sWhisper son kelime sonu %.3f; gercek bitisi kontrol.py son ile olc)'
          % (os.path.join(a.klasor, 'zamanlar.json'), N / a.fps, N, not_, kel[-1][2]))
    print('KELIMELER  ' + '  '.join('%.2f:%s' % (w[1], w[0]) for w in kel))
    print('           (Whisper yazimi: ekrana yazilacak metni metin.txt den al, zamani buradan)')
    for p in sorted(os.listdir(a.klasor)):
        if p.endswith('.mp4'):
            b = bilgi(os.path.join(a.klasor, p))['video']
            print('CEKIM   %-16s %d kare = %.3f sn  (sahnede data-start / data-duration senin)' % (p, b['kare'], b['kare'] / b['fps']))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='komut', required=True)
    p = sp.add_parser('zaman', help='voice word timings -> zamanlar.json/js for sahne_baslat.py')
    p.add_argument('klasor', help='folder with your cut shots'); p.add_argument('--kelimeler', required=True,
                   help='word timings {"kelimeler": [[word, start, end, p], ...]} of the voice, e.g. panel/isler/<id>/ses/ses.json')
    p.add_argument('--sure', type=float, help='edit length in s (default: just after the last heard speech of the voice)')
    p.add_argument('--ses', help='the voice wav the length is measured on (default: ses.wav next to --kelimeler)')
    p.add_argument('--fps', type=float, default=30, help='edit frame rate (default 30)')
    p.add_argument('--en', type=int, default=1080, help='edit width in px written into zamanlar.json (default 1080)')
    p.add_argument('--boy', type=int, default=1920, help='edit height in px (default 1920)')
    p.add_argument('--whisper', action='store_true', help='use the given --kelimeler as is, even when the aligned '
                   'ses-hizali.json made from it exists')
    p.add_argument('--ustune-yaz', action='store_true', help='replace zamanlar.json/js written before by this kit')
    p.set_defaults(f=cmd_zaman)
    p = sp.add_parser('bant', help='find letterbox bars'); p.add_argument('video')
    p.add_argument('--bas', type=float, default=0); p.add_argument('--son', type=float); p.set_defaults(f=cmd_bant)
    p = sp.add_parser('kes', help='cut one vertical shot'); p.add_argument('video')
    p.add_argument('--bas', type=float, required=True, help='source second of the first frame')
    p.add_argument('--son', type=float, help='source second of the last frame'); p.add_argument('--kare', type=int, help='or: number of source frames')
    p.add_argument('--takip', help='crop centre keys s:x[:y],... (0-1 of the real picture)')
    p.add_argument('--yakin', type=float, default=1.0); p.add_argument('--alan', default='oto')
    p.add_argument('--hiz', type=float, default=1.0); p.add_argument('--ara-kare', action='store_true')
    p.add_argument('--parcalar', help='JSON with zaman.py "parcalar" (source seconds) for a real-frame speed ramp; '
                   '--bas and --son (or --kare) are still required: the first part\'s bas and the last part\'s son')
    p.add_argument('--fps', type=float, default=30, help='output frame rate (default 30)')
    p.add_argument('--en', type=int, default=1080, help='output width in px (default 1080; the crop keeps en:boy)')
    p.add_argument('--boy', type=int, default=1920, help='output height in px (default 1920)')
    p.add_argument('--crf', type=int, default=14); p.add_argument('--cikti', required=True)
    p.add_argument('--ustune-yaz', action='store_true', help='replace an output a kit tool wrote before (never a file it did not write)')
    p.set_defaults(f=cmd_kes)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
