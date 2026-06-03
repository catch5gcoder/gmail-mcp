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
echo  Running it now for this session...
wscript.exe "%VBS_PATH%"
echo  Server started. Open http://gmail.local
echo.
pause
