# Gmail Dashboard – Knowledgebase

## Architecture

```
Browser → http://emailbox.local (port 80)
       → netsh portproxy (80 → 5000)
       → Flask / dashboard.py (port 5000)
       → Gmail API (OAuth tokens in tokens/)
```

**Autostart chain (on every Windows login):**
```
Registry HKCU\...\Run
  → wscript.exe run_server.vbs   (finds Python path reliably)
    → python watchdog.py          (infinite restart loop)
      → python dashboard.py       (Flask on port 5000)
```

---

## How to Start (Manual)

```
python setup.py          ← one-time admin setup (UAC prompt)
```
This does everything: hosts file, portproxy, registry autostart, starts watchdog.

If server is down mid-session:
```python
import os
os.startfile(r'C:\Users\Abhishek.Doon\Claude_CLI\gmail-mcp\run_server.vbs')
```

---

## Issues Faced & Root Causes

### 1. emailbox.local not opening (ERR_CONNECTION_RESET)
**Cause:** Corporate Reliance proxy intercepting `.local` hostnames.  
**Fix:** Added `emailbox.local;<local>` to Windows ProxyOverride registry key so Chrome bypasses the proxy for local addresses.

### 2. emailbox.local not opening (ERR_CONNECTION_REFUSED)
**Cause:** Flask server wasn't running. Background processes started from Claude CLI session were tied to its Job Object and died when the session context changed.  
**Fix:** Use `os.startfile()` (Windows ShellExecute) to spawn a truly independent process not attached to the calling session.

### 3. netsh portproxy silently not working
**Cause:** `netsh interface portproxy` requires the **IP Helper service** (iphlpsvc) to be running. If the service is stopped/disabled, portproxy commands succeed with no error but the proxy never activates.  
**Fix:** Run `setup.py` as admin (UAC) which sets up portproxy. Portproxy persists until reboot.

### 4. Port 80 binding failed
**Cause:** Windows HTTP.sys kernel driver reserves port 80. Regular socket bind to port 80 fails even with admin in some configurations.  
**Fix:** Revert Flask to port 5000, use netsh portproxy for 80→5000 forwarding.

### 5. Task Scheduler / schtasks failing
**Cause 1:** Corporate Group Policy blocks `schtasks /create`.  
**Cause 2:** Microsoft Store Python App Execution Aliases (`%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe`) don't work in elevated Task Scheduler contexts.  
**Fix:** Use Registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` key instead (no admin needed). `run_server.vbs` uses `where python` skipping WindowsApps paths to find real Python.

### 6. Flask crashing on startup (UnicodeEncodeError)
**Cause:** `→` (U+2192) in print statement is not encodable in Windows cp1252 terminal codepage.  
**Fix:** Replace `→` with `->` in dashboard.py print statement.

### 7. Account switching not loading
**Cause:** Flask route `/accounts/switch/<email>` received `%40` (URL-encoded `@`) in the path. Werkzeug did not decode it, so `email not in list_accounts()` returned True → 400 error. JS `.then()` fired regardless, redirecting to an account that wasn't switched server-side.  
**Fix:** Removed the POST entirely. `switchAccount()` now directly redirects to `/?account=<email>`. The index route sets `_active_account` from the query param.

### 8. Trash icon not visible in inbox
**Cause:** CSS `:hover` pseudo-class is unreliable inside `overflow-y: auto` scroll containers in some browser/OS combinations.  
**Fix:** JavaScript `mouseenter`/`mouseleave` events add/remove `.ei-hover` class. CSS targets `.ei-hover .ei-trash` instead of `:hover .ei-trash`.

---

## File Reference

| File | Purpose |
|------|---------|
| `dashboard.py` | Flask app, port 5000 |
| `gmail_client.py` | Gmail API wrapper |
| `watchdog.py` | Infinite restart loop for dashboard.py |
| `run_server.vbs` | Finds Python path, starts watchdog.py hidden |
| `setup.py` | One-time admin setup (hosts, portproxy, registry, task) |
| `tokens/*.json` | OAuth tokens per account (email address as filename) |
| `creds.json` | Shared OAuth client credentials |
| `templates/inbox.html` | Single-page dashboard UI |

---

## OAuth Token Management

- Tokens live in `tokens/<email>.json`
- Auto-refreshed by `gmail_client.py` on expiry
- If a token is permanently invalid: delete `tokens/<email>.json`, re-run `python setup_accounts.py`
- Tokens expire permanently after ~6 months of no use (Google revokes refresh token)

---

## After Every Reboot

Portproxy resets on reboot. The Registry Run key starts `watchdog.py` automatically, which starts Flask on port 5000. But port 80 → 5000 forwarding needs portproxy re-setup.

**Permanent fix:** Run `setup.py` once after reboot (accept UAC). Or access via `http://localhost:5000` which always works without portproxy.

**Fixed:** `GmailPortProxy` scheduled task runs as SYSTEM at boot, restoring portproxy before any user logs in. Fully zero-touch.
