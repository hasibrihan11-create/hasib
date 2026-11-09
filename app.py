#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AVI GLORY · Master API Server (Railway Ready)

Endpoints:
  GET /glory?guild_id=XXX&region= BD   → gen 4 bots, join, launch main.py engine
  GET /stop?group_id=XXX                → kill main.py engine for this group
  GET /restart?group_id=XXX             → restart engine with SAME bots
  GET /status?group_id=XXX              → live glory + bot status
  GET /list                             → all groups
  GET /info?guild_id=XXX                → guild preview

Har group ke liye:
  • 4 fresh bots gen (gen.py)
  • Real join (/join API)
  • Bio update
  • Save to AVI1_GENS/accounts-{region}.json
  • Spawn: python main.py (as separate process)
  • 8 ghante baad auto-kill
"""

import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import sys, json, time, asyncio, subprocess, traceback, uuid, signal
import urllib.parse, urllib.request, urllib.error
from typing import List, Dict, Optional, Tuple, Set
from aiohttp import web

# ═══════════════ CONFIG ═══════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GUILD_API_BASE = "https://danger-guild-management-web.vercel.app"
GUILD_API_JOIN = f"{GUILD_API_BASE}/join"
BIO_API = "https://star-bio-api.lovable.app/api/public/bio-upload"
BIO_TEXT = os.environ.get("AVI_BIO_TEXT", "A V I   C O D E X   I S   K I N G")

GEN_FILE = os.path.join(BASE_DIR, "gen.py")
MAIN_FILE = os.path.join(BASE_DIR, "main.py")
GEN_OUT_DIR = os.path.join(BASE_DIR, "AVI1_GENS")
DB_FILE = os.path.join(BASE_DIR, "glory_groups.json")

GEN_REGION = os.environ.get("AVI_GEN_REGION", " BD").upper()
FIXED_BOT_COUNT = 4
GLORY_TIME_LIMIT = 8 * 3600

WEB_HOST = os.environ.get("AVI_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("PORT", os.environ.get("AVI_WEB_PORT", "8080")))

DEFAULT_PASSWORD = "AVI__"
MAX_JOIN_ROUNDS = 5

# ═══════════════ STORAGE ═══════════════
GROUPS_DB: Dict[str, dict] = {}
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            GROUPS_DB = json.load(f)
    except Exception:
        GROUPS_DB = {}

def save_db():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(GROUPS_DB, f, indent=2, default=str)
    except Exception:
        pass

# ═══════════════ HTTP ═══════════════
def _http_get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "AVI-GLORY/21", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try: return resp.status, json.loads(body), body
            except: return resp.status, None, body
    except urllib.error.HTTPError as e:
        try: body = e.read().decode("utf-8", errors="replace")
        except: body = ""
        return e.code, None, body
    except Exception as e:
        return 0, None, str(e)

# ═══════════════ GUILD INFO ═══════════════
def fetch_guild_norm(guild_id, region=" BD"):
    url = f"{GUILD_API_BASE}/guild?guild_id={guild_id}&region={region}"
    code, js, _ = _http_get_json(url, timeout=15)
    if code != 200 or not isinstance(js, dict) or js.get("status") != "success":
        return None
    leader = js.get("GuildLeader") or {}
    return {
        "guild_name": js.get("GuildName", f"Guild {guild_id}"),
        "guild_id": str(guild_id),
        "guild_level": int(js.get("GuildLevel", 1) or 1),
        "region": js.get("GuildRegion", region),
        "leader_id": str(leader.get("Uid", "")),
        "leader_name": str(leader.get("Name", "")),
        "slogan": js.get("GuildSlogan", ""),
        "current_members": int(js.get("CurrentMembers", 0) or 0),
        "max_members": int(js.get("MaxMembers", 35) or 35),
        "total_glory": int(js.get("TotalActivityPoints", 0) or 0),
        "weekly_glory": int(js.get("WeeklyActivityPoints", 0) or 0),
    }

def get_member_count(guild_id, region):
    url = f"{GUILD_API_BASE}/guild?guild_id={guild_id}&region={region}"
    code, js, _ = _http_get_json(url, timeout=15)
    if code == 200 and isinstance(js, dict):
        return int(js.get("CurrentMembers", 0) or 0)
    return 0

def extract_member_uids(raw):
    out = set()
    if not isinstance(raw, dict): return out
    for key in ("Members", "members", "GuildMembers", "Accounts", "accounts"):
        arr = raw.get(key)
        if isinstance(arr, list):
            for m in arr:
                if isinstance(m, dict):
                    for f in ("Uid", "uid", "AccountId", "account_id"):
                        v = m.get(f)
                        if v: out.add(str(v).strip())
    return out

def is_in_guild(guild_id, region, uid):
    url = f"{GUILD_API_BASE}/guild?guild_id={guild_id}&region={region}"
    code, js, _ = _http_get_json(url, timeout=15)
    if code == 200 and isinstance(js, dict):
        return str(uid) in extract_member_uids(js)
    return False

# ═══════════════ JOIN & BIO ═══════════════
def send_join(guild_id, uid, password):
    params = urllib.parse.urlencode({"guild_id": guild_id, "uid": uid, "password": password})
    url = f"{GUILD_API_JOIN}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AVI-GLORY/21"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                js = json.loads(body)
                ok = js.get("success") is True or str(js.get("status", "")).lower() in ("ok", "success", "joined")
                if js.get("success") is False or js.get("error"): ok = False
                return ok, str(js.get("message") or js.get("error") or "OK")[:140]
            except:
                return 200 <= resp.status < 300, "OK"
    except Exception as e:
        return False, str(e)[:140]

def send_bio(uid, password):
    params = urllib.parse.urlencode({"bio": BIO_TEXT, "uid": uid, "password": password})
    url = f"{BIO_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AVI-GLORY/21"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except:
        return False

# ═══════════════ GEN.PY ═══════════════
def run_gen(count, region):
    if not os.path.exists(GEN_FILE): return False
    env = os.environ.copy()
    env["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
    args = [sys.executable, GEN_FILE, "gen", str(count), region, "y"]
    try:
        proc = subprocess.run(args, cwd=BASE_DIR, env=env, timeout=300, capture_output=True, text=True)
        for line in proc.stdout.split("\n"):
            if line.strip(): print(f"    │ {line}")
        return proc.returncode == 0
    except Exception as e:
        print(f"gen error: {e}")
        return False

def load_generated(region):
    path = os.path.join(GEN_OUT_DIR, f"accounts-{region.upper()}.json")
    if not os.path.exists(path): return []
    try:
        with open(path) as f: raw = json.load(f)
    except:
        return []
    out = []
    for a in raw if isinstance(raw, list) else []:
        if isinstance(a, dict):
            u = str(a.get("uid") or a.get("account_id") or "").strip()
            p = str(a.get("password") or "").strip()
            if u and p: out.append({"uid": u, "password": p})
    return out

# ═══════════════ BOT ENGINE LAUNCHER ═══════════════
# main.py ke andar bot engine chalta hai. Hum usko subprocess me launch karte hain.
# main.py `accounts.json` padhta hai (load_accounts function) aur uske saare bots ko start karta hai.
# 
# Structure:
#   group["engine_proc"] = Popen(main.py)
#   group["engine_pid"] = proc.pid

import tempfile

def _write_accounts_for_engine(accounts: List[Dict]):
    """main.py 'accounts.json' padhta hai — 4 bots yahan write karo."""
    path = os.path.join(BASE_DIR, "accounts.json")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=1)
        os.replace(tmp, path)
        return True
    except Exception as e:
        print(f"accounts.json write error: {e}")
        return False

def start_engine_process():
    """main.py ko background process me start karo."""
    if not os.path.exists(MAIN_FILE):
        return None, "main.py not found"
    env = os.environ.copy()
    env["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
    env["AVI_SKIP_WEB"] = "1"  # main.py ko web server skip karne bolo
    try:
        # Unix me alag process group me start karo taaki saare child processes kill kar sake
        kwargs = {"cwd": BASE_DIR, "env": env, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT}
        if sys.platform != "win32":
            kwargs["preexec_fn"] = os.setsid
        proc = subprocess.Popen([sys.executable, MAIN_FILE], **kwargs)
        return proc, None
    except Exception as e:
        return None, str(e)

def stop_engine_process(proc):
    """main.py process aur uske saare child processes kill karo."""
    if not proc: return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(1)
            try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except: pass
    except Exception:
        try: proc.kill()
        except: pass

# ═══════════════ PIPELINE (async) ═══════════════
async def create_and_join(region, guild_id, count, group):
    """
    Gen → join → verify → bio → save → spawn engine.
    Sab step live `group` me update hota hai.
    """
    log = lambda m: print(f"  [{group.get('group_id','?')}] {m}")
    region = region.upper()
    count = FIXED_BOT_COUNT

    log(f"Generating {count} fresh bots for guild={guild_id}")
    for attempt in range(1, MAX_JOIN_ROUNDS + 1):
        ok = await asyncio.get_event_loop().run_in_executor(None, run_gen, count, region)
        await asyncio.sleep(1)
        accs = load_generated(region)
        if len(accs) >= count:
            log(f"Generated {len(accs)} accounts")
            break
        log(f"Only {len(accs)}/{count} — retry {attempt}")
        await asyncio.sleep(2)

    if not accs:
        group["status"] = "FAILED"; group["error"] = "No accounts generated"; save_db()
        return

    pool = accs[-count:]
    initial_count = await asyncio.get_event_loop().run_in_executor(None, get_member_count, guild_id, region)
    log(f"Initial guild members: {initial_count}")

    joined, burned = [], set()
    for round_num in range(1, MAX_JOIN_ROUNDS + 1):
        if len(joined) >= count: break
        needed = count - len(joined)
        if round_num == 1:
            candidates = [a for a in pool if a["uid"] not in burned]
        else:
            await asyncio.get_event_loop().run_in_executor(None, run_gen, needed, region)
            await asyncio.sleep(1)
            all_accs = load_generated(region)
            candidates = [a for a in all_accs if a["uid"] not in burned][-needed:]
        if not candidates: continue

        for acc in candidates:
            if len(joined) >= count: break
            uid = acc["uid"]
            ok, msg = await asyncio.get_event_loop().run_in_executor(
                None, send_join, guild_id, uid, acc["password"])
            if ok:
                joined.append(acc)
                log(f"Joined {uid[:12]}… ({len(joined)}/{count})")
                group["auth_uids"].append(uid)
                group["accounts"].append({
                    "uid": uid, "auth_uid": uid, "nickname": acc.get("name", "Guest"),
                    "level": 1, "gained_exp": 0, "status": "ONLINE"})
                save_db()
            else:
                burned.add(uid)
                log(f"Failed {uid[:12]}…: {msg}")
            await asyncio.sleep(1.5)

    if not joined:
        group["status"] = "FAILED"; group["error"] = "No joins"; save_db()
        return

    log(f"Verifying {len(joined)} joins...")
    await asyncio.sleep(6)
    valid = []
    for acc in joined:
        found = await asyncio.get_event_loop().run_in_executor(
            None, is_in_guild, guild_id, region, acc["uid"])
        if found: valid.append(acc)
        else:
            log(f"Fake join: {acc['uid'][:12]}")
            group["auth_uids"] = [x for x in group["auth_uids"] if x != acc["uid"]]
            group["accounts"] = [x for x in group["accounts"] if x["auth_uid"] != acc["uid"]]
    joined = valid
    if not joined:
        group["status"] = "FAILED"; group["error"] = "All fake joins"; save_db()
        return

    log(f"Bio update for {len(joined)} accounts...")
    for acc in joined:
        await asyncio.get_event_loop().run_in_executor(None, send_bio, acc["uid"], acc["password"])
        await asyncio.sleep(1)

    # Save accounts.json (main.py uses this)
    if not _write_accounts_for_engine([{"uid": a["uid"], "password": a["password"]} for a in joined]):
        group["status"] = "FAILED"; group["error"] = "Cannot write accounts.json"; save_db()
        return

    # Launch main.py bot engine
    log(f"Launching bot engine for {len(joined)} accounts...")
    proc, err = start_engine_process()
    if err:
        group["status"] = "FAILED"; group["error"] = f"Engine: {err}"; save_db()
        return

    group["engine_pid"] = proc.pid
    group["engine_proc"] = proc
    group["status"] = "RUNNING"
    group["started_at"] = time.time()
    group["initial_glory"] = group["total_glory"]
    save_db()
    log(f"✅ Bot engine running (PID {proc.pid})")

    # 8-hour worker
    await _glory_worker(group["group_id"])

async def _glory_worker(group_id):
    group = GROUPS_DB.get(group_id)
    if not group: return
    start_ts = group["started_at"]
    while True:
        if GROUPS_DB.get(group_id, {}).get("status") != "RUNNING":
            log = lambda m: print(f"  [{group_id}] {m}")
            log("Stopped manually")
            break
        elapsed = time.time() - start_ts
        if elapsed >= GLORY_TIME_LIMIT:
            log = lambda m: print(f"  [{group_id}] {m}")
            log("8 hours complete — stopping engine")
            proc = group.get("engine_proc")
            if proc: stop_engine_process(proc)
            group["status"] = "COMPLETED"
            group["engine_pid"] = None
            group["engine_proc"] = None
            save_db()
            return
        # Refresh glory
        try:
            info = await asyncio.get_event_loop().run_in_executor(
                None, fetch_guild_norm, group["guild_id"], group["region"])
            if info:
                group["total_glory"] = info["total_glory"]
                group["weekly_glory"] = info["weekly_glory"]
                group["glory_gained"] = max(0, info["total_glory"] - group["initial_glory"])
                group["current_members"] = info["current_members"]
                group["elapsed_seconds"] = int(elapsed)
                group["remaining_seconds"] = int(max(0, GLORY_TIME_LIMIT - elapsed))
                save_db()
        except Exception:
            pass
        await asyncio.sleep(60)

# ═══════════════ API HANDLERS ═══════════════
async def api_home(request):
    return web.Response(text=f"""
