# -*- coding: utf-8 -*-
"""kontrol.py - technical faults only. It does not judge taste and does not ask for any effect.

  ozet   size, fps, length, sound:                 py -3 alet/kontrol.py ozet klip.mp4
  serit  consecutive frames around a moment (--once / --sonra = FRAMES, whole numbers):
                                                    py -3 alet/kontrol.py serit klip.mp4 --an 9.13 --once 3 --sonra 3 --cikti k/an.jpg
         whole edit, 16 frames incl. first and last:  py -3 alet/kontrol.py serit klip.mp4 --esit 16 --sutun 8 --cikti k/hepsi.jpg
         caption area close up (stray marks, cut dots/cedillas):
                                                    py -3 alet/kontrol.py serit klip.mp4 --kareler 58,374,403 --kirp 1080:560:0:1100 --genislik 540 --cikti k/yazi.jpg
  kopya  repeated frames inside motion (fake slow): py -3 alet/kontrol.py kopya is/zaman/video.mp4
  siyah  1-2 black frames between filled ones (a window missing for a frame; captions on it do not hide it):
                                                    py -3 alet/kontrol.py siyah short.mp4
  donma  WARNING only: a shot's first frame shown twice right after a cut (start a hair past the frame grid):
                                                    py -3 alet/kontrol.py donma short.mp4
  kayma  sound vs picture drift after attaching:    py -3 alet/kontrol.py kayma klip.mp4 is/ses-final.wav
  son    does it end on the last word (<= 0.10 s):  py -3 alet/kontrol.py son klip.mp4 --zaman is/zaman
         with a bed/music under the voice, measure the voice alone:
                                                    py -3 alet/kontrol.py son short.mp4 --konusma panel/isler/<id>/ses/ses.wav
  alan   Shorts UI zones drawn on frames (eye check for text placement):
                                                    py -3 alet/kontrol.py alan klip.mp4 --kareler 0,120,300 --cikti k/alan.jpg
  hepsi  all automatic checks, last line "SONUC: GECTI" or "SONUC: KALDI: <reasons>"; exit code 0 = GECTI, 1 = KALDI:
                                                    py -3 alet/kontrol.py hepsi klip.mp4 --zaman is/zaman --ses is/ses-final.wav
         It first prints when the checked video was written ("DOSYA") and fails when the sound given with --ses, or
         the rendered picture ses.py ekle made it from, was written AFTER it: the check would look at an old video.
         Short with a cekim.py folder as --zaman: only the shots the stage uses are checked for repeats (--sahne).
"""
import argparse, os, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortak import bilgi, ses_oku, ETIKET_FONT, SR, konusma_sonu, son_80ms, alet_kaydi


def ozet(path, en=1080, boy=1920, fps=30, min_s=15, max_s=60):
    b = bilgi(path)
    v, s = b['video'], b['ses']
    hata = []
    print('OZET    %s' % path)
    if not v:
        return ['goruntu yok']
    print('        %dx%d  %.3f fps  %.3f sn  kare %s  ses %s' % (v['w'], v['h'], v['fps'], b['sure'], v['kare'] or '?',
                                                                  '%d Hz %d kanal' % (s['sr'], s['kanal']) if s else 'YOK'))
    if (v['w'], v['h']) != (en, boy):
        hata.append('boyut %dx%d (beklenen %dx%d)' % (v['w'], v['h'], en, boy))
    if abs(v['fps'] - fps) > 0.01:
        hata.append('fps %.3f (beklenen %g)' % (v['fps'], fps))
    if not s:
        hata.append('ses yok')
    if not (min_s <= b['sure'] <= max_s):
        hata.append('sure %.2f sn (%g-%g disinda)' % (b['sure'], min_s, max_s))
    return hata


def gri_kareler(path, w=96):
    b = bilgi(path)['video']
    h = int(round(b['h'] * w / b['w'] / 2)) * 2
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:v:0', '-vf', 'scale=%d:%d,format=gray' % (w, h),
                          '-fps_mode', 'passthrough', '-f', 'rawvideo', '-'], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w).astype(np.float32)


