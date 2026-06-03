@echo off
:: Registers Gmail Dashboard to start silently at Windows login (no window popup)
:: Must be run as Administrator

set TASK_NAME=GmailDashboard
set VBS_PATH=%~dp0run_server.vbs

:: Add hosts entry if missing
findstr /C:"gmail.local" "C:\Windows\System32\drivers\etc\hosts" >nul 2>&1
if errorlevel 1 (
    echo 127.0.0.1 gmail.local >> "C:\Windows\System32\drivers\etc\hosts"
)

:: Add gmail.local to Windows proxy bypass list so corporate proxy doesn't intercept it
for /f "tokens=2*" %%a in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride 2^>nul') do set BYPASS=%%b
echo %BYPASS% | findstr /C:"gmail.local" >nul 2>&1
if errorlevel 1 (
    if "%BYPASS%"=="" (
        reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride /t REG_SZ /d "gmail.local;<local>" /f >nul 2>&1
    ) else (
        reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride /t REG_SZ /d "%BYPASS%;gmail.local" /f >nul 2>&1
    )
)

:: Port proxy: forward port 80 → 5000 (persists until reboot, no per-run admin needed)
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=127.0.0.1 >nul 2>&1
netsh interface portproxy add v4tov4 listenport=80 listenaddress=127.0.0.1 connectport=5000 connectaddress=127.0.0.1 >nul 2>&1

:: Kill any stale Python dashboard processes
taskkill /f /im python.exe >nul 2>&1
timeout /t 1 >nul

:: Remove existing task if present
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Create task: run silently at login with admin rights, no window
schtasks /create /tn "%TASK_NAME%" ^
  /tr "wscript.exe \"%VBS_PATH%\"" ^
  /sc onlogon ^
  /rl highest ^
  /f >nul 2>&1

echo.
echo  Done! Gmail Dashboard will start silently at every login.
echo  No window will pop up - just open http://gmail.local
echo.
echo  Starting server now...
wscript.exe "%VBS_PATH%"
timeout /t 3 >nul
echo  Server started. Open http://gmail.local
echo  (If gmail.local still fails, try http://127.0.0.1:5000)
echo.
pause