╔═══════════════════════════════════════════════════════════════╗
║  🎮 AVI GLORY API — RAILWAY EDITION                          ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  🚀 START:                                                    ║
║     /glory?guild_id=3055327268&region= BD                     ║
║                                                               ║
║  📊 STATUS:                                                   ║
║     /status?group_id=GRP-XXXXXX                               ║
║                                                               ║
║  🛑 STOP:                                                     ║
║     /stop?group_id=GRP-XXXXXX                                 ║
║                                                               ║
║  🔄 RESTART:                                                  ║
║     /restart?group_id=GRP-XXXXXX                              ║
║                                                               ║
║  📋 LIST:                                                     ║
║     /list                                                     ║
║                                                               ║
║  ℹ️  INFO:                                                    ║
║     /info?guild_id=3055327268                                 ║
║                                                               ║
║  ⚙️  FEATURES:                                                ║
║     • 4 fresh bots per group                                  ║
║     • Real /join API + verify                                 ║
║     • main.py engine auto-launched                            ║
║     • 8-hour auto-kill                                        ║
║     • Restart uses SAME bots                                  ║
╚═══════════════════════════════════════════════════════════════╝
""", content_type="text/plain")

async def api_glory(request):
    guild_id = str(request.query.get("guild_id", "")).strip()
    region = str(request.query.get("region", GEN_REGION)).upper()
    if not guild_id.isdigit():
        return web.Response(text="❌ Invalid guild_id", content_type="text/plain")

    info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_norm, guild_id, region)
    if not info:
        return web.Response(text=f"❌ Guild {guild_id} not found in {region}", content_type="text/plain")

    group_id = f"GRP-{uuid.uuid4().hex[:6].upper()}"
    GROUPS_DB[group_id] = {
        "group_id": group_id, "guild_id": guild_id, "region": region,
        "guild_name": info["guild_name"], "guild_level": info["guild_level"],
        "leader_id": info["leader_id"], "leader_name": info["leader_name"],
        "slogan": info["slogan"], "current_members": info["current_members"],
        "max_members": info["max_members"],
        "initial_glory": info["total_glory"], "total_glory": info["total_glory"],
        "weekly_glory": info["weekly_glory"], "glory_gained": 0,
        "elapsed_seconds": 0, "remaining_seconds": GLORY_TIME_LIMIT,
        "status": "GENERATING", "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "auth_uids": [], "accounts": [],
        "engine_pid": None, "engine_proc": None,
    }
    save_db()

    asyncio.create_task(create_and_join(region, guild_id, FIXED_BOT_COUNT, GROUPS_DB[group_id]))

    return web.Response(text=f"""
