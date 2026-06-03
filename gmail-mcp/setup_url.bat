@echo off
findstr /C:"emailbox.local" "C:\Windows\System32\drivers\etc\hosts" >nul 2>&1
if errorlevel 1 (
    echo 127.0.0.1 emailbox.local >> "C:\Windows\System32\drivers\etc\hosts"
)
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=127.0.0.1 >nul 2>&1
netsh interface portproxy add v4tov4 listenport=80 listenaddress=127.0.0.1 connectport=5000 connectaddress=127.0.0.1
