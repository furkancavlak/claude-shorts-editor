@echo off
rem Short Motoru paneli: cift tikla, panel arka planda acilir ve tarayicida gorunur. Kapatmak icin Paneli-kapat.cmd.
chcp 65001 >nul
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo Node.js bu bilgisayarda yok, panel acilamadi.
  echo Ne yap: nodejs.org adresinden Node.js'i kur ^(LTS surumu^), sonra bu dosyaya yeniden cift tikla.
  echo.
  pause
  exit /b 1
)
node "panel\ac.js"
if errorlevel 1 (
  echo.
  pause
  exit /b 1
)
