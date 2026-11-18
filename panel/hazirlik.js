// hazirlik.js - the engine's preparation of a job, in ONE place. panel/is_ac.js (the chat entry) runs it in the
// foreground; panel/server.js (the read-only watch page) only asks it whether a preparation is still alive.
// Job folder contract (panel/isler/<id>/, is.json via is_dosyasi.js) is unchanged:
//   Klip:  yazi/ (yazi.json, yazi.txt, adaylar.md/json, isaretler.json, enerji.json), kamera/ (kamera.json, kamera-bak.jpg);
//          order: transcription, camera suggestion, then the moments (klip_bul.py gets the camera box)
//   Short: ses/ (ses.wav, ses.json, ses-hizali.json = the same words snapped to the sound by alet/kelime.py), metin.txt
// While it runs, is.json carries "hazirlayan": {pid, baslangic}; it is removed when the preparation ends either way.
// is.dil (only when the job was opened with --dil) goes to kod/ses_yazi.py as --dil; without it the speech is Turkish.
// Nothing is downloaded, nothing the user gave is changed; no model other than the local Whisper is started.
'use strict';
const fs = require('fs');
const path = require('path');
const { spawn, execFileSync } = require('child_process');
const J = require('./is_dosyasi');

const PANEL = __dirname, MOTOR = path.dirname(PANEL), KOD = path.join(MOTOR, 'kod'), ALET = path.join(MOTOR, 'alet');
const PY = process.env.PANEL_PYTHON ? process.env.PANEL_PYTHON.split(' ') : (process.platform === 'win32' ? ['py', '-3'] : ['python3']);
const ENV = { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONDONTWRITEBYTECODE: '1' };
const SHORT_TURLER = ['tek_bilgi', 'liste', 'karsilastirma'];
const VIDEO_UZ = ['.mp4', '.mkv', '.mov', '.webm', '.ts', '.m4v', '.flv', '.avi'];
const SES_UZ = ['.wav', '.m4a', '.mp3', '.ogg', '.flac', '.aac', '.webm', '.mp4', '.mov', '.opus'];
const SOHBET_UZ = ['.txt', '.json', '.log', '.csv'];
const AN_RE = /^((\d+:)?\d{1,2}:\d{2}|\d+(\.\d+)?)(\s*[-–—]\s*((\d+:)?\d{1,2}:\d{2}|\d+(\.\d+)?))?$/;
const KOPYA_SINIR = 500 * 1024 * 1024;     // a Short video bigger than this is used in place, not copied
const SHORT_EN_AZ_SN = 10;                 // the shortest Short (panel/kapi_topla.js and alet/kontrol.py use the same)
const SHORT_EN_AZ_KELIME = 25;             // about 10 s of speech

let yaz = m => process.stdout.write(m + '\n');
const ciktiVer = f => { yaz = f; };
const dakika = s => { s = Math.floor(+s); const h = Math.floor(s / 3600), d = Math.floor(s / 60) % 60, n = String(s % 60).padStart(2, '0');
  return h ? `${h}:${String(d).padStart(2, '0')}:${n}` : `${d}:${n}`; };
const virgul = x => (+x).toFixed(1).replace('.', ',');

