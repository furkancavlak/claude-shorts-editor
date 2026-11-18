# -*- coding: utf-8 -*-
"""sahne_baslat.py - an EMPTY HyperFrames + GSAP stage. No design inside: no title, no caption style, no effects.
It only gives you the "window rig": a window = a rectangle on the canvas + its own camera into its own video, all
driven by CSS variables, so a layout can change by moving/reshaping windows instead of cutting.

Clip (zaman.py folder): every video in it gets one window; video.mp4 fills the canvas, the others start as a 0x0 point.
  py -3 alet/sahne_baslat.py is/sahne --zaman is/zaman
Info Short (several shots): give only the shots you use, with where they sit on the timeline (seconds):
  py -3 alet/sahne_baslat.py is/sahne --zaman is/v --cekimler is/cekimler.json
  cekimler.json: [{"dosya": "is/v/pov.mp4", "bas": 1.07, "sure": 3.70}, {"dosya": "is/v/tekne.mp4", "bas": 4.53,
                   "sure": 1.80, "medya_bas": 0.2}]
  "dosya": an absolute path, or a path relative to the folder you run the command in (the engine root); only when
  nothing is there, relative to the folder of cekimler.json. "ad" (optional) = window and media name, default the
  file name without .mp4. Each shot window fills the canvas and is visible only from bas to bas+sure: a hard cut,
  a starting point to replace with your own edit, not an edit. bas and bas+sure are put on the frame grid (n/fps),
  rounded DOWN (3.6667 -> 3.6666): a start a hair after a frame leaves that frame black (IZGARA line says so).
Refresh after the time map or the shots changed (re-copies the media, updates the timing attributes and the length;
your scene code is not touched; matching is by the media file name kaynak/<name>.mp4):
  py -3 alet/sahne_baslat.py is/sahne --zaman is/v --cekimler is/cekimler.json --yenile
  A shot new in the json gets a window right after the other shot windows, with an unused data-track-index; a shot
  gone from the json keeps its window (UYARI line; nothing is deleted, take it out yourself if you do not want it).
Render: hyperframes render is/sahne --output is/sahne/render/taslak.mp4 --quality draft --workers 2
  (2 workers: safe while other jobs or renders run on this computer; 3 only when nothing else runs, more fills memory)
Fonts: use only families the page declares with @font-face from a file in fonts/. A font-family with no @font-face in
the page, or one that starts with a generic name (sans-serif, monospace ...), makes the HyperFrames render download
fonts from Google Fonts without asking (sending the page's letters along). --yenile warns about both.
"""
import argparse, glob, json, math, os, re, shutil, sys

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)
from _ortak import bilgi, alet_yazdi_mi, yazildi
FONT_ADAY = [os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Windows\Fonts\Oswald-Bold.ttf'),
             r'C:\Windows\Fonts\bahnschrift.ttf', r'C:\Windows\Fonts\segoeuib.ttf', r'C:\Windows\Fonts\arialbd.ttf']

