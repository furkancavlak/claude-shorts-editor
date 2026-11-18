@echo off
rem Short Motoru panelini kapatir (yalniz panelin kendi kaydettigi PID'i durdurur).
chcp 65001 >nul
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js bu bilgisayarda yok; panel de calisiyor olamaz.
  pause
  exit /b 0
)
node "panel\dur.js"
timeout /t 3 >nul
