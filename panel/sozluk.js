// sozluk.js - the panel's shared words (sozluk.json) and the one plain-language status of a job.
// Used by server.js (the page gets the same object as `panelde`) and durum.js (`ozet` prints it as text),
// so the user on the page and an agent in a terminal read the same sentence for the same state.
'use strict';
const fs = require('fs');
const path = require('path');

const S = JSON.parse(fs.readFileSync(path.join(__dirname, 'sozluk.json'), 'utf8').replace(/^﻿/, ''));
const SESSIZ_MS = 30 * 60 * 1000;          // Claude working with no news for this long counts as silent (same as server.js)
const SIRA = ['ses', 'kanit', 'kurgu', 'kapi', 'hazir'];

const turAdi = t => (S.turler[t] || {}).ad || t;
const anaTur = t => (S.turler[t] || {}).ana || 'short';
function asamaAdi(tarz, a) { const x = S.asamalar[a] || {}; return (tarz === 'klip' && x.ad_klip) || x.ad || a; }
function asamaSimdi(tarz, a) { const x = S.asamalar[a] || {}; return (tarz === 'klip' && x.simdi_klip) || x.simdi || ''; }

// Is the preparation of a "calisiyor" job still running? panel/is_ac.js (panel/hazirlik.js) writes
// is.hazirlayan = {pid, baslangic} while it prepares and removes it at the end. A job opened by an older is_ac.js has
// no such record: silent for 10 minutes counts as stopped. Windows reuses PIDs: a live PID with no news for 4 hours is
// not trusted either (the longest step, the moment finder, writes nothing for up to a few hours on a long recording).
const ESKI_SESSIZ_MS = 10 * 60 * 1000, PID_SESSIZ_MS = 4 * 3600 * 1000;
function yasiyor(pid) { try { process.kill(pid, 0); return true; } catch (e) { return e.code === 'EPERM'; } }
function hazirlikSuruyor(is) {
  if (!is || is.durum !== 'calisiyor') return false;
  const sessiz = Date.now() - Date.parse(is.guncellendi || 0);
  if (is.hazirlayan && /^\d+$/.test(String(is.hazirlayan.pid))) return sessiz < PID_SESSIZ_MS && yasiyor(+is.hazirlayan.pid);
  return sessiz < ESKI_SESSIZ_MS;
}

// The one question after delivery ("En çok neyi beğendin?") is shown only once the agent says it asked it
// (node panel/durum.js <iş> soruldu): is.soru = {metin, zaman}, not older than this delivery.
function soruMetni(is) {
  if (!is || is.durum !== 'hazir' || !is.soru || !is.soru.metin) return null;
  const teslim = Date.parse((is.asamalar && is.asamalar.hazir && is.asamalar.hazir.zaman) || 0) || 0;
  return Date.parse(is.soru.zaman || 0) >= teslim - 2000 ? String(is.soru.metin) : null;
}

// the job's short name a person says in the chat ("GTA 6'yı almadan önce", "yayin-14-kasim"): the title, the first words
// of the text, or the recording's file name. The page and the "Ne yap?" sentence use the same name.
function isAdi(is) {
  const dosya = is.ham && is.ham[0] && is.ham[0].ad ? String(is.ham[0].ad).replace(/\.[^.]+$/, '') : '';
  if (is.tarz === 'klip' && dosya) return dosya;
  const metin = is.baslik || (is.metin && !String(is.metin).includes('�') ? is.metin : '') || (is.yazi && is.yazi.metin) || '';
  if (String(metin).trim()) { const k = String(metin).trim().split(/\s+/); return k.slice(0, 4).join(' ').replace(/[.,;:!?]+$/, '') + (k.length > 4 ? '…' : ''); }
  return dosya || 'İş ' + is.id;
}

