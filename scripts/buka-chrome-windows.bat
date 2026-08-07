@echo off
REM Pembuka Chrome portal yang berdiri sendiri, terpisah dari jendela aplikasi.
REM Buka sekali, login, lalu biarkan terbuka. Aplikasi cukup "Uji koneksi".
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m inaproc_autoinput.buka_chrome
if errorlevel 1 pause
