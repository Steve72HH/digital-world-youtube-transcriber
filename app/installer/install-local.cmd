@echo off
setlocal

set "APP_NAME=Digital World YouTube Transcriber"
set "TARGET=%LOCALAPPDATA%\Programs\Digital World YouTube Transcriber"
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Digital World YouTube Transcriber"

echo Installiere %APP_NAME% nach:
echo %TARGET%

if not exist "%TARGET%" mkdir "%TARGET%"
if not exist "%TARGET%\tools" mkdir "%TARGET%\tools"
if not exist "%STARTMENU%" mkdir "%STARTMENU%"

copy /y "Digital-World-YouTube-Transcriber.exe" "%TARGET%\" >nul
copy /y "requirements-runtime.txt" "%TARGET%\" >nul
copy /y "install-dependencies.ps1" "%TARGET%\tools\" >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $shortcut = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Digital World YouTube Transcriber.lnk'); $shortcut.TargetPath = '%TARGET%\Digital-World-YouTube-Transcriber.exe'; $shortcut.WorkingDirectory = '%TARGET%'; $shortcut.Save(); $menu = $ws.CreateShortcut('%STARTMENU%\Digital World YouTube Transcriber.lnk'); $menu.TargetPath = '%TARGET%\Digital-World-YouTube-Transcriber.exe'; $menu.WorkingDirectory = '%TARGET%'; $menu.Save()"

echo.
echo Installiere/aktualisiere yt-dlp, OpenAI Whisper und FFmpeg, falls moeglich...
powershell -NoProfile -ExecutionPolicy Bypass -File "%TARGET%\tools\install-dependencies.ps1"

echo.
echo Installation abgeschlossen.
start "" "%TARGET%\Digital-World-YouTube-Transcriber.exe"