function guvenliAd(ad) {
  const temiz = String(ad || 'dosya').normalize('NFC').replace(/[\\/:*?"<>|\x00-\x1f]/g, '_').replace(/^\.+/, '').slice(0, 120);
  return temiz || 'dosya';
}
function bosYer(klasor, ad) {           // never overwrite: a.mp4 -> a-2.mp4
  const uz = path.extname(ad), kok = ad.slice(0, ad.length - uz.length);
  let aday = ad, i = 2;
  while (fs.existsSync(path.join(klasor, aday))) aday = `${kok}-${i++}${uz}`;
  return aday;
}
function yeniId(isler) {
  const d = new Date(), p = n => String(n).padStart(2, '0'), harf = 'abcdefghjkmnpqrstuvwxyz23456789';
  let id;
  do {
    id = `${String(d.getFullYear()).slice(2)}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}-` +
      harf[Math.floor(Math.random() * harf.length)] + harf[Math.floor(Math.random() * harf.length)];
  } while (fs.existsSync(path.join(isler, id)));
  return id;
}
// dropped into every job folder so an agent session that opens the folder finds its instructions (absolute paths)
const claudeIcin = (id, klasor) => `# Bu klasör Short Motoru panelinin bir işi (iş ${id})

Bu işi yapman istendiyse:
1. Talimatı oku: \`${path.join(PANEL, 'AJAN-TALIMATI.md')}\`
2. Bütün komutları motorun kök klasöründe çalıştır: \`${MOTOR}\`
   (önce oraya geç: \`cd "${MOTOR}"\`). Talimattaki \`panel/isler/<id>\` bu işte \`${klasor}\` demektir.
3. İşin durumu \`is.json\` içinde; durumu yalnız \`node panel/durum.js "${klasor}" ...\` ile yaz. Hiçbir dosyayı silme.
4. Panelin kullanıcıya gösterdiğini metin olarak görmek için: \`node panel/durum.js "${klasor}" ozet\`. Kullanıcıya yazarken panelin adlarını kullan (\`panel/sozluk.json\`).
`;

// ffprobe facts; the real picture range comes from packet times (parts cut out of a longer video keep its clock).
// MPEG-TS (even when named .mp4) writes "25.392033," with a trailing comma: split on commas too.
function probe(dosya) {
  try {
    const j = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration:stream=codec_type,width,height,r_frame_rate',
      '-of', 'json', dosya], { windowsHide: true, encoding: 'utf8' }));
    const v = (j.streams || []).find(s => s.codec_type === 'video');
    const b = { sure: j.format && j.format.duration ? Math.round(+j.format.duration * 100) / 100 : null,
      en: v ? v.width : null, boy: v ? v.height : null, goruntu: !!v, sesli: (j.streams || []).some(s => s.codec_type === 'audio') };
    if (!v) return b;
    const [n, d] = String(v.r_frame_rate || '30/1').split('/'); const kare = (+d || 1) / (+n || 30);
    let o2 = '';
    try { o2 = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time', '-of', 'csv=p=0', dosya],
      { windowsHide: true, encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 }); } catch (_) {}
    const t = String(o2).split(/[\s,]+/).filter(s => s.trim() !== '').map(Number).filter(isFinite);
    if (t.length) {
      let a = Infinity, e = -Infinity; for (const x of t) { if (x < a) a = x; if (x > e) e = x; }
      e += kare;
      b.bas = Math.round(a * 1000) / 1000; b.bitis = Math.round(e * 1000) / 1000; b.sure = Math.round((e - a) * 100) / 100;
    }
    return b;
  } catch (_) { return null; }
}

