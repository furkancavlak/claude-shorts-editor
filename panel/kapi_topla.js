#!/usr/bin/env node
// kapi_topla.js - the gate of a FREELY edited job (alet/ tool kit): runs alet/kontrol.py on every finished video and
// writes the job's kapi_sonuc.txt in the shape the panel reads ("[GECTI] 1 klip-1: ..." lines + "SONUC: ...").
//
//   Klip (Editli):  node panel/kapi_topla.js panel/isler/<id>
//                   reads panel/isler/<id>/klipler/klipler.json; every entry names its own "zaman" (the zaman.py
//                   output folder the clip was built from) and "ses" (the final mastered wav attached to it),
//                   both relative to klipler/.
//   Short:          node panel/kapi_topla.js panel/isler/<id> --ses <final.wav> [--zaman <shots folder>]
//                   checks panel/isler/<id>/short.mp4; --zaman = the folder alet/cekim.py cut the shots into (the
//                   shots the stage's index.html uses are checked for repeated frames; kontrol.py finds the stage, or
//                   give --sahne <stage folder>), or a zaman.py output folder
//   Any other option (e.g. --konusma x.wav) is passed on unchanged to every "kontrol.py hepsi" call, except
//   --min / --max: the length limits (Short 10-60 s, clip 15-60 s) are not changed from here.
//
// Writes <video>.kontrol.txt next to every video (kontrol.py's own output) and panel/isler/<id>/kapi_sonuc.txt.
// Klip: also writes each clip's measured size ("boyut") and length ("sure") into klipler.json (the panel shows
// them). Nothing else changes.
// Then: node panel/durum.js <iş> kapi <iş>/kapi_sonuc.txt   and   node panel/durum.js <iş> hazir ...
// Exit code 0 = every video passed, 1 = something did not pass (kapi_sonuc.txt says what), 2 = wrong use / missing file.
'use strict';
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const J = require('./is_dosyasi');

const MOTOR = path.dirname(__dirname);
const KONTROL = path.join(MOTOR, 'alet', 'kontrol.py');
const PY = process.env.PANEL_PYTHON ? process.env.PANEL_PYTHON.split(' ') : (process.platform === 'win32' ? ['py', '-3'] : ['python3']);
// kontrol.py hepsi prints one line per check; a missing line means that check did not run
const GEREKEN_KLIP = ['OZET', 'SIYAH', 'KOPYA', 'KAYMA', 'SON'];
const GEREKEN_SHORT = ['OZET', 'SIYAH', 'KAYMA', 'SON'];

function kullan(m) { console.error('HATA: ' + m + '\n' + fs.readFileSync(__filename, 'utf8').split('\n').slice(1, 20).join('\n')); process.exit(2); }

const arg = process.argv.slice(2);
if (!arg[0] || arg[0].startsWith('--')) kullan('iş klasörünü ver');
const klasor = path.resolve(arg[0]);
const is = J.oku(klasor);
if (!is) kullan('iş dosyası yok: ' + path.join(klasor, 'is.json'));
const bayraklar = {}, ek = [];           // --ses / --zaman are ours; everything else goes on to kontrol.py as given
for (let i = 1; i < arg.length; i++) {
  if ((arg[i] === '--ses' || arg[i] === '--zaman') && arg[i + 1] != null) bayraklar[arg[i]] = arg[++i];
  else if (/^--(min|max)(=|$)/.test(arg[i])) kullan('süre sınırı kapıdan değiştirilmez (' + arg[i] + '). Video sınırın dışındaysa kullanıcıya söyle: Short 10-60 sn, klip 15-60 sn (panel/AJAN-TALIMATI.md, "Çıta": malzeme inceyse)');
  else ek.push(arg[i]);
}

