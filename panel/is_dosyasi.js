// is_dosyasi.js - the job status file (isler/<id>/is.json): read, write safely, parse the gate result.
// Shared by server.js (the panel) and durum.js (what a Claude session calls to report progress).
// No dependencies. Files are written as UTF-8 without BOM, via a temp file + rename.
'use strict';
const fs = require('fs');
const path = require('path');

const ASAMALAR = ['ses', 'kanit', 'kurgu', 'kapi', 'hazir'];
// stage names come from the shared word list (sozluk.json) so the page, durum.js and the instructions agree
const ASAMA_AD = Object.fromEntries(ASAMALAR.map(a => [a, require('./sozluk').asamaAdi(null, a)]));
// stage states: bekliyor | suruyor | tamam | claude (waiting for the user's Claude) | durdu | kaldi | hata
// job states:   hazirlaniyor | calisiyor | claude_bekliyor | claude_calisiyor | durdu | kaldi | hazir | hata

function simdi() { return new Date().toISOString(); }

function bosIs(id, tarz, metin) {
  const asamalar = {};
  for (const a of ASAMALAR) asamalar[a] = { durum: 'bekliyor', not: '', zaman: null };
  return {
    surum: 1, id, olusturuldu: simdi(), guncellendi: simdi(),
    tarz, metin: metin || null, ham: [], ses: null,
    durum: 'hazirlaniyor', aciklama: 'Dosyalar yükleniyor.',
    asamalar, kapi: null, sonuc: null, baslik: null,
    talimat: 'panel/AJAN-TALIMATI.md',
    gecmis: [{ zaman: simdi(), olay: 'İş açıldı.' }],
  };
}

function oku(klasor) {
  const yol = path.join(klasor, 'is.json');
  for (let i = 0; i < 5; i++) {
    try {
      let t = fs.readFileSync(yol, 'utf8');
      if (t.charCodeAt(0) === 0xfeff) t = t.slice(1);
      return JSON.parse(t);
    } catch (e) {
      if (e.code === 'ENOENT') return null;
      // half-written by someone else: wait a moment and try again
      const bitis = Date.now() + 60; while (Date.now() < bitis) { /* short wait */ }
    }
  }
  return null;
}

function yaz(klasor, is) {
  is.guncellendi = simdi();
  const yol = path.join(klasor, 'is.json');
  const gecici = yol + '.' + process.pid + '.yaziliyor';
  fs.writeFileSync(gecici, JSON.stringify(is, null, 1), { encoding: 'utf8' });
  for (let i = 0; i < 20; i++) {
    try { fs.renameSync(gecici, yol); return; } catch (e) {
      if (i === 19) throw e;
      const bitis = Date.now() + 50; while (Date.now() < bitis) { /* file busy on Windows: retry */ }
    }
  }
}

function olay(is, metin) {
  is.gecmis = is.gecmis || [];
  is.gecmis.push({ zaman: simdi(), olay: metin });
}

function asamaKoy(is, asama, durum, not) {
  if (!is.asamalar[asama]) throw new Error('bilinmeyen aşama: ' + asama);
  is.asamalar[asama] = { durum, not: not || '', zaman: simdi() };
}

// "[GECTI] 1 KANIT: ..." lines + "SONUC: GECTI" (kod/kapi.py output)
function kapiCoz(metin) {
  const satirlar = [], uyarilar = []; let sonuc = null;
  for (const ham of String(metin).split(/\r?\n/)) {
    const s = ham.trim(); if (!s) continue;
    let m = s.match(/^\[(GECTI|KALDI)\]\s*(\d+)?\s*([^:]+):\s*(.*)$/);
    if (m) { satirlar.push({ durum: m[1], no: m[2] ? +m[2] : null, ad: m[3].trim(), ayrinti: m[4].trim() }); continue; }
    m = s.match(/^SONUC:\s*(\w+)/);
    if (m) sonuc = m[1];
    m = s.match(/^UYARI:\s*(.*)$/);              // a note under the gate, not a check (e.g. a clip without a score)
    if (m) uyarilar.push(m[1]);
  }
  return { sonuc, satirlar, uyarilar };
}

module.exports = { ASAMALAR, ASAMA_AD, bosIs, oku, yaz, olay, asamaKoy, kapiCoz, simdi };
