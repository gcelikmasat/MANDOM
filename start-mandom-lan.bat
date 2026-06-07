@echo off
REM Launch Mandom reachable from other devices on your Wi-Fi (phone, etc.).
REM Find your PC's IPv4 with `ipconfig`, then open http://<that-ip>:8000 on the phone.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Set up the venv first (see README).
  pause
  exit /b 1
)

echo Your LAN addresses:
ipconfig | findstr /C:"IPv4"
echo Open  http://^<one-of-the-IPs-above^>:8000  on your phone.
echo.

".venv\Scripts\python.exe" run.py --host 0.0.0.0 --no-browser
pause
