@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if errorlevel 1 (
    echo.
    echo HandWheel could not start. Run "Install HandWheel.bat" first.
    pause
    exit /b 1
)