def kopya(path):
    f = gri_kareler(path)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))        # d[i] = change from frame i to i+1
    bul = []
    for i in range(1, len(d) - 1):
        # frame i+1 repeats frame i while the picture moves before and after = a doubled frame
        if d[i] < 0.35 and d[i - 1] > 1.5 and d[i + 1] > 1.5:
            bul.append(i + 1)
    fps = bilgi(path)['video']['fps'] or 30
    ks = []                                    # zaman.py's video.mp4: the source second of every output frame
    zj = os.path.join(os.path.dirname(os.path.abspath(path)), 'zamanlar.json')
    if os.path.basename(path) == 'video.mp4' and os.path.exists(zj):
        import json
        ks = json.load(open(zj, encoding='utf-8')).get('kare_kaynak_sn') or []
    yer = lambda k: 'kare %d (%.3f sn%s)' % (k, k / fps, ', kaynak %.3f sn' % ks[k] if k < len(ks) else '')
    print('KOPYA   %s: %d kare, hareket icinde tekrar eden kare %d%s' % (
        path, len(f), len(bul), (' -> ' + ', '.join(yer(k) for k in bul[:20])) if bul else ''))
    if bul:
        print('        not: yayin kayitlarinda kaynagin kendisi de kare tekrarlar; kare_bak.py --hiz kaynak ile kaynaga bak')
    # 1-2 isolated repeats are usually the stream's own dropped frames; more means the retime duplicated frames
    return ['%d tekrar eden kare (ilk: %s)' % (len(bul), bul[:5])] if len(bul) > 2 else []


def donma(path, g=None):
    """A WARNING only, never a fail: the first frame after a hard cut shown twice while the shot moves on after it =
    a shot start a hair past the frame grid (22.8667 instead of 22.8666) that the renderer snapped: its first frame
    repeats (a hidden freeze). Measured 18.11.2026: found both such starts in two Shorts before repair (change 0.09 and
    0.33 between the two frames), nothing in the three repaired ones (smallest change right after a cut there 0.96).
    A still shot after a cut is not counted (the picture has to move right after the repeat)."""
    g = gri_kareler(path) if g is None else g
    d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))        # d[i] = change from frame i to i+1
    fps = bilgi(path)['video']['fps'] or 30
    bul = [c for c in range(1, len(d) - 1) if d[c - 1] > 12 and d[c] < 0.5 and d[c + 1] > 1.5]
    print('DONMA   %s: kesmeden hemen sonra iki kez gorunen ilk kare %d%s' % (
        path, len(bul), (' -> ' + ', '.join('kare %d (%.3f sn)' % (c, c / fps) for c in bul[:20])) if bul else ''))
    if bul:
        print('UYARI   cekim basinda bir kare donma (KALDI degil): o cekimin baslangici kare izgarasinda mi bak (n/fps, '
              '4 hanede asagi kirpilmis: sahne_baslat.py --yenile), sahne pencereyi kendi koduyla aciyorsa Math.round(t*fps). '
              'Kaynakta da ayniysa (fragmanin kendi tekrari) sorun degil: kare_bak.py --hiz kaynak ile bak')
    return bul