// run one engine step in the foreground: its lines are kept in panel-gunluk.txt and shown (all, or those goster() keeps)
function calistir(komut, args, klasor, sure, satirda, goster) {
  return new Promise(ok => {
    const gunluk = path.join(klasor, 'panel-gunluk.txt');
    fs.appendFileSync(gunluk, `\n$ ${komut} ${args.map(a => JSON.stringify(a)).join(' ')}\n`);
    let cikti = '', kalan = '';
    const c = spawn(komut, args, { cwd: klasor, windowsHide: true, env: ENV });
    const zaman = setTimeout(() => { try { c.kill(); } catch (_) {} }, sure);
    const al = d => { d = String(d); cikti += d; fs.appendFileSync(gunluk, d); kalan += d;
      const s = kalan.split(/\r?\n/); kalan = s.pop();
      for (const x of s) { if (!x.trim() || /\[ WARN:/.test(x)) continue; if (!goster || goster(x)) yaz('   ' + x); if (satirda) try { satirda(x); } catch (_) {} } };
    c.stdout.on('data', al); c.stderr.on('data', al);
    c.on('error', e => { clearTimeout(zaman); fs.appendFileSync(gunluk, 'BAŞLAMADI: ' + e.message + '\n'); ok({ kod: -1, cikti: e.message }); });
    c.on('close', kod => { clearTimeout(zaman); fs.appendFileSync(gunluk, `(çıkış kodu ${kod})\n`); ok({ kod, cikti }); });
  });
}

// ------------------------------------------------------------------ setup check (nothing is installed or downloaded)
// returns the list of missing things (empty = ready)
function kurulumEksigi() {
  const eksik = [];
  for (const p of ['ffmpeg', 'ffprobe']) { try { execFileSync(p, ['-hide_banner', '-version'], { windowsHide: true, stdio: 'ignore' }); } catch (_) { eksik.push(p); } }
  let j = null;
  try {
    const o = execFileSync(PY[0], [...PY.slice(1), path.join(PANEL, 'hazir_mi.py')], { windowsHide: true, encoding: 'utf8', env: ENV, timeout: 120000 });
    j = JSON.parse(o.trim().split(/\r?\n/).pop());
  } catch (_) { eksik.push('Python (' + PY.join(' ') + ')'); }
  if (j) {
    for (const p of Object.values(j.paketler || {})) if (!p.var) eksik.push('Python paketi ' + p.pip);
    if (j.paketler && j.paketler.faster_whisper && j.paketler.faster_whisper.var && !j.model) eksik.push('Whisper modeli (yazıya dökme, ~1,6 GB)');
    if (j.dosyalar && !j.dosyalar.yuz_modeli) eksik.push('kod/model/yunet.onnx');
  }
  return eksik;
}

// ------------------------------------------------------------------ transcription device and an honest time estimate
// The device is decided by kod/ses_yazi.py (the same test as its --cihaz: GPU libraries found AND a card seen by
// CTranslate2): asked, never guessed here, no model is loaded. Seconds per hour of recording come from ses_yazi.py
// (SANIYE_SAAT, measured on the test PC: processor 649 s, graphics card 108 s); a busy computer was ~1.5x slower.
function yaziCihazi() {
  const kod = [
    'import json, sys', 'sys.path.insert(0, sys.argv[1])',
    'try:',
    '    import ses_yazi as s',
    '    if hasattr(s, "cuda_ara"):',
    '        c = s.cuda_ara(); lib, eksik = c["gpu_kutuphane"], len(c["eksik"])',
    '    else:',
    '        k, e = s.cuda_klasorleri(); lib, eksik = bool(k) and not e, len(e)',
    '    try:',
    '        import ctranslate2; kart = ctranslate2.get_cuda_device_count()',
    '    except Exception:',
    '        kart = None',
    '    print(json.dumps({"gpu": bool(lib and kart), "kart": kart, "eksik": eksik, "saat": getattr(s, "SANIYE_SAAT", {"cpu": 649, "cuda": 108})}))',
    'except Exception as x:',
    '    print(json.dumps({"gpu": None, "hata": str(x)[:120]}))'].join('\n');
  try {
    const o = execFileSync(PY[0], [...PY.slice(1), '-c', kod, KOD], { windowsHide: true, encoding: 'utf8', env: ENV, timeout: 60000 });
    return JSON.parse(o.trim().split(/\r?\n/).pop());
  } catch (_) { return { gpu: null }; }
}
// --dil: asked from kod/ses_yazi.py (dil_kodu, the same check the transcription makes) before anything is written.
// -> { kod: 'en' } | { hata: '...' }. When Python itself cannot answer, only the shape is checked.
function dilKontrol(dil) {
  const kod = ['import sys', 'sys.path.insert(0, sys.argv[1])', 'import ses_yazi as s',
    'try: print("DIL " + s.dil_kodu(sys.argv[2]))', 'except ValueError as e: print("HATA " + str(e))'].join('\n');
  try {
    const s = execFileSync(PY[0], [...PY.slice(1), '-c', kod, KOD, String(dil)], { windowsHide: true, encoding: 'utf8', env: ENV, timeout: 60000 })
      .trim().split(/\r?\n/).pop();
    if (s.startsWith('DIL ')) return { kod: s.slice(4) };
    if (s.startsWith('HATA ')) return { hata: s.slice(5) };
  } catch (_) {}
  const d = String(dil).trim().toLowerCase();
  return /^(auto|[a-z]{2,3})$/.test(d) ? { kod: d } : { hata: `bilinmeyen dil kodu '${dil}': tr, en, de ... ya da auto` };
}
// the transcription's flags: none when the job has no language (old jobs, or none given) = exactly the command as before
const dilArg = is => is.dil ? ['--dil', is.dil] : [];
// "dil en" for the job's history; nothing for Turkish (the default, as before)
const dilYazi = y => !y || !y.dil || y.dil === 'tr' ? '' : ` · dil ${y.dil}` + (y.dil_secim === 'tanindi' ? ` (Whisper tanıdı, olasılık ${y.dil_olasilik})` : '');
function yaziTahmini(saniye, cihaz) {
  const S = cihaz.saat || { cpu: 649, cuda: 108 }, saat = (saniye || 0) / 3600;
  const dk = sn => sn < 90 ? `~${Math.max(10, Math.round(sn / 10) * 10)} sn` : `~${Math.round(sn / 60)} dk`;
  const ne = cihaz.gpu === true ? 'ekran kartında (GPU)'
    : cihaz.gpu === false ? (cihaz.kart ? 'işlemcide (CPU): ekran kartı kütüphaneleri eksik (py -3 kod/ses_yazi.py --cihaz ayrıntıyı yazar)'
      : 'işlemcide (CPU): NVIDIA ekran kartı görünmüyor')
      : 'bilinmeyen cihazda (kod/ses_yazi.py cihazı söylemedi)';
  let sure;
  if (saniye < 120) sure = 'model açılışıyla birlikte yarım-bir dakika';
  else if (cihaz.gpu === true) sure = `${dk(saat * S.cuda)} (ölçülen: saatlik kayıt ${Math.round(S.cuda / 60)} dk)`;
  else sure = `${dk(saat * S.cpu)}, bilgisayar meşgulse ${dk(saat * S.cpu * 1.5)} (ölçülen: saatlik kayıt işlemcide ${Math.round(S.cpu / 60)} dk)`;
  return { ne, sure, uzun: cihaz.gpu !== true && saat * S.cpu > 8 * 60 };
}

// ------------------------------------------------------------------ is a preparation still running? (the watch page asks)
// the check lives in sozluk.js (durumOzet shows "Yarıda kaldı" with it); is.hazirlayan is written by hazirla below
const { hazirlikSuruyor } = require('./sozluk');

// ------------------------------------------------------------------ preparation
// bilgiler: Map of probe results already taken; returns { kod: 0 | 1, neden, uyari } (the caller prints and exits)
async function hazirla(klasor, bilgiler) {
  const degistir = f => { const x = J.oku(klasor); f(x); J.yaz(klasor, x); return x; };
  let is = degistir(x => { x.durum = 'calisiyor'; x.aciklama = 'Dosyalar okunuyor.'; x.hazirlayan = { pid: process.pid, baslangic: J.simdi() };
    J.olay(x, 'Motor hazırlığa başladı (sohbetten açılan iş).'); });
  try {
    for (const h of is.ham) {
      const yol = path.resolve(klasor, h.dosya);
      const b = (bilgiler && bilgiler.get(yol)) || probe(yol); if (!b) continue;
      Object.assign(h, b);
      if (b.bas != null) J.olay(is, `${h.ad}: ${virgul(b.sure)} sn görüntü` + (b.bas > 0.5 ? ` (kayıtta ${dakika(b.bas)}–${dakika(b.bitis)})` : '') + '.');
    }
    if (is.ses) { const b = probe(path.join(klasor, is.ses.dosya)); if (b) Object.assign(is.ses, b); }
    J.yaz(klasor, is);
    const bozuk = is.ham.filter(h => !h.goruntu);
    if (bozuk.length) {
      const x = degistir(x => { J.asamaKoy(x, 'ses', 'hata', ''); x.durum = 'hata'; x.aciklama = '“' + bozuk.map(h => h.ad).join('”, “') + '” açılmıyor ya da içinde görüntü yok.';
        x.ne_yap = 'Doğru videoyla yeni iş aç.'; J.olay(x, x.aciklama); });
      return { kod: 1, neden: x.aciklama };
    }
    return await (is.tarz === 'klip' ? klipHazirla(klasor, degistir) : shortHazirla(klasor, degistir));
  } catch (e) {          // an unexpected error: the job says so (never left "calisiyor" with nobody preparing it)
    try { degistir(x => { x.durum = 'hata'; x.aciklama = 'Hazırlık bir yerde takıldı.'; x.hata_ayrinti = String(e && e.stack || e);
      x.ne_yap = null; J.olay(x, x.aciklama); }); } catch (_) {}
    return { kod: 1, neden: 'Hazırlık bir yerde takıldı: ' + String(e && e.message || e) };
  } finally {
    try { degistir(x => { delete x.hazirlayan; }); } catch (_) {}
  }
}

async function shortHazirla(klasor, degistir) {
  let is = J.oku(klasor);
  degistir(x => { J.asamaKoy(x, 'ses', 'suruyor', ''); x.aciklama = 'Ses yazıya dökülüyor.'; });
  let sesDosya = is.ses ? path.join(klasor, is.ses.dosya) : null;
  if (!sesDosya && is.metin) {
    const hazir = path.join(klasor, 'ses', 'yer-tutucu-ses.wav');
    if (fs.existsSync(hazir) && fs.statSync(hazir).size > 1000) sesDosya = hazir;      // rerun: the stand-in voice is already there
    else {
      yaz('1/3 Metin Windows\'un Türkçe sesiyle okunuyor (yer tutucu ses; gerçek ses sonra verilebilir).');
      fs.writeFileSync(path.join(klasor, 'metin.txt'), is.metin, 'utf8');
      const hedef = path.join(klasor, 'ses', bosYer(path.join(klasor, 'ses'), 'yer-tutucu-ses.wav'));
      const r = await calistir('powershell', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', path.join(KOD, 'tts_tr.ps1'),
        path.join(klasor, 'metin.txt'), hedef, '1.15'], klasor, 120000);
      if (r.kod !== 0 || !fs.existsSync(hedef)) {
        degistir(x => { J.asamaKoy(x, 'ses', 'durdu', 'Yer tutucu ses yapılamadı'); x.durum = 'durdu'; x.aciklama = 'Windows\'un Türkçe sesi çalışmadı; deneme sesi yapılamadı.';
          x.ne_yap = 'Kendi sesini kaydedip ver (node panel/durum.js <iş> yeni-ses <kayıt>) ya da Windows\'a Türkçe konuşma sesini ekle (KURULUM-AJAN.md adım 8).'; J.olay(x, x.aciklama); });
        return { kod: 1, neden: 'Yer tutucu ses yapılamadı (Türkçe Windows sesi yok ya da çalışmadı).' };
      }
      sesDosya = hedef;
    }
    degistir(x => { x.ses = { dosya: path.relative(klasor, sesDosya).split(path.sep).join('/'), ad: 'yer-tutucu-ses.wav', yer_tutucu: true,
      boyut: fs.statSync(sesDosya).size }; J.olay(x, 'Metin, Windows\'un Türkçe sesiyle yer tutucu sese çevrildi.'); });
  }
  const sj = path.join(klasor, 'ses', 'ses.json');
  if (!fs.existsSync(sj)) {
    yaz('2/3 Ses yazıya dökülüyor (bu bilgisayarda, yerel Whisper).');
    degistir(x => { x.aciklama = 'Ses yazıya dökülüyor (bu bilgisayarda).'; });
    const r = await calistir(PY[0], [...PY.slice(1), path.join(KOD, 'ses_yazi.py'), sesDosya, path.join(klasor, 'ses'), ...dilArg(is)], klasor, 15 * 60 * 1000);
    if (r.kod !== 0 || !fs.existsSync(sj)) return yazamadi(klasor, degistir, r);
  } else yaz('2/3 Ses zaten yazıya dökülmüş (ses/ses.json var), atlandı.');
  const s = JSON.parse(fs.readFileSync(sj, 'utf8')), n = (s.kelimeler || []).length;
  // Whisper writes sentence-first words 0.2-0.7 s early: snap every word to the sound once (alet/kelime.py); the kit's
  // cekim.py zaman takes ses-hizali.json by itself. A failure here only means "Whisper times", never a stop.
  const hj = path.join(klasor, 'ses', 'ses-hizali.json'), sw = path.join(klasor, 'ses', 'ses.wav');
  if (n && fs.existsSync(sw) && !fs.existsSync(hj)) {
    yaz('3/3 Kelime zamanları sese oturtuluyor (alet/kelime.py hizala --hepsi).');
    const r = await calistir(PY[0], [...PY.slice(1), path.join(ALET, 'kelime.py'), 'hizala', sw, sj, '--hepsi', '--cikti', hj], klasor, 5 * 60 * 1000,
      null, x => /^\s*(EN COK KAYAN|CIKTI|HATA|UYARI)/.test(x));    // the word-by-word table stays in panel-gunluk.txt
    degistir(x => J.olay(x, r.kod === 0 && fs.existsSync(hj) ? 'Kelime zamanları sese oturtuldu (ses/ses-hizali.json).'
      : 'Kelime zamanları sese oturtulamadı; Whisper zamanları kullanılacak (ayrıntı: panel-gunluk.txt).'));
  } else if (fs.existsSync(hj)) yaz('3/3 Kelimeler zaten sese oturtulmuş (ses/ses-hizali.json var), atlandı.');
  degistir(x => {
    if (n) J.asamaKoy(x, 'ses', 'tamam', `${n} kelime, ${virgul(s.sure)} sn`);
    else J.asamaKoy(x, 'ses', 'claude', 'Seste kelime duyulmadı');
    J.olay(x, n ? `Ses yazıya döküldü: ${n} kelime${dilYazi(s)}.` : 'Ses dosyasında kelime duyulmadı.');
    J.asamaKoy(x, 'kanit', 'claude', ''); x.durum = 'claude_bekliyor';
    x.aciklama = 'Hazırlık bitti; Claude sohbette işe devam ediyor.'; J.olay(x, "İş Claude'a hazır.");
  });
  const uyari = [];
  if (n && (+s.sure < SHORT_EN_AZ_SN || n < SHORT_EN_AZ_KELIME))
    uyari.push(`UYARI: ses ${virgul(s.sure)} sn, ${n} kelime. Short en az ${SHORT_EN_AZ_SN} sn (kabaca ${SHORT_EN_AZ_KELIME} kelime); ` +
      'kurmadan önce kullanıcıya "bir-iki cümle ekle" de (panel/AJAN-TALIMATI.md, Çıta, "Malzeme inceyse").');
  return { kod: 0, uyari };
}

