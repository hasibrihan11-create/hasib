# -*- coding: utf-8 -*-
# ============================================================
#  dashboard_server.py — RBC GLORY Dashboard + API Server
# ============================================================
import asyncio
import json
import os
import time
import uuid
import traceback
from typing import Dict, List, Optional

from aiohttp import web

# ==================== INJECTED GLOBALS ====================
# Yeh variables app.py se inject honge
bot_state = None
ACTIVE_GROUPS: Dict[str, dict] = {}
CREATE_ACCOUNTS_FUNC = None
FETCH_GUILD_INFO = None
RUN_GROUP_CREATION = None
JOIN_GUILD_FUNC = None

DEFAULT_PASSWORD = "RBC__"
DEFAULT_COUNT = 4
GLORY_TIME_LIMIT = 8 * 3600  # 8 Hours

_sync_task = None
_score_task = None

# ==================== GUILD INFO NORMALIZER ====================
def _normalize_guild_info(raw: dict) -> dict:
    if not isinstance(raw, dict): return None
    leader = raw.get("GuildLeader") or {}
    officers = raw.get("Officers") or []
    gid = raw.get("GuildId")
    score = int(raw.get("TotalActivityPoints", 0) or raw.get("score", 0) or 0)
    weekly = int(raw.get("WeeklyActivityPoints", 0) or 0)
    
    return {
        "status": str(raw.get("status", "success")),
        "raw": raw,
        "clan_name": str(raw.get("GuildName") or f"Guild {gid or '?'}"),
        "guild_id": str(gid or ""),
        "guild_level": int(raw.get("GuildLevel", 1) or 1),
        "region": str(raw.get("GuildRegion", "") or ""),
        "leader_id": str(leader.get("Uid", "") or ""),
        "max_members": int(raw.get("MaxMembers", 0) or 0),
        "current_members": int(raw.get("CurrentMembers", 0) or 0),
        "score": score,
        "weekly_activity": weekly,
        "leader_name": str(leader.get("Name", "") or ""),
        "leader_level": int(leader.get("Level", 1) or 1),
        "slogan": str(raw.get("GuildSlogan", "") or ""),
        "auto_approval": str(raw.get("AutoApprovalStatus", "OFF") or "OFF"),
        "officers_count": len(officers),
    }

async def _ensure_normalized(info) -> dict:
    if not info or not isinstance(info, dict): return None
    if "clan_name" in info and "guild_level" in info: return info
    if str(info.get("status", "")).lower() == "success" or "GuildName" in info:
        return _normalize_guild_info(info)
    return None

# ==================== ACCOUNT SNAPSHOT ====================
def _account_snapshot(auth_uid: str, fallback: dict = None) -> dict:
    auth_uid = str(auth_uid)
    acc = None
    if bot_state:
        game_id = bot_state.auth_to_game_id.get(auth_uid)
        if game_id: acc = bot_state.accounts.get(str(game_id))
    if acc:
        return {
            "uid": str(acc.get("uid", auth_uid)),
            "auth_uid": auth_uid,
            "nickname": acc.get("nickname", "Generating..."),
            "level": int(acc.get("level", 1) or 1),
            "gained_exp": int(acc.get("gained_exp", 0) or 0),
            "status": acc.get("status", "ONLINE"),
        }
    if fallback: return dict(fallback)
    return {"uid": auth_uid, "auth_uid": auth_uid, "nickname": "Generating...", "level": 1, "gained_exp": 0, "status": "GENERATING"}

def _refresh_group_accounts(group: dict) -> None:
    auth_uids = group.get("auth_uids", []) or []
    initial_map = {a["auth_uid"]: a for a in group.get("initial_accounts", [])}
    accounts = [_account_snapshot(au, fallback=initial_map.get(str(au))) for au in auth_uids]
    group["accounts"] = accounts
    if group.get("status") == "GENERATING" and accounts:
        if any(a.get("status") != "GENERATING" for a in accounts):
            group["status"] = "RUNNING"

