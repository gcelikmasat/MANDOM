@echo off
REM Launch Mandom as a native desktop window (no browser tab).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo No virtual environment found. Set it up once with:
  echo     py -3.13 -m venv .venv
  echo     .venv\Scripts\activate
  echo     pip install -e ".[web,desktop]"
  pause
  exit /b 1
)

".venv\Scripts\pythonw.exe" desktop.py