HTML = r'''<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>sahne</title>
<style>
  /* FONTS: only families declared here with @font-face from a local file in fonts/. A font-family with no @font-face
     in this page, or one that starts with sans-serif / monospace / system-ui, makes the HyperFrames render download
     fonts from Google Fonts without asking. Another font: copy its .ttf into fonts/ and add an @font-face for it. */
  @font-face { font-family: "SahneFont"; src: url("fonts/__FONT__") format("truetype"); }
__FONT2__
  html, body { margin: 0; padding: 0; background: #000; }
  #root { position: relative; width: __EN__px; height: __BOY__px; overflow: hidden; background: #000;
          font-family: "SahneFont", sans-serif; color: #fff; }

  /* WINDOW RIG: a .pencere is a rectangle (--x --y --w --h --r, canvas px) with its own camera
     (--cx --cy = which source pixel sits in the window centre, --z = zoom, source px -> canvas px). */
  .pencere { position: absolute; overflow: hidden;
             left: calc(var(--x) * 1px); top: calc(var(--y) * 1px);
             width: calc(var(--w) * 1px); height: calc(var(--h) * 1px);
             border-radius: calc(var(--r) * 1px); }
  .kamera { position: absolute; left: 0; top: 0; transform-origin: 0 0;
            transform: translate(calc(var(--w) * 0.5px - var(--cx) * var(--z) * 1px),
                                 calc(var(--h) * 0.5px - var(--cy) * var(--z) * 1px)) scale(var(--z)); }
  .kamera video { display: block; }
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__SURE__" data-width="__EN__" data-height="__BOY__" data-fps="__FPS__">
__PENCERELER__
  <script src="gsap.min.js"></script>
  <script src="zamanlar.js"></script>
  <script>
  (function () {
    const Z = window.ZAMAN;   // kelimeler [[word, start, end, source_start, cut]], olaylar {}, kesmeler [], sure, fps (output seconds)
    const tl = gsap.timeline({ paused: true });

    // A window state. Seek-safe rule: every move is fromTo with immediateRender:false, so any frame renders the same
    // no matter in which order the renderer asks for frames.
    const P = (x, y, w, h, r, cx, cy, z) => ({ '--x': x, '--y': y, '--w': w, '--h': h, '--r': r, '--cx': cx, '--cy': cy, '--z': z });
    const ft = (sel, from, to, dur, ease, at) =>
      tl.fromTo(sel, from, Object.assign({}, to, { duration: dur, ease: ease, immediateRender: false }), at);
    const st = (sel, vars, at) => tl.set(sel, vars, at);

    // starting state: the main video fills the canvas ("cover"), camera on the source centre
__BASLANGIC__
    // Your edit goes here: decide from what happens in the clip. Example of the mechanics only:
    //   ft('#p-video', P(...nu), P(...yeni), 0.6, 'power3.inOut', Z.olaylar.bir_an);
    // Words: Z.kelimeler[i][1] is when word i starts on THIS timeline.

    window.__timelines = window.__timelines || {};
    window.__timelines['main'] = tl;
  })();
  </script>
</div>
</body>
</html>
'''


def izgara(t, fps):
    """a time on the frame grid (n/fps), rounded DOWN and written down (4 decimals) so it is never past the frame: a
    start a hair after frame n (3.6667 > 110/30) leaves frame n without the window = one black frame in the video.
    A value within 0.02 frame of a grid point (1.4333 = 43/30 written short) is that grid point."""
    k = t * fps
    n = round(k) if abs(k - round(k)) < 0.02 else math.floor(k)
    return math.floor(n / fps * 10000 + 1e-6) / 10000


def izgaraya_oturt(liste, fps):
    """bas and son (= bas + sure) of every shot onto the frame grid; says which ones moved"""
    for c in liste:
        bas, son = izgara(c['bas'], fps), izgara(c['bas'] + c['sure'], fps)
        if abs(bas - c['bas']) > 0.00005:
            print('IZGARA  %-16s bas %.4f -> %.4f (kare izgarasina asagi yuvarlandi: arada kalan bas o karede pencereyi '
                  'gostermez, video tek siyah kare olur)' % (c['ad'], c['bas'], bas))
        c['bas'], c['son'] = bas, max(son, bas)


def cekim_listesi(path):
    d = json.load(open(path, encoding='utf-8'))
    d = d['cekimler'] if isinstance(d, dict) else d
    kok = os.path.dirname(os.path.abspath(path))
    out = []
    for c in d:
        f = c['dosya']
        if not os.path.isabs(f) and not os.path.exists(f):
            f = os.path.join(kok, f)
        if not os.path.exists(f):
            sys.exit('cekim dosyasi yok: %s' % c['dosya'])
        ad = c.get('ad') or os.path.splitext(os.path.basename(f))[0]
        out.append({'dosya': f, 'ad': ad, 'bas': float(c['bas']), 'sure': float(c['sure']),
                    'medya_bas': float(c.get('medya_bas', 0))})
    adlar = [c['ad'] for c in out]
    if len(set(adlar)) != len(adlar):
        sys.exit('ayni adli iki cekim var: %s (birine "ad" ver)' % adlar)
    return out


def html_uyarisi(klasor):
    diger = [f for f in os.listdir(klasor) if f.lower().endswith('.html') and f != 'index.html']
    if diger:
        print('UYARI   sahne klasorunde ikinci bir .html var (%s): hyperframes lint "multiple_root_compositions" verir. '
              'Klasorun disina tasi ya da uzantisini degistir.' % ', '.join(diger))


GENEL_FONT = {'sans-serif', 'serif', 'monospace', 'cursive', 'fantasy', 'system-ui', 'ui-sans-serif', 'ui-serif',
              'ui-monospace', 'emoji', 'math', 'fangsong', '-apple-system', 'blinkmacsystemfont'}


