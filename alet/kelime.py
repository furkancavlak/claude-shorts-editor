# -*- coding: utf-8 -*-
"""kelime.py - snap Whisper word times to the sound. Whisper word starts can be off by 0.1-1 s (a word written at
486.16 whose sound starts at 487.20). This looks at the speech-band energy around each chosen word and moves its start
and end onto where the sound actually is. It never changes the text.

  hizala  py -3 alet/kelime.py hizala kayit.mp4 panel/isler/<id>/yazi/yazi.json --aralik 480:495 --cikti is/yazi-hizali.json
          py -3 alet/kelime.py hizala ses/ses.wav ses/ses.json --hepsi --cikti is/ses-hizali.json
          (choose words with --kelimeler "Battleskirt,M9", --aralik 480:495 (Whisper start inside), or --hepsi)

The output has the same shape {"kelimeler": [[word, start, end, p], ...]} so zaman.py --kelimeler and
cekim.py zaman --kelimeler read it directly. Each changed word is printed with its contrast (speech level over the
local floor): under 10 dB the sound is not clear enough and the Whisper time is kept ("GUVENSIZ").
Reliable when the voice is louder than what is under it; game sound or music at the same level can pull a start
early or late. Look at the frames or listen when it matters (the result line says which words moved most).
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortak import ses_oku, konusma_db, kelime_hizala, yazma_izni, yazildi, gecici_ad


def hizala_liste(media, kel, secili, kayma=0.0):
    """snap the chosen word indices; returns new list and a report list"""
    out = [list(w) for w in kel]
    rapor = []
    for i in secili:
        w = kel[i]
        ws, we = w[1] + kayma, w[2] + kayma
        alt = kel[i - 1][2] + kayma if i > 0 else None
        ust = kel[i + 1][1] + kayma if i + 1 < len(kel) else None
        bas = max(0.0, ws - 2.0)
        x = ses_oku(media, bas=bas, sure=(we - ws) + 4.0)
        e = konusma_db(x)
        s, t, c = kelime_hizala(e, bas, ws, we, alt, ust)
        ok = c >= 10
        if ok:
            out[i][1], out[i][2] = round(s - kayma, 3), round(t - kayma, 3)
        rapor.append((i, w[0], w[1], w[2], out[i][1], out[i][2], c, ok))
    return out, rapor


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='komut', required=True)
    p = sp.add_parser('hizala', help='snap chosen words to the sound')
    p.add_argument('medya', help='the audio or video the timings belong to (same seconds)')
    p.add_argument('kelimeler_json', help='{"kelimeler": [[word, start, end, p], ...]}')
    p.add_argument('--kelimeler', help='comma separated words to snap (every occurrence, case-insensitive)')
    p.add_argument('--aralik', help='a:b seconds, snap words whose Whisper start is inside (--cikti is still the WHOLE word '
                   'file: only the chosen words get new times, the rest are copied unchanged)')
    p.add_argument('--hepsi', action='store_true', help='snap every word (slow on a long recording)')
    p.add_argument('--cikti', required=True); p.add_argument('--ustune-yaz', action='store_true')
    a = ap.parse_args()
    yazma_izni(a.cikti, a.ustune_yaz)
    d = json.load(open(a.kelimeler_json, encoding='utf-8'))
    kel = d['kelimeler']
    if a.hepsi:
        sec = list(range(len(kel)))
    elif a.kelimeler:
        ad = {z.strip().lower() for z in a.kelimeler.split(',') if z.strip()}
        sec = [i for i, w in enumerate(kel) if w[0].strip().lower().strip('.,!?;:') in {q.strip('.,!?;:') for q in ad}]
    elif a.aralik:
        lo, hi = [float(z) for z in a.aralik.split(':')]
        sec = [i for i, w in enumerate(kel) if lo <= w[1] <= hi]
    else:
        sys.exit('--kelimeler, --aralik ya da --hepsi ver')
    if not sec:
        sys.exit('secilen kelime yok')
    yeni, rapor = hizala_liste(a.medya, kel, sec)
    print('KELIME  (Whisper bas-son  ->  ses bas-son, fark, kontrast)')
    for i, w, s0, e0, s1, e1, c, ok in rapor:
        print('  %4d %-16s %8.3f-%8.3f -> %8.3f-%8.3f  %+.2f/%+.2f sn  %4.1f dB%s' % (
            i, w[:16], s0, e0, s1, e1, s1 - s0, e1 - e0, c, '' if ok else '  GUVENSIZ (Whisper zamani kaldi)'))
    buyuk = sorted(rapor, key=lambda r: -max(abs(r[4] - r[2]), abs(r[5] - r[3])))[:3]
    print('EN COK KAYAN  ' + ', '.join('%s %+.2f sn' % (r[1], r[4] - r[2]) for r in buyuk) + '  (gerekirse karelere bak / dinle)')
    d2 = dict(d)
    d2['kelimeler'] = yeni
    d2['hizalama'] = {'arac': 'kelime.py', 'degisen': [r[0] for r in rapor if r[7]], 'kaynak': os.path.abspath(a.kelimeler_json)}
    tmp = gecici_ad(a.cikti)
    try:
        json.dump(d2, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.replace(tmp, a.cikti)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    yazildi(a.cikti, 'kelime.py')
    print('CIKTI   %s' % a.cikti)


if __name__ == '__main__':
    main()
