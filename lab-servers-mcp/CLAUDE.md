# UPF 5G Lab Dashboard — CLAUDE.md

## Project
Flask dashboard for Jio UPF 5G lab operations (R1/R8/R13/R14 clusters).  
**Owner:** Abhishek Doon — abhishek.doon@ril.com — Reliance/Jio  
**URL:** http://lt0198625/UPF5GLab  
**Repo:** `C:\Users\Abhishek.Doon\Claude_CLI\lab-servers-mcp\`  
**Full topology/state KB:** `knowledge.md` in this folder — read it before any SSH or code change.

---

## Hard Rules (NEVER violate)

1. **No PowerShell** — it is broken on this machine. Always use Bash tool or `python` / `cmd`.
2. **Always `sudo`** on R1/R8/R13/R14 servers — the `upf` user lacks direct permissions.
3. **`triggerSrr:false`** in every deleteStaleSessions payload — omitting it returns INVALID_JSON.
4. **Ask before touching anything that's working.** "dare you screw what's already working. ASK ALWAYS in case of doubt."
5. **Minimum tokens** — batch parallel tool calls, no re-reads, no verbose summaries, skip confirmations unless failure.
6. **No mocking** — integration tests/SSH checks must hit real servers.

---

## How to Run / Restart

```bat
python app.py          # or double-click start.bat
```

**Flask** runs on port 80, `threaded=True`, LAN IP `10.51.138.14`.  
**Task Scheduler:** `UPF5GLab_Dashboard` auto-starts on logon.  
After ANY template edit you MUST restart Flask (Jinja caches compiled templates):

```bash
# Bash tool — find and kill all PIDs on port 80 first:
netstat -ano | findstr "0.0.0.0:80.*LISTENING"
# then:
taskkill //F //PID <pid>    # dangerouslyDisableSandbox: true
# Two processes often run simultaneously — kill ALL of them.
```

---

## Architecture

```
app.py                  # Flask app — single file, all routes + logic
server_checker.py       # SSH health check helper
templates/
  servers.html          # Home page — cluster status pills
  upf_ops.html          # UPF Ops page — run commands, view configs