# ==================== WORKER CANCELLATION ====================
def _cancel_group_workers(group: dict) -> None:
    if not bot_state: return
    for auth_uid in list(group.get("auth_uids", [])):
        au = str(auth_uid)
        game_id = bot_state.auth_to_game_id.get(au)
        for key in (au, str(game_id) if game_id else ""):
            if not key: continue
            task = bot_state.account_workers.pop(key, None)
            if task:
                try: task.cancel()
                except Exception: pass

# ==================== SYNC LOOPS ====================
async def _sync_loop():
    try:
        while True:
            if ACTIVE_GROUPS:
                for g in list(ACTIVE_GROUPS.values()):
                    try: _refresh_group_accounts(g)
                    except Exception: pass
            await asyncio.sleep(3.0)
    except asyncio.CancelledError: pass

async def _score_updater_loop():
    try:
        while True:
            for g in list(ACTIVE_GROUPS.values()):
                if g.get("status") in ("RUNNING", "GENERATING", "STOPPED"):
                    try:
                        if FETCH_GUILD_INFO:
                            info = await FETCH_GUILD_INFO(g["guild_id"], g.get("region", "IND"))
                            norm = await _ensure_normalized(info)
                            if norm:
                                current_score = int(norm.get("score", 0) or 0)
                                current_weekly = int(norm.get("weekly_activity", 0) or 0)
                                
                                initial_weekly = int(g.get("initial_weekly", current_weekly))
                                if initial_weekly == 0 and current_weekly > 0:
                                    initial_weekly = current_weekly
                                    g["initial_weekly"] = current_weekly

                                old_weekly = g.get("current_weekly", initial_weekly)
                                if current_weekly < old_weekly:
                                    initial_weekly = 0
                                    g["initial_weekly"] = 0
                                
                                g["current_score"] = current_score
                                g["current_weekly"] = current_weekly
                                g["glory_pushed"] = max(0, current_weekly - initial_weekly)
                                g["current_members"] = int(norm.get("current_members", 0) or 0)
                                g["max_members"] = int(norm.get("max_members", 35) or 35)
                    except Exception: pass
            await asyncio.sleep(30.0)
    except asyncio.CancelledError: pass

# ==================== API HANDLERS ====================

async def handle_index(request):
    base = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(base, "templates", "index.html"), os.path.join(base, "index.html")):
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return web.Response(text=f.read(), content_type="text/html", charset="utf-8")
            except Exception: continue
    return web.Response(text="<h1>Glory Engine</h1><p>index.html not found.</p>", content_type="text/html", charset="utf-8")

async def api_stats(request):
    accs = list(bot_state.accounts.values()) if bot_state else []
    return web.json_response({
        "total_accounts": len(accs),
        "online": sum(1 for a in accs if a.get("status") not in ("OFFLINE", "PAUSED")),
        "total_matches": bot_state.total_matches if bot_state else 0,
        "matches_started": bot_state.matches_started if bot_state else 0,
        "total_gained_exp": bot_state.total_exp_gained if bot_state else 0,
        "uptime": int(time.time() - bot_state.start_time) if bot_state else 0,
        "groups": len(ACTIVE_GROUPS or {}),
        "creating": bool(bot_state.creating) if bot_state else False,
    })

async def api_get_groups(request):
    groups = list(ACTIVE_GROUPS.values()) if ACTIVE_GROUPS else []
    for g in groups:
        try: _refresh_group_accounts(g)
        except Exception: pass
    groups.sort(key=lambda x: x.get("started_at", 0), reverse=True)

    out = []
    for g in groups:
        view = {k: v for k, v in g.items() if k not in ("initial_accounts", "auth_uids")}
        out.append(view)
    return web.json_response({"groups": out})

async def api_guild_info(request):
    guild_id = str(request.query.get("guild_id", "")).strip()
    region = str(request.query.get("region", "IND")).strip().upper()
    if not guild_id.isdigit():
        return web.json_response({"ok": False, "error": "Guild ID must be numeric"})
    
    raw = None
    if FETCH_GUILD_INFO:
        try: raw = await FETCH_GUILD_INFO(guild_id, region)
        except Exception: pass

    try:
        info = await _ensure_normalized(raw)
        if not info:
            return web.json_response({"ok": False, "error": "Guild not found"})
        return web.json_response({"ok": True, "info": info})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

