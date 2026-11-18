#!/usr/bin/env node
// server.js - the local watch page of the Shorts edit engine. No dependencies. READ ONLY.
//
//   node panel/server.js            -> http://127.0.0.1:4317   (PANEL_PORT to change)
//   node panel/dur.js               -> stops it by the PID written to panel/calisiyor.pid (PANEL_PID_DOSYA to change)
//
// What it does: shows the jobs in the jobs folder (isler/<id>/is.json, written only by panel/is_ac.js and
// panel/durum.js from the user's own Claude Code chat), their files, the plain status, the setup check and the style
// notebook. It answers GET (and HEAD) only: it never opens, prepares or changes a job, never starts Claude or a model,
// never calls the internet, never deletes a file. The preparation it used to run lives in panel/hazirlik.js
// (run by panel/is_ac.js); this page only asks it whether a preparation is still alive ("Yarıda kaldı").
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const { pipeline } = require('stream');
const { execFile } = require('child_process');
const J = require('./is_dosyasi');
const SZ = require('./sozluk');                     // shared Turkish words + the plain status the page and durum.js show

const PANEL = __dirname;
const MOTOR = path.dirname(PANEL);                  // engine root (has kod/)
const KOD = path.join(MOTOR, 'kod');
const ISLER = process.env.PANEL_ISLER ? path.resolve(process.env.PANEL_ISLER) : path.join(PANEL, 'isler');   // PANEL_ISLER: test copy only
const ARAYUZ = path.join(PANEL, 'arayuz');
const PORT = +(process.env.PANEL_PORT || 4317);
const HOST = '127.0.0.1';
const PY = process.env.PANEL_PYTHON ? process.env.PANEL_PYTHON.split(' ') : (process.platform === 'win32' ? ['py', '-3'] : ['python3']);
const MOTOR_AD = path.basename(MOTOR);
const PID_DOSYA = process.env.PANEL_PID_DOSYA ? path.resolve(process.env.PANEL_PID_DOSYA) : path.join(PANEL, 'calisiyor.pid');   // test copies: elsewhere
const TARZIM = process.env.PANEL_TARZIM ? path.resolve(process.env.PANEL_TARZIM) : path.join(MOTOR, 'tarzim');   // style notebook, read only
const TAKILDI_MS = 30 * 60 * 1000;                  // Claude working with no news for this long: the page says "Claude ses vermiyor"

fs.mkdirSync(ISLER, { recursive: true });
const kopyaCumle = (id, tarz) => SZ.kopyaCumle(path.join(ISLER, id), tarz);

// ------------------------------------------------------------------ helpers
const TURLER = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.txt': 'text/plain; charset=utf-8', '.md': 'text/plain; charset=utf-8',
  '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime', '.wav': 'audio/wav', '.m4a': 'audio/mp4',
  '.mp3': 'audio/mpeg', '.jpg': 'image/jpeg', '.png': 'image/png', '.ttf': 'font/ttf', '.svg': 'image/svg+xml' };

function gonder(res, kod, govde, tur) {
  const b = typeof govde === 'string' || Buffer.isBuffer(govde) ? govde : JSON.stringify(govde);
  res.writeHead(kod, { 'Content-Type': tur || 'application/json; charset=utf-8', 'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff' });
  res.end(b);
}
function hata(res, kod, mesaj) { gonder(res, kod, { hata: mesaj }); }
function icinde(kok, yol) { const r = path.relative(kok, yol); return r && !r.startsWith('..') && !path.isAbsolute(r); }

