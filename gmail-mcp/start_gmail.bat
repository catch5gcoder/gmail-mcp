@echo off
title Gmail Dashboard
cd /d "%~dp0"

:: Add hosts entry if missing
findstr /C:"gmail.local" "C:\Windows\System32\drivers\etc\hosts" >nul 2>&1
if errorlevel 1 (
    echo 127.0.0.1 gmail.local >> "C:\Windows\System32\drivers\etc\hosts"
)

echo.
echo  Starting Gmail Dashboard...
echo  Open http://gmail.local in your browser
echo  Press Ctrl+C to stop
echo.

python dashboard.py
pause
