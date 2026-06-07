@echo off
REM Build a click-and-go Mandom.exe (no Python needed by the end user).
REM Output: dist\Mandom\Mandom.exe  (zip the dist\Mandom folder to share it)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Set up the venv first (see README).
  pause
  exit /b 1
)

echo Installing build deps...
".venv\Scripts\python.exe" -m pip install -e ".[web,desktop]" pyinstaller --quiet

echo Generating icon...
".venv\Scripts\python.exe" -c "from PIL import Image; Image.open('app/web/static/icon-512.png').save('mandom.ico', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"

echo Building...
".venv\Scripts\pyinstaller.exe" --noconfirm --windowed --name Mandom --icon mandom.ico ^
  --add-data "app/web/templates;app/web/templates" ^
  --add-data "app/web/static;app/web/static" ^
  --collect-all webview ^
  desktop.py

echo.
echo Done -^> dist\Mandom\Mandom.exe
pause
