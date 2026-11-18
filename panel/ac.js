#!/usr/bin/env node
// ac.js - opens the panel for a double click (Paneli-ac.cmd). Starts panel/server.js in the background with no
// window (its output goes to panel/panel-cikti.txt), waits until it answers, then opens the page in the browser.
// If the panel already runs, it only opens the page. PANEL_TARAYICI_YOK=1 skips the browser (tests).
// Starts nothing else: never Claude, never a download.
'use strict';
const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

const PANEL = __dirname;
const PORT = +(process.env.PANEL_PORT || 4317);
const ADRES = `http://127.0.0.1:${PORT}/`;

function kim() {
  return new Promise(ok => {
    const r = http.get({ host: '127.0.0.1', port: PORT, path: '/api/kim', timeout: 1500 }, res => {
      let g = ''; res.on('data', c => { g += c; }); res.on('end', () => { try { ok(JSON.parse(g).pid || null); } catch (_) { ok(null); } });
    });
    r.on('timeout', () => r.destroy()); r.on('error', () => ok(null));
  });
}
function tarayici() {
  if (process.env.PANEL_TARAYICI_YOK) { console.log('Panel açık: ' + ADRES + ' (tarayıcı açılmadı: PANEL_TARAYICI_YOK)'); return; }
  const k = process.platform === 'win32' ? ['cmd', ['/c', 'start', '', ADRES]] : process.platform === 'darwin' ? ['open', [ADRES]] : ['xdg-open', [ADRES]];
  spawn(k[0], k[1], { detached: true, stdio: 'ignore', windowsHide: true }).unref();
  console.log('Panel açık: ' + ADRES);
}

(async () => {
  if (await kim()) return tarayici();                       // already running
  const cikti = fs.openSync(path.join(PANEL, 'panel-cikti.txt'), 'a');
  const c = spawn(process.execPath, [path.join(PANEL, 'server.js')], { cwd: path.dirname(PANEL), detached: true, windowsHide: true,
    stdio: ['ignore', cikti, cikti], env: process.env });
  c.unref();
  for (let i = 0; i < 40; i++) {                            // up to ~20 s
    await new Promise(r => setTimeout(r, 500));
    if (await kim()) return tarayici();
  }
  console.log('Panel açılmadı. Ayrıntı: panel\\panel-cikti.txt dosyasının sonunda.');
  process.exitCode = 1;
})();
