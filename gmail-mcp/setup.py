"""One-time setup: elevates itself, fixes hosts, portproxy, task scheduler, starts server."""
import ctypes, sys, os, subprocess, time
from pathlib import Path

HERE = Path(__file__).parent

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def elevate():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{__file__}"', str(HERE), 1)
    sys.exit(0)

def run(cmd):
    subprocess.run(cmd, shell=True, capture_output=True)

if not is_admin():
    elevate()

# --- running as admin from here ---

# 1. Hosts file
hosts = Path(r"C:\Windows\System32\drivers\etc\hosts")
txt = hosts.read_text()
lines = [l for l in txt.splitlines() if "gmail.local" not in l and "emailbox.local" not in l]
lines.append("127.0.0.1 emailbox.local")
hosts.write_text("\n".join(lines) + "\n")

# 2. Port proxy 80 → 5000
run("netsh interface portproxy delete v4tov4 listenport=80 listenaddress=127.0.0.1")
run("netsh interface portproxy add v4tov4 listenport=80 listenaddress=127.0.0.1 connectport=5000 connectaddress=127.0.0.1")

# 3. Proxy bypass
run('reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyOverride /t REG_SZ /d "emailbox.local;<local>" /f')

# 4. Store real python.exe path for the service (sys.executable = python.exe here)
(HERE / "python_path.txt").write_text(sys.executable)

# 4b. Install Windows Service (replaces watchdog + scheduled tasks)
run(f'"{sys.executable}" "{HERE / "service.py"}" stop')
run(f'"{sys.executable}" "{HERE / "service.py"}" remove')
time.sleep(1)
run(f'"{sys.executable}" "{HERE / "service.py"}" --startup auto install')
# Restart on failure: 3 attempts, 5-second delay each
run('sc failure GmailDashboard reset= 86400 actions= restart/5000/restart/5000/restart/5000')
run('sc start GmailDashboard')

print("Done. Open http://emailbox.local")
input("Press Enter to close...")