def font_uyarisi(klasor):
    """HyperFrames 0.8.x, while rendering, fetches from Google Fonts (without asking; the page's letters go along as
    the "text" parameter) every font-family it does not find as an @font-face in the page, and puts Inter in front of
    a family list that starts with a generic name, then completes Inter from Google Fonts too. Warn about both and about
    remote font/style addresses, so the stage keeps to the local files in fonts/."""
    try:
        html = open(os.path.join(klasor, 'index.html'), encoding='utf-8').read()
    except OSError:
        return
    ad = lambda s: s.strip().strip('"\'').strip().lower()
    yuzler = {ad(m.split(',')[0]) for m in re.findall(r'@font-face\s*\{[^}]*?font-family\s*:\s*([^;}]+)', html, re.I)}
    govde = re.sub(r'@font-face\s*\{[^}]*\}', '', html)
    sorun = []
    for deger in re.findall(r'font-family\s*:\s*([^;}{<>]+)', govde, re.I):
        deger = deger.strip().rstrip('"\'').strip()           # an inline style="..." ends with the attribute's quote
        ilk = ad(deger.split(',')[0])
        if not ilk or ilk.startswith('var(') or ilk in ('inherit', 'initial', 'unset', 'revert', 'revert-layer'):
            continue
        if ilk in GENEL_FONT:
            sorun.append('"font-family: %s" genel bir adla basliyor: render basina Inter koyar ve onu Google Fonts\'tan '
                         'tamamlar. Ilk ad senin @font-face ailen olsun (ornek: "SahneFont", %s).' % (deger.strip(), ilk))
        elif ilk not in yuzler:
            sorun.append('"%s" icin sayfada @font-face yok: render onu Google Fonts\'tan indirir (bulamazsa bilgisayardaki '
                         'fontu gomer). Dosyasini fonts/ icine koyup @font-face ile tanimla.'
                         % deger.split(',')[0].strip().strip('"\'').strip())
    for m in re.findall(r'(?:url\(\s*["\']?|href\s*=\s*["\'])(https?://[^"\')\s]+)', html, re.I):
        if re.search(r'font|\.woff|\.ttf|\.otf|\.css', m, re.I):
            sorun.append('uzak adres: %s (render onu indirir; dosyayi sahne klasorune koy)' % m)
    for s in dict.fromkeys(sorun):
        print('UYARI   yazi tipi: ' + s)


YER = '  <script src="gsap.min.js"></script>'      # windows sit before this line of the scaffold
PENCERE = re.compile(r'<div id="p-[^"]+" class="pencere"[^>]*>\s*<div class="kamera">\s*<video\b[^>]*>\s*</video>\s*'
                     r'</div>\s*</div>')            # one shot window as this tool writes it


def pencere_html(c, i, v, en, boy, satir_ici=False):
    """one Short shot window (hard cut by data-bas/data-son); satir_ici = its starting state inline (--yenile)"""
    z = max(en / v['w'], boy / v['h'])
    stil = (' style="--x:0;--y:0;--w:%d;--h:%d;--r:0;--cx:%g;--cy:%g;--z:%.4f"' % (en, boy, v['w'] / 2, v['h'] / 2, z)
            if satir_ici else '')
    return ('  <div id="p-%s" class="pencere" data-bas="%.4f" data-son="%.4f"%s>\n    <div class="kamera"><video id="v-%s" '
            'src="kaynak/%s.mp4" data-start="%.4f" data-duration="%.4f" data-media-start="%.4f" data-track-index="%d" '
            'muted playsinline style="width:%dpx;height:%dpx"></video></div>\n  </div>'
            % (c['ad'], c['bas'], c['son'], stil, c['ad'], c['ad'], c['bas'], c['son'] - c['bas'], c['medya_bas'], i,
               v['w'], v['h']))


def medya_kopyala(src, dst):
    """copy a shot into the stage; an existing file is replaced only if this kit copied it there"""
    if os.path.exists(dst) and not alet_yazdi_mi(dst):
        print('ATLANDI %s: aletler kopyalamamis (eski bir sahne ya da senin dosyan); yenisini elle koy' % dst)
        return False
    shutil.copy2(src, dst)
    yazildi(dst, 'sahne_baslat.py')
    return True


