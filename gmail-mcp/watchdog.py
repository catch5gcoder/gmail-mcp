"""Keeps dashboard.py running forever. Auto-restarts on crash."""
import subprocess, sys, time, os
from pathlib import Path

HERE = Path(__file__).parent

# Portproxy setup (runs as admin via scheduled task — survives reboots)
os.system("netsh interface portproxy delete v4tov4 listenport=80 listenaddress=127.0.0.1 >nul 2>&1")
os.system("netsh interface portproxy add v4tov4 listenport=80 listenaddress=127.0.0.1 connectport=5000 connectaddress=127.0.0.1 >nul 2>&1")

while True:
    try:
        subprocess.run([sys.executable, str(HERE / "dashboard.py")], cwd=str(HERE))
    except Exception:
        pass
    time.sleep(2)  # brief pause before restart
