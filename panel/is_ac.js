#!/usr/bin/env node
// is_ac.js - open a job from the chat (no web server, no browser) and run the engine's preparation in the foreground.
// The job folder is the one contract every part reads (panel/isler/<id>/is.json + files): panel/durum.js,
// panel/AJAN-TALIMATI.md and the watch page (panel/server.js, read only) all read it the same way.
//
//   node panel/is_ac.js klip <kayıt.mp4> [--adet 3] [--kurgu sade|editli] [--altyazisiz] [--an 12:30-13:05]... [--anlar "12:30;45:10-45:40"]
//                            [--sohbet <sohbet.txt|.json>] [--sohbet-kutu x0,y0,x1,y1] [--ses-izi 0]
//   node panel/is_ac.js short <tek_bilgi|liste|karsilastirma> --video <dosya|klasör>... (--metin "..." | --metin-dosya <m.txt>) [--ses <kayıt.m4a>]
//   node panel/is_ac.js devam <iş klasörü ya da kimliği>      continue: half-prepared, stopped, broken or gate-failed job
//   node panel/is_ac.js --help                                this text
//
// Klip: captions are on unless --altyazisiz (--altyazi is still accepted and changes nothing). The recording is used
// IN PLACE from its path (never copied). Short: the videos are copied into ham/ (a file over 500 MB is used in place
// instead), the voice into ses/. Nothing the user gave is moved, changed or deleted. Every job gets an empty bak/ for
// the agent's contact sheets.
// Preparation (panel/hazirlik.js), in this order: Klip = transcription of the recording (local Whisper) -> camera
// suggestion (kod/kamera_bul.py) -> candidate moments (kod/klip_bul.py, which uses the camera box); Short =
// placeholder voice from the text when no voice is given (Windows Turkish voice) -> transcription -> the words snapped
// to the sound (alet/kelime.py hizala --hepsi -> ses/ses-hizali.json). Before it starts, the transcription device
// (graphics card or processor) and a time estimate are printed.
// Refuses before writing anything when a requirement is missing (see KURULUM-AJAN.md).
// Jobs folder: panel/isler/, or PANEL_ISLER (same variable as the page). Exit: 0 ready, 1 failed, 2 wrong use, 3 setup missing.
'use strict';
const fs = require('fs');
const path = require('path');
const J = require('./is_dosyasi');
const SZ = require('./sozluk');
const H = require('./hazirlik');

const ISLER = process.env.PANEL_ISLER ? path.resolve(process.env.PANEL_ISLER) : path.join(H.PANEL, 'isler');
const { virgul, VIDEO_UZ, SES_UZ, SOHBET_UZ, AN_RE, SHORT_TURLER, KOPYA_SINIR } = H;

