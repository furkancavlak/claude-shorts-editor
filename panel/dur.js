#!/usr/bin/env node
// dur.js - stops the panel by the PID it wrote to panel/calisiyor.pid, or to PANEL_PID_DOSYA (never by process name).
//
// calisiyor.pid holds "<pid> <port>" while the panel runs and is emptied when it stops. An empty file, a PID that no
// longer runs, or a PID that is no longer the panel (Windows reuses PIDs) all mean "the panel is not running": the
// file is emptied and nothing is killed. Before killing, the panel is asked over HTTP (/api/kim) which PID it has;
// only a matching answer is stopped. Exit code 0 in every "not running" case.
'use strict';
const fs = require('fs');
const path = require('path');
const http = require('http');
const dosya = process.env.PANEL_PID_DOSYA ? path.resolve(process.env.PANEL_PID_DOSYA) : path.join(__dirname, 'calisiyor.pid');   // same variable as server.js
let ham = '';
try { ham = fs.readFileSync(dosya, 'utf8').trim(); } catch (_) {}
const [pidY, portY] = ham.split(/\s+/);
const bosalt = () => { try { fs.writeFileSync(dosya, ''); } catch (_) {} };
if (!/^\d+$/.test(pidY || '')) { console.log('Panel çalışmıyor (calisiyor.pid boş).'); process.exit(0); }
const pid = +pidY, port = /^\d+$/.test(portY || '') ? +portY : +(process.env.PANEL_PORT || 4317);

function yasiyor(p) { try { process.kill(p, 0); return true; } catch (e) { return e.code === 'EPERM'; } }
if (!yasiyor(pid)) { bosalt(); console.log(`Panel çalışmıyor (PID ${pid} kapanmış; kayıt temizlendi).`); process.exit(0); }

const r = http.get({ host: '127.0.0.1', port, path: '/api/kim', timeout: 2000 }, res => {
  let g = ''; res.on('data', c => { g += c; });
  res.on('end', () => {
    let kim = null; try { kim = JSON.parse(g).pid; } catch (_) {}
    if (kim !== pid) { bosalt(); console.log(`Panel çalışmıyor (PID ${pid} artık panel değil; ona dokunulmadı, kayıt temizlendi).`); return; }
    try { process.kill(pid); bosalt(); console.log('Panel durduruldu (PID ' + pid + ').'); }
    catch (e) { console.error('Durdurulamadı: ' + e.message); process.exitCode = 1; }
  });
});
r.on('timeout', () => r.destroy(new Error('cevap yok')));
r.on('error', () => { bosalt(); console.log(`Panel çalışmıyor (PID ${pid} panel gibi cevap vermedi; ona dokunulmadı, kayıt temizlendi).`); });