def siyah(path, esik=0.16, g=None):
    """1-2 (nearly) black frames whose neighbours on both sides are filled = a window missing for a frame or two (a
    shot whose data-start / data-bas sits a hair after the frame grid, e.g. 3.6667 > 110/30, or stage code that opens
    and closes windows on t*fps without Math.round: on some frames it lands a hair under the whole number). Content independent:
    captions and labels may stay on the black frame, and a missing part of a split screen counts too. esik = the
    share of the frame that is dark (<= 20 of 255) on those 1-2 frames and at least 10 brighter on BOTH neighbours
    (measured on 18.11.2026 Shorts: real missing windows 0.20-0.92, cuts into a dark shot at most 0.12). A planned
    fade or a dark shot is not caught (the neighbours are dark as well); 3 or more black frames are not caught."""
    g = gri_kareler(path) if g is None else g
    f = g <= 20                                              # dark pixels
    fps = bilgi(path)['video']['fps'] or 30
    n, bul, k = len(g), [], 1
    while k < n - 1:
        hit = None
        for L in (1, 2):
            e = k + L - 1
            if e + 1 >= n:
                break
            yeni = (np.logical_and.reduce(f[k:e + 1])
                    & (np.minimum(g[k - 1], g[e + 1]) - g[k:e + 1].max(axis=0) >= 10)).mean()
            if yeni >= esik:
                hit = (k, L, yeni)
                break
        if hit:
            bul.append(hit)
            k += hit[1] + 1
        else:
            k += 1
    yer = lambda h: 'kare %s (%.3f sn, karenin %%%d\'i)' % (
        h[0] if h[1] == 1 else '%d-%d' % (h[0], h[0] + 1), h[0] / fps, round(h[2] * 100))
    print('SIYAH   %s: %d kare, dolu iki kare arasinda 1-2 karelik siyahlik %d%s' % (
        path, n, len(bul), (' -> ' + ', '.join(yer(h) for h in bul[:20])) if bul else ''))
    if bul:
        print('        not: o karede bir pencere yok. Iki nedeni olur: (1) cekim baslangici kare izgarasinda degil: '
              'data-start / data-bas n/fps olmali, 4 hanede asagi kirpilmis (3.6666, 3.6667 degil); sahne_baslat.py '
              '--yenile duzeltir. (2) Sahnenin kendi kodu pencereyi t*fps ya da saniyeyle acip kapatiyor: karsilastirmayi '
              'Math.round(t*fps) ile yap (alet/ALETLER.md, "Kesme ani kare ile"). Siyah kare cekimin kendisindeyse '
              '(fragmanin kendi kesmesi) kare_bak.py --hiz kaynak ile bak, cekimi o kareden sonra baslat')
    return ['%d yerde 1-2 karelik siyah kare (ilk: %s; ya cekim baslangici kare izgarasinda degil: sahne_baslat.py '
            '--yenile, ya da sahnenin pencere kodu kare sayisini yuvarlamiyor: Math.round(t*fps))'
            % (len(bul), yer(bul[0]))] if bul else []


def sahnedeki_cekimler(video, zaman, sahne=None):
    """the shots of a cekim.py folder that the stage really uses (shots cut but left out of the edit are not counted).
    The stage: --sahne, else the render ses.py ekle recorded (<sahne>/render/x.mp4), else the only folder next to the
    shots folder with an index.html. A shot matches by file name (kaynak/<name>.mp4) or, when it got another "ad", by
    size and time of the copy sahne_baslat.py made. No stage found = every shot in the folder, with a NOT line."""
    hepsi_ = sorted(os.path.join(zaman, f) for f in os.listdir(zaman) if f.lower().endswith('.mp4'))
    if not sahne:
        g = ((alet_kaydi(video) or {}).get('girdiler') or {}).get('goruntu')
        aday = [os.path.dirname(g), os.path.dirname(os.path.dirname(g))] if g else []
        if not any(os.path.isfile(os.path.join(d, 'index.html')) for d in aday):
            ust = os.path.dirname(os.path.abspath(zaman))
            aday = [os.path.join(ust, d) for d in sorted(os.listdir(ust))
                    if os.path.isfile(os.path.join(ust, d, 'index.html'))]
            aday = aday if len(aday) == 1 else []
        sahne = next((d for d in aday if os.path.isfile(os.path.join(d, 'index.html'))), None)
    elif not os.path.isfile(os.path.join(sahne, 'index.html')):
        sys.exit('--sahne klasorunde index.html yok: %s' % sahne)
    if not sahne:
        print('NOT     sahne bulunamadi (--sahne <sahne klasoru> ver): cekim klasorundeki butun cekimler denetlendi')
        return hepsi_
    import re
    html = open(os.path.join(sahne, 'index.html'), encoding='utf-8').read()
    imza = lambda p: (os.path.getsize(p), int(os.path.getmtime(p)))
    ad = {os.path.basename(p).lower(): p for p in hepsi_}
    im = {imza(p): p for p in hepsi_}
    kullan, disari = [], []
    for src in dict.fromkeys(re.findall(r'<video\b[^>]*?\bsrc="([^"]+)"', html, re.I)):
        yol = os.path.join(sahne, src)
        p = ad.get(os.path.basename(src).lower()) or (im.get(imza(yol)) if os.path.isfile(yol) else None)
        (kullan if p else disari).append(p or src)
    kullan = sorted(set(kullan))
    print('CEKIMLER sahne %s: cekim klasorundeki %d cekimden %d tanesi sahnede, yalniz onlar denetlendi%s' % (
        sahne, len(hepsi_), len(kullan), ('; sahnede olup bu klasorde olmayan (denetlenmedi): ' + ', '.join(disari))
        if disari else ''))
    return kullan


