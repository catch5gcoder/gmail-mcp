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

# 4. Kill stale server
run("taskkill /f /im python.exe")
time.sleep(1)

# 5a. SYSTEM startup task — restores portproxy at every boot (runs before login, no UAC ever)
run('schtasks /delete /tn "GmailPortProxy" /f')
run('schtasks /create /tn "GmailPortProxy" '
    '/tr "netsh interface portproxy add v4tov4 listenport=80 listenaddress=127.0.0.1 connectport=5000 connectaddress=127.0.0.1" '
    '/sc onstart /ru SYSTEM /f')

# 5b. User login task — starts watchdog (Flask)
vbs = str(HERE / "run_server.vbs")
run(f'schtasks /delete /tn "GmailDashboard" /f')
run(f'schtasks /create /tn "GmailDashboard" /tr "wscript.exe \\"{vbs}\\"" /sc onlogon /rl highest /f')

# 6. Start server now
subprocess.Popen([sys.executable, str(HERE / "watchdog.py")], cwd=str(HERE),
                 creationflags=subprocess.CREATE_NO_WINDOW)

print("Done. Open http://emailbox.local")
input("Press Enter to close...")