// one video -> { durum, ayrinti, sure } ; kontrol.py's full output is kept next to the video
// klip: zaman = zaman.py output (video.mp4 + zamanlar.json); short: zaman = cekim.py shots folder (or a zaman.py one)
function denetle(ad, video, zaman, ses, sinir, gereken, klip) {
  if (!fs.existsSync(video)) kullan(ad + ': video yok: ' + video);
  if (!ses || !fs.existsSync(ses)) kullan(ad + ': son ses dosyası (ses) yok: ' + ses);
  if (zaman && !fs.existsSync(zaman)) kullan(ad + ': zaman klasörü yok: ' + zaman);
  if (zaman && klip) for (const f of ['video.mp4', 'zamanlar.json'])
    if (!fs.existsSync(path.join(zaman, f))) kullan(ad + ': zaman klasöründe ' + f + ' yok (alet/zaman.py çıktısı olmalı): ' + zaman);
  if (zaman && !klip && !fs.existsSync(path.join(zaman, 'video.mp4')) && !fs.readdirSync(zaman).some(f => /\.mp4$/i.test(f)))
    kullan(ad + ': çekim klasöründe hiç .mp4 yok (alet/cekim.py çekimleri buraya yazar): ' + zaman);
  // kontrol.py reads the last word from zamanlar.json in that folder (cekim.py zaman writes it)
  if (zaman && !klip && !fs.existsSync(path.join(zaman, 'zamanlar.json')))
    kullan(ad + ': çekim klasöründe zamanlar.json yok; önce: py -3 alet/cekim.py zaman "' + zaman + '" --kelimeler <iş>/ses/ses.json');
  const a = [...PY.slice(1), KONTROL, 'hepsi', video, '--ses', ses, '--min', String(sinir[0]), '--max', String(sinir[1]), ...ek];
  if (zaman) a.push('--zaman', zaman);
  const r = spawnSync(PY[0], a, { cwd: MOTOR, encoding: 'utf8', windowsHide: true, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  const cikti = String(r.stdout || '') + (r.stderr ? String(r.stderr) : '');
  fs.writeFileSync(video + '.kontrol.txt', cikti, 'utf8');
  const satirlar = cikti.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const sonuc = [...satirlar].reverse().find(s => /^SONUC:/.test(s)) || '';
  const eksik = gereken.filter(g => !satirlar.some(s => s.startsWith(g + ' ') || s === g));
  const neden = [];
  // kontrol.py hepsi exits 0 on GECTI and 1 on KALDI (older versions: 0 on both); anything else is a crash
  if (!sonuc || !(r.status === 0 || (r.status === 1 && /^SONUC:\s*KALDI/.test(sonuc))))
    neden.push('kontrol.py çalışmadı (ayrıntı: ' + path.basename(video) + '.kontrol.txt)');
  if (/^SONUC:\s*KALDI/.test(sonuc)) neden.push(sonuc.replace(/^SONUC:\s*KALDI:?\s*/, ''));
  if (eksik.length) neden.push('yapılmayan kontrol: ' + eksik.join(', '));
  const kopya = satirlar.filter(s => /^KOPYA\s/.test(s));
  // the black-frame check in a few words (its full line carries the video's path)
  const sy = (satirlar.find(s => /^SIYAH\s/.test(s)) || '').match(/siyahlik (\d+)/);
  const siyah = sy ? 'SIYAH 1-2 karelik siyah kare ' + sy[1] : '';
  if (siyah && neden.length && !neden.some(n => /siyah kare/.test(n))) neden.push(siyah);
  // a shot's first frame shown twice after a cut: kontrol.py only warns, so it never turns the result into KALDI
  const dn = (satirlar.find(s => /^DONMA\s/.test(s)) || '').match(/iki kez gorunen ilk kare (\d+)(.*)$/);
  if (dn && +dn[1] > 0) uyari.push(ad + ': çekim başında bir kare donma' + dn[2].replace(/\s+/g, ' ') + ' (kontrol.py donma; ayrıntı ' + path.basename(video) + '.kontrol.txt)');
  const ozet = [siyah, kopya.length > 1   // a shots folder: one line for all of its shots
    ? `KOPYA ${kopya.length} çekim, hareket içinde tekrar eden kare toplam ${kopya.reduce((t, s) => t + +((s.match(/tekrar eden kare (\d+)/) || [])[1] || 0), 0)}`
    : kopya[0], ...satirlar.filter(s => /^(KAYMA|SON)\s/.test(s))].filter(Boolean).map(s => s.replace(/\s+/g, ' ')).join(' | ');
  const boyut = (satirlar[satirlar.findIndex(s => s.startsWith('OZET')) + 1] || '').replace(/\s+/g, ' ');
  const sure = parseFloat((boyut.match(/([\d.]+) sn/) || [])[1]);           // the video's real length (ffprobe)
  return neden.length ? { durum: 'KALDI', ayrinti: neden.join(' ; '), sure }
    : { durum: 'GECTI', ayrinti: [boyut, ozet].filter(Boolean).join(' | '), sure };
}

const satir = [], uyari = [];
if (is.tarz === 'klip') {
  const kk = path.join(klasor, 'klipler'), lj = path.join(kk, 'klipler.json');
  if (!fs.existsSync(lj)) kullan('klipler.json yok: ' + lj);
  let liste; try { liste = JSON.parse(fs.readFileSync(lj, 'utf8').replace(/^﻿/, '')); } catch (e) { kullan('klipler.json okunamadı: ' + e.message); }
  if (!Array.isArray(liste) || !liste.length) kullan('klipler.json boş ya da liste değil');
  for (const k of liste) {
    const eksikAlan = ['ad', 'video', 'zaman', 'ses', 'bas', 'son', 'sure', 'neden', 'baslik'].filter(f => k[f] == null || k[f] === '');
    if (eksikAlan.length) kullan('klipler.json, ' + (k.ad || '?') + ': eksik alan: ' + eksikAlan.join(', '));
    if (k.puan == null) uyari.push(k.ad + ': puan yok (panel klipleri puana göre sıralar)');
  }
  liste.forEach((k, i) => {
    // a range the USER gave is cut as given: outside 15-60 s it is a note, not a fail (same as kod/klip_kapi.py)
    const verilen = k.kullanici && k.kullanici.tur === 'aralik';
    if (verilen && !(k.sure >= 15 && k.sure <= 60)) uyari.push(`${k.ad}: senin verdiğin aralık ${k.sure} sn, 15-60 sn dışında`);
    const r = denetle(k.ad, path.join(kk, k.video), path.join(kk, k.zaman), path.join(kk, k.ses), verilen ? [1, 3600] : [15, 60], GEREKEN_KLIP, true);
    satir.push(`[${r.durum}] ${i + 1} ${k.ad}: ${r.ayrinti}`);
    k.boyut = fs.statSync(path.join(kk, k.video)).size;
    if (r.sure > 0) k.sure = Math.round(r.sure * 100) / 100;
  });
  fs.writeFileSync(lj, JSON.stringify(liste, null, 1) + '\n', 'utf8');
} else {
  const ses = bayraklar['--ses'], zaman = bayraklar['--zaman'];
  if (!ses) kullan('Short işinde --ses <son ses dosyası> gerekli');
  // 10 s = the shortest Short (the same number as alet/kontrol.py's --min default, alet/ALETLER.md and panel/AJAN-TALIMATI.md)
  const r = denetle('short', path.join(klasor, 'short.mp4'), zaman && path.resolve(zaman), path.resolve(ses), [10, 60],
    zaman ? [...GEREKEN_SHORT, 'KOPYA'] : GEREKEN_SHORT, false);
  if (!zaman) uyari.push('--zaman verilmedi: kare kopyası kontrolü yapılmadı');
  satir.push(`[${r.durum}] 1 short: ${r.ayrinti}`);
}
const gecti = satir.every(s => s.startsWith('[GECTI]'));
const metin = [...satir, ...uyari.map(u => 'UYARI: ' + u), 'SONUC: ' + (gecti ? 'GECTI' : 'KALDI')].join('\n') + '\n';
fs.writeFileSync(path.join(klasor, 'kapi_sonuc.txt'), metin, 'utf8');
process.stdout.write(metin);
console.log('Yazıldı: ' + path.join(klasor, 'kapi_sonuc.txt'));
process.exit(gecti ? 0 : 1);