🚀 GLORY STARTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Group:      {group_id}
Guild:      {info['guild_name']} ({guild_id})
Level:      {info['guild_level']}
Leader:     {info['leader_name']} (UID: {info['leader_id']})
Slogan:     {info['slogan'] or 'No slogan'}
Members:    {info['current_members']}/{info['max_members']}
Glory:      {info['total_glory']} total | {info['weekly_glory']} weekly
Duration:   8 hours auto-stop
Bots:       {FIXED_BOT_COUNT}

📊 Status:  /status?group_id={group_id}
🛑 Stop:    /stop?group_id={group_id}
🔄 Restart: /restart?group_id={group_id}
""", content_type="text/plain")

async def api_stop(request):
    gid = str(request.query.get("group_id", "")).strip()
    g = GROUPS_DB.get(gid)
    if not g: return web.Response(text=f"❌ {gid} not found", content_type="text/plain")
    g["status"] = "STOPPED"
    proc = g.get("engine_proc")
    if proc:
        await asyncio.get_event_loop().run_in_executor(None, stop_engine_process, proc)
    g["engine_pid"] = None; g["engine_proc"] = None
    for acc in g.get("accounts", []): acc["status"] = "OFFLINE"
    save_db()
    return web.Response(text=f"🛑 {gid} stopped. All bots offline.", content_type="text/plain")

async def api_restart(request):
    gid = str(request.query.get("group_id", "")).strip()
    g = GROUPS_DB.get(gid)
    if not g: return web.Response(text=f"❌ {gid} not found", content_type="text/plain")
    if g.get("status") == "RUNNING":
        return web.Response(text=f"⚠️ {gid} is already RUNNING", content_type="text/plain")

    saved_accs = [{"uid": a["uid"], "password": a.get("password", DEFAULT_PASSWORD)}
                  for a in g.get("accounts", []) if a.get("status") == "ONLINE"]
    if saved_accs and g.get("status") == "STOPPED":
        if not _write_accounts_for_engine(saved_accs):
            return web.Response(text="❌ Cannot write accounts.json", content_type="text/plain")
        proc, err = start_engine_process()
        if err: return web.Response(text=f"❌ Engine: {err}", content_type="text/plain")
        g["status"] = "RUNNING"
        g["started_at"] = time.time()
        g["engine_pid"] = proc.pid; g["engine_proc"] = proc
        g["initial_glory"] = g.get("total_glory", 0)
        g["glory_gained"] = 0
        save_db()
        asyncio.create_task(_glory_worker(gid))
        return web.Response(text=f"🔄 {gid} restarted with SAME {len(saved_accs)} bots.", content_type="text/plain")
    else:
        g["status"] = "GENERATING"
        g["auth_uids"] = []; g["accounts"] = []
        save_db()
        asyncio.create_task(create_and_join(g["region"], g["guild_id"], FIXED_BOT_COUNT, g))
        return web.Response(text=f"🔄 {gid} restarting with FRESH bots...", content_type="text/plain")

async def api_status(request):
    gid = str(request.query.get("group_id", "")).strip()
    g = GROUPS_DB.get(gid)
    if not g: return web.Response(text=f"❌ {gid} not found", content_type="text/plain")

    elapsed = int(time.time() - g.get("started_at", time.time())) if g.get("started_at") else 0
    remaining = max(0, GLORY_TIME_LIMIT - elapsed)

    if g.get("status") == "RUNNING":
        try:
            info = await asyncio.get_event_loop().run_in_executor(
                None, fetch_guild_norm, g["guild_id"], g["region"])
            if info:
                g["total_glory"] = info["total_glory"]
                g["weekly_glory"] = info["weekly_glory"]
                g["glory_gained"] = max(0, info["total_glory"] - g.get("initial_glory", 0))
                g["current_members"] = info["current_members"]
                save_db()
        except: pass

    online = sum(1 for a in g.get("accounts", []) if a.get("status") == "ONLINE")
    return web.Response(text=f"""
