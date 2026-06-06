@echo off
REM One-click launcher for Mandom (Windows).
REM Double-click this file to start the app and open it in your browser.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo No virtual environment found. Create it once with:
  echo     py -3.13 -m venv .venv
  echo     .venv\Scripts\activate
  echo     pip install -e ".[web]"
  pause
  exit /b 1
)

".venv\Scripts\python.exe" run.py %*
pause
