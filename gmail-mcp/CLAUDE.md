# Gmail Dashboard – CLAUDE.md

## What This Project Is
A personal Gmail web dashboard running at `http://emailbox.local`.
Multi-account, real-time SSE push, trash/restore, compose — all via Gmail API.
No cloud hosting. Runs entirely on the user's Windows laptop.

## Current Architecture

```
Browser → http://emailbox.local
        → netsh portproxy (port 80 → 5000)
        → Flask dashboard.py (127.0.0.1:5000)
        → Gmail API (OAuth tokens in tokens/)
```

**Persistence stack:**
```
Windows Service "GmailDashboard"  ← managed by SCM, starts at boot
  → python.exe dashboard.py       ← path read from python_path.txt
  → restarts Flask on crash       ← 2-second loop in service.py

Windows Service "GmailPortProxy"  ← SYSTEM account, runs at boot
  → netsh portproxy 80→5000       ← restored before user logs in
```

## Key Files

| File | Purpose |
|------|---------|
| `dashboard.py` | Flask app, port 5000 |
| `gmail_client.py` | Gmail API wrapper, OAuth, token refresh |
| `service.py` | Windows Service — keeps Flask running via SCM |
| `setup.py` | One-time admin installer (UAC) — run once to set everything up |
| `watchdog.py` | Legacy loop (kept for manual use; service is primary now) |
| `run_server.vbs` | Finds real python.exe, starts watchdog hidden |
| `python_path.txt` | Stores real python.exe path (written by setup.py, read by service.py) |
| `templates/inbox.html` | Entire frontend — single HTML file |
| `tokens/*.json` | OAuth tokens, one file per account, named `<email>.json` |
| `creds.json` | Shared OAuth client credentials from Google Cloud Console |
| `KNOWLEDGEBASE.md` | Full issue log and root cause analysis |

## Critical Known Issues (Read Before Changing Anything)

### 1. sys.executable in Windows Service = pythonservice.exe, NOT python.exe
`sys.executable` inside a pywin32 service returns the pywin32 host binary.
Always use `python_path.txt` to get the real Python path. Never use `sys.executable` in service.py.

### 2. Corporate proxy intercepts .local hostnames
Reliance corporate proxy resets connections to `emailbox.local`.
Fix is in registry: `HKCU\...\Internet Settings\ProxyOverride` = `emailbox.local;<local>`.
setup.py sets this. If it breaks again, re-run setup.py.

### 3. netsh portproxy needs IP Helper service
`netsh interface portproxy` silently does nothing if the IP Helper service (iphlpsvc) is stopped.
The GmailPortProxy Windows Service handles this at boot as SYSTEM.

### 4. Multiple launchers = port 5000 conflict
If both the Windows Service AND any other launcher (watchdog, run_server.vbs) start Flask simultaneously, they fight for port 5000 and crash each other.
Only the Windows Service should manage Flask. Do not start dashboard.py manually if the service is running.

### 5. CSS :hover unreliable in scroll containers
The inbox email list uses `overflow-y: auto`. CSS `:hover` on `.email-item` doesn't reliably trigger inside scroll containers.
Fix: JS `mouseenter`/`mouseleave` adds `.ei-hover` class. CSS targets `.email-item.ei-hover .ei-trash`.

### 6. Account switching — never use URL path for email
`/accounts/switch/<email>` fails because Werkzeug doesn't decode `%40` → `@` in URL path segments.
Account switching is done by direct redirect to `/?account=<email>` (query param). The index route sets `_active_account`. No POST involved.

### 7. Windows cp1252 terminal encoding
Avoid non-ASCII characters (→ ✓ etc.) in any print() statements in dashboard.py or watchdog.py.
They crash on Windows terminals using cp1252 codepage. Use ASCII only (`->`, `OK`, etc.).

## Setup / Recovery Commands

**Full reinstall (run once, needs UAC):**
```
python setup.py
```
Does: hosts file, portproxy, proxy bypass registry, installs Windows Service, starts it.

**Check service status:**
```
sc query GmailDashboard
sc query GmailPortProxy
```

**Restart service manually:**
```
sc stop GmailDashboard && sc start GmailDashboard
```

**If OAuth token broken for an account:**
```
del tokens\<email>.json
python setup_accounts.py
```

**Verify everything is working:**
```python
import socket
for p in [80, 5000]:
    s=socket.socket(); s.settimeout(1)
    print(p, 'UP' if s.connect_ex(('127.0.0.1',p))==0 else 'DOWN'); s.close()
```

## Environment
- Windows 11 Enterprise, corporate machine (Reliance / RIL)
- Python 3.13 at `C:\Users\Abhishek.Doon\AppData\Local\Programs\Python\Python313\`
- Corporate proxy active — all `.local` domains must be in ProxyOverride
- Group Policy blocks `schtasks /create` — use Windows Services or Registry Run key instead
- PowerShell is broken on this machine — use Bash or cmd