def yenile(a, Z):
    ix = os.path.join(a.klasor, 'index.html')
    if not os.path.exists(ix):
        sys.exit('sahne yok: %s' % ix)
    html = open(ix, encoding='utf-8').read()
    sure = '%.4f' % (Z['kare'] / Z['fps'] - 0.0004)
    html, n = re.subn(r'(<div id="root"[^>]*?data-duration=")[^"]*(")', r'\g<1>%s\g<2>' % sure, html, count=1)
    if a.cekimler:
        liste = cekim_listesi(a.cekimler)
        m = re.search(r'<div id="root"[^>]*?data-fps="([\d.]+)"', html)
        izgaraya_oturt(liste, float(m.group(1)) if m else Z['fps'])
    else:
        liste = [{'dosya': v, 'ad': os.path.splitext(os.path.basename(v))[0], 'bas': 0.0, 'son': float(sure),
                  'sure': float(sure), 'medya_bas': 0.0} for v in sorted(glob.glob(os.path.join(a.zaman, '*.mp4')))]
    shutil.copy2(os.path.join(a.zaman, 'zamanlar.js'), os.path.join(a.klasor, 'zamanlar.js'))
    print('YENILE  %s: uzunluk %s sn, zamanlar.js yenilendi' % (a.klasor, sure))
    for c in liste:
        dst = os.path.join(a.klasor, 'kaynak', c['ad'] + '.mp4')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        kop = medya_kopyala(c['dosya'], dst)
        tag = re.compile(r'<video\b[^>]*\bsrc="kaynak/%s\.mp4"[^>]*>' % re.escape(c['ad']))
        bulundu = 0

        def ayarla(m):
            t = m.group(0)
            for k, v in (('data-start', '%.4f' % c['bas']), ('data-duration', '%.4f' % (c['son'] - c['bas'])),
                         ('data-media-start', '%.4f' % c['medya_bas'])):
                t = re.sub(r'\b%s="[^"]*"' % k, '%s="%s"' % (k, v), t) if re.search(r'\b%s="' % k, t) \
                    else t.replace('<video', '<video %s="%s"' % (k, v), 1)
            return t
        html, bulundu = tag.subn(ayarla, html)
        html = re.sub(r'(<div id="p-%s"[^>]*?data-bas=")[^"]*("[^>]*?data-son=")[^"]*(")' % re.escape(c['ad']),
                      r'\g<1>%.4f\g<2>%.4f\g<3>' % (c['bas'], c['son']), html)
        ek = ''
        if not bulundu and a.cekimler:
            # a shot added to cekimler.json: its window goes in next to the other shot windows (same layer, under
            # whatever you put after them), with the same hard cut (state inline, your script is not touched) and a
            # track index no other media uses; placing and moving it is your edit
            v = bilgi(c['dosya'])['video']
            izler = [int(x) for x in re.findall(r'\bdata-track-index="(\d+)"', html)]
            yeni = pencere_html(c, max(izler) + 1 if izler else 0, v, a.en, a.boy, satir_ici=True)
            son_pencere = list(PENCERE.finditer(html))
            if son_pencere:
                e = son_pencere[-1].end()
                html = html[:e] + '\n' + yeni + html[e:]
                ek = '  PENCERE EKLENDI #p-%s (oteki cekim pencerelerinin hemen arkasina; tam ekran, yalniz kendi ' \
                     'zamaninda gorunur; yerini sen ver)' % c['ad']
            elif YER in html:
                html = html.replace(YER, yeni + '\n' + YER, 1)
                ek = '  PENCERE EKLENDI #p-%s (cekim penceresi bulunamadi, sayfanin sonuna kondu: ust katmanlarinin ' \
                     'onune gecebilir, yerini kendin tasi)' % c['ad']
            else:
                ek = '  (index.html icinde kaynak/%s.mp4 yok: pencereyi kendin ekle)' % c['ad']
        elif not bulundu:
            ek = '  (index.html icinde kaynak/%s.mp4 yok: pencereyi kendin ekle)' % c['ad']
        print('CEKIM   %-16s %s  bas %.4f  sure %.3f%s' % (c['ad'], 'kopyalandi' if kop else 'eski medya', c['bas'], c['sure'], ek))
    kullanilan = {c['ad'] for c in liste}
    for f in sorted(glob.glob(os.path.join(a.klasor, 'kaynak', '*.mp4'))):
        ad = os.path.splitext(os.path.basename(f))[0]
        if ad not in kullanilan:
            print('NOT     kaynak/%s.mp4 listede yok (silinmedi)' % ad)
    for ad in dict.fromkeys(re.findall(r'<video\b[^>]*\bsrc="kaynak/([^"]+)\.mp4"', html)):
        if ad not in kullanilan:
            print('UYARI   kaynak/%s.mp4 listede yok ama index.html\'de penceresi duruyor (#p-%s): video hala zamaninda '
                  'gorunur. Istemiyorsan o pencereyi index.html\'den kendin cikar (silinmedi)' % (ad, ad))
    open(ix, 'w', encoding='utf-8', newline='\n').write(html)
    html_uyarisi(a.klasor)
    font_uyarisi(a.klasor)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('klasor', help='new stage folder (or an existing one with --yenile)')
    ap.add_argument('--zaman', required=True, help='zaman.py output folder, or the cekim.py shots folder (zamanlar.js/json)')
    ap.add_argument('--cekimler', help='JSON list of the shots you use: dosya, bas, sure, optional medya_bas and ad '
                    '(dosya: absolute, or relative to where you run the command; else relative to the json\'s folder)')
    ap.add_argument('--yenile', action='store_true', help='update media, timings and length of an existing stage')
    ap.add_argument('--font', help='a .ttf file to use as "SahneFont": the engine\'s own kod/font/Anton.ttf (full Turkish '
                    'letters) or any .ttf on this PC (default: first of Oswald-Bold, Bahnschrift, Segoe UI Bold, Arial Bold)')
    ap.add_argument('--font2', help='optional second .ttf (e.g. small text), declared as "SahneFont2"; e.g. '
                    'C:\\Windows\\Fonts\\bahnschrift.ttf')
    ap.add_argument('--en', type=int, default=1080, help='stage width in px (default 1080)')
    ap.add_argument('--boy', type=int, default=1920, help='stage height in px (default 1920)')
    a = ap.parse_args()
    if a.font2 and not os.path.isfile(a.font2):
        sys.exit('--font2 dosyasi yok: %s' % a.font2)
    Z = json.load(open(os.path.join(a.zaman, 'zamanlar.json'), encoding='utf-8'))
    if a.yenile:
        return yenile(a, Z)
    if os.path.exists(a.klasor) and os.listdir(a.klasor):
        sys.exit('klasor bos degil: %s (var olan sahneyi guncellemek icin --yenile)' % a.klasor)
    font = a.font or next((f for f in FONT_ADAY if os.path.exists(f)), None)
    if not font:
        sys.exit('font bulunamadi, --font ile kurulu bir .ttf ver')
    liste = cekim_listesi(a.cekimler) if a.cekimler else None      # check the list before creating anything
    yeni = not os.path.exists(a.klasor)
    try:
        kur(a, Z, font, liste)
    except BaseException:
        if yeni and os.path.isdir(a.klasor):
            shutil.rmtree(a.klasor, ignore_errors=True)               # only the folder this run created
        raise


