# -*- coding: utf-8 -*-
"""kare_bak.py - contact sheets of a video range so you can SEE what happens and when.
Every tile is labelled with its source second (top-left) and source frame number k (below it).
  overview:   --hiz 1        (1 frame per second)
  close look: --hiz 10
  exact:      --hiz kaynak   (every source frame; use a short range, add --kirp to zoom on a HUD/face)

Example:  py -3 alet/kare_bak.py kayit.mp4 --bas 440 --son 470 --hiz 1 --cikti bak/genel.jpg
          py -3 alet/kare_bak.py kayit.mp4 --bas 452.0 --son 452.8 --hiz kaynak --kirp 700:300:600:330 --cikti bak/yakin.jpg
Looking again at the same range: add --ustune-yaz (renews the sheets this tool wrote; no _2 copies piling up).
"""
import argparse, glob, math, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortak import bilgi, ETIKET_FONT, run, alet_yazdi_mi, yazildi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--bas', type=float, default=0.0, help='start second (source time)')
    ap.add_argument('--son', type=float, help='end second (default: start + 10)')
    ap.add_argument('--hiz', default='1', help='frames per second to sample, or "kaynak" for every source frame')
    ap.add_argument('--kirp', help='crop before looking, ffmpeg crop syntax w:h:x:y in source pixels')
    ap.add_argument('--sutun', type=int, default=6, help='tiles per row (default 6)')
    ap.add_argument('--genislik', type=int, default=320, help='tile width in px (default 320)')
    ap.add_argument('--en-fazla', type=int, default=48, help='tiles per sheet; more frames -> more sheets (default 48)')
    ap.add_argument('--cikti', default='kareler.jpg', help='output jpg; several sheets get _01, _02 ...')
    ap.add_argument('--ustune-yaz', action='store_true', help='renew sheets this tool wrote before under the same '
                    '--cikti (yours or an old version\'s are never overwritten); without it an existing sheet stops the run')
    a = ap.parse_args()
    b = bilgi(a.video)
    v = b['video']
    if not v:
        sys.exit('goruntu yok')
    V0, SF = v['bas'], v['fps']
    # seconds are the frame timestamps the labels show; on a file that starts later (a trailer segment whose first frame
    # is at 33.2 s) smaller numbers are taken as counted from the file start, as before
    # a start printed rounded (25.39 for a first frame at 25.392) is the first frame, not 25.39 s after it
    pay = 0.5 / (SF or 30) + 0.005
    kaynak_sn = lambda s: V0 if V0 > 0 and V0 - pay <= s < V0 else (s + V0 if V0 > 0 and s < V0 else s)
    bas = kaynak_sn(a.bas)
    son = kaynak_sn(a.son if a.son is not None else a.bas + 10)
    # an MPEG-TS file (even one named .mp4) lists its stream twice: read the first line only
    son_k = int(run(['ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries',
                     'stream=nb_read_packets', '-of', 'csv=p=0', a.video]).stdout.strip().splitlines()[0].split(',')[0]) - 1
    KF = max(0, int(math.ceil((bas - V0) * SF - 1e-6)))
    KL = min(son_k, int(math.floor((son - V0) * SF + 1e-6)))
    if KL < KF:
        sys.exit('aralikta kare yok (dosyanin kareleri %.3f-%.3f sn)' % (V0, V0 + son_k / SF))
    kaynak = a.hiz == 'kaynak' or float(a.hiz) >= SF
    step = 1.0 if kaynak else SF / float(a.hiz)
    idx = sorted({KF + int(round(m * step)) for m in range(int((KL - KF) / step + 1e-9) + 1)})
    idx = [k for k in idx if k <= KL]
    # the real frame index of a decoded frame (timestamps kept with -copyts)
    K = 'round((t-%.6f)*%.6f)' % (V0, SF)
    sec = 'eq(%d+round(round((%s-%d)/%.6f)*%.6f),%s)' % (KF, K, KF, step, step, K)
    fs = max(14, a.genislik // 14)
    lab = ("drawtext=fontfile='%s':text='%%{pts\\:flt}':x=4:y=4:fontsize=%d:fontcolor=yellow:box=1:boxcolor=black@0.7,"
           "drawtext=fontfile='%s':text='k%%{eif\\:%s\\:d}':x=4:y=%d:fontsize=%d:fontcolor=white:box=1:boxcolor=black@0.7"
           % (ETIKET_FONT, fs, ETIKET_FONT, K.replace(',', '\\,'), fs + 10, int(fs * 0.85)))
    os.makedirs(os.path.dirname(os.path.abspath(a.cikti)), exist_ok=True)
    root, ext = os.path.splitext(a.cikti)
    ext = ext or '.jpg'
    eski = sorted(glob.glob(root + '_[0-9][0-9]' + ext))
    for old in eski:
        if not a.ustune_yaz:
            sys.exit('cikti zaten var: %s (ayni kagidi yenilemek icin --ustune-yaz ekle; baska bir bakis icin baska '
                     '--cikti adi ver)' % old)
        if not alet_yazdi_mi(old):
            sys.exit('cikti zaten var ve kare_bak.py yazmamis (eski surum ya da senin dosyan), ustune yazilmaz: %s' % old)
    sayfalar = [idx[i:i + a.en_fazla] for i in range(0, len(idx), a.en_fazla)]
    outs = []
    for n, sf in enumerate(sayfalar, 1):
        cols = min(a.sutun, len(sf))
        rows = int(math.ceil(len(sf) / cols))
        vf = ["select='between(%s,%d,%d)*%s'" % (K, sf[0], sf[-1], sec)]
        if a.kirp:
            vf.append('crop=%s' % a.kirp)
        vf += ['scale=%d:-2' % a.genislik, lab, 'tile=%dx%d:padding=4:color=0x202020' % (cols, rows)]
        t0 = V0 + sf[0] / SF
        ss = max(0.0, t0 - V0 - 0.5 / SF)            # -ss counts from the file's first frame
        out = '%s_%02d%s' % (root, n, ext)
        cmd = ['ffmpeg', '-v', 'error', '-ss', '%.6f' % ss, '-t', '%.6f' % ((sf[-1] - sf[0] + 1.5) / SF), '-copyts',
               '-i', a.video, '-map', '0:v:0', '-vf', ','.join(vf), '-vsync', '0', '-frames:v', '1', '-q:v', '3', out]
        r = subprocess.run(cmd[:1] + ['-y'] + cmd[1:], capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr[-1500:])
        yazildi(out, 'kare_bak.py')
        outs.append(out)
    fazla = [o for o in eski if os.path.abspath(o) not in {os.path.abspath(x) for x in outs}]
    if fazla:
        print('NOT     onceki calismanin fazladan sayfalari duruyor (silinmedi): %s' % ', '.join(fazla))
    print('%d kare, %d sayfa, hiz %s, aralik %.3f-%.3f sn (k%d-k%d)%s' % (
        len(idx), len(outs), a.hiz, V0 + KF / SF, V0 + KL / SF, KF, KL, ', kirp ' + a.kirp if a.kirp else ''))
    for o in outs:
        print('  ' + os.path.abspath(o))
    print('Etiket: sari = karenin gercek kaynak saniyesi, beyaz kN = kaynak kare numarasi (kaynak fps %g, ilk kare %.6f sn)'
          % (SF, V0))
    if not kaynak:
        print('Not: bu sayfa her %.1f kareden birini gosteriyor; kesme noktasini --hiz kaynak ile oku.' % step)


if __name__ == '__main__':
    main()