async function klipHazirla(klasor, degistir) {
  const is = J.oku(klasor), h = is.ham[0], kayit = path.resolve(klasor, h.dosya), hedef = path.join(klasor, 'yazi'), yj = path.join(hedef, 'yazi.json');
  if (!fs.existsSync(yj)) {
    yaz('1/3 Kaydın sesi yazıya dökülüyor (bu bilgisayarda; uzun kayıtta sürer, ilerleme aşağıda).');
    degistir(x => { J.asamaKoy(x, 'ses', 'suruyor', ''); x.aciklama = 'Kaydın sesi yazıya dökülüyor (bu bilgisayarda). Uzun kayıtta bu biraz sürer.'; });
    let son = 0;
    const r = await calistir(PY[0], [...PY.slice(1), path.join(KOD, 'ses_yazi.py'), '--uzun', kayit, hedef, String(is.ses_izi || 0), ...dilArg(is)], klasor,
      8 * 3600 * 1000, satir => {
        const m = satir.match(/^ILERLEME (\d+)\/(\d+) parca %(\d+).*kalan ~(\d+) sn/);
        if (!m || Date.now() - son < 3000) return; son = Date.now();
        const dk = Math.max(1, Math.round(+m[4] / 60));
        degistir(x => { J.asamaKoy(x, 'ses', 'suruyor', `%${m[3]} · ${m[1]}/${m[2]} parça`); x.aciklama = `Kaydın sesi yazıya dökülüyor: %${m[3]} (yaklaşık ${dk} dk kaldı).`; });
      });
    if (r.kod !== 0 || !fs.existsSync(yj)) return yazamadi(klasor, degistir, r);
  } else yaz('1/3 Kayıt zaten yazıya dökülmüş (yazi/yazi.json var), atlandı.');
  const y = JSON.parse(fs.readFileSync(yj, 'utf8')), n = (y.kelimeler || []).length;
  if (!n) {
    degistir(x => { J.asamaKoy(x, 'ses', 'durdu', 'Kayıtta konuşma duyulmadı'); x.durum = 'durdu'; x.aciklama = 'Kayıtta konuşma duyamadım. Klip için kayıtta konuşma olmalı.';
      x.ne_yap = 'Kayıtta birden çok ses kanalı olabilir: konuşmanın olduğu kanalla (--ses-izi 1) ya da konuşmalı başka bir kayıtla yeni iş aç.'; J.olay(x, x.aciklama); });
    return { kod: 1, neden: 'Kayıtta konuşma duyulmadı.' };
  }
  // the camera BEFORE the moments: kod/klip_bul.py lowers a candidate whose camera box shows no face (--kamera)
  const kd = path.join(klasor, 'kamera');
  if (!fs.existsSync(path.join(kd, 'kamera.json'))) {
    yaz('2/3 Kayıtta yayıncı kamerası aranıyor.');
    degistir(x => { x.aciklama = 'Kayıtta yayıncı kamerası aranıyor.'; });
    await calistir(PY[0], [...PY.slice(1), path.join(KOD, 'kamera_bul.py'), kayit, kd], klasor, 10 * 60 * 1000);
  } else yaz('2/3 Kamera önerisi zaten var (kamera/kamera.json), atlandı.');
  let kam = null; try { kam = JSON.parse(fs.readFileSync(path.join(kd, 'kamera.json'), 'utf8')); } catch (_) {}
  if (!fs.existsSync(path.join(hedef, 'adaylar.json'))) {
    yaz('3/3 Aday anlar çıkarılıyor (sesin, söylenenlerin ve sohbetin hızlandığı yerler).');
    const ek = [];
    if (is.anlar && is.anlar.length) ek.push('--anlar', path.join(klasor, 'anlar.txt'));
    if (is.sohbet) ek.push('--sohbet', path.join(klasor, is.sohbet.dosya));
    if (is.sohbet_kutu) ek.push('--kutu', is.sohbet_kutu.join(','));
    // a box already confirmed in the job (durum.js kamera) wins over the suggestion; no box = no flag, as before
    const ik = is.kamera || {}, kutu = ik.yok ? 'yok' : Array.isArray(ik.kutu) ? ik.kutu.join(',')
      : kam && Array.isArray(kam.kamera) ? kam.kamera.join(',') : null;
    if (kutu) ek.push('--kamera', kutu);
    if (is.sohbet || is.sohbet_kutu) degistir(x => { x.aciklama = 'Sohbetin hızlandığı yerler ölçülüyor.'; });
    await calistir(PY[0], [...PY.slice(1), path.join(KOD, 'klip_bul.py'), hedef, String(is.adet || 3), ...ek], klasor, 3 * 3600 * 1000);
  } else yaz('3/3 Aday anlar zaten var (yazi/adaylar.json), atlandı.');
  let isr = null; try { isr = JSON.parse(fs.readFileSync(path.join(hedef, 'isaretler.json'), 'utf8')); } catch (_) {}
  degistir(x => {
    if (kam) {
      x.kamera_oneri = { kamera: kam.kamera, yuz: kam.yuz, yuz_kare: kam.yuz_bulunan_kare, kare_sayisi: kam.kare, not: kam.not,
        kare: 'kamera/kamera-kare.jpg', kare_px: [Math.min(1920, kam.kayit_px[0]), Math.round(Math.min(1920, kam.kayit_px[0]) * kam.kayit_px[1] / kam.kayit_px[0])] };
      J.olay(x, kam.kamera ? `Kamera kutusu önerildi (yüz ${kam.yuz_bulunan_kare}/${kam.kare} karede aynı yerde). Claude kareye bakıp doğrulayacak.`
        : 'Kayıtta kamera kutusu bulunamadı: ' + kam.not + '. Claude kareye bakıp karar verecek.');
    }
    J.asamaKoy(x, 'ses', 'tamam', `${n} kelime, ${Math.round(y.sure / 60)} dk kayıt, ${Math.round(y.sure_sn || 0)} sn sürdü`);
    J.olay(x, `Kayıt yazıya döküldü: ${n} kelime (${Math.round(y.sure / 60)} dk${dilYazi(y)}). Aday anlar çıkarıldı.`);
    if (isr) for (const g of isr.gunluk || []) J.olay(x, 'İşaretler: ' + g + '.');
    J.asamaKoy(x, 'kanit', 'claude', ''); x.durum = 'claude_bekliyor';
    x.aciklama = x.anlar && x.anlar.length ? `Hazırlık bitti; Claude verilen ${x.anlar.length} anı cümle sınırlarına oturtup kuracak.`
      : `Hazırlık bitti; Claude ${x.adet || 3} klip için anları seçecek.`;
    J.olay(x, "İş Claude'a hazır.");
  });
  return { kod: 0 };
}

