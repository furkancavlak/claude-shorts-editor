// Short Motoru izleme sayfası (v2) - READ ONLY. A job is opened and run from the user's own Claude Code chat; this page only
// shows who is working ("Şimdi"), the newest video big ("Son çıkan"), older outputs, and the style notebook. It never writes.
// Words come from GET /api/sozluk (panel/sozluk.json); each job's headline ("panelde": name, plain sentence, "3/5 · Kurgu",
// Ne oldu / Ne yap) is computed by the server with the same code durum.js uses, so the page and an agent read the same
// sentence. File paths are kept out of sight: they sit in title attributes and in the agents' text status (GET /api/ozet).
'use strict';
(function () {
  const $ = s => document.querySelector(s);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ---------------------------------------------------------- theme: dark unless light was picked (remembered)
  const kok = document.documentElement;
  function temaKoy(t, kaydet) {
    t = t === 'light' ? 'light' : 'dark';
    kok.setAttribute('data-theme', t);
    document.querySelectorAll('.tema button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tema === t)));
    if (kaydet) try { localStorage.setItem('panel-tema', t); } catch (_) {}
  }
  const adres = new URLSearchParams(location.search);
  let tema0 = null; try { tema0 = localStorage.getItem('panel-tema'); } catch (_) {}
  if (adres.get('tema')) temaKoy(adres.get('tema'), true); else temaKoy(tema0);
  document.querySelectorAll('.tema button').forEach(b => b.addEventListener('click', () => temaKoy(b.dataset.tema, true)));

  // ---------------------------------------------------------- words
  let S = { kim: {}, turler: {}, defter: {}, kurulum: {}, sira_sende: {}, baslat: {}, bolumler: {} };
  const kel = (yol, yedek) => { let x = S; for (const k of yol.split('.')) x = x && x[k]; return x == null ? (yedek || '') : x; };
  const doldur = (t, d) => String(t || '').replace(/\{(\w+)\}/g, (_, k) => d[k] == null ? '' : d[k]);
  // "Kalıcı tercih · 3 videoda söyledin" -> the part before the first " · " in bold
  const vurgula = t => { const i = t.indexOf(' · '); return i < 0 ? esc(t) : `<b>${esc(t.slice(0, i))}</b>${esc(t.slice(i))}`; };

  // the chat bubble beside a waiting question (drawn by Codex)
  const BALON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" aria-hidden="true"><path d="M4 2H14Q16 2 16 4V11Q16 13 14 13H8L4 16V13Q2 13 2 11V4Q2 2 4 2Z"/></svg>';

  // ---------------------------------------------------------- time, sizes
  const saat = iso => iso ? new Date(iso).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) : '';
  function gunSaat(iso) {
    if (!iso) return '';
    const d = new Date(iso), b = new Date(), dun = new Date(b - 864e5);
    if (d.toDateString() === b.toDateString()) return 'bugün ' + saat(iso);
    if (d.toDateString() === dun.toDateString()) return 'dün ' + saat(iso);
    return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long' }) + ' ' + saat(iso);
  }
  function sure(iso) {              // "4 dk", "1 sa 10 dk"
    if (!iso) return ''; const dk = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
    if (dk < 1) return 'az önce';
    return dk < 60 ? dk + ' dk' : Math.floor(dk / 60) + ' sa' + (dk % 60 ? ' ' + dk % 60 + ' dk' : '');
  }
  const mb = n => n == null ? '' : n >= 1e9 ? (n / 1e9).toFixed(2).replace('.', ',') + ' GB' : n >= 1e6 ? (n / 1e6).toFixed(1).replace('.', ',') + ' MB' : Math.max(1, Math.round(n / 1e3)) + ' KB';
  const dk = s => { s = Math.floor(+s); const h = Math.floor(s / 3600), d = Math.floor(s / 60) % 60, n = String(s % 60).padStart(2, '0');
    return h ? `${h}:${String(d).padStart(2, '0')}:${n}` : `${d}:${n}`; };

  // ---------------------------------------------------------- jobs
  const isler = new Map(); let defter = null;
  const pd = is => is.panelde || { durum: is.durum, durum_adi: is.durum, kim: 'sen', sira: '', eylem: is.aciklama || '', asamalar: [], tur: is.tarz, ad: 'İş ' + is.id };
  const url = (is, v) => `/isler/${encodeURIComponent(is.id)}/${String(v).split('/').map(encodeURIComponent).join('/')}`;
  const yol = (is, v) => is.klasor ? is.klasor + (v ? '\\' + String(v).split('/').join('\\') : '') : (v || '');
  const bittiZaman = is => (is.asamalar && is.asamalar.hazir && is.asamalar.hazir.zaman) || is.guncellendi;
  // two waiting jobs with the same name (two jobs from one recording) are told apart by their start time;
  // a row in Şimdi always shows its start time, so it needs no suffix
  let ayni = new Set();
  const ad = is => pd(is).ad || 'İş ' + is.id;
  const ayirtAd = is => ayni.has(ad(is)) ? `${ad(is)}, ${saat(is.olusturuldu)}'de başlayan` : ad(is);
  // The one question after delivery: only once the agent said it asked it (node panel/durum.js <iş> soruldu -> is.soru,
  // not older than this delivery; the server also sends it as panelde.soru), while the job is fresh and the notebook
  // has nothing for it yet
  function soruMetni(is) {
    const p = pd(is);
    if (p.soru !== undefined) return p.soru;
    if (is.durum !== 'hazir' || !is.soru || !is.soru.metin) return null;          // an older server: the same test here
    return Date.parse(is.soru.zaman) >= Date.parse(bittiZaman(is)) - 2000 ? is.soru.metin : null;
  }
  function soruBekliyor(is) {
    if (is.durum !== 'hazir' || !soruMetni(is) || !defter || defter.kapali || defter.var === null) return false;
    if (Date.now() - Date.parse(bittiZaman(is)) > 6 * 3600e3) return false;
    return !(defter.isler || []).includes(is.id);
  }
  // "Sıra sende" only when the user really has to answer in the chat
  const siraSende = is => ['durdu', 'kaldi'].includes(is.durum) && !pd(is).ozel ? is.durum : soruBekliyor(is) ? 'hazir' : null;
  // the idea of the edit (durum.js fikir), the one thing tried on purpose ("Deneme: …") and the agent's own verdict ("Hüküm: …")
  const sonNot = (is, re) => { const g = (is.gecmis || []).slice().reverse().find(x => re.test(x.olay || '')); return g ? g.olay.replace(re, '').trim() : ''; };
  const hukumAl = is => is.hukum || sonNot(is, /^H[üu]k[üu]m:\s*/i);
  const denemeAl = is => is.deneme || sonNot(is, /^Deneme:\s*/i);
  function fikirSon(is) {           // a running job: the idea recorded last ("klip-2" for an Editli clip)
    const f = Object.entries(is.fikir || {}).filter(([, x]) => x && x.metin).sort((a, b) => String(b[1].zaman).localeCompare(String(a[1].zaman)))[0];
    return f ? { ad: f[0], metin: f[1].metin } : null;
  }
  const hataMi = p => p.durum === 'hata' || p.ozel === 'yarida';

  function isSatir(is) {
    const p = pd(is), hata = hataMi(p), sira = siraSende(is);
    const cizgi = (p.asamalar || []).map(a => `<li data-d="${esc(a.durum)}" title="${esc(a.ad + ': ' + a.durum_adi)}"></li>`).join('');
    const calisiyor = ['calisiyor', 'claude_calisiyor', 'hazirlaniyor'].includes(is.durum) && !p.ozel;
    const adimYazi = p.adim ? `${p.adim.no}/${p.adim.toplam} · ${p.adim.ad}${calisiyor && p.asama_zaman ? ' · ' + sure(p.asama_zaman) : ''}` : '';
    const suAn = calisiyor && p.su_an && p.su_an.replace(/\.$/, '') !== p.eylem ? p.su_an : '';
    const neYap = p.ne_yap && sira !== 'durdu' ? p.ne_yap : '';
    const f = fikirSon(is), dn = denemeAl(is);
    const fikirYazi = f ? `Fikir${f.ad === 'short' ? '' : ' (' + f.ad + ')'}: ${f.metin}` : '';
    return `<article class="is" data-ajan="is-${esc(is.id)}" data-durum="${esc(is.durum)}" data-hata="${hata ? 1 : 0}">
      <div class="is-ust"><span class="is-ad" title="${esc(yol(is))}">${esc(ad(is))}</span><span class="is-tur">${esc(p.tur)} · ${esc(saat(is.olusturuldu))}'de başladı</span></div>
      <p class="is-eylem">${hata ? '<span class="isaret-hata" aria-label="hata">●</span>' : ''}<span>${esc(p.eylem)}</span></p>
      ${cizgi ? `<div class="adim"><ol class="cizgi" aria-label="Beş adım">${cizgi}</ol><span class="adim-yazi">${esc(adimYazi)}</span></div>` : ''}
      ${suAn ? `<p class="su-an" title="${esc(suAn)}">${esc(suAn)}</p>` : ''}
      ${fikirYazi ? `<p class="su-an" data-ajan="fikir" title="${esc(fikirYazi)}"><b>${esc(fikirYazi.slice(0, fikirYazi.indexOf(':') + 1))}</b>${esc(fikirYazi.slice(fikirYazi.indexOf(':') + 1))}</p>` : ''}
      ${dn ? `<p class="su-an" data-ajan="deneme" title="${esc('Deneme: ' + dn)}"><b>Deneme:</b> ${esc(dn)}</p>` : ''}
      ${p.ne_oldu || neYap ? `<div class="sorun">${p.ne_oldu && p.ne_oldu !== p.eylem ? `<p><b>Ne oldu?</b> ${esc(p.ne_oldu)}</p>` : ''}${neYap ? `<p><b>Ne yap?</b> ${esc(neYap)}</p>` : ''}</div>` : ''}
    </article>`;
  }

  // ---------------------------------------------------------- outputs: every finished video (a Short, or each clip), newest first
  function ciktilar(biten) {
    const L = [];
    for (const is of biten) {
      const p = pd(is);
      if (is.tarz === 'klip') {
        const K = ((is.sonuc && is.sonuc.klipler) || []).slice().sort((a, b) => (b.puan || 0) - (a.puan || 0));
        K.forEach((k, i) => L.push({ is, p, video: k.video, eksik: k.eksik, baslik: k.baslik || k.ad, sure: k.sure, boyut: k.boyut,
          fikir: k.fikir || (is.fikir && is.fikir[k.ad] && is.fikir[k.ad].metin) || '',
          ek: `${K.length > 1 ? `${K.length} klipten ${i + 1}. · ` : ''}kayıtta ${dk(k.bas)}–${dk(k.son)}` }));
      } else if (is.sonuc && is.sonuc.video) {
        L.push({ is, p, video: is.sonuc.video, eksik: is.sonuc.eksik, baslik: is.baslik || p.ad, sure: is.sonuc.sure, boyut: is.sonuc.boyut, ek: '',
          fikir: is.sonuc.fikir || (is.fikir && is.fikir.short && is.fikir.short.metin) || '' });
      }
    }
    return L;
  }
  const oynatici = (c, sinif) => c.eksik
    ? `<div class="yok">Dosya bulunamadı (silinmiş ya da taşınmış).</div>`
    : `<video class="${sinif || ''}" controls playsinline preload="metadata" src="${esc(url(c.is, c.video))}#t=0.6" title="${esc(yol(c.is, c.video))}"></video>`;
  const sureYazi = c => c.sure ? `<span data-sure>${esc(dk(c.sure))}</span>` : '<span data-sure></span>';
  const indir = (c, ek) => c.eksik ? '' : `<a class="indir" href="${esc(url(c.is, c.video))}?indir=1" download title="${esc(yol(c.is, c.video))}" data-ajan="indir">İndir${ek || ''}</a>`;
  function denemeSatir(is) {
    const d = denemeAl(is); if (!d) return '';
    const tepki = defter && defter.denemeler ? defter.denemeler[is.id] : null;
    const t = tepki === 'tuttu' ? 'Beğendin.' : tepki === 'tutmadi' ? 'Tutmadı.' : '';
    return `<p class="deneme" data-ajan="deneme"><b>Deneme:</b> ${esc(d)}${t ? `<span class="yardim">${t}</span>` : ''}</p>`;
  }
  const fikirSatir = c => c.fikir ? `<p class="deneme" data-ajan="fikir"><b>Fikir:</b> ${esc(c.fikir)}</p>` : '';
  const hukumSatir = is => { const h = hukumAl(is); return h ? `<p class="deneme" data-ajan="hukum"><b>Claude'un hükmü:</b> ${esc(h)}</p>` : ''; };
  function sonKart(c) {
    return `<article class="son" data-ajan="cikti-${esc(c.is.id)}">${oynatici(c)}
      <div class="son-bilgi"><h3 class="son-baslik">${esc(c.baslik)}</h3>
        <p class="son-meta">${esc(c.p.tur)} · ${esc(gunSaat(bittiZaman(c.is)))} · ${sureYazi(c)}${c.boyut ? ' · ' + esc(mb(c.boyut)) : ''}${c.ek ? '<br>' + esc(c.ek) : ''}</p>
        ${fikirSatir(c)}
        ${denemeSatir(c.is)}
        ${hukumSatir(c.is)}
        ${indir(c)}</div></article>`;
  }
  const kucukKart = c => `<article class="kucuk" data-ajan="cikti-${esc(c.is.id)}">${oynatici(c)}
      <h3 title="${esc(c.baslik)}">${esc(c.baslik)}</h3>
      <p class="yardim" style="margin:0">${esc(c.p.tur)} · ${esc(gunSaat(bittiZaman(c.is)))} · ${sureYazi(c)}</p>${indir(c)}</article>`;

  // ---------------------------------------------------------- the notebook (read only; the user's own words, no internal codes)
  function defterCiz() {
    const el = $('#defter'), D = defter;
    if (!D) { el.innerHTML = '<p class="bos">Defter okunuyor…</p>'; return; }
    if (D.var === null) { el.innerHTML = '<p class="bos">Defter şu an okunamadı.</p>'; return; }
    if (D.kapali) { el.innerHTML = `<p class="bos" data-ajan="defter-kapali">${esc(kel('defter.kapali'))}</p>`; return; }
    const satir = [];
    const soz = s => `<span class="soz">${esc(s)}</span>`;
    const li = (tur, sol, sag) => satir.push(`<li data-tur="${tur}"><span>${sol}</span><span class="aciklama">${vurgula(sag)}</span></li>`);
    if (D.var) {
      for (const c of D.celiskiler || []) li('celiski', c.taraflar.map(t => soz(t.soz)).join(`<span class="ya-da">${esc(kel('defter.ya_da', 'ya da'))}</span>`), kel('defter.celiski'));
      for (const t of D.tercihler || []) li('tercih', soz(t.soz || t.cevap),
        (t.acik && t.video < D.esik ? kel('defter.tercih_acik') : doldur(kel('defter.tercih'), { n: t.video })) + (t.eski ? ' · ' + kel('defter.eski') : ''));
      const celKonu = new Set((D.celiskiler || []).map(c => c.konu));     // a subject in a contradiction is shown there, not twice
      for (const s of (D.sayilanlar || []).filter(s => s.video > 0 && !celKonu.has(s.konu))) {
        const n = Math.min(s.video, s.esik), kalan = s.esik - n;
        li('sayilan', soz((s.sozler[s.sozler.length - 1] || {}).soz),
          doldur(kel(s.soracak || kalan <= 0 ? 'defter.sayilan_soracak' : kalan === 1 ? 'defter.sayilan_bir' : 'defter.sayilan'), { n, esik: s.esik, kalan }));
      }
      for (const r of (D.tutmayanlar || []).filter(r => r.kapsam !== 'bu-video' && ['ret', 'deney'].includes(r.tur) && !celKonu.has(r.konu)))   // a change request is a wish, not a "no"
        li('tutmadi', soz(r.soz), kel(r.tur === 'deney' ? 'defter.deney' : 'defter.ret') + (r.kez > 1 ? ` · ${r.kez} kez` : ''));
    }
    if (!satir.length) { el.innerHTML = `<p class="bos" data-ajan="defter-bos">${esc(kel('defter.yok'))}</p>`; return; }
    el.innerHTML = `<p class="defter-giris">${esc(kel('defter.giris'))}${D.video ? ` <span class="yardim">Defterde ${D.video} video var.</span>` : ''}</p><ul class="notlar">${satir.join('')}</ul>`;
  }

  // ---------------------------------------------------------- draw
  function ciz() {
    const hepsi = [...isler.values()];
    const adlar = hepsi.filter(is => is.durum !== 'hazir' || siraSende(is)).map(ad); ayni = new Set(adlar.filter((a, i) => adlar.indexOf(a) !== i));
    const aktif = hepsi.filter(is => is.durum !== 'hazir').sort((a, b) => String(b.guncellendi).localeCompare(String(a.guncellendi)));
    const biten = hepsi.filter(is => is.durum === 'hazir').sort((a, b) => String(bittiZaman(b)).localeCompare(String(bittiZaman(a))));

    // the head of Şimdi: one thin line per job the user really has to answer
    const bekleyen = hepsi.filter(siraSende).sort((a, b) => String(b.guncellendi).localeCompare(String(a.guncellendi)));
    const serit = $('#cevapSerit');
    serit.hidden = !bekleyen.length;
    serit.innerHTML = bekleyen.slice(0, 3).map(is => `<p class="sira-sende" data-ajan="sira-sende-${esc(is.id)}">${BALON}<span><b>${esc(kel('sira_sende.baslik', 'Sıra sende'))}</b> · ${esc(ayirtAd(is))} (${esc(pd(is).tur)}): ${esc(doldur(kel('sira_sende.' + siraSende(is)), { soru: soruMetni(is) || '' }))}</span></p>`).join('');

    const ornek = (kel('baslat.ornekler') || []).map(o => `<p class="ornek">${esc(o)}</p>`).join('');
    $('#simdiListe').innerHTML = aktif.length ? `<div class="isler">${aktif.map(isSatir).join('')}</div>`
      : `<div class="baslat" data-ajan="simdi-bos"><p>${esc(kel('baslat.giris', 'Şu an süren iş yok.'))}</p>${ornek}</div>`;

    // outputs: keep playing videos untouched
    const C = ciktilar(biten);
    const oynuyor = [...document.querySelectorAll('#sonCikan video, #ciktiListe video')].some(v => !v.paused);
    const imza = JSON.stringify(biten.map(is => [is.id, is.guncellendi, denemeAl(is), hukumAl(is), is.fikir, is.sonuc && is.sonuc.fikir,
      defter && defter.denemeler && defter.denemeler[is.id]]));
    $('#ustIzgara').dataset.tek = C.length ? '0' : '1';
    $('#ustIzgara').dataset.bos = C.length && !aktif.length ? '1' : '0';
    $('#sonCikanBolum').hidden = !C.length;
    $('#oncekiBolum').hidden = C.length < 2;
    const sc = $('#sonCikan');
    if (!oynuyor && sc.dataset.imza !== imza) {
      sc.dataset.imza = imza;
      sc.innerHTML = C.length ? sonKart(C[0]) : '';
      const eski = C.slice(1), ILK = 8;
      $('#ciktiListe').innerHTML = !eski.length ? '' : `<div class="seri">${eski.slice(0, ILK).map(kucukKart).join('')}</div>` +
        (eski.length > ILK ? `<details class="eski-ciktilar"><summary>Daha eski ${eski.length - ILK} çıktı</summary><div class="seri">${eski.slice(ILK).map(kucukKart).join('')}</div></details>` : '');
      // a Short has no stored duration: read it from the video itself
      document.querySelectorAll('#sonCikan video, #ciktiListe video').forEach(v => v.addEventListener('loadedmetadata', () => {
        const s = v.parentElement.querySelector('[data-sure]'); if (s && !s.textContent && isFinite(v.duration)) s.textContent = dk(Math.round(v.duration));
      }, { once: true }));
    }
  }
  function baglanti(ok) {
    $('#baglanti').className = 'nokta ' + (ok ? 'acik' : 'kopuk');
    $('#baglantiYazi').textContent = ok ? 'Kendiliğinden yenilenir' : 'Panel kapalı: “Paneli-ac.cmd”ye çift tıkla';
  }
  async function hepsiniAl() {
    try { const r = await fetch('/api/isler'); const j = await r.json(); isler.clear(); for (const is of j.isler) isler.set(is.id, is); baglanti(true); ciz(); }
    catch (_) { baglanti(false); }
  }
  let defterSuruyor = false;
  async function defterAl() {
    if (defterSuruyor) return; defterSuruyor = true;
    try { const r = await fetch('/api/defter'); defter = r.ok ? await r.json() : { var: null }; } catch (_) { defter = defter || { var: null }; }
    defterSuruyor = false; defterCiz(); ciz();
  }
  let kurulumEksik = false;
  async function hazirMi() {
    try {
      const r = await fetch('/api/hazir-mi'); const j = await r.json(); if (!r.ok) return;
      const eksik = j.maddeler.filter(m => !m.var && m.sart), el = $('#kurulumSerit');
      kurulumEksik = eksik.length > 0; el.hidden = !kurulumEksik;
      el.innerHTML = !kurulumEksik ? '' : `<div><span class="isaret-hata" aria-label="eksik">●</span><b>${esc(kel('kurulum.eksik'))}</b><details><summary>${esc(kel('kurulum.liste', 'Ne eksik?'))}</summary><ul>${eksik.map(m => `<li>${esc(m.baslik)}</li>`).join('')}</ul></details></div>`;
    } catch (_) {}
  }

  async function basla() {
    try { const r = await fetch('/api/sozluk'); if (r.ok) S = await r.json(); } catch (_) {}
    document.querySelectorAll('[data-bolum]').forEach(h => { h.textContent = kel('bolumler.' + h.dataset.bolum, h.textContent); });
    defterCiz(); await hepsiniAl(); defterAl(); hazirMi();
    let bekle = null;
    try {
      const es = new EventSource('/api/olaylar');
      es.addEventListener('is', e => { const is = JSON.parse(e.data); isler.set(is.id, is); ciz(); clearTimeout(bekle); bekle = setTimeout(defterAl, 1500); });
      es.onopen = () => baglanti(true);
      es.onerror = () => hepsiniAl();
    } catch (_) { setInterval(hepsiniAl, 5000); }
    setInterval(hepsiniAl, 30000);     // safety net + fresh "how long" times
    setInterval(defterAl, 30000);      // the notebook changes from the chat, not through job events
    setInterval(() => { if (kurulumEksik) hazirMi(); }, 60000);   // a missing piece installed from the chat clears the warning
  }
  basla();
})();