// ------------------------------------------------------------------ job summary for the screen
const sonSatir = (is, re) => { const d = (is.gecmis || []).slice().reverse().find(g => re.test(g.olay || '')); return d ? d.olay.replace(re, '').trim() : null; };
function ozet(id) {
  const klasor = path.join(ISLER, id);
  const is = J.oku(klasor); if (!is) return null;
  const ek = {};
  try {
    const s = JSON.parse(fs.readFileSync(path.join(klasor, 'ses', 'ses.json'), 'utf8'));
    ek.yazi = { sure: s.sure, kelime: (s.kelimeler || []).length, metin: (s.kelimeler || []).map(k => k[0]).join(' ').slice(0, 1200), model: s.model };
  } catch (_) {}
  if (is.tarz === 'klip') {
    try {
      const y = JSON.parse(fs.readFileSync(path.join(klasor, 'yazi', 'yazi.json'), 'utf8'));
      ek.yazi = { sure: y.sure, kelime: (y.kelimeler || []).length, model: y.model, yazma_sn: y.sure_sn,
        metin: (y.kelimeler || []).slice(0, 220).map(k => k[0]).join(' ') + ((y.kelimeler || []).length > 220 ? ' …' : '') };
    } catch (_) {}
    try {   // the moments Claude chose (klip_plan.json): shown while the clips are being built
      const p = JSON.parse(fs.readFileSync(path.join(klasor, 'klip_plan.json'), 'utf8'));
      ek.klip_plan = (p.klipler || []).map(k => ({ ad: k.ad, bas: k.bas, son: k.son, neden: k.neden, baslik: k.baslik, puan: k.puan == null ? null : k.puan, kullanici: k.kullanici || null }))
        .sort((a, b) => (b.puan || 0) - (a.puan || 0));
      ek.klip_duzen = { duzen: p.duzen, altyazi: !!p.altyazi };
    } catch (_) {}
    try {   // markers handed to Claude: user moments, loudness peaks, chat peaks (with their source)
      const m = JSON.parse(fs.readFileSync(path.join(klasor, 'yazi', 'isaretler.json'), 'utf8'));
      ek.isaretler = { anlar: (m.anlar || []).map(a => ({ satir: a.satir, tur: a.tur, bas: a.bas, son: a.son, sure: a.sure, uyari: a.uyari })),
        ses: (m.ses_tepesi || []).length, sohbet: (m.sohbet_tepesi || []).map(s => ({ t: s.t, kat: s.kat, kaynak: s.kaynak })), gunluk: m.gunluk || [] };
    } catch (_) {}
    if (is.sonuc && Array.isArray(is.sonuc.klipler)) for (const k of is.sonuc.klipler) if (!fs.existsSync(path.join(klasor, k.video))) k.eksik = true;
  }
  try {
    const p = JSON.parse(fs.readFileSync(path.join(klasor, 'plan.json'), 'utf8'));
    ek.plan = (p.cumleler || []).map(c => ({ metin: c.metin, duzen: c.duzen,
      kanit: (c.kanit || []).map(k => ({ kaynak: k.kaynak, bas: k.bas, son: k.son, ne: k.ne })) }));
  } catch (_) {}
  // the gate result: from is.json, or straight from kapi_sonuc.txt when the agent only wrote the file.
  // While Claude is still working (or the job waits for Claude) a gate file is an in-between round: the talimat runs
  // the gate after every fix, so a red line there is not the result. Only the final state shows it.
  if (['claude_calisiyor', 'claude_bekliyor'].includes(is.durum)) {
    is.kapi = null; if (is.durum === 'claude_calisiyor') is.kapi_suruyor = true;
  } else if (!is.kapi) {
    try {
      const yol = path.join(klasor, 'kapi_sonuc.txt');
      // after 'yeniden dene' (or a stage started again) an older gate file must not come back as the current result
      if (!is.kapi_sifir || fs.statSync(yol).mtimeMs > Date.parse(is.kapi_sifir)) {
        const k = J.kapiCoz(fs.readFileSync(yol, 'utf8')); if (k.sonuc) is.kapi = { ...k, dosya: 'kapi_sonuc.txt' };
      }
    } catch (_) {}
  }
  if (is.sonuc && is.sonuc.video && !fs.existsSync(path.join(klasor, is.sonuc.video))) is.sonuc.eksik = true;
  if (is.durum === 'claude_calisiyor' && Date.now() - Date.parse(is.guncellendi) > TAKILDI_MS) is.sessiz_dk = Math.round((Date.now() - Date.parse(is.guncellendi)) / 60000);
  // "calisiyor" but the is_ac.js that prepares it is gone (is.hazirlayan.pid no longer runs; older jobs: 10 min of silence)
  if (is.durum === 'calisiyor' && !SZ.hazirlikSuruyor(is)) is.takildi = true;
  is.cumle = kopyaCumle(id, is.tarz);
  is.panelde = SZ.durumOzet(is, { takildi: !!is.takildi });   // the page's headline; durum.js ozet prints the same
  is.klasor = klasor;
  // the one thing the agent tried on purpose ("Deneme: ...") and its own verdict ("Hüküm: ..."): the last history line of each
  if (!is.deneme) { const d = sonSatir(is, /^Deneme:\s*/i); if (d) is.deneme = d; }
  if (!is.hukum) { const h = sonSatir(is, /^H[üu]k[üu]m:\s*/i); if (h) is.hukum = h; }
  return { ...is, ...ek };
}
function hepsi() {
  return fs.readdirSync(ISLER, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => ozet(d.name)).filter(Boolean)
    .sort((a, b) => String(b.olusturuldu).localeCompare(String(a.olusturuldu)));
}