dp_state_cache.json     # DP VIP→instance map (R1) + cluster HA state (R8/R13/R14)
knowledge.md            # Full topology, state snapshots, known issues
```

### Key Routes
| Route | Purpose | Speed |
|-------|---------|-------|
| `GET /UPF5GLab/full-status` | Fresh SSH check ALL 4 rings (semaphore 8) | ~30s, every 5 min |
| `GET /UPF5GLab/cluster-status` | R1 HA detail — UCM/Proxy + per-VPP-instance state | dynamic |
| `GET /UPF5GLab/cluster-quick/<ring>` | Fast HA for R8/R13/R14 from cache + fresh proxy VIPs | ≤2s |
| `GET /UPF5GLab/cluster-ha/<ring>` | Full SSH rebuild for R8/R13/R14 — updates cache | ~30-60s |
| `POST /upf/api/run` | Execute UPF Ops command |  |
| `POST /upf/api/all-rings-dp-run` | Run DP command across ALL 88 VPP instances |  |

### Home Page Refresh Logic
- **Server online/offline** (`full-status`): every 5 minutes
- **HA pills** (`cluster-status` + `cluster-quick`): every **5 seconds** via `setInterval(refreshHaStatus, 5000)`
- Last HA fetch time shown per ring in panel subtitle

---

## SSH / Connectivity
- **Jump server:** `10.63.92.34` — user `abhishek.doon` — SSH key auth
- **Pattern:** `paramiko.SSHClient` → jump → `open_channel("direct-tcpip", (target_ipv6, 22), ...)`
- **Max concurrent SSH:** 8 (Semaphore in ThreadPoolExecutor)
- **All server IPs are IPv6.** Always wrap in `[...]` for curl.
- Transient SSH failures (exit 255) are normal — retry once before escalating.

---

## R1 VIP→Instance Map (Fully Automatic)

`cluster_status_api()` builds `vip_map` dynamically:
1. **Fast path:** reads `dp_state_cache.json["R1"]["vip_map"]`
2. **Auto-rebuild:** if any proxy VIP is missing from cache → SSH all 4 DP servers, `show interface address` on `upf-dp-1` (port 5000) + `upf-dp-2` (port 5001), rebuild, save
3. **Filter:** only VIPs in proxy Active/Standby/OOS lists kept — management IPs ignored via `if vl not in _known_vips: continue`
4. **Priority:** `Active(3) > Standby(2) > OOS(1)` — never downgraded

VPP binary path (R1):  
`/opt/upf/vpp_stable_2210/build-root/install-vpp-native/vpp/bin/vppctl`  
LD path (R1):  
`/opt/upf/vpp_stable_2210/build-root/install-vpp-native/vpp/lib64:/opt/vpp/external/x86_64/lib/`

---

## OOS Detection
- **R1:** VIP in proxy output → look up vip_map → if not in Active or Standby → OOS. OOS clusters emit no VIP in proxy output — identified by absence.
- **R8/R13/R14 (`_check_dp`):** VPP has IPs but none match proxy lists → OOS. No IPs at all → Unknown.
- **Pill colours:** Active = green, Standby = amber, OOS = red.

---

## DP Cache
`dp_state_cache.json` holds:
- `["R1"]["vip_map"]` — VIP → [alias, instance] map, built by `_build_r1_vip_map()`
- `["R8/R13/R14"]["dp_detail"]` — per-container state, built by `cluster-ha`
- Delete this file to force full rebuild for all rings (safe — auto-rebuilt on next request).

---

## Cluster Topology Quick Reference

| Ring | CPs | DPs | VPP instances/server | Total VPPs |
|------|-----|-----|---------------------|------------|
| R1 | CP1, CP2 | DP1-4 | 2 (ports 5000/5001) | 8 |
| R8 | CP1, CP2 | DP1-5 | 4 (ports 5000-5003) | 20 |
| R13 | CP1-4 | DP1-5 | 6 containers × port 5000 | 30 |
| R14 | CP1-4 | DP1-5 | 6 containers × port 5000 | 30 |

**R1 CP VIP** (`143a:0018:0:3:3`) — NOT in CLUSTERS dict, NOT SSH-checked, it's a VIP only.  
**R8-DP5** — excluded from monitoring (has extra dev containers).  
**R14-CP4** — missing `pfcpproxy_cl6`/`upfcm_cl6` → shows Unknown, expected.  
**R14 CL6 Dp 0** — OUT_OF_SERVICE (known).  
**R1 Dp 0 & Dp 3** — HOT_STANDBY (no VIP assigned), normal.

Full IP addresses, proxy OAM ports, UCM VIPs → see `knowledge.md`.

---

## Common Gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| Page shows stale state after template edit | Flask Jinja cache | Kill all PIDs on port 80, restart |
| Two processes on port 80 | Leftover zombie | `netstat` + `taskkill` both PIDs |
| `NameError: datetime` inside route function | Import not at top of function | Add `from datetime import ...` inside the `if` block |
| Management IPs showing as OOS | vip_map captures all IPs | Filter with `if vl not in _known_vips` |
| OOS overwrites Standby | Wrong priority logic | Use `_prio` dict, never downgrade |
| `INVALID_JSON` from deleteStaleSessions | Missing `triggerSrr:false` | Always include it in payload |
| `UnicodeEncodeError` on Windows | Unicode arrow in print | Use plain ASCII in print statements |

---

## UPF Ops Commands Reference

```bash
# Get cluster status (PFCP Proxy)
curl -gs 'http://[PFCP_OAM_IP]:8806/action=getUpfClusterStatus'

# Delete stale sessions (MUST include triggerSrr:false)
curl -gi --data '{"staleSessionsMarkerTime":20,"triggerSrr":false}' \
  http://[PFCP_OAM_IP]:8806/action=deleteStaleSessions

# VPP CLI (inside DP container)
sudo docker exec <container> bash -c \
  'export LD_LIBRARY_PATH=... && /path/to/vppctl -s localhost:<port> show interface address'
```

CM commands run inside `upfcm` (R1) or `upfcm_clN` (R8/R13/R14). FCAPS port: 8001.

---

## What NOT to do
- Do not hardcode VIP→instance mappings — they change after failovers.
- Do not remove the `if vl not in _known_vips: continue` filter in `cluster_status_api`.
- Do not change HA refresh interval without checking `setInterval` in both `servers.html` AND `upf_ops.html`.
- Do not run `taskkill` or other destructive commands without `dangerouslyDisableSandbox: true`.
- Do not add `R1-CP-VIP` back to CLUSTERS — it is not a real server.