def kayma(path, master):
    a = ses_oku(path).mean(1)
    m = ses_oku(master).mean(1)
    n = min(len(a), len(m))
    if n < SR:
        return ['ses cok kisa']
    mid = n // 2
    seg = slice(max(0, mid - SR), min(n, mid + SR))
    best, bv = 0, -1e18
    for L in range(-4800, 4801, 8):
        val = float(np.dot(a[seg], np.roll(m[:n], L)[seg]))
        if val > bv:
            best, bv = L, val
    lo = best - 8
    for L in range(lo, lo + 17):
        val = float(np.dot(a[seg], np.roll(m[:n], L)[seg]))
        if val > bv:
            best, bv = L, val
    ms = best / SR * 1000
    print('KAYMA   ses-goruntu kaymasi %.2f ms (mp4 icindeki ses, ana sese gore)' % ms)
    return ['ses %.1f ms kaymis' % ms] if abs(ms) > 5 else []


def son(path, son_kelime=None, kesik=None, konusma=None):
    """does the picture end on the last word? With konusma (a voice-only track on the same timeline: the voice wav of
    a Short, or the clip's retimed ses.wav before the bed/effects) the speech is measured there, so a background bed
    or music in the mix cannot look like speech."""
    b = bilgi(path)
    # the same measure cekim.py zaman uses to choose the default length (alet/_ortak.py)
    r, ref, t_last = konusma_sonu(ses_oku(konusma or path).mean(1))
    dur = b['video']['kare'] / b['video']['fps'] if b['video']['kare'] else b['sure']
    gap = dur - t_last
    tail = son_80ms(r, dur)                            # last 80 ms of the picture, without the final 20 ms fade
    msg = 'SON     goruntu biter %.3f sn, son %s %.3f sn, aradaki %.3f sn' % (
        dur, 'konusma' if konusma else 'duyulan ses', t_last, gap)
    if son_kelime is not None:
        msg += ' (Whisper son kelime sonu %.3f)' % son_kelime
    print(msg)
    if not konusma:
        print('        (yalniz karisima bakildi; altta yatak/muzik varsa --konusma <yalniz ses> ver)')
    hata = []
    if gap > 0.10:
        hata.append('son kelimeden sonra %.2f sn daha var (en fazla 0.10)' % gap)
    if gap < -0.05:
        hata.append('goruntu bittikten sonra %.2f sn daha konusma var: son kelime kesiliyor (ya da yanlis ses izi)' % -gap)
    if tail > ref - 6:
        hata.append('son 80 ms hala yuksek (%.0f dB, tepe %.0f): son kelime kesilmis olabilir' % (tail, ref))
    if kesik:
        hata.append('son kelime "%s" kaynakta parcanin sonundan sonra da suruyor: yarida kesiliyor' % kesik)
    return hata