// ------------------------------------------------------------------ watching job files (agent writes them)
const izleyiciler = new Set();
const imza = new Map();
function imzaAl(id) {
  const k = path.join(ISLER, id); let s = '';
  for (const f of ['is.json', 'kapi_sonuc.txt', 'plan.json', 'klip_plan.json', path.join('yazi', 'isaretler.json'), path.join('ses', 'ses.json'), path.join('yazi', 'yazi.json')]) {
    try { const st = fs.statSync(path.join(k, f)); s += f + st.mtimeMs + ':' + st.size + ';'; } catch (_) {}
  }
  return s;
}
function tara() {
  let adlar = [];
  try { adlar = fs.readdirSync(ISLER, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name); } catch (_) { return; }
  for (const id of adlar) {
    const s = imzaAl(id);
    if (imza.get(id) !== s) {
      const ilk = !imza.has(id); imza.set(id, s);
      if (!ilk || izleyiciler.size) { const o = ozet(id); if (o) yayinla('is', o); }
    }
  }
}
function yayinla(olay, veri) {
  const satir = `event: ${olay}\ndata: ${JSON.stringify(veri)}\n\n`;
  for (const r of izleyiciler) { try { r.write(satir); } catch (_) {} }
}
setInterval(tara, 700);
setInterval(() => { for (const r of izleyiciler) { try { r.write(': nabız\n\n'); } catch (_) {} } }, 20000);

