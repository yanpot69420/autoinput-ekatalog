@echo off
rem Pintasan untuk Windows. Klik dua kali berkas ini, atau klik kanan ->
rem "Send to" -> "Desktop (create shortcut)" supaya ada di Desktop.
rem
rem Memakai pythonw.exe, bukan python.exe, supaya jendela hitam Command Prompt
rem tidak ikut muncul di belakang aplikasi.
rem
rem Path-nya relatif terhadap letak berkas ini, jadi folder proyek boleh
rem dipindah ke mana pun tanpa perlu mengubah apa-apa.

setlocal
set "PROYEK=%~dp0.."
set "PYW=%PROYEK%\.venv\Scripts\pythonw.exe"

if not exist "%PYW%" (
  echo Lingkungan Python belum disiapkan.
  echo.
  echo Jalankan sekali dari folder proyek:
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -e . playwright
  echo.
  pause
  exit /b 1
)

cd /d "%PROYEK%"
start "" "%PYW%" -m inaproc_autoinput.app
endlocal