def tazelik(path, ses=None):
    """Is the checked video newer than what it should contain? Prints when it was written. A fault when the sound
    given with --ses, or the rendered picture / sound alet/ses.py ekle recorded as its inputs, was written later
    (1 s tolerance): a second-round output that could not be written leaves the old video behind."""
    mt = os.path.getmtime(path)
    once = time.time() - mt
    print('DOSYA   %s yazildi %s (%s once)' % (path, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mt)),
                                              '%d sn' % once if once < 120 else '%d dk' % (once // 60)))
    kayit = alet_kaydi(path)
    girdi = dict((kayit or {}).get('girdiler') or {})
    ad = {'goruntu': 'goruntu (render)', 'ses': 'eklenen ses'}
    bak = [(ad.get(k, k), v) for k, v in girdi.items()]
    if ses and os.path.normcase(os.path.abspath(ses)) != os.path.normcase(girdi.get('ses') or ''):
        if girdi.get('ses'):
            print('NOT     bu videoya ses.py ekle baska bir ses eklemis: %s (--ses %s)' % (girdi['ses'], ses))
        bak.append(('--ses', ses))
    if not kayit or not girdi:
        print('NOT     bu videonun hangi render dosyasindan yapildigi kayitli degil (ses.py ekle ile yazilmamis ya da eski '
              'surum): render dosyasinin saatini kendin karsilastir')
    hata = []
    for etiket, yol in bak:
        if os.path.exists(yol) and os.path.getmtime(yol) > mt + 1.0:
            hata.append('%s %s videodan %d sn sonra yazildi: denetlenen video ESKI (yeniden ekle: ses.py ekle <render> <ses> '
                        '%s --ustune-yaz)' % (etiket, yol, os.path.getmtime(yol) - mt, path))
    return hata


def serit(path, an, once, sonra, cikti, gen=300, kirp=None, esit=None, kareler=None, sutun=None):
    v = bilgi(path)['video']
    if kareler:
        fr = sorted(set(kareler))
    elif esit:
        n = v['kare'] or int(round(bilgi(path)['sure'] * v['fps']))
        fr = sorted({int(round(i * (n - 1) / (esit - 1))) for i in range(esit)})
    else:
        f0 = int(round(an * v['fps']))
        fr = [f for f in range(f0 - once, f0 + sonra + 1) if f >= 0]
    sel = '+'.join('eq(n\\,%d)' % f for f in fr)
    cols = min(sutun or len(fr), len(fr))
    vf = ("select='%s',%sscale=%d:-2,drawtext=fontfile='%s':text='kare %%{eif\\:round(t*%g)\\:d} / %%{pts\\:flt} sn':x=6:y=6:"
          "fontsize=%d:fontcolor=yellow:box=1:boxcolor=black@0.7,tile=%dx%d:padding=4:color=0x202020"
          % (sel, 'crop=%s,' % kirp if kirp else '', gen, ETIKET_FONT, v['fps'], max(14, gen // 16), cols,
             (len(fr) + cols - 1) // cols))
    os.makedirs(os.path.dirname(os.path.abspath(cikti)), exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vf', vf, '-fps_mode', 'passthrough', '-frames:v', '1', cikti], check=True)
    print('SERIT   %s  kareler %s (%.3f-%.3f sn)'
          % (cikti, fr, fr[0] / v['fps'], fr[-1] / v['fps']))


def alan(path, kareler, cikti, alt=0.18, sag=0.11, ust=0.06, gen=360):
    v = bilgi(path)['video']
    sel = '+'.join('eq(n\\,%d)' % f for f in kareler)
    W, H = v['w'], v['h']
    vf = ("select='%s',drawbox=x=0:y=%d:w=%d:h=%d:color=red@0.35:t=fill,drawbox=x=%d:y=0:w=%d:h=%d:color=red@0.25:t=fill,"
          "drawbox=x=0:y=0:w=%d:h=%d:color=orange@0.25:t=fill,scale=%d:-2,tile=%dx1:padding=4:color=0x202020"
          % (sel, int(H * (1 - alt)), W, int(H * alt) + 1, int(W * (1 - sag)), int(W * sag) + 1, H, W, int(H * ust) + 1,
             gen, len(kareler)))
    os.makedirs(os.path.dirname(os.path.abspath(cikti)), exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vf', vf, '-fps_mode', 'passthrough', '-frames:v', '1', cikti], check=True)
    print('ALAN    %s  kareler %s; kirmizi = alt %%%d ve sag %%%d (Shorts dugmeleri/yazisi), turuncu = ust %%%d. '
          'Okunmasi gereken yazi kirmizida olmamali.' % (cikti, kareler, alt * 100, sag * 100, ust * 100))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='komut', required=True)
    p = sp.add_parser('ozet'); p.add_argument('video')
    p = sp.add_parser('serit'); p.add_argument('video'); p.add_argument('--an', type=float, help='moment in seconds')
    p.add_argument('--once', type=int, default=3, help='FRAMES before --an (a whole number, not seconds; default 3)')
    p.add_argument('--sonra', type=int, default=3, help='FRAMES after --an (a whole number, not seconds; default 3)')
    p.add_argument('--cikti', default='serit.jpg')
    p.add_argument('--kirp', help='zoom first: ffmpeg crop w:h:x:y on the edit (e.g. the caption area 1080:520:0:1100)')
    p.add_argument('--esit', type=int, help='instead of --an: N evenly spaced frames, first and last included')
    p.add_argument('--kareler', help='instead of --an: exact frame numbers, e.g. 58,374,403')
    p.add_argument('--sutun', type=int, help='tiles per row (default: all in one row)')
    p.add_argument('--genislik', type=int, default=300, help='tile width (default 300)')
    p = sp.add_parser('kopya'); p.add_argument('video')
    p = sp.add_parser('siyah'); p.add_argument('video')
    p = sp.add_parser('donma'); p.add_argument('video')
    p = sp.add_parser('kayma'); p.add_argument('video'); p.add_argument('master')
    p = sp.add_parser('son'); p.add_argument('video'); p.add_argument('--zaman', help='zaman.py folder (reads the last word)')
    p.add_argument('--konusma', help='voice-only track on the same timeline (Short: ses/ses.wav; clip: zaman/ses.wav)')
    p = sp.add_parser('alan'); p.add_argument('video'); p.add_argument('--kareler', required=True); p.add_argument('--cikti', default='alan.jpg')
    p = sp.add_parser('hepsi'); p.add_argument('video'); p.add_argument('--zaman', help='zaman.py folder (checks its video.mp4 for repeats) '
                                                                        'or the cekim.py shots folder (checks every shot)')
    p.add_argument('--konusma', help='voice-only track for the end check (see son)')
    p.add_argument('--sahne', help='Short: the HyperFrames stage folder; only the shots its index.html uses are checked '
                   'for repeats (default: found from the render ses.py ekle recorded, or the only stage next to --zaman)')
    p.add_argument('--ses', help='final mastered wav that was attached'); p.add_argument('--min', type=float, default=10,
                   help='shortest length in s. 10 = a Short (panel/kapi_topla.js uses the same number); a clip is 15: --min 15')
    p.add_argument('--max', type=float, default=60)
    a = ap.parse_args()

    def son_kelime(z):
        if not z:
            return None, None
        import json
        k = json.load(open(os.path.join(z, 'zamanlar.json'), encoding='utf-8')).get('kelimeler')
        if not k:
            return None, None
        return k[-1][2], (k[-1][0] if len(k[-1]) > 4 and k[-1][4] else None)

    if a.komut == 'ozet':
        h = ozet(a.video, min_s=0, max_s=1e9); print('  ' + ('; '.join(h) if h else 'tamam'))
    elif a.komut == 'serit':
        if a.an is None and not a.esit and not a.kareler:
            sys.exit('serit: --an, --esit ya da --kareler ver')
        serit(a.video, a.an, a.once, a.sonra, a.cikti, gen=a.genislik, kirp=a.kirp, esit=a.esit,
              kareler=[int(z) for z in a.kareler.split(',')] if a.kareler else None, sutun=a.sutun)
    elif a.komut == 'kopya':
        kopya(a.video)
    elif a.komut == 'siyah':
        siyah(a.video)
    elif a.komut == 'donma':
        donma(a.video)
    elif a.komut == 'kayma':
        kayma(a.video, a.master)
    elif a.komut == 'son':
        h = son(a.video, *son_kelime(a.zaman), konusma=a.konusma); print('  ' + ('; '.join(h) if h else 'tamam'))
    elif a.komut == 'alan':
        alan(a.video, [int(x) for x in a.kareler.split(',')], a.cikti)
    elif a.komut == 'hepsi':
        hata = ozet(a.video, min_s=a.min, max_s=a.max)
        hata += tazelik(a.video, a.ses)
        g = gri_kareler(a.video)                             # decoded once for both
        hata += siyah(a.video, g=g)
        donma(a.video, g=g)                                  # a warning line only, never KALDI
        if a.zaman:
            # clip: zaman.py's video.mp4; info Short: no video.mp4, the shots of that cekim.py folder the stage uses
            vz = os.path.join(a.zaman, 'video.mp4')
            for vp in [vz] if os.path.exists(vz) else sahnedeki_cekimler(a.video, a.zaman, a.sahne):
                hata += kopya(vp)
        hata += kayma(a.video, a.ses) if a.ses else []
        hata += son(a.video, *son_kelime(a.zaman), konusma=a.konusma)
        if not a.zaman:
            print('NOT     --zaman verilmedi: kare kopyasi kontrolu atlandi')
        if not a.ses:
            print('NOT     --ses verilmedi: kayma kontrolu atlandi')
        print('NOT     yazi yerlesimi otomatik olculmez: kontrol.py alan ile bak')
        print('SONUC: GECTI' if not hata else 'SONUC: KALDI: ' + ' | '.join(hata))
        sys.exit(1 if hata else 0)


if __name__ == '__main__':
    main()