async def api_join_guild(request):
    try: data = await request.json()
    except Exception: return web.json_response({"ok": False, "error": "Invalid JSON"})

    guild_id = str(data.get("guild_id", "")).strip()
    region = str(data.get("region", "IND")).strip().upper()
    auth_uid = str(data.get("auth_uid", "")).strip()

    if not guild_id.isdigit() or not auth_uid:
        return web.json_response({"ok": False, "error": "Guild ID & auth_uid required"})

    acc = bot_state.account_credentials.get(auth_uid) if bot_state else None
    if not acc:
        return web.json_response({"ok": False, "error": "Bot not found"})

    try:
        ok = await JOIN_GUILD_FUNC(guild_id, acc.get("auth_uid"), acc.get("auth_password"), region=region, token=acc.get("token"))
        return web.json_response({"ok": bool(ok)})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

async def api_create_team(request):
    try:
        data = await request.json()
        region = str(data.get("region", "IND")).upper()
        guild_id = str(data.get("guild_id") or data.get("clan_id") or "").strip()
        count = int(data.get("count", DEFAULT_COUNT))
        password = str(data.get("password", DEFAULT_PASSWORD)).strip() or DEFAULT_PASSWORD

        if not guild_id or not guild_id.isdigit():
            return web.json_response({"ok": False, "error": "Valid numeric Guild ID required"})

        if bot_state and bot_state.creating:
            return web.json_response({"ok": False, "error": "Another creation in progress"})

        group_key = f"{guild_id}_{region}"
        existing = ACTIVE_GROUPS.get(group_key)
        if existing and existing.get("status") in ("RUNNING", "GENERATING"):
            return web.json_response({"ok": False, "error": "Group already running"})

        info = None
        if FETCH_GUILD_INFO:
            try:
                raw = await FETCH_GUILD_INFO(guild_id, region)
                info = await _ensure_normalized(raw)
            except Exception: pass

        if info:
            clan_name = info.get("clan_name") or f"Guild {guild_id}"
            level = int(info.get("guild_level", 1) or 1)
            leader_id = str(info.get("leader_id", "") or "")
            max_members = int(info.get("max_members", 35) or 35)
            current_members = int(info.get("current_members", 0) or 0)
            initial_score = int(info.get("score", 0) or 0)
            initial_weekly = int(info.get("weekly_activity", 0) or 0)
        else:
            clan_name = f"Guild {guild_id}"
            level, leader_id = 1, ""
            max_members, current_members = 35, 0
            initial_score = 0
            initial_weekly = 0

        ACTIVE_GROUPS[group_key] = {
            "group_key": group_key,
            "guild_id": guild_id,
            "group_name": clan_name,
            "clan_name": clan_name,
            "level": level,
            "leader_id": leader_id,
            "max_members": max_members,
            "current_members": current_members,
            "region": region,
            "initial_score": initial_score,
            "current_score": initial_score,
            "initial_weekly": initial_weekly,
            "current_weekly": initial_weekly,
            "glory_pushed": 0,
            "status": "GENERATING",
            "started_at": time.time(),
            "auth_uids": [],
            "initial_accounts": [],
            "accounts": [],
            "guild_info": info,
        }

        asyncio.create_task(RUN_GROUP_CREATION(group_key, region, count, guild_id, password))
        return web.json_response({"ok": True, "msg": f"Launched for {clan_name}", "group_key": group_key, "guild_info": info})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

async def api_stop_group(request):
    try:
        data = await request.json()
        group_key = str(data.get("group_key", ""))
        g = ACTIVE_GROUPS.get(group_key)
        if not g:
            return web.json_response({"ok": False, "error": "Group not found"})
        
        _cancel_group_workers(g)
        g["status"] = "STOPPED"
        for a in g.get("accounts", []): a["status"] = "STOPPED"
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