📊 STATUS — {gid}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status:       {g.get('status')}
Guild:        {g.get('guild_name')} ({g.get('guild_id')})
Level:        {g.get('guild_level')}
Region:       {g.get('region')}
Leader:       {g.get('leader_name')} (UID: {g.get('leader_id')})
Members:      {g.get('current_members')}/{g.get('max_members', 35)}

💎 Total Glory:    {g.get('total_glory', 0)}
📈 Glory Gained:   +{g.get('glory_gained', 0)}
📊 Weekly Glory:   {g.get('weekly_glory', 0)}

🤖 Bots:          {online}/{len(g.get('accounts', []))} online
🔧 Engine PID:    {g.get('engine_pid') or 'not running'}
⏱  Elapsed:       {elapsed//3600}h {(elapsed%3600)//60}m
⏳ Remaining:     {remaining//3600}h {(remaining%3600)//60}m

🛑 /stop?group_id={gid}
🔄 /restart?group_id={gid}
""", content_type="text/plain")

async def api_list(request):
    if not GROUPS_DB:
        return web.Response(text="📋 No groups yet. Start: /glory?guild_id=XXX", content_type="text/plain")
    lines = ["╔══════════════════════════════════════════════════════╗",
             "║  📋 ACTIVE GROUPS                                    ║",
             "╠══════════════════════════════════════════════════════╣"]
    for gid, g in GROUPS_DB.items():
        lines.append(f"║  {gid} │ {g.get('guild_name', '?')[:18]:18} │ {g.get('status', '?'):10} │ +{g.get('glory_gained', 0)}")
    lines.append("╚══════════════════════════════════════════════════════╝")
    return web.Response(text="\n".join(lines), content_type="text/plain")

async def api_info(request):
    gid = str(request.query.get("guild_id", "")).strip()
    region = str(request.query.get("region", GEN_REGION)).upper()
    if not gid.isdigit():
        return web.Response(text="❌ Invalid guild_id", content_type="text/plain")
    info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_norm, gid, region)
    if not info:
        return web.Response(text=f"❌ Not found", content_type="text/plain")
    return web.Response(text=f"""
ℹ️ GUILD INFO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name:     {info['guild_name']}
ID:       {info['guild_id']}
Level:    {info['guild_level']}
Region:   {info['region']}
Leader:   {info['leader_name']} (UID: {info['leader_id']})
Slogan:   {info['slogan'] or 'No slogan'}
Members:  {info['current_members']}/{info['max_members']}
Glory:    {info['total_glory']} total | {info['weekly_glory']} weekly

🚀 Start: /glory?guild_id={gid}&region={region}
""", content_type="text/plain")

# ═══════════════ APP ═══════════════
async def main():
    print(f"\n{'═'*62}")
    print(f"  🎮 AVI GLORY MASTER API")
    print(f"  Port: {WEB_PORT} | Region: {GEN_REGION} | Bots: {FIXED_BOT_COUNT}")
    print(f"{'═'*62}\n")

    app = web.Application()
    app.router.add_get("/", api_home)
    app.router.add_get("/glory", api_glory)
    app.router.add_get("/stop", api_stop)
    app.router.add_get("/restart", api_restart)
    app.router.add_get("/status", api_status)
    app.router.add_get("/list", api_list)
    app.router.add_get("/info", api_info)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_HOST, WEB_PORT)
    await site.start()
    print(f"✅ Server ready → http://{WEB_HOST}:{WEB_PORT}\n")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠ Stopped")