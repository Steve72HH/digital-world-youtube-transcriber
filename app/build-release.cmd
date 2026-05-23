@echo off
setlocal
cd /d "%~dp0"
set VERSION=1.1.1
set APP_EXE=Digital-World-YouTube-Transcriber.exe
set RELEASE_DIR=%~dp0release\Digital-World-YouTube-Transcriber-%VERSION%

python build_exe.py
python -m PyInstaller --noconfirm --windowed --onefile --name "Digital-World-YouTube-Transcriber" --icon "%~dp0assets\logo.ico" --add-data "%~dp0assets;assets" "%~dp0youtube_transcriber.pyw"

if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%\installer"
mkdir "%RELEASE_DIR%\tools"

copy /y "%~dp0dist\%APP_EXE%" "%RELEASE_DIR%\%APP_EXE%" >nul
copy /y "%~dp0..\README.md" "%RELEASE_DIR%\README.md" >nul
copy /y "%~dp0installer\install-dependencies.ps1" "%RELEASE_DIR%\tools\install-dependencies.ps1" >nul
copy /y "%~dp0requirements-runtime.txt" "%RELEASE_DIR%\requirements-runtime.txt" >nul
copy /y "%~dp0installer\Digital-World-YouTube-Transcriber.iss" "%RELEASE_DIR%\installer\Digital-World-YouTube-Transcriber.iss" >nul
copy /y "%~dp0installer\install-local.cmd" "%RELEASE_DIR%\installer\install-local.cmd" >nul
copy /y "%~dp0installer\build-iexpress-installer.ps1" "%RELEASE_DIR%\installer\build-iexpress-installer.ps1" >nul

if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "%~dp0installer\Digital-World-YouTube-Transcriber.iss"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    "C:\Program Files\Inno Setup 6\ISCC.exe" "%~dp0installer\Digital-World-YouTube-Transcriber.iss"
) else (
    echo Inno Setup 6 wurde nicht gefunden. Erstelle einfachen IExpress-Installer...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\build-iexpress-installer.ps1"
)

if exist "%~dp0dist\Digital-World-YouTube-Transcriber-Installer-%VERSION%.exe" (
    copy /y "%~dp0dist\Digital-World-YouTube-Transcriber-Installer-%VERSION%.exe" "%RELEASE_DIR%\Digital-World-YouTube-Transcriber-Installer-%VERSION%.exe" >nul
)

echo Release fertig:
echo %RELEASE_DIR%
