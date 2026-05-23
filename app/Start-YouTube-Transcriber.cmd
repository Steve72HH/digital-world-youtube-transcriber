@echo off
setlocal
cd /d "%~dp0"
where pyw.exe >nul 2>nul
if %errorlevel%==0 (
    start "" pyw.exe "%~dp0youtube_transcriber.pyw"
    exit /b
)

where pythonw.exe >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw.exe "%~dp0youtube_transcriber.pyw"
    exit /b
)

python "%~dp0youtube_transcriber.pyw"
