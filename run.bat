@echo off
setlocal
title BCM Emir Todo - Server Lokal

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Virtual environment belum tersedia. Ikuti langkah instalasi di README.md.
    pause
    exit /b 1
)

if not exist "%~dp0.env" (
    echo File .env belum tersedia. Salin .env.example menjadi .env dan isi konfigurasi database.
    pause
    exit /b 1
)

set "ENV_FILE=%~dp0.env"
echo Pastikan MySQL XAMPP sudah aktif.
echo Buka http://127.0.0.1:5000 setelah server berjalan.
echo Tekan Ctrl+C untuk menghentikan aplikasi.
echo.
"%~dp0.venv\Scripts\python.exe" "%~dp0app.py"
if errorlevel 1 (
    echo.
    echo Aplikasi berhenti dengan kendala. Periksa pesan di atas.
    pause
    exit /b 1
)
endlocal