// ------------------------------------------------------------------ setup check (GET /api/hazir-mi)
// Only LOOKS: ffmpeg/ffprobe answer, Python + its packages + the speech model in the local cache + the font
// (panel/hazir_mi.py), and whether Claude Code is installed (`where claude`: looked up, never run). Nothing is
// installed or downloaded. PANEL_SAHTE_EKSIK="ffmpeg,model" marks items missing (screenshots / tests only).
function bak(komut, args, sure = 60000) {
  return new Promise(ok => execFile(komut, args, { windowsHide: true, timeout: sure, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } },
    (e, out) => ok({ ok: !e, out: String(out || '') })));
}
let hazirOnbellek = null, hazirSuruyor = null;
async function hazirMi() {
  const py = PY.join(' '), m = [];
  const ff = await bak('ffmpeg', ['-hide_banner', '-version']), fp = await bak('ffprobe', ['-hide_banner', '-version']);
  m.push({ ad: 'ffmpeg', baslik: 'Video aracı (ffmpeg)', var: ff.ok, sart: true, yap: 'ffmpeg kur (komut satırında: winget install Gyan.FFmpeg), sonra paneli kapatıp aç.' });
  m.push({ ad: 'ffprobe', baslik: 'Video bilgi aracı (ffprobe)', var: fp.ok, sart: true, yap: 'ffprobe ffmpeg ile gelir: ffmpeg\'i kur, sonra paneli kapatıp aç.' });
  const r = await bak(PY[0], [...PY.slice(1), path.join(PANEL, 'hazir_mi.py')], 120000);
  let j = null; try { j = JSON.parse(r.out.trim().split(/\r?\n/).pop()); } catch (_) {}
  m.push({ ad: 'python', baslik: 'Python', var: !!j, sart: true, yap: `Python 3 kur (python.org), sonra paneli kapatıp aç. Panel “${py}” komutunu arıyor.` });
  const ADLAR = { numpy: 'numpy', PIL: 'Pillow (resim)', cv2: 'OpenCV (kamera bulma)', scipy: 'SciPy', faster_whisper: 'faster-whisper (yazıya dökme)' };
  const paket = j ? j.paketler : {};
  for (const k of Object.keys(ADLAR)) {
    const p = paket[k]; m.push({ ad: k, baslik: 'Python paketi: ' + ADLAR[k], var: !!(p && p.var), sart: true,
      yap: `Komut satırında “${py} -m pip install ${p ? p.pip : k}” yaz, sonra paneli kapatıp aç.` });
  }
  m.push({ ad: 'model', baslik: 'Yazıya dökme modeli', var: !!(j && j.model), sart: true, not: j && j.model ? j.model : '',
    yap: 'Konuşmayı yazıya döken model bu bilgisayarda yok; o olmadan iş ilerlemez. Claude Code\'a “bu depoyu kur” yaz: modeli senin onayınla bir kez indirir (~1,6 GB). Motor modeli kendisi indirmez. Kurulum bitince bu uyarı izleme sayfasından kendiliğinden kalkar.' });
  m.push({ ad: 'yazi_tipi', baslik: 'Yazı tipi (Anton)', var: !!(j && j.dosyalar && j.dosyalar.yazi_tipi), sart: true,
    yap: 'Motor klasöründe kod/font/Anton.ttf yok. Motoru indirdiğin yerden bu dosyayı geri koy.' });
  m.push({ ad: 'yuz_modeli', baslik: 'Kamera bulma modeli', var: !!(j && j.dosyalar && j.dosyalar.yuz_modeli), sart: false,
    yap: 'Şart değil: kamerayı karede fareyle çizersin ya da Claude bulur.' });
  const cl = await bak(process.platform === 'win32' ? 'where' : 'which', ['claude'], 10000);   // looked up, never run
  m.push({ ad: 'claude', baslik: 'Claude Code', var: cl.ok && cl.out.trim().length > 0, sart: true,
    yap: 'Claude Code kurulu görünmüyor. Kur (claude.com/claude-code), sonra paneli kapatıp aç. Panel Claude\'u hiç açmaz; işler Claude Code sohbetinden açılır, panel yalnız izler.' });
  const sahte = String(process.env.PANEL_SAHTE_EKSIK || '').split(/[ ,]+/).filter(Boolean);
  for (const x of m) if (sahte.includes(x.ad)) x.var = false;
  return { zaman: J.simdi(), maddeler: m, eksik: m.filter(x => !x.var && x.sart).length, sahte: sahte.length > 0 };
}
function hazirAl(yeniden) {
  if (hazirOnbellek && !yeniden) return Promise.resolve(hazirOnbellek);
  if (!hazirSuruyor) hazirSuruyor = hazirMi().then(x => { hazirOnbellek = x; hazirSuruyor = null; return x; }, () => { hazirSuruyor = null; return null; });
  return hazirSuruyor;
}

// ------------------------------------------------------------------ style notebook (GET /api/defter), READ ONLY
// alet/tarz.py goster --json reads tarzim/ and writes nothing; the answer is kept until gunluk.md or KAPALI changes.
let defterOnbellek = { imza: null, veri: null };
function defterAl() {
  return new Promise(ok => {
    if (!fs.existsSync(TARZIM)) return ok({ var: false, kapali: false, klasor: TARZIM });
    let imza = '';
    for (const f of ['gunluk.md', 'KAPALI', 'ayar.json']) { try { const st = fs.statSync(path.join(TARZIM, f)); imza += f + st.mtimeMs + ':' + st.size + ';'; } catch (_) {} }
    if (defterOnbellek.imza === imza && defterOnbellek.veri) return ok(defterOnbellek.veri);
    execFile(PY[0], [...PY.slice(1), path.join(MOTOR, 'alet', 'tarz.py'), '--klasor', TARZIM, 'goster', '--json', '--son', '6'],
      { windowsHide: true, timeout: 30000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } }, (e, out) => {
        let j = null; try { j = JSON.parse(String(out).trim().split(/\r?\n/).pop()); } catch (_) {}
        if (!j) return ok({ var: null, hata: 'Defter okunamadı.', klasor: TARZIM });
        defterOnbellek = { imza, veri: j }; ok(j);
      });
  });
}