def kur(a, Z, font, liste):
    os.makedirs(os.path.join(a.klasor, 'fonts'), exist_ok=True)
    os.makedirs(os.path.join(a.klasor, 'kaynak'), exist_ok=True)
    shutil.copy2(font, os.path.join(a.klasor, 'fonts', os.path.basename(font)))
    shutil.copy2(os.path.join(KOK, 'vendor', 'gsap.min.js'), os.path.join(a.klasor, 'gsap.min.js'))
    shutil.copy2(os.path.join(a.zaman, 'zamanlar.js'), os.path.join(a.klasor, 'zamanlar.js'))
    pen, bas = [], []
    sure = '%.4f' % (Z['kare'] / Z['fps'] - 0.0004)
    if liste:
        izgaraya_oturt(liste, Z['fps'])
        for i, c in enumerate(liste):
            name = c['ad']
            medya_kopyala(c['dosya'], os.path.join(a.klasor, 'kaynak', name + '.mp4'))
            v = bilgi(c['dosya'])['video']
            z = max(a.en / v['w'], a.boy / v['h'])
            pen.append(pencere_html(c, i, v, a.en, a.boy))
            bas.append("    st('#p-%s', P(0, 0, %d, %d, 0, %g, %g, %.4f), 0);   // %s %dx%d, on screen %.3f-%.3f s" % (
                name, a.en, a.boy, v['w'] / 2, v['h'] / 2, z, name, v['w'], v['h'], c['bas'], c['son']))
        bas.append("    // each shot is visible only inside its own time (data-bas .. data-son, refreshed by --yenile): a hard cut.\n"
                   "    document.querySelectorAll('.pencere[data-bas]').forEach(p => { const b = +p.dataset.bas, e = +p.dataset.son;\n"
                   "      if (b > 0.0005) { st(p, { autoAlpha: 0 }, 0); st(p, { autoAlpha: 1 }, b); }\n"
                   "      if (e < Z.sure - 0.0005) st(p, { autoAlpha: 0 }, e); });")
        vids = [c['dosya'] for c in liste]
        adlar = [c['ad'] for c in liste]
    else:
        vids = sorted(glob.glob(os.path.join(a.zaman, '*.mp4')), key=lambda p: (os.path.basename(p) != 'video.mp4', p))
        for i, vp in enumerate(vids):
            name = os.path.splitext(os.path.basename(vp))[0]
            medya_kopyala(vp, os.path.join(a.klasor, 'kaynak', name + '.mp4'))
            v = bilgi(vp)['video']
            z = max(a.en / v['w'], a.boy / v['h'])
            pen.append('  <div id="p-%s" class="pencere">\n    <div class="kamera"><video id="v-%s" src="kaynak/%s.mp4" '
                       'data-start="0" data-duration="%s" data-media-start="0" data-track-index="%d" muted playsinline '
                       'style="width:%dpx;height:%dpx"></video></div>\n  </div>' % (name, name, name, sure, i, v['w'], v['h']))
            if i == 0:
                bas.append("    st('#p-%s', P(0, 0, %d, %d, 0, %g, %g, %.4f), 0);   // %s %dx%d: fills the canvas (cover)" % (
                    name, a.en, a.boy, v['w'] / 2, v['h'] / 2, z, name, v['w'], v['h']))
            else:
                bas.append("    st('#p-%s', P(%d, %d, 0, 0, 0, %g, %g, %.4f), 0);   // %s %dx%d: starts as a 0x0 point (hidden); "
                           "give it a rectangle when you need it" % (name, a.en // 2, a.boy // 2, v['w'] / 2, v['h'] / 2, z,
                                                                      name, v['w'], v['h']))
        adlar = [os.path.splitext(os.path.basename(v))[0] for v in vids]
    font2 = ''
    if a.font2:
        shutil.copy2(a.font2, os.path.join(a.klasor, 'fonts', os.path.basename(a.font2)))
        font2 = '  @font-face { font-family: "SahneFont2"; src: url("fonts/%s") format("truetype"); }' % os.path.basename(a.font2)
    html = (HTML.replace('__FONT2__\n', font2 + '\n' if font2 else '')
            .replace('__FONT__', os.path.basename(font)).replace('__EN__', str(a.en)).replace('__BOY__', str(a.boy))
            .replace('__SURE__', sure).replace('__FPS__', '%g' % Z['fps'])
            .replace('__PENCERELER__', '\n'.join(pen)).replace('__BASLANGIC__', '\n'.join(bas)))
    open(os.path.join(a.klasor, 'index.html'), 'w', encoding='utf-8', newline='\n').write(html)
    print('SAHNE   %s' % os.path.abspath(a.klasor))
    print('        %d pencere: %s' % (len(adlar), ', '.join('#p-' + n for n in adlar)))
    print('        sure %s sn (= %d kare / %g fps, 0,0004 eksik: render tam %d kare yazsin diye), %dx%d, font %s%s'
          % (sure, Z['kare'], Z['fps'], Z['kare'], a.en, a.boy, os.path.basename(font),
             ' + SahneFont2 ' + os.path.basename(a.font2) if a.font2 else ''))
    print('SES     sahnede ses yok: ses.py miks ile ayri hazirlanir, render sonrasi ses.py ekle ile goruntuye eklenir')
    print('RENDER  hyperframes render "%s" --output "%s" --quality draft --workers 2'
          % (a.klasor, os.path.join(a.klasor, 'render', 'taslak.mp4')))
    print('        (2 isci: bilgisayarda baska is ya da render calisirken de guvenli; yalniz hicbir sey calismiyorsa 3, '
          'fazlasi bellegi doldurur)')
    print('NOT     yazi tipi: yalniz fonts/ icindeki dosyalari @font-face ile tanimlayip kullan; tanimsiz bir ad ya da '
          'sans-serif ile baslayan font-family render sirasinda Google Fonts\'tan sormadan indirilir (--yenile denetler)')
    print('NOT     sahne klasorunde index.html disinda .html birakma: lint "multiple_root_compositions" verir')


if __name__ == '__main__':
    main()