const yaz = m => process.stdout.write(m + '\n');
function dur(kod, m) { (kod === 0 ? process.stdout : process.stderr).write(m + '\n'); process.exit(kod); }
const kullanim = () => fs.readFileSync(__filename, 'utf8').split('\n').filter(s => /^\/\/\s{2,}(node panel|\s+\[--)/.test(s)).map(s => s.replace(/^\/\/ ?/, '')).join('\n');
function kullan(m) { dur(2, 'HATA: ' + m + '\n' + kullanim()); }
// the page's words (sozluk.js); a plain fallback so a word-list change can never stop a preparation
const turYazi = is => { try { return SZ.durumOzet(is).tur; } catch (_) { return is.tarz + (is.kurgu ? ' · ' + is.kurgu : ''); } };
const ozetYazi = (is, klasor) => { try { return SZ.ozetMetni(is, SZ.durumOzet(is), { klasor }); }
  catch (_) { return `İş ${is.id} · ${turYazi(is)}\nDurum: ${is.durum} · ${is.aciklama || ''}`; } };
const temizYol = s => path.resolve(String(s || '').trim().replace(/^"(.*)"$/, '$1'));

function kurulumKontrol() {
  const eksik = H.kurulumEksigi();
  if (eksik.length) dur(3, 'KURULUM EKSIK: ' + eksik.join(', ') + '\nİş açılmadı, hiçbir şey yazılmadı. Önce kurulum: KURULUM-AJAN.md ' +
    '(kullanıcıya: "Önce kurulumu tamamlamam gerekiyor"; ne kurulu, ne eksik: py -3 kur_kontrol.py).');
}

// ------------------------------------------------------------------ arguments
const BAYRAK = ['altyazi', 'altyazisiz', 'help'];           // flags without a value
function argOku(liste) {
  const a = { _: [], video: [], an: [] };
  for (let i = 0; i < liste.length; i++) {
    const x = liste[i];
    if (x === '-h') { a.help = true; continue; }
    if (!x.startsWith('--')) { a._.push(x); continue; }
    const ad = x.slice(2);
    if (BAYRAK.includes(ad)) { a[ad] = true; continue; }
    const v = liste[++i]; if (v === undefined) kullan(x + ' için değer yok');
    if (ad === 'video') a.video.push(v); else if (ad === 'an') a.an.push(v); else a[ad] = v;
  }
  return a;
}

function videoListesi(girdiler) {
  const out = [];
  for (const g of girdiler) {
    const y = temizYol(g); let st;
    try { st = fs.statSync(y); } catch (_) { dur(2, 'HATA: Bu adreste dosya ya da klasör yok: ' + y); }
    if (st.isDirectory()) {
      const f = fs.readdirSync(y).filter(n => VIDEO_UZ.includes(path.extname(n).toLowerCase())).sort().map(n => path.join(y, n));
      if (!f.length) dur(2, 'HATA: Bu klasörde video yok (mp4, mkv, mov, webm): ' + y);
      out.push(...f);
    } else if (VIDEO_UZ.includes(path.extname(y).toLowerCase())) out.push(y);
    else dur(2, 'HATA: "' + path.basename(y) + '" bir video değil (mp4, mkv, mov, webm).');
  }
  return out;
}

// the transcription device and how long it will take, printed BEFORE the long step starts
function cihazYaz(saniye, ne) {
  const c = H.yaziCihazi(), t = H.yaziTahmini(saniye, c);
  yaz(`YAZIYA DOKME ${t.ne}; ${ne} için tahmin ${t.sure}.` + (t.uzun ? ' Komut senin süre sınırını aşabilir: arka planda çalıştır, bitince çıktısını oku.' : ''));
}

// ------------------------------------------------------------------ create
async function olustur(tur, a) {
  const klip = tur === 'klip';
  let kayit, videolar = [], ses = null, sohbet = null, metin = '';
  const yeni = {}, uyarilar = [];
  if (klip) {
    if (a._.length !== 1) kullan('Klip için tek bir kayıt ver: node panel/is_ac.js klip "<kayıt.mp4>"');
    kayit = temizYol(a._[0]);
    let st; try { st = fs.statSync(kayit); } catch (_) { dur(2, 'HATA: Bu adreste dosya yok: ' + kayit); }
    if (!st.isFile() || !VIDEO_UZ.includes(path.extname(kayit).toLowerCase())) dur(2, 'HATA: "' + path.basename(kayit) + '" bir video değil (mp4, mkv, mov, webm).');
    yeni.adet = Math.max(1, Math.min(10, parseInt(a.adet, 10) || 3));
    yeni.altyazi = a.altyazisiz !== true;              // captions on unless the user said "altyazısız"
    if (a.kurgu && !['sade', 'editli'].includes(a.kurgu)) dur(2, 'HATA: --kurgu sade ya da editli olmalı.');
    yeni.kurgu = a.kurgu === 'editli' ? 'editli' : 'sade';
    const anlar = [...a.an, ...String(a.anlar || '').split(/[;\r\n]+/)].map(x => x.trim()).filter(Boolean);
    const kotu = anlar.filter(x => !AN_RE.test(x));
    if (kotu.length) dur(2, 'HATA: "' + kotu.join('", "') + '" anını anlayamadım. Dakika:saniye yaz: 12:30, aralık için 12:30-13:05, bir saati geçerse 1:02:30.');
    if (anlar.length > 20) dur(2, 'HATA: En çok 20 an verilebilir.');
    if (anlar.length) { yeni.anlar = anlar; yeni.adet = anlar.length; }
    if (a['sohbet-kutu']) {
      const k = String(a['sohbet-kutu']).split(/[ ,;]+/).filter(Boolean).map(Number);
      if (k.length !== 4 || k.some(v => !(v >= 0 && v <= 1)) || k[0] >= k[2] || k[1] >= k[3]) dur(2, 'HATA: --sohbet-kutu 0 ile 1 arası dört sayı olmalı: 0.75,0.1,1,0.9');
      yeni.sohbet_kutu = k;
    }
    if (a['ses-izi'] !== undefined) { const n = parseInt(a['ses-izi'], 10); if (!(n >= 0)) dur(2, 'HATA: --ses-izi 0, 1, 2 ... olmalı.'); yeni.ses_izi = n; }
    if (a.sohbet) {
      sohbet = temizYol(a.sohbet);
      if (!fs.existsSync(sohbet) || !SOHBET_UZ.includes(path.extname(sohbet).toLowerCase())) dur(2, 'HATA: Sohbet dosyası yok ya da .txt/.json değil: ' + sohbet);
    }
  } else {
    if (!SHORT_TURLER.includes(a._[0])) kullan('Short türü şunlardan biri: tek_bilgi, liste, karsilastirma');
    if (!a.video.length) dur(2, 'HATA: Short için en az bir video ver: --video "<dosya ya da klasör>"');
    videolar = videoListesi(a.video);
    if (a['metin-dosya']) { try { metin = fs.readFileSync(temizYol(a['metin-dosya']), 'utf8').replace(/^﻿/, ''); } catch (_) { dur(2, 'HATA: Metin dosyası okunamadı: ' + a['metin-dosya']); } }
    else metin = a.metin || '';
    metin = metin.replace(/\r\n/g, '\n').trim().slice(0, 4000);
    if (a.ses) {
      ses = temizYol(a.ses);
      if (!fs.existsSync(ses) || !SES_UZ.includes(path.extname(ses).toLowerCase())) dur(2, 'HATA: Ses dosyası yok ya da tanınmadı (wav, m4a, mp3): ' + ses);
    }
    if (!ses && !metin) dur(2, 'HATA: Short için sesini (--ses) ya da söyleyeceklerini (--metin / --metin-dosya) ver.');
    if (!ses && process.platform !== 'win32') dur(2, 'HATA: Ses dosyası yok ve yer tutucu ses yalnız Windows\'ta var: --ses ile kaydı ver.');
    const kelime = metin ? metin.split(/\s+/).filter(Boolean).length : 0;
    if (!ses && kelime < H.SHORT_EN_AZ_KELIME)
      uyarilar.push(`UYARI: metin ${kelime} kelime; Short en az ${H.SHORT_EN_AZ_SN} sn (kabaca ${H.SHORT_EN_AZ_KELIME} kelime). Kurmadan önce kullanıcıya "bir-iki cümle ekle" de ` +
        '(panel/AJAN-TALIMATI.md, Çıta, "Malzeme inceyse"). İş yine de açılıyor.');
  }
  kurulumKontrol();
  // every video must open before anything is written: a refused request leaves nothing behind
  const bilgiler = new Map();
  for (const v of klip ? [kayit] : videolar) {
    const b = H.probe(v);
    if (!b || !b.goruntu) dur(2, 'HATA: "' + path.basename(v) + '" açılmıyor ya da içinde görüntü yok. Doğru videoyu ver.');
    bilgiler.set(v, b);
  }
  fs.mkdirSync(ISLER, { recursive: true });
  const id = H.yeniId(ISLER), klasor = path.join(ISLER, id);
  const is = J.bosIs(id, klip ? 'klip' : a._[0], klip ? '' : metin);
  Object.assign(is, yeni);
  is.acan = 'sohbet';                      // opened from the chat with is_ac.js
  for (const d of ['ham', 'ses', 'bak']) fs.mkdirSync(path.join(klasor, d), { recursive: true });
  if (is.anlar) fs.writeFileSync(path.join(klasor, 'anlar.txt'), is.anlar.join('\n') + '\n', 'utf8');
  fs.writeFileSync(path.join(klasor, 'CLAUDE-ICIN.md'), H.claudeIcin(id, klasor), 'utf8');
  if (klip) {
    is.ham = [{ dosya: kayit, ad: path.basename(kayit), boyut: fs.statSync(kayit).size, yerinde: true }];
    J.olay(is, 'Kayıt yerinde kullanılacak (kopyalanmadı): ' + kayit);
    if (sohbet) {
      const uz = path.extname(sohbet).toLowerCase(), hk = path.join(klasor, 'sohbet'); fs.mkdirSync(hk, { recursive: true });
      fs.copyFileSync(sohbet, path.join(hk, 'sohbet' + uz), fs.constants.COPYFILE_EXCL);
      is.sohbet = { dosya: 'sohbet/sohbet' + uz, ad: H.guvenliAd(path.basename(sohbet)), boyut: fs.statSync(sohbet).size };
      J.olay(is, 'Sohbet dosyası eklendi: ' + is.sohbet.ad);
    }
  } else {
    J.yaz(klasor, is);
    for (const v of videolar) {
      const st = fs.statSync(v), asil = H.guvenliAd(path.basename(v));
      if (st.size > KOPYA_SINIR) {
        is.ham.push({ dosya: v, ad: asil, boyut: st.size, yerinde: true });
        J.olay(is, 'Video yerinde kullanılacak (büyük olduğu için kopyalanmadı): ' + v);
        continue;
      }
      const hedefAd = H.bosYer(path.join(klasor, 'ham'), asil);
      yaz(`Video kopyalanıyor: ${asil} (${virgul(st.size / 1048576)} MB)`);
      fs.copyFileSync(v, path.join(klasor, 'ham', hedefAd), fs.constants.COPYFILE_EXCL);
      bilgiler.set(path.join(klasor, 'ham', hedefAd), bilgiler.get(v));   // the copy is the same file: no second look
      const k = { dosya: 'ham/' + hedefAd, ad: hedefAd, boyut: st.size }; if (hedefAd !== asil) k.asil_ad = asil;
      is.ham.push(k);
      J.olay(is, 'Video eklendi: ' + k.ad + (k.asil_ad ? ` (bilgisayarındaki adı: ${k.asil_ad})` : ''));
      J.yaz(klasor, is);
    }
    is.videolar_tamam = videolar.length;      // devam: a copy cut short is noticed
    if (ses) {
      const uz = path.extname(ses).toLowerCase(), hedefAd = H.bosYer(path.join(klasor, 'ses'), 'kayit' + uz);
      fs.copyFileSync(ses, path.join(klasor, 'ses', hedefAd), fs.constants.COPYFILE_EXCL);
      is.ses = { dosya: 'ses/' + hedefAd, ad: H.guvenliAd(path.basename(ses)), boyut: fs.statSync(ses).size };
      J.olay(is, 'Ses eklendi: ' + is.ses.ad);
    }
    if (metin) fs.writeFileSync(path.join(klasor, 'metin.txt'), metin, 'utf8');
  }
  is.durum = 'calisiyor'; is.aciklama = 'Hazırlanıyor.';
  J.yaz(klasor, is);
  yaz(`İŞ AÇILDI ${id} (${turYazi(is)})\nKlasör: ${klasor}`);
  for (const u of uyarilar) yaz(u);
  if (klip) cihazYaz(bilgiler.get(kayit).sure, `${H.dakika(bilgiler.get(kayit).sure)} kayıt`);
  else {
    // only a real sound has a length here; a text-only job's voice is made later and its real length is printed then
    const sb = ses ? H.probe(ses) : null, kel = metin.split(/\s+/).filter(Boolean).length, sn = sb && sb.sure ? sb.sure : kel / 2.6;
    cihazYaz(sn, sb && sb.sure ? `${Math.round(sn)} sn ses` : `${kel} kelimelik metnin sesi (süresi ses yapılınca yazılır)`);
  }
  return bitir(klasor, await H.hazirla(klasor, bilgiler));
}

// last lines: where the job is and what the agent does next
function bitir(klasor, r, asama) {
  const is = J.oku(klasor), klip = is.tarz === 'klip', cita = !(klip && is.kurgu !== 'editli');
  for (const u of r.uyari || []) yaz(u);
  const L = ['', ozetYazi(is, klasor), ''];
  if (r.kod === 0) {
    L.push(`HAZIR ${is.id}`, `KLASOR ${klasor}`,
      `SONRAKI (ajan): panel/AJAN-TALIMATI.md, ${klip ? `A. Klip işi (${is.kurgu === 'editli' ? 'A2 Editli' : 'A1 Sade'})` : 'B. Short işi'}` +
      (asama ? `, "${SZ.asamaAdi(is.tarz, asama)}" (${asama}) aşamasından` : '') +
      (cita ? '; kurmadan önce "Çıta" bölümünü oku (iş onu geçince biter)' : '') + `. Talimattaki panel/isler/<id> bu işte "${klasor}".`,
      `DURUM node panel/durum.js "${klasor}" ozet`);
  } else {
    L.push(`DURDU ${is.id}: ${r.neden}`, `KLASOR ${klasor}`, `DEVAM node panel/is_ac.js devam "${klasor}"   (sorunu giderdikten sonra; yapılan adımlar tekrarlanmaz)`);
  }
  dur(r.kod, L.join('\n'));
}

// ------------------------------------------------------------------ continue a job ("işe devam et", "düzelt ve yeniden dene")
// 1. preparation not finished (stopped half way, or the transcription failed): the missing steps run again;
// 2. after preparation, stopped / broken / gate failed: the job goes back to Claude from its first unfinished stage,
//    the agent redoes that stage;
// 3. Claude already working, waiting for Claude, or done: nothing changes; the status is printed.
async function devam(arg) {
  if (!arg) kullan('iş klasörünü ya da kimliğini ver');
  const klasor = fs.existsSync(temizYol(arg)) ? temizYol(arg) : path.join(ISLER, arg);
  const is = J.oku(klasor);
  if (!is) dur(2, 'HATA: Bu işi bulamadım: ' + klasor);
  if (H.hazirlikSuruyor(is)) dur(1, 'HATA: Bu işin hazırlığı şu an çalışıyor (PID ' + ((is.hazirlayan || {}).pid || '?') + '); bitmesini bekle: node panel/durum.js "' + klasor + '" ozet');
  try { fs.mkdirSync(path.join(klasor, 'bak'), { recursive: true }); } catch (_) {}
  const hazirlikBitti = is.asamalar.ses.durum === 'tamam' || (is.asamalar.kanit && is.asamalar.kanit.durum !== 'bekliyor');
  if (!hazirlikBitti) {
    if (is.tarz !== 'klip' && (!is.ham.length || (is.acan === 'sohbet' && is.videolar_tamam == null)))
      dur(1, 'HATA: Bu işin videoları kopyalanırken iş yarıda kesilmiş. Aynı videolarla yeni iş aç (bu klasöre dokunulmadı): ' + klasor);
    kurulumKontrol();
    yaz('Hazırlık yarıda kalmış; eksik adımlar yeniden çalışıyor (bitenler atlanır).');
    const yj = is.tarz === 'klip' ? path.join(klasor, 'yazi', 'yazi.json') : path.join(klasor, 'ses', 'ses.json');
    if (!fs.existsSync(yj)) {
      const kaynak = is.tarz === 'klip' ? path.resolve(klasor, is.ham[0].dosya) : is.ses ? path.join(klasor, is.ses.dosya) : null;
      const b = kaynak ? H.probe(kaynak) : null, kel = String(is.metin || '').split(/\s+/).filter(Boolean).length;
      const sn = b && b.sure ? b.sure : kel / 2.6;
      cihazYaz(sn, is.tarz === 'klip' ? `${H.dakika(sn)} kayıt`
        : b && b.sure ? `${Math.round(sn)} sn ses` : `${kel} kelimelik metnin sesi (süresi ses yapılınca yazılır)`);
    }
    return bitir(klasor, await H.hazirla(klasor, null));
  }
  const sessiz = is.durum === 'claude_calisiyor' && Date.now() - Date.parse(is.guncellendi) > SZ.SESSIZ_MS;
  if (['durdu', 'kaldi', 'hata'].includes(is.durum) || sessiz) {
    const ilk = J.ASAMALAR.find(a => is.asamalar[a].durum !== 'tamam') || 'kanit', neden = is.aciklama;
    let gec = false;
    for (const a of J.ASAMALAR) {
      if (a === ilk) gec = true;
      if (gec) J.asamaKoy(is, a, a === ilk ? 'claude' : 'bekliyor', a === ilk && a === 'ses' ? 'Claude yapacak.' : '');
    }
    if (is.kapi) is.onceki_kapi = is.kapi;             // the old gate result stays in the file, out of the way
    is.kapi = null; is.kapi_sifir = J.simdi(); is.sonuc = null;
    is.durum = 'claude_bekliyor'; is.aciklama = 'Yeniden Claude\'a verildi.'; is.ne_yap = null; is.hata_ayrinti = null;
    J.olay(is, 'Yeniden denendi. Önceki durum: ' + neden);
    J.yaz(klasor, is);
    try { fs.writeFileSync(path.join(klasor, 'CLAUDE-ICIN.md'), H.claudeIcin(is.id, klasor), 'utf8'); } catch (_) {}
    yaz(`YENIDEN: iş "${SZ.asamaAdi(is.tarz, ilk)}" aşamasından yeniden Claude'a verildi. Önceki durum: ${neden}`);
    return bitir(klasor, { kod: 0 }, ilk);
  }
  yaz(is.durum === 'hazir' ? 'Bu iş bitmiş (Hazır). Değişiklik istenirse panel/AJAN-TALIMATI.md D ile sor, yeniden kur ve teslim et.'
    : 'Hazırlık bitmiş ve iş zaten Claude\'da; aşağıdaki aşamalardan "Claude\'da" ya da "sürüyor" olanından devam et.');
  return bitir(klasor, { kod: 0 });
}

// ------------------------------------------------------------------ main
const [komut, ...geri] = process.argv.slice(2);
if (!komut || ['--help', '-h', 'help', 'yardim'].includes(komut)) {
  if (komut) dur(0, kullanim());
  kullan('ne açılacak? klip, short ya da devam');
}
const a = argOku(geri);
if (a.help) dur(0, kullanim());
(async () => {
  if (komut === 'klip') return olustur('klip', a);
  if (komut === 'short') return olustur('short', a);
  if (komut === 'devam') return devam(a._[0]);
  kullan('bilinmeyen komut: ' + komut);
})().catch(e => dur(1, 'HATA: ' + (e && e.stack || e)));
