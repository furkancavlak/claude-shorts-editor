#!/usr/bin/env node
// durum.js - a Claude session reports a job's progress to the panel (writes isler/<id>/is.json).
//
//   node panel/durum.js <is_klasoru> basla <asama> ["ne yapılıyor"]     stage starts (asama: ses|kanit|kurgu|kapi); later stages go back to waiting
//   node panel/durum.js <is_klasoru> bitti <asama> ["kısa sonuç"]       stage done
//   node panel/durum.js <is_klasoru> durdu <asama> "neden"              stopped, needs the creator (e.g. no proof)
//   node panel/durum.js <is_klasoru> hata  <asama> "neden"              something broke
//   node panel/durum.js <is_klasoru> kapi  <kapi_sonuc.txt>             reads kod/kapi.py output into the job
//   node panel/durum.js <is_klasoru> hazir <short.mp4> ["başlık önerisi"]
//   node panel/durum.js <is_klasoru> hazir <klipler/klipler.json>      Klip style: every clip with its reason and title
//   node panel/durum.js <is_klasoru> kutu x0,y0,x1,y1 ["nasıl bulundu"]  Klip: chat box found on a frame
//   node panel/durum.js <is_klasoru> not "satır"                        a line in the job's history ("Deneme: …" and "Hüküm: …" are written this way)
//   node panel/durum.js <is_klasoru> fikir [klip-adı] "tek cümle"        Editli clip / Short: the idea of the edit, written BEFORE building
//   node panel/durum.js <is_klasoru> kamera x0,y0,x1,y1 [yuz x0,y0,x1,y1] ["nasıl"]   Klip: camera box confirmed on a frame
//   node panel/durum.js <is_klasoru> kamera yok ["neden"]               Klip: no streamer camera in the recording
//   node panel/durum.js <is_klasoru> yeni-ses <kayit.m4a>               Short: the real voice replaces the stand-in one
//   node panel/durum.js <is_klasoru> soruldu ["soru"]                   after delivery: the one question was asked in the chat (page shows "Sıra sende")
//   node panel/durum.js <is_klasoru> goster                             prints the status file (+ "panelde": what the page shows)
//   node panel/durum.js <is_klasoru> ozet                               the page's status as plain text: whose turn, what to do now
//   node panel/durum.js <is_klasoru> ac [--hepsi] [--yaz]                opens the delivered video (Klip: the best clip) in the system player; gate failed: the built one
//
// hazir refuses an Editli clip or a Short that has no recorded idea (fikir) or no "Deneme: …" note; Sade passes.
// Exit code 0 = written, 2 = wrong use or refused (the message says what to run).
// ac: 0 = ACILDI (a player was seen with the file), 3 = ACMA ISTENDI / ACILMADI (not seen: give the TAM YOL line), 1 = ACILAMADI.
'use strict';
const fs = require('fs');
const path = require('path');
const J = require('./is_dosyasi');

const [klasorArg, komut, a1, a2] = process.argv.slice(2);
function kullan(m) {
  const L = fs.readFileSync(__filename, 'utf8').split('\n').slice(1), n = L.findIndex(s => !s.startsWith('//'));
  console.error('HATA: ' + m + '\n' + L.slice(0, n < 0 ? 24 : n).join('\n')); process.exit(2);
}
if (!klasorArg || !komut) kullan('eksik bilgi');
const klasor = path.resolve(klasorArg);
const is = J.oku(klasor);
if (!is) kullan('iş dosyası yok: ' + path.join(klasor, 'is.json'));

// every Turkish name (stages, states, checks) comes from the shared word list panel/sozluk.json
const SZ = require('./sozluk');
const asamaAdi = a => SZ.asamaAdi(is.tarz, a);   // Klip names its own steps
const SIMDIKI = Object.fromEntries(['ses', 'kanit', 'kurgu', 'kapi'].map(a => [a, SZ.asamaSimdi(is.tarz, a)]));
const KAPI_AD = SZ.S.kontroller;