async def api_restart_group(request):
    try:
        data = await request.json()
        group_key = str(data.get("group_key", ""))
        g = ACTIVE_GROUPS.get(group_key)
        if not g:
            return web.json_response({"ok": False, "error": "Group not found"})

        _cancel_group_workers(g)
        g["status"] = "GENERATING"
        g["started_at"] = time.time()
        g["accounts"] = []
        g["auth_uids"] = []
        g["initial_accounts"] = []
        
        g["initial_score"] = g.get("current_score", 0)
        g["initial_weekly"] = g.get("current_weekly", 0)
        g["glory_pushed"] = 0
        g.pop("error", None)

        region = g.get("region", "IND")
        guild_id = g.get("guild_id")

        asyncio.create_task(RUN_GROUP_CREATION(group_key, region, DEFAULT_COUNT, guild_id, DEFAULT_PASSWORD))
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

# ==================== DIRECT GET URL HANDLERS (Browser) ====================

async def api_glory_start(request):
    """GET /glory?guild_id=XXX&region=IND"""
    guild_id = str(request.query.get("guild_id", "")).strip()
    region = str(request.query.get("region", "IND")).strip().upper()
    
    if not guild_id.isdigit():
        return web.Response(text="❌ Invalid Guild ID", content_type="text/plain")
    
    group_key = f"{guild_id}_{region}"
    if group_key in ACTIVE_GROUPS and ACTIVE_GROUPS[group_key].get("status") in ("RUNNING", "GENERATING"):
        return web.Response(text=f"⚠️ Already running: /status?group_id={group_key}", content_type="text/plain")

    # Fetch info
    info = None
    if FETCH_GUILD_INFO:
        try:
            raw = await FETCH_GUILD_INFO(guild_id, region)
            info = await _ensure_normalized(raw)
        except Exception: pass

    if not info:
        return web.Response(text=f"❌ Guild {guild_id} not found", content_type="text/plain")

    ACTIVE_GROUPS[group_key] = {
        "group_key": group_key, "guild_id": guild_id, "group_name": info["clan_name"], 
        "clan_name": info["clan_name"], "level": info["guild_level"], "leader_id": info["leader_id"],
        "max_members": info["max_members"], "current_members": info["current_members"],
        "region": region, "initial_score": info["score"], "current_score": info["score"],
        "initial_weekly": info["weekly_activity"], "current_weekly": info["weekly_activity"], 
        "glory_pushed": 0, "status": "GENERATING", "started_at": time.time(),
        "auth_uids": [], "initial_accounts": [], "accounts": [], "guild_info": info,
    }

    asyncio.create_task(RUN_GROUP_CREATION(group_key, region, DEFAULT_COUNT, guild_id, DEFAULT_PASSWORD))
    
    return web.Response(text=f"""
🚀 GLORY PUSHING STARTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Group ID:     {group_key}
Guild:        {info['clan_name']}
Level:        {info['guild_level']}
Region:       {region}
Total Glory:  {info['score']}
Bots:         {DEFAULT_COUNT}

📊 Status: /status?group_id={group_key}
🛑 Stop:   /stop?group_id={group_key}
    """, content_type="text/plain")

async def api_glory_stop(request):
    """GET /stop?group_id=XXX"""
    group_key = str(request.query.get("group_id", "")).strip()
    g = ACTIVE_GROUPS.get(group_key)
    if not g: return web.Response(text="❌ Group not found", content_type="text/plain")
    
    _cancel_group_workers(g)
    g["status"] = "STOPPED"
    for a in g.get("accounts", []): a["status"] = "OFFLINE"
    
    return web.Response(text=f"🛑 Stopped {group_key}. Bots offline.", content_type="text/plain")

async def api_glory_restart(request):
    """GET /restart?group_id=XXX"""
    group_key = str(request.query.get("group_id", "")).strip()
    g = ACTIVE_GROUPS.get(group_key)
    if not g: return web.Response(text="❌ Group not found", content_type="text/plain")
    if g.get("status") == "RUNNING": return web.Response(text="⚠️ Already running", content_type="text/plain")

    _cancel_group_workers(g)
    g["status"] = "GENERATING"
    g["started_at"] = time.time()
    g["accounts"] = []; g["auth_uids"] = []; g["initial_accounts"] = []
    g["initial_score"] = g.get("current_score", 0)
    g["initial_weekly"] = g.get("current_weekly", 0)
    g["glory_pushed"] = 0

    asyncio.create_task(RUN_GROUP_CREATION(group_key, g["region"], DEFAULT_COUNT, g["guild_id"], DEFAULT_PASSWORD))
    return web.Response(text=f"🔄 Restarting {group_key}…", content_type="text/plain")