// ------------------------------------------------------------------ static files with Range (video seeking)
// stream.pipeline closes the file when the browser goes away (a seek, a closed tab): no handle stays open on a video
function dosyaGonder(req, res, yol, indir) {
  let st; try { st = fs.statSync(yol); } catch (_) { return hata(res, 404, 'dosya yok'); }
  if (!st.isFile()) return hata(res, 404, 'dosya yok');
  const tur = TURLER[path.extname(yol).toLowerCase()] || 'application/octet-stream';
  const bas = { 'Content-Type': tur, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' };
  if (indir) bas['Content-Disposition'] = `attachment; filename*=UTF-8''${encodeURIComponent(path.basename(yol))}`;
  const r = req.headers.range && req.headers.range.match(/bytes=(\d*)-(\d*)/);
  if (r) {
    let a = r[1] === '' ? st.size - +r[2] : +r[1], b = r[1] !== '' && r[2] !== '' ? +r[2] : st.size - 1;
    if (isNaN(a) || a < 0 || a >= st.size || b < a) { res.writeHead(416, { 'Content-Range': `bytes */${st.size}` }); return res.end(); }
    b = Math.min(b, st.size - 1);
    res.writeHead(206, { ...bas, 'Content-Range': `bytes ${a}-${b}/${st.size}`, 'Content-Length': b - a + 1 });
    if (req.method === 'HEAD') return res.end();
    return pipeline(fs.createReadStream(yol, { start: a, end: b }), res, () => {});
  }
  res.writeHead(200, { ...bas, 'Content-Length': st.size });
  if (req.method === 'HEAD') return res.end();
  pipeline(fs.createReadStream(yol), res, () => {});
}

// ------------------------------------------------------------------ routes (GET and HEAD only)
const YARDIM = `Short motoru izleme sayfası: yollar (yalnız bu bilgisayar, http://${HOST}:${PORT}). Sayfa yalnız okur.
Adlar (iş türleri, aşamalar, durumlar): GET /api/sozluk (dosyası panel/sozluk.json). Ajan adımları: panel/AJAN-TALIMATI.md.

  GET  /api/yardim                 bu metin
  GET  /api/sozluk                 ortak Türkçe adlar (JSON)
  GET  /api/ozet                   bütün işlerin durumu, sade metin (en yenisi üstte)
  GET  /api/is/<id>/ozet           tek işin durumu, sayfadaki cümlenin aynısı (?json = JSON)
  GET  /api/isler                  bütün işler, tam bilgi (JSON; her işte "panelde" = sayfanın başlığı)
  GET  /api/olaylar                canlı akış (SSE, olay adı "is")
  GET  /api/defter                 tarz defteri (yalnız okur; PANEL_TARZIM ile başka klasör)
  GET  /api/hazir-mi               kurulum kontrolü (?yeniden = yeniden bak); hiçbir şey kurmaz
  GET  /api/kim                    sayfanın PID'i ve kapısı
  GET  /isler/<id>/<dosya>         işin bir dosyası (?indir = indirme)

İş açmak, işi sürdürmek ve durumu yazmak sohbettendir, sayfadan değil (başka her istek 405 alır):
  node panel/is_ac.js klip|short|devam ...      iş açar, hazırlar, yarım işi sürdürür
  node panel/durum.js panel/isler/<id> ...      durumu yazar (is.json elle yazılmaz)
  node panel/durum.js panel/isler/<id> ozet     bu sayfanın metni, sayfa kapalıyken de
Sayfa Claude'u ya da bir modeli hiç başlatmaz, hiçbir dosyayı yazmaz ya da silmez.
`;

async function yonlendir(req, res) {
  const url = new URL(req.url, `http://${HOST}`);
  const p = decodeURIComponent(url.pathname);
  // only this computer may talk to the page
  const host = req.headers.host || '';
  if (!/^(127\.0\.0\.1|localhost)(:\d+)?$/.test(host)) return hata(res, 403, 'yalnız bu bilgisayar');
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.setHeader('Allow', 'GET, HEAD');
    return hata(res, 405, 'Bu sayfa yalnız okur. İş açmak ve durum yazmak sohbetten: node panel/is_ac.js, node panel/durum.js (GET /api/yardim).');
  }

  if (p === '/api/kim') return gonder(res, 200, { pid: process.pid, port: PORT });   // dur.js checks this before stopping
  // for agents: the routes in plain words (no need to read this file), the shared words, one job's status as text
  if (p === '/api/yardim') return gonder(res, 200, YARDIM, 'text/plain; charset=utf-8');
  if (p === '/api/sozluk') return gonder(res, 200, SZ.S);
  if (p === '/api/defter') return gonder(res, 200, await defterAl());
  const mo = p.match(/^\/api\/is\/([\w-]+)\/ozet$/);
  if (mo) {
    const o = ozet(mo[1]); if (!o) return hata(res, 404, 'Bu işi bulamadım. GET /api/isler bütün işleri listeler.');
    if (url.searchParams.has('json')) return gonder(res, 200, o.panelde);
    return gonder(res, 200, SZ.ozetMetni(o, o.panelde, { cumle: o.cumle, klasor: o.klasor }) + '\n', 'text/plain; charset=utf-8');
  }
  if (p === '/api/ozet') {   // every job, one block each, newest first
    const L = hepsi().map(o => SZ.ozetMetni(o, o.panelde, { cumle: o.cumle, klasor: o.klasor }));
    return gonder(res, 200, (L.length ? L.join('\n\n') : 'Henüz iş yok.') + '\n', 'text/plain; charset=utf-8');
  }
  if (p === '/api/hazir-mi') {
    const x = await hazirAl(url.searchParams.has('yeniden'));
    return x ? gonder(res, 200, x) : hata(res, 500, 'Kontrol yapılamadı. Paneli kapatıp yeniden aç.');
  }
  if (p === '/api/isler') return gonder(res, 200, { isler: hepsi(), motor: MOTOR_AD });
  if (p === '/api/olaylar' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-store', Connection: 'keep-alive' });
    res.write('retry: 2000\n\n'); izleyiciler.add(res); req.on('close', () => izleyiciler.delete(res)); return;
  }
  const m = p.match(/^\/isler\/([\w-]+)\/(.+)$/);
  if (m) {
    const kok = path.join(ISLER, m[1]), yol = path.resolve(kok, m[2]);
    if (!icinde(kok, yol)) return hata(res, 403, 'izin yok');
    return dosyaGonder(req, res, yol, url.searchParams.has('indir'));
  }
  if (p === '/font/Anton.ttf') return dosyaGonder(req, res, path.join(KOD, 'font', 'Anton.ttf'));
  const yol = path.resolve(ARAYUZ, '.' + (p === '/' ? '/index.html' : p));
  if (!icinde(ARAYUZ, yol)) return hata(res, 404, 'yok');
  return dosyaGonder(req, res, yol);
}

const sunucu = http.createServer((req, res) => { yonlendir(req, res).catch(e => { try { hata(res, 500, e.message); } catch (_) {} }); });
sunucu.listen(PORT, HOST, () => {
  fs.writeFileSync(PID_DOSYA, process.pid + ' ' + PORT);   // '<pid> <port>'; emptied on stop
  tara(); hazirAl();
  console.log(`Panel açık: http://${HOST}:${PORT}   (PID ${process.pid}; durdurmak için Ctrl+C ya da: node panel/dur.js)`);
});
sunucu.on('error', e => { console.error('Panel açılamadı: ' + e.message); process.exit(1); });
function kapan() { try { if (fs.readFileSync(PID_DOSYA, 'utf8').trim().split(/\s+/)[0] === String(process.pid)) fs.writeFileSync(PID_DOSYA, ''); } catch (_) {} process.exit(0); }
process.on('SIGINT', kapan); process.on('SIGTERM', kapan);
