"""Keeps dashboard.py running forever. Logs crashes to watchdog.log."""
import subprocess, sys, time, os
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).parent
LOG  = HERE / "watchdog.log"

def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

# Portproxy setup (runs as admin via scheduled task)
os.system("netsh interface portproxy delete v4tov4 listenport=80 listenaddress=127.0.0.1 >nul 2>&1")
os.system("netsh interface portproxy add v4tov4 listenport=80 listenaddress=127.0.0.1 connectport=5000 connectaddress=127.0.0.1 >nul 2>&1")

log("Watchdog started")

while True:
    try:
        log("Starting dashboard.py")
        result = subprocess.run(
            [sys.executable, str(HERE / "dashboard.py")],
            cwd=str(HERE)
        )
        log(f"dashboard.py exited with code {result.returncode}")
    except Exception as e:
        log(f"Exception launching dashboard.py: {e}")
    time.sleep(2)
