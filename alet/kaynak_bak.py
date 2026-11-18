# -*- coding: utf-8 -*-
"""kaynak_bak.py - what is this video file: size, frame rate, audio, and how slow real slow motion can go.

Example:  py -3 alet/kaynak_bak.py kayit.mp4 --cikti-fps 30 --olc --bas 440 --son 470
Cuts inside a multi-shot piece (a trailer part): source second and frame of every hard cut, and the shots between:
          py -3 alet/kaynak_bak.py ham/video-2.mp4 --kesmeler            (whole file; --bas/--son for a range)
          (ffmpeg scene score; --esik 6 is the default, lower finds softer cuts; check a cut with kare_bak.py --hiz
          kaynak; a shot longer than 4 s gets an UYARI line: try a lower --esik)
"""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortak import bilgi, loudness, run


UZUN_CEKIM = 4.0     # a "shot" longer than this in a trailer piece usually hides a soft cut


def kesmeler(video, v, bas=None, son=None, esik=6.0):
    """hard cuts by ffmpeg's scene score (select filter, 0-100 here) on a small copy of the picture; times are source
    seconds (timestamps kept). Measured 18.11.2026 on a fast trailer piece: the old scdet at 10 found 0 of 5 cuts in
    48.2-54.5 s (dark, same-tone shots score 7-25 here); cuts closer than 3 frames count once (the higher score)."""
    cmd = ['ffmpeg', '-hide_banner', '-nostats', '-copyts']
    V0, SF = v['bas'], v['fps'] or 30
    if bas is not None:
        cmd += ['-ss', '%.6f' % max(0.0, bas - V0 if V0 > 0 and bas >= V0 - 0.02 else bas)]
    if son is not None:
        # an INPUT option: as an output option it is compared with the kept source timestamps and stops after 3 frames
        cmd += ['-t', '%.6f' % max(0.05, son - (bas if bas is not None else V0))]
    cmd += ['-i', video]
    r = run(cmd + ['-map', '0:v:0', '-an', '-vf', "scale=320:-2,select='gte(scene\\,0)',metadata=print:key=lavfi.scene_score",
                   '-f', 'null', '-'])
    out, t = [], None
    for satir in r.stderr.splitlines():
        m = re.search(r'pts_time:\s*([\d.]+)', satir)
        if m:
            t = float(m.group(1))
        m = re.search(r'lavfi\.scene_score=([\d.]+)', satir)
        if m and t is not None and out is not None:
            sk = float(m.group(1)) * 100
            if sk < esik:
                continue
            k = int(round((t - V0) * SF))
            if out and k - out[-1][1] < 3:
                if sk > out[-1][2]:
                    out[-1] = (t, k, sk)
            else:
                out.append((t, k, sk))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--cikti-fps', type=float, default=30, help='frame rate of the edit you will render (default 30)')
    ap.add_argument('--olc', action='store_true', help='also measure loudness (LUFS) of the audio, optionally only --bas..--son')
    ap.add_argument('--bas', type=float, help='seconds, start of the range to measure')
    ap.add_argument('--son', type=float, help='seconds, end of the range to measure')
    ap.add_argument('--kesmeler', action='store_true', help='list the hard cuts (source second, frame k) in --bas..--son '
                    'or the whole file, and the shots between them')
    ap.add_argument('--esik', type=float, default=6.0, help='cut sensitivity for --kesmeler (ffmpeg scene score x 100, '
                    'default 6; lower finds softer cuts, and more false ones)')
    a = ap.parse_args()
    b = bilgi(a.video)
    v, s = b['video'], b['ses']
    print('DOSYA   %s' % a.video)
    print('SURE    %.3f sn' % b['sure'])
    if v:
        print('GORUNTU %dx%d  %s  fps %.3f (ortalama %.3f)  ilk kare %.6f sn  kare sayisi %s' % (
            v['w'], v['h'], v['codec'], v['fps'], v['fps_ort'], v['bas'], v['kare'] or '?'))
        if abs(v['fps'] - v['fps_ort']) > 0.05 * max(v['fps'], 1):
            print('        UYARI: degisken kare hizi olabilir (VFR); kare sayimlari kayabilir')
        oran = a.cikti_fps / v['fps'] if v['fps'] else 1
        if oran < 1:
            print('YAVASLATMA  %g fps cikti icin en dusuk gercek hiz %.2fx (her kaynak karesi bir kez; daha yavasi kare kopyalar)'
                  % (a.cikti_fps, oran))
        else:
            print('YAVASLATMA  YOK: kaynak %g fps, cikti %g fps; 1.0x altindaki her hiz kare kopyalar' % (v['fps'], a.cikti_fps))
        print('KARE NO     kaynak karesi k, kaynak saniyesi = %.6f + k / %g' % (v['bas'], v['fps']))
    else:
        print('GORUNTU yok')
    if s:
        print('SES     %s  %d Hz  %d kanal  ilk ornek %.6f sn (goruntuye gore %+.3f sn)' % (
            s['codec'], s['sr'], s['kanal'], s['bas'], s['bas'] - (v['bas'] if v else 0)))
    else:
        print('SES     yok')
    if a.olc and s:
        path = a.video
        if a.bas is not None or a.son is not None:
            import tempfile
            tmp = os.path.join(tempfile.gettempdir(), 'kaynak_bak_olc.wav')
            cmd = ['ffmpeg', '-v', 'error', '-y']
            if a.bas is not None:
                cmd += ['-ss', str(a.bas)]
            cmd += ['-i', a.video]
            if a.son is not None:
                cmd += ['-t', str(a.son - (a.bas or 0))]
            run(cmd + ['-vn', '-ac', '2', '-ar', '48000', tmp])
            path = tmp
        L = loudness(path)
        if L:
            print('YUKSEKLIK  %.1f LUFS  tepe %.1f dBTP  LRA %.1f' % (L['I'], L['TP'], L['LRA']))
    if a.kesmeler and v:
        K = kesmeler(a.video, v, a.bas, a.son, a.esik)
        ilk = a.bas if a.bas is not None and a.bas >= v['bas'] else v['bas']
        n = v['kare'] or int((run(['ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries',
                                   'stream=nb_read_packets', '-of', 'csv=p=0', a.video]).stdout.strip().splitlines() or ['0'])[0]
                             .split(',')[0] or 0)
        # end of the last frame; the container duration of a cut-out piece can count from 0, not from its first frame
        bitis = a.son if a.son is not None else v['bas'] + n / (v['fps'] or 30)
        print('KESMELER %d (esik %g; saniye = yeni cekimin ilk karesi, kaynak saniyesi)' % (len(K), a.esik))
        for t, k, sk in K:
            print('  %9.3f sn  k%-6d skor %.1f' % (t, k, sk))
        sinir = [ilk] + [t for t, _, _ in K] + [bitis]
        print('CEKIMLER ' + ', '.join('%.3f-%.3f' % (x, y) for x, y in zip(sinir, sinir[1:]) if y - x > 0.01) +
              '  (kesmenin iki yanina kare_bak.py --hiz kaynak ile bak)')
        uzun = ['%.3f-%.3f' % (x, y) for x, y in zip(sinir, sinir[1:]) if y - x > UZUN_CEKIM]
        if uzun:
            print('UYARI   %g sn\'den uzun cekim var (%s): icinde yumusak bir kesme kacmis olabilir. --esik %g ile yeniden '
                  'dene ve kare_bak.py --hiz 10 ile bak' % (UZUN_CEKIM, ', '.join(uzun), max(1, a.esik / 2)))


if __name__ == '__main__':
    main()
