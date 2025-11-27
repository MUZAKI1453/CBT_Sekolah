@echo off
REM -----------------------------------------
REM Masuk ke folder project
cd /d D:\CBT_Sekolah\CBT_Sekolah

REM Aktifkan virtual environment
call D:\CBT_Sekolah\.venv\Scripts\activate.bat

REM Jalankan Flask via Waitress di background
start "FlaskApp" cmd /k D:\CBT_Sekolah\.venv\Scripts\python.exe app.py

REM Jalankan Cloudflare Tunnel di background
start "CloudflareTunnel" cmd /k cloudflared tunnel run mytunnel

echo Flask + Cloudflare Tunnel running in production...
pause