// is: the job (is.json, or server.js's summary). ek: { takildi } (default: "calisiyor" but its preparation is not running)
function durumOzet(is, ek = {}) {
  let d = S.durumlar[is.durum] || { ad: is.durum, kim: 'sen', simdi: '' };
  let ozel = null, ne_oldu = null;
  const takildi = ek.takildi === undefined ? is.durum === 'calisiyor' && !hazirlikSuruyor(is) : !!ek.takildi;
  const sessizDk = is.durum === 'claude_calisiyor' && is.guncellendi && Date.now() - Date.parse(is.guncellendi) > SESSIZ_MS
    ? Math.round((Date.now() - Date.parse(is.guncellendi)) / 60000) : 0;
  if (sessizDk) { ozel = 'sessiz'; d = { ...d, ...S.ozel_durumlar.sessiz }; ne_oldu = d.ne_oldu.replace('{dk}', sessizDk); }
  else if (takildi) { ozel = 'yarida'; d = { ...d, ...S.ozel_durumlar.yarida }; ne_oldu = d.ne_oldu; }
  else if (['durdu', 'kaldi', 'hata'].includes(is.durum)) ne_oldu = is.aciklama || null;
  // ne_yap: only when something is wrong, and always something to say to Claude in the chat
  const ad = isAdi(is);
  const ne_yap = String((ozel ? d.ne_yap : ['durdu', 'hata'].includes(is.durum) ? (is.ne_yap || d.ne_yap) : (d.ne_yap || '')) || '').replace(/\{is\}/g, ad);
  const klip = anaTur(is.tarz) === 'klip';
  const asamalar = SIRA.filter(a => is.asamalar && is.asamalar[a]).map(a => ({ kod: a, ad: asamaAdi(is.tarz, a),
    kisa: (klip && (S.asamalar[a] || {}).kisa_klip) || (S.asamalar[a] || {}).kisa || asamaAdi(is.tarz, a),
    durum: is.asamalar[a].durum, durum_adi: S.asama_durumlari[is.asamalar[a].durum] || is.asamalar[a].durum, not: is.asamalar[a].not || '',
    zaman: is.asamalar[a].zaman || null }));
  const suren = asamalar.slice().reverse().find(a => ['durdu', 'kaldi', 'hata'].includes(a.durum)) ||
    asamalar.find(a => ['suruyor', 'claude'].includes(a.durum));          // a problem stage wins over a running one
  // where the job is on its five steps: the problem/running step, else the first one not done ("3/5 · Kurgu")
  const yer = suren || asamalar.find(a => a.durum !== 'tamam') || asamalar[asamalar.length - 1];
  const adim = yer ? { no: asamalar.indexOf(yer) + 1, toplam: asamalar.length, ad: yer.kisa } : null;
  // one plain sentence of what is happening now ("Claude kurguluyor", "Motor konuşmayı yazıya döküyor")
  const sa = suren && ['suruyor', 'claude'].includes(suren.durum) ? S.asamalar[suren.kod] || {} : null;
  const eylem = String(ozel ? (d.eylem || ne_oldu) : ['calisiyor', 'claude_calisiyor'].includes(is.durum) && sa && (sa.eylem || sa.eylem_klip)
    ? ((klip && sa.eylem_klip) || sa.eylem) : (d.eylem || d.ad || '')).replace('{dk}', sessizDk);
  return {
    durum: is.durum, ozel, durum_adi: d.ad, kim: d.kim, sira: S.kim[d.kim], ad, eylem, adim,
    ne_oldu, ne_yap: ne_yap || null, simdi: ozel ? ne_oldu : d.simdi,
    su_an: is.durum === 'claude_calisiyor' || is.durum === 'calisiyor' ? (is.aciklama || '') : '',
    asama: suren ? suren.ad : null, asama_kod: suren ? suren.kod : null, asama_zaman: suren ? suren.zaman : null, asamalar,
    tur: anaTur(is.tarz) === 'klip' ? S.ana_turler.klip.ad + (is.kurgu ? ' · ' + ((S.kurgu[is.kurgu] || {}).ad || is.kurgu) : '')
      : S.ana_turler.short.ad + ' · ' + turAdi(is.tarz),
    soru: soruMetni(is),
  };
}

// the instruction an agent session reads for this job (kept for agents and the API; the page does not show it)
const kopyaCumle = (klasor, tarz) => `"${path.join(klasor, 'CLAUDE-ICIN.md')}" dosyasını oku ve bu ${anaTur(tarz) === 'klip' ? 'Klip' : 'Short'} işini yap.`;

// the same status as plain text lines (durum.js ozet, GET /api/is/<id>/ozet)
function ozetMetni(is, o, ek = {}) {
  const L = [`İş ${is.id} · ${o.ad} · ${o.tur}`,
    `Durum: ${o.durum_adi} · ${o.sira}${o.adim ? ` · ${o.adim.no}/${o.adim.toplam} ${o.adim.ad}` : ''}`];
  if (o.eylem && o.eylem !== o.durum_adi) L.push(`Şu iş: ${o.eylem}`);
  if (o.ne_oldu) L.push(`Ne oldu: ${o.ne_oldu}`);
  else L.push(`Şimdi: ${o.simdi}`);
  if (o.su_an) L.push(`Şu an: ${o.su_an}`);
  if (o.ne_yap) L.push(`Ne yap: ${o.ne_yap}`);
  L.push('Aşamalar: ' + o.asamalar.map(a => `${a.ad} ${a.durum_adi}`).join(' · '));
  if (ek.cumle && ['claude_bekliyor', 'claude_calisiyor'].includes(is.durum)) L.push(`Ajan için: ${ek.cumle}`);
  if (is.durum === 'hazir' && is.sonuc) {
    if (is.sonuc.video) L.push(`Video: ${ek.klasor ? path.join(ek.klasor, is.sonuc.video) : is.sonuc.video}`);
    for (const k of is.sonuc.klipler || []) L.push(`Klip: ${ek.klasor ? path.join(ek.klasor, k.video) : k.video}${k.baslik ? ' · ' + k.baslik : ''}`);
    const soru = o.soru === undefined ? soruMetni(is) : o.soru;      // only after "durum.js soruldu"
    if (soru) L.push(String(S.hazir_soru).replace('{soru}', soru));
  }
  return L.join('\n');
}

module.exports = { S, SESSIZ_MS, turAdi, anaTur, asamaAdi, asamaSimdi, isAdi, durumOzet, ozetMetni, kopyaCumle, hazirlikSuruyor, soruMetni };