async def api_glory_status(request):
    """GET /status?group_id=XXX"""
    group_key = str(request.query.get("group_id", "")).strip()
    g = ACTIVE_GROUPS.get(group_key)
    if not g: return web.Response(text="❌ Group not found", content_type="text/plain")
    
    elapsed = int(time.time() - g.get("started_at", time.time()))
    remaining = max(0, GLORY_TIME_LIMIT - elapsed)
    
    return web.Response(text=f"""
📊 STATUS — {group_key}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Guild:       {g.get('clan_name')}
Status:      {g.get('status')}
Total Glory: {g.get('current_score')}
Glory Gained:+{g.get('glory_pushed')}
Bots Online: {sum(1 for a in g.get('accounts', []) if a.get('status') == 'ONLINE')}/{len(g.get('accounts', []))}
Time Left:   {remaining // 3600}h {(remaining % 3600) // 60}m
    """, content_type="text/plain")

async def api_glory_list(request):
    """GET /list"""
    if not ACTIVE_GROUPS: return web.Response(text="No groups active.", content_type="text/plain")
    lines = ["📋 ACTIVE GROUPS:"]
    for gid, g in ACTIVE_GROUPS.items():
        lines.append(f"  {gid} | {g.get('clan_name')} | Status: {g.get('status')} | Glory: +{g.get('glory_pushed')}")
    return web.Response(text="\n".join(lines), content_type="text/plain")

# ==================== MIDDLEWARE & STARTUP ====================
@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        return web.Response(status=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        })
    try:
        response = await handler(request)
    except web.HTTPException as e:
        response = web.json_response({"ok": False, "error": e.reason or str(e)}, status=e.status)
    except Exception as e:
        traceback.print_exc()
        response = web.json_response({"ok": False, "error": str(e)}, status=500)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

async def start_web_dashboard(host: str, port: int, bot_state_arg, active_groups: dict = None, 
                              create_accounts_func=None, fetch_info_func=None, run_creation_func=None, 
                              join_guild_func=None):
    global bot_state, ACTIVE_GROUPS, CREATE_ACCOUNTS_FUNC, FETCH_GUILD_INFO, RUN_GROUP_CREATION, JOIN_GUILD_FUNC, _sync_task, _score_task

    bot_state = bot_state_arg
    ACTIVE_GROUPS = active_groups if active_groups is not None else {}
    CREATE_ACCOUNTS_FUNC = create_accounts_func
    FETCH_GUILD_INFO = fetch_info_func
    RUN_GROUP_CREATION = run_creation_func
    JOIN_GUILD_FUNC = join_guild_func

    app = web.Application(middlewares=[cors_middleware])

    # Dashboard HTML & JSON APIs
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_get("/api/groups", api_get_groups)
    app.router.add_get("/api/guild_info", api_guild_info)
    app.router.add_post("/api/create_team", api_create_team)
    app.router.add_post("/api/join_guild", api_join_guild)
    app.router.add_post("/api/groups/stop", api_stop_group)
    app.router.add_post("/api/groups/restart", api_restart_group)

    # Direct Browser URLs
    app.router.add_get("/glory", api_glory_start)
    app.router.add_get("/stop", api_glory_stop)
    app.router.add_get("/restart", api_glory_restart)
    app.router.add_get("/status", api_glory_status)
    app.router.add_get("/list", api_glory_list)

    if _sync_task is None or _sync_task.done():
        _sync_task = asyncio.create_task(_sync_loop())
        
    if _score_task is None or _score_task.done():
        _score_task = asyncio.create_task(_score_updater_loop())

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    print(f"\n[WEB] 🌐 Dashboard & API ready → http://{host}:{port}")
    print(f"[WEB] 🚀 Start → http://localhost:{port}/glory?guild_id=XXX")
    return runner