function yazamadi(klasor, degistir, r) {
  const satir = ((r.cikti || '').match(/HATA[^\n]*/) || [])[0];
  const neden = satir ? satir.replace(/^HATA:\s*/, '') : 'yazıya dökme çalışmadı (ayrıntı: panel-gunluk.txt)';
  degistir(x => { J.asamaKoy(x, 'ses', 'hata', neden); x.durum = 'hata'; x.hata_ayrinti = neden; x.aciklama = 'Konuşma yazıya dökülemedi: ' + neden;
    x.ne_yap = 'Kurulumu kontrol et (py -3 kur_kontrol.py), sonra: node panel/is_ac.js devam "' + klasor + '"'; J.olay(x, x.aciklama); });
  return { kod: 1, neden: 'Konuşma yazıya dökülemedi: ' + neden };
}

module.exports = { PANEL, MOTOR, KOD, PY, SHORT_TURLER, VIDEO_UZ, SES_UZ, SOHBET_UZ, AN_RE, KOPYA_SINIR, SHORT_EN_AZ_SN, SHORT_EN_AZ_KELIME,
  ciktiVer, dakika, virgul, guvenliAd, bosYer, yeniId, claudeIcin, probe, calistir, kurulumEksigi, yaziCihazi, yaziTahmini,
  dilKontrol, hazirlikSuruyor, hazirla };