function asamaKontrol(a) { if (!J.ASAMALAR.includes(a) || a === 'hazir') kullan('aşama şunlardan biri olmalı: ses, kanit, kurgu, kapi'); }
// "Kurgu bitti: 2 klip" given to 'bitti kurgu' would read "Kurgu bitti. Kurgu bitti: 2 klip": the repeated head is dropped
function onEkSil(a, metin, fiil) {
  let m = String(metin || '').trim();
  for (const ad of new Set([SZ.asamaAdi(is.tarz, a), SZ.asamaAdi(null, a)])) {
    const re = new RegExp('^' + ad.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s+' + fiil + '\\s*[.:;,–-]?\\s*', 'iu');
    m = m.replace(re, '');
  }
  return m;
}

// The idea of the edit. A Sade clip is a plain cut by design and has none. An Editli clip and every Short need one
// sentence, recorded before building: is.fikir = { short | <clip name>: { metin, zaman } } (kept for the watch page).
const SADE = is.tarz === 'klip' && is.kurgu !== 'editli';
const DENEME = /^Deneme:\s*\S/i;   // the same line the watch page shows under the video
const HUKUM = /^H[üu]k[üu]m:\s*\S/i;   // the agent's own verdict before delivery (Çıta 5), shown with the video
const BU_IS = 'node panel/durum.js "' + klasor + '"';
const fikirKomutu = ad => BU_IS + ' fikir ' + (is.tarz === 'klip' ? (ad || 'klip-1') + ' ' : '') + '"<tek cümle>"';
function planAdlari() {   // Klip: the clip names in klip_plan.json (empty when it is not written yet)
  try { return (JSON.parse(fs.readFileSync(path.join(klasor, 'klip_plan.json'), 'utf8')).klipler || []).map(k => k.ad).filter(Boolean); } catch (_) { return []; }
}
// hazir: these videos (clip names, or ['short']) are not delivered without an idea each and one "Deneme: …" note
function citaEksigi(adlar) {
  if (SADE) return;
  const fikirsiz = adlar.filter(ad => !(is.fikir && is.fikir[ad] && is.fikir[ad].metin));
  const denemeYok = !(is.gecmis || []).some(g => DENEME.test(g.olay || ''));
  if (!fikirsiz.length && !denemeYok) return;
  const L = ['TESLIM EDILMEDI: ' + [fikirsiz.length ? 'kayıtlı fikir yok (' + fikirsiz.join(', ') + ')' : '',
    denemeYok ? '"Deneme: …" notu yok' : ''].filter(Boolean).join('; ') + '.'];
  if (fikirsiz.length) {
    L.push('Fikir = bu videoyu "görüntü + altyazı"dan ayıran, bu klipte ya da metinde olandan doğan tek cümle (kurmadan önce yazılır):');
    for (const ad of fikirsiz) L.push('  ' + fikirKomutu(ad));
    L.push('Videoda böyle bir fikir görünmüyorsa cümle uydurma: kurguya dön ya da kullanıcıya neyin eksik olduğunu söyle (panel/AJAN-TALIMATI.md, "Çıta").');
  }
  if (denemeYok) L.push('Deneme = bu işte ilk kez bilerek denediğin tek şey:', '  ' + BU_IS + ' not "Deneme: <ne denedin>"');
  L.push('Sonra aynı hazir komutunu yeniden çalıştır. (Sade klipte bunlar istenmez.)');
  console.error(L.join('\n'));
  process.exit(2);
}

// ------------------------------------------------------------------ ac: open a video and SEE that it opened (Windows)
// The file is handed to Windows (ShellExecute, the user's default player), then for up to ~7 s this looks for a NEW process
// whose command line holds the file's full path, or a window whose title gained the file's name (a player that was
// already open and took the file). Only that counts as ACILDI. Run attached and hidden: a PowerShell started detached
// (old version) exits at once without running anything. The path travels in an environment variable, never quoted.
const PS_AC = [
  "$ErrorActionPreference = 'Stop'; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
  '$f = $env:DURUM_AC_DOSYA; $fl = $f.ToLowerInvariant(); $ad = [IO.Path]::GetFileName($f)',
  '$oturum = (Get-Process -Id $PID).SessionId',
  "if ($oturum -eq 0 -or -not [Environment]::UserInteractive) { 'EKRANYOK ' + $oturum; exit 0 }",
  '$once = @{}; foreach ($x in Get-Process) { $once[[int]$x.Id] = [string]$x.MainWindowTitle }',
  '$si = New-Object System.Diagnostics.ProcessStartInfo; $si.FileName = $f; $si.UseShellExecute = $true',
  "try { $p = [System.Diagnostics.Process]::Start($si) } catch { 'HATA ' + $_.Exception.Message; exit 0 }",
  'for ($i = 0; $i -lt 14; $i++) {',
  '  Start-Sleep -Milliseconds 500',
  "  foreach ($c in @(Get-CimInstance Win32_Process -Filter 'CommandLine IS NOT NULL')) {",
  '    if ([int]$c.ProcessId -ne $PID -and -not $once.ContainsKey([int]$c.ProcessId) -and $c.CommandLine.ToLowerInvariant().Contains($fl)) {',
  "      'ACILDI ' + $c.ProcessId + ' ' + $c.Name + ' komut-satiri'; exit 0 } }",
  '  foreach ($x in Get-Process) { $t = [string]$x.MainWindowTitle',
  '    if ($t.Contains($ad) -and (-not $once.ContainsKey([int]$x.Id) -or -not $once[[int]$x.Id].Contains($ad))) {',
  "      'ACILDI ' + $x.Id + ' ' + $x.ProcessName + ' pencere-basligi'; exit 0 } }",
  '}',
  "if ($p -and -not $p.HasExited) { 'GORULMEDI calisiyor ' + $p.Id + ' ' + $p.ProcessName } elseif ($p) { 'GORULMEDI kapandi' } else { 'GORULMEDI surec-yok' }",
].join('\n');

function videoAc(dosya) {
  const cp = require('child_process');
  if (process.platform !== 'win32') {     // macOS open / Linux xdg-open: the request is made, the player is not looked for
    const k = process.platform === 'darwin' ? 'open' : 'xdg-open';
    const r = cp.spawnSync(k, [dosya], { stdio: 'ignore', timeout: 15000 });
    if (r.status === 0) return { kod: 3, L: ['ACMA ISTENDI ' + dosya, `  (${k} isteği kabul etti; oynatıcının açıldığını bu sistemde göremiyorum: kullanıcıya açıldı mı diye sor)`] };
    return { kod: 1, L: ['ACILAMADI ' + dosya + ` (${k}: ${r.error ? r.error.message : 'çıkış ' + r.status})`] };
  }
  const r = cp.spawnSync('powershell', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', PS_AC],
    { env: { ...process.env, DURUM_AC_DOSYA: dosya }, encoding: 'utf8', windowsHide: true, timeout: 60000 });
  const s = String(r.stdout || '').trim().split(/\r?\n/).pop() || '', p = s.split(' ');
  if (p[0] === 'ACILDI') return { kod: 0, L: ['ACILDI ' + dosya, `  (oynatıcı ${p.slice(2, -1).join(' ')}, PID ${p[1]}; ${p[p.length - 1] === 'komut-satiri'
    ? 'dosya oynatıcının komut satırında' : 'oynatıcının penceresi dosyanın adını gösteriyor'})`] };
  if (p[0] === 'GORULMEDI') return { kod: 3, L: ['ACMA ISTENDI ' + dosya, '  (Windows isteği kabul etti ama 7 sn içinde dosyayı açan bir oynatıcı görmedim' +
    (p[1] === 'calisiyor' ? `; başlatılan ${p[3]} (PID ${p[2]}) çalışıyor, dosyayı açıp açmadığı belli değil` : p[1] === 'kapandi'
      ? '; başlatılan program hemen kapandı' : '') + '. "Açtım" deme: kullanıcıya açıldı mı diye sor, açılmadıysa yolu ver.)'] };
  if (p[0] === 'EKRANYOK') return { kod: 3, L: ['ACILMADI ' + dosya, '  (bu oturumda ekran yok: uzaktan bağlantı ya da hizmet oturumu; oynatıcı burada açılamaz)'] };
  const neden = p[0] === 'HATA' ? s.slice(5) : (r.error ? r.error.message : String(r.stderr || '').trim().split(/\r?\n/)[0] || 'PowerShell cevap vermedi');
  return { kod: 1, L: ['ACILAMADI ' + dosya + ' (' + neden + ')'] };
}

let kaydedilen = null;     // not / fikir / kutu / kamera / soruldu: what was recorded (the job's state does not change)
switch (komut) {
  case 'goster': {
    // head first, then the fields that are only written when set (with their empty value), the rest, the history,
    // and last what the page shows ("panelde")
    const bos = is.tarz === 'klip'
      ? { kurgu: 'sade', adet: null, altyazi: false, ses_izi: 0, anlar: [], sohbet: null, sohbet_kutu: null, kamera: null, kamera_oneri: null }
      : { metin: null, yazi_duzeltme: null, ses: null };
    if (!SADE) bos.fikir = null;
    const out = { id: is.id, tarz: is.tarz, durum: is.durum, aciklama: is.aciklama, ...bos };
    for (const [k, v] of Object.entries(is)) if (k !== 'gecmis') out[k] = v;
    out.gecmis = is.gecmis || [];
    out.panelde = SZ.durumOzet(is);   // the same plain status the page shows (durum_adi, sira, simdi ...)
    console.log(JSON.stringify(out, null, 1));
    process.exit(0);
  }
  case 'ozet': {
    // cumle: the sentence the page shows (CLAUDE-ICIN.md of this job folder, Klip/Short by kind)
    console.log(SZ.ozetMetni(is, SZ.durumOzet(is), { cumle: SZ.kopyaCumle(klasor, is.tarz), klasor }));
    if (!SADE) {
      const f = Object.entries(is.fikir || {});
      for (const [ad, x] of f) console.log('Fikir' + (ad === 'short' ? '' : ' (' + ad + ')') + ': ' + x.metin);
      if (!f.length && is.durum !== 'hazir') console.log('Fikir: henüz yazılmadı (kurmadan önce: ' + fikirKomutu() + ')');
      for (const re of [DENEME, HUKUM]) { const d = (is.gecmis || []).filter(g => re.test(g.olay || '')).pop(); if (d) console.log(d.olay.trim()); }
    }
    process.exit(0);
  }
  case 'ac': {
    // after delivery: open the video for the user with the system's own player (nothing is written)
    const ek = process.argv.slice(4), yazYalniz = ek.includes('--yaz');
    let liste = is.sonuc ? (is.sonuc.video ? [is.sonuc.video] : (is.sonuc.klipler || []).map(k => k.video)) : [];
    if (!liste.length && is.durum === 'kaldi') {   // gate failed and the user accepts it as it is: the built video, not delivered
      const kj = path.join(klasor, 'klipler', 'klipler.json');
      if (is.tarz !== 'klip' && fs.existsSync(path.join(klasor, 'short.mp4'))) liste = ['short.mp4'];
      else if (is.tarz === 'klip' && fs.existsSync(kj)) try { liste = JSON.parse(fs.readFileSync(kj, 'utf8')).map(k => 'klipler/' + k.video); } catch (_) {}
    }
    if (!liste.length) kullan('bu işte teslim edilmiş video yok (önce: durum.js ... hazir)');
    let kod = 0;
    for (const r of ek.includes('--hepsi') ? liste : liste.slice(0, 1)) {
      const dosya = path.resolve(klasor, r);
      if (!fs.existsSync(dosya)) kullan('video yok: ' + dosya);
      if (yazYalniz) {    // the command a person can run by hand, and the path to give the user
        console.log(process.platform === 'win32' ? `powershell -NoProfile -Command "Start-Process -FilePath '${dosya.replace(/'/g, "''")}'"`
          : (process.platform === 'darwin' ? 'open' : 'xdg-open') + ' "' + dosya + '"');
        console.log('TAM YOL ' + dosya);
        continue;
      }
      const s = videoAc(dosya);
      console.log(s.L.join('\n'));
      if (s.kod) console.log('TAM YOL ' + dosya);
      kod = s.kod === 1 || kod === 1 ? 1 : Math.max(kod, s.kod);
    }
    process.exit(kod);
  }
  case 'basla': {
    asamaKontrol(a1);
    const not = onEkSil(a1, a2, 'başladı');
    // a stage starts again (2nd round, a change after delivery): what came after it is no longer true. The later stages
    // wait again and an old gate result moves to onceki_kapi (the page and 'ozet' never show "sürüyor" and "geçmedi" together)
    const sonra = J.ASAMALAR.slice(J.ASAMALAR.indexOf(a1) + 1).filter(a => is.asamalar[a] && is.asamalar[a].durum !== 'bekliyor');
    for (const a of sonra) J.asamaKoy(is, a, 'bekliyor', '');
    const kapiVardi = !!is.kapi;
    if (is.kapi) { is.onceki_kapi = is.kapi; is.kapi = null; is.kapi_sifir = J.simdi(); }
    J.asamaKoy(is, a1, 'suruyor', not);
    is.durum = 'claude_calisiyor'; is.aciklama = not || SIMDIKI[a1];
    J.olay(is, asamaAdi(a1) + ' başladı.' + (not ? ' ' + not : ''));
    if (sonra.length) console.log('YENIDEN: ' + sonra.map(asamaAdi).join(', ') + ' yeniden bekliyor' +
      (kapiVardi ? ' (eski kontrol sonucu onceki_kapi\'de; teslimden önce kontrolü yeniden çalıştır)' : '') + '.');
    if (a1 === 'kurgu' && !SADE) {   // the order in panel/AJAN-TALIMATI.md: basla kurgu, look, record the idea, then build
      const adlar = is.tarz === 'klip' ? planAdlari() : ['short'];
      const eksik = (adlar.length ? adlar : [null]).filter(ad => !(ad && is.fikir && is.fikir[ad] && is.fikir[ad].metin));
      if (eksik.length && !(is.tarz !== 'klip' && is.fikir && is.fikir.short))
        console.log('SIRADA: bakınca fikri tek cümleyle kaydet, sonra kur (Çıta 2; hazir onsuz teslim etmez):\n' + eksik.map(ad => '  ' + fikirKomutu(ad)).join('\n'));
    }
    break;
  }
  case 'bitti': {
    asamaKontrol(a1);
    const not = onEkSil(a1, a2, 'bitti');
    J.asamaKoy(is, a1, 'tamam', not);
    is.durum = 'claude_calisiyor'; is.aciklama = asamaAdi(a1) + ' bitti.' + (not ? ' ' + not : '');
    J.olay(is, is.aciklama);
    break;
  }
  case 'durdu':
  case 'hata': {
    asamaKontrol(a1);
    const not = onEkSil(a1, a2, komut);
    if (!not) kullan('nedeni yaz');
    J.asamaKoy(is, a1, komut, not);
    is.durum = komut; is.aciklama = not;
    J.olay(is, asamaAdi(a1) + (komut === 'durdu' ? ' durdu: ' : ' hata: ') + not);
    break;
  }
  case 'kapi': {
    if (!a1) kullan('kapi_sonuc.txt yolunu ver');
    const yol = path.resolve(a1);
    const k = J.kapiCoz(fs.readFileSync(yol, 'utf8'));
    if (!k.sonuc) kullan('dosyada "SONUC:" satırı yok: ' + yol);
    k.dosya = path.relative(klasor, yol).split(path.sep).join('/');
    is.kapi = k;
    const kalan = k.satirlar.filter(s => s.durum === 'KALDI');
    // the build round that was announced with 'basla kurgu' is what the gate just checked: it is done either way
    if (is.asamalar.kurgu && is.asamalar.kurgu.durum === 'suruyor') J.asamaKoy(is, 'kurgu', 'tamam', is.asamalar.kurgu.not);
    if (k.sonuc === 'GECTI') {
      J.asamaKoy(is, 'kapi', 'tamam', k.satirlar.length + ' kontrolün hepsi geçti');
      is.durum = 'claude_calisiyor'; is.aciklama = 'Son kontrolden geçti.';
      J.olay(is, 'Son kontrol: geçti (' + k.satirlar.length + ' kontrol).');
    } else {
      const adlar = kalan.map(s => KAPI_AD[s.ad] || s.ad).join(', ').toLocaleLowerCase('tr');
      J.asamaKoy(is, 'kapi', 'kaldi', adlar + ' geçmedi');
      is.durum = 'kaldi'; is.aciklama = 'Son kontrolden geçmedi: ' + adlar + '.';
      J.olay(is, 'Son kontrol: geçmedi (' + adlar + ').');
    }
    break;
  }
  case 'hazir': {
    if (!a1) kullan('Short dosyasının yolunu ver');
    const yol = path.resolve(a1);
    if (!fs.existsSync(yol)) kullan('dosya yok: ' + yol);
    if (!is.kapi && is.onceki_kapi) kullan('bir aşama yeniden başladığı için eski kontrol sonucu geçersiz: kontrolü yeniden çalıştır, sonra durum.js ... kapi kapi_sonuc.txt');
    if (!is.kapi || is.kapi.sonuc !== 'GECTI') kullan('kapıdan geçmeyen Short hazır sayılmaz (önce: durum.js ... kapi kapi_sonuc.txt)');
    if (is.tarz === 'klip') {
      // Klip: the argument is klipler.json written by kod/klip.py (one entry per clip: video, neden, baslik ...)
      if (!/\.json$/i.test(yol)) kullan('Klip işinde hazir komutu klipler.json ister: durum.js <iş> hazir <iş>/klipler/klipler.json');
      const liste = JSON.parse(fs.readFileSync(yol, 'utf8')); const kk = path.dirname(yol);
      if (!Array.isArray(liste) || !liste.length) kullan('klipler.json boş');
      const rel = p => path.relative(klasor, path.join(kk, p)).split(path.sep).join('/');
      for (const k of liste) if (!fs.existsSync(path.join(kk, k.video))) kullan('klip dosyası yok: ' + path.join(kk, k.video));
      citaEksigi(liste.map(k => k.ad));
      is.sonuc = { klipler: liste.map(k => ({ ad: k.ad, video: rel(k.video), serit: k.kareler ? rel(k.kareler + '/serit.jpg') : null, bas: k.bas, son: k.son,
        sure: k.sure, neden: k.neden, baslik: k.baslik, puan: k.puan == null ? null : k.puan, boyut: k.boyut, kullanici: k.kullanici || null,
        fikir: (!SADE && is.fikir && is.fikir[k.ad] && is.fikir[k.ad].metin) || null }))
        .sort((a, b) => (b.puan || 0) - (a.puan || 0)) };   // best first
      is.baslik = a2 || null;
      J.asamaKoy(is, 'hazir', 'tamam', liste.length + ' klip');
      is.durum = 'hazir'; is.aciklama = liste.length + ' klip hazır.';
      J.olay(is, liste.length + ' klip hazır.');
      break;
    }
    citaEksigi(['short']);
    is.sonuc = { video: path.relative(klasor, yol).split(path.sep).join('/'), boyut: fs.statSync(yol).size, fikir: is.fikir.short.metin };
    if (a2) is.baslik = a2;
    J.asamaKoy(is, 'hazir', 'tamam', '');
    is.durum = 'hazir'; is.aciklama = 'Short hazır.';
    J.olay(is, 'Short hazır: ' + is.sonuc.video);
    break;
  }
  case 'kutu': {   // Klip: chat box found by looking at a frame, as 0-1 of the frame "x0,y0,x1,y1"
    const k = String(a1 || '').split(/[ ,;]+/).filter(Boolean).map(Number);
    if (k.length !== 4 || k.some(v => !(v >= 0 && v <= 1)) || k[0] >= k[2] || k[1] >= k[3]) kullan('kutu 0-1 arası dört sayı olmalı: x0,y0,x1,y1');
    is.sohbet_kutu = k; J.olay(is, 'Sohbet kutusu kareden bulundu: ' + k.join(', ') + (a2 ? ' (' + a2 + ')' : '') + '.');
    kaydedilen = 'sohbet kutusu kaydedildi: ' + k.join(',');
    break;
  }
  case 'kamera': {   // Klip: Claude's decision after looking at a frame (kamera_bul.py suggestion confirmed or corrected)
    const oku = v => { const k = String(v || '').split(/[ ,;]+/).filter(Boolean).map(Number);
      return k.length === 4 && k.every(x => x >= 0 && x <= 1) && k[0] < k[2] && k[1] < k[3] ? k : null; };
    const r = process.argv.slice(4);
    if (r[0] === 'yok') { is.kamera = { yok: true, kaynak: 'claude', zaman: J.simdi() };
      J.olay(is, 'Kayıtta yayıncı kamerası yok' + (r[1] ? ' (' + r[1] + ')' : '') + '; kamerasız düzen.');
      kaydedilen = 'kamera kaydedildi: yok (kamerasız düzen)'; break; }
    const kutu = oku(r[0]); if (!kutu) kullan('kamera x0,y0,x1,y1 (0-1) ya da "kamera yok"');
    let yuz = null, not = '';
    if (r[1] === 'yuz') { yuz = oku(r[2]); if (!yuz) kullan('yuz x0,y0,x1,y1 (0-1)'); not = r[3] || ''; } else not = r[1] || '';
    is.kamera = { kutu, yuz, kaynak: 'claude', zaman: J.simdi() };
    J.olay(is, 'Kamera kutusu: ' + kutu.join(', ') + (yuz ? '; yüz bulundu' : '; yüz yok') + (not ? ' (' + not + ')' : '') + '.');
    kaydedilen = 'kamera kaydedildi: ' + kutu.join(',') + (yuz ? ', yüz ' + yuz.join(',') : ', yüz yok');
    break;
  }
  case 'yeni-ses': {   // Short made with the stand-in voice: the user's real recording arrives, the job starts again at 'ses'
    if (is.tarz === 'klip') kullan('Klip işinde ayrı ses yok; kayıt kendi sesiyle kullanılır');
    if (!a1) kullan('gerçek ses dosyasının yolunu ver');
    const kaynak = path.resolve(a1);
    if (!fs.existsSync(kaynak) || !fs.statSync(kaynak).isFile()) kullan('ses dosyası yok: ' + kaynak);
    const uz = path.extname(kaynak).toLowerCase();
    if (!['.wav', '.m4a', '.mp3', '.ogg', '.flac', '.aac', '.webm', '.mp4', '.mov', '.opus'].includes(uz)) kullan('ses dosyasını tanımadım: wav, m4a ya da mp3 ver');
    const sk = path.join(klasor, 'ses'); fs.mkdirSync(sk, { recursive: true });
    const yer = ad => { const e = path.extname(ad), k = ad.slice(0, ad.length - e.length); let x = ad, i = 2;
      while (fs.existsSync(path.join(sk, x))) x = `${k}-${i++}${e}`; return x; };     // never overwrite
    // the stand-in's words, aligned words and voice stay, renamed: kod/ses_yazi.py writes ses.wav / ses.json again
    for (const f of ['ses.json', 'ses-hizali.json', 'ses.wav']) if (fs.existsSync(path.join(sk, f))) fs.renameSync(path.join(sk, f), path.join(sk, yer('onceki-' + f)));
    const hedef = yer('kayit' + uz);
    fs.copyFileSync(kaynak, path.join(sk, hedef), fs.constants.COPYFILE_EXCL);    // a copy: the user's file is not touched
    if (is.ses) is.onceki_ses = is.ses;
    if (is.yazi_duzeltme) { is.onceki_yazi_duzeltme = is.yazi_duzeltme; is.yazi_duzeltme = null; }
    is.ses = { dosya: 'ses/' + hedef, ad: path.basename(kaynak), boyut: fs.statSync(path.join(sk, hedef)).size };
    for (const a of J.ASAMALAR) J.asamaKoy(is, a, a === 'ses' ? 'claude' : 'bekliyor', a === 'ses' ? 'Gerçek ses geldi; zamanlar yeniden çıkarılacak.' : '');
    if (is.kapi) is.onceki_kapi = is.kapi;
    is.kapi = null; is.kapi_sifir = J.simdi(); is.sonuc = null;
    is.durum = 'claude_calisiyor'; is.aciklama = 'Gerçek ses geldi: Short bu sesle yeniden kuruluyor.';
    J.olay(is, 'Gerçek ses eklendi (' + is.ses.ad + '); yer tutucu sesle yapılan Short yerine yenisi kurulacak.');
    console.log('SONRAKI node panel/is_ac.js devam "' + klasor + '"   (yeni sesi yazıya döker ve kelimeleri sese oturtur)');
    break;
  }
  case 'fikir': {  // Editli clip / Short: the one-sentence idea of the edit (panel/AJAN-TALIMATI.md, "Çıta")
    if (SADE) kullan('Sade klip düz kesimdir, fikir istenmez; bu komut Editli klip ve Short içindir');
    const klip = is.tarz === 'klip';
    if (klip && !a2) kullan('Klip işinde her klibin fikri ayrı yazılır: ' + fikirKomutu());
    const ad = klip ? a1 : 'short';
    const cumle = String((klip || (a1 === 'short' && a2) ? a2 : a1) || '').replace(/\s+/g, ' ').trim();
    if (klip && !/^[\w.-]+$/.test(ad)) kullan('klip adı klip_plan.json\'daki "ad" olmalı (ör. klip-1): ' + fikirKomutu());
    if (cumle.split(' ').length < 5) kullan('fikri tek tam cümleyle yaz (en az 5 kelime): bu videoyu "görüntü + altyazı"dan ayıran ne? ' + fikirKomutu(ad));
    is.fikir = is.fikir || {};
    const eski = is.fikir[ad];
    is.fikir[ad] = { metin: cumle, zaman: J.simdi() };
    J.olay(is, 'Fikir' + (klip ? ' (' + ad + ')' : '') + (eski ? ' değişti' : '') + ': ' + cumle);
    console.log('FIKIR ' + ad + ': ' + cumle);
    kaydedilen = 'fikir ' + (eski ? 'değişti' : 'kaydedildi') + ' (' + ad + ')';
    break;
  }
  case 'not': {    // a line in the job's history ("Olanlar"), e.g. why a step was skipped
    if (!a1) kullan('notu yaz');
    J.olay(is, a1);
    console.log('NOT ' + a1);
    kaydedilen = DENEME.test(a1) ? 'deneme notu geçmişe yazıldı (sayfa videonun altında gösterir)'
      : HUKUM.test(a1) ? 'hüküm geçmişe yazıldı (sayfa ve ozet gösterir)' : 'not geçmişe yazıldı';
    break;
  }
  case 'soruldu': {  // after delivery the one question (D) was asked in the chat: only now the page says "Sıra sende"
    if (is.durum !== 'hazir') kullan('soruldu teslimden sonra yazılır (önce hazir); bu iş şu an: ' + is.durum);
    const soru = String(a1 || 'En çok neyi beğendin?').replace(/\s+/g, ' ').trim().slice(0, 200);
    is.soru = { metin: soru, zaman: J.simdi() };
    J.olay(is, 'Claude sohbette sordu: “' + soru + '”');
    console.log('SORULDU ' + soru);
    kaydedilen = 'soru kaydedildi; izleme sayfası "Sıra sende" gösterir';
    break;
  }
  default: kullan('bilinmeyen komut: ' + komut);
}
J.yaz(klasor, is);
if (kaydedilen) console.log('TAMAM ' + is.id + ': ' + kaydedilen + ' (işin durumu değişmedi: ' + is.durum + ')');
else console.log('TAMAM ' + is.id + ': ' + is.durum + ' - ' + is.aciklama);
