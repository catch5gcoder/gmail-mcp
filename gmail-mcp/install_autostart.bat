@echo off
:: Registers Gmail Dashboard to start automatically at Windows login
:: Must be run as Administrator (launch_gmail.vbs handles this)

set TASK_NAME=GmailDashboard
set BAT_PATH=%~dp0start_gmail.bat

:: Remove existing task if present
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Create task: run at login, with highest privileges, hidden window
schtasks /create /tn "%TASK_NAME%" ^
  /tr "cmd.exe /c \"%BAT_PATH%\"" ^
  /sc onlogon ^
  /rl highest ^
  /f >nul 2>&1

echo.
echo  Gmail Dashboard will now start automatically at login.
echo  To start it now without rebooting, double-click launch_gmail.vbs
echo.
pause
