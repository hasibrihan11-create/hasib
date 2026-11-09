# CS Match Starter

Standalone Clash Squad match starter extracted from `LW UDP SOURCE`.

- Starts **CS only** (no Lone Wolf / guest maker / level-up loop)
- Web UI to paste `uid:pass` and spawn `cs_boost/cs_engine.py`
- Live job status + log tail

## Run

```powershell
cd "C:\Users\User\OneDrive\programming\FF APIS\PROJEXT FOLDERS\CS MATCH STARTER"
pip install -r requirements.txt
python server.py
```

Open http://127.0.0.1:20340 (no login).  
Env: `CS_UI_PORT`, `CS_AFK_POST_JOIN_S`, `CS_NODE_MAX`.

## CLI (no UI)

```powershell
cd cs_boost
python cs_engine.py <guest_uid> <password>
```

## Layout

```
CS MATCH STARTER/
  server.py           # aiohttp web UI + job manager
  templates/          # login + dashboard
  cs_boost/           # CS UDP engine (from LW UDP SOURCE)
  devices.json        # device fingerprints (optional)
  requirements.txt
```

Source of engine: `LW UDP SOURCE/cs_boost` (Python 3.10-safe `_udp_sendto` / `_udp_recvfrom`).
