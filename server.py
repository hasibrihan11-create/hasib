# -*- coding: utf-8 -*-
"""CS Match Starter — thin web UI around cs_boost/cs_engine.py."""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from typing import Any, Dict, List

from aiohttp import web

ROOT = os.path.dirname(os.path.abspath(__file__))
CS_DIR = os.path.join(ROOT, "cs_boost")
CS_ENGINE = os.path.join(CS_DIR, "cs_engine.py")
TEMPLATES = os.path.join(ROOT, "templates")

PORT = int(os.environ.get("CS_UI_PORT", "20340"))
HOST = os.environ.get("CS_UI_HOST", "0.0.0.0")

# job_id -> job dict
JOBS: Dict[str, Dict[str, Any]] = {}
MAX_LOG_LINES = 400
CS_AFK_POST_JOIN_S = float(os.environ.get("CS_AFK_POST_JOIN_S", "45"))
CS_MATCH_TIMEOUT = float(os.environ.get("CS_MATCH_TIMEOUT", "700"))
CS_NODE_MAX = max(1, int(os.environ.get("CS_NODE_MAX", "20")))


def _now() -> float:
    return time.time()


def _public_job(j: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": j["id"],
        "uid": j["uid"],
        "status": j["status"],
        "started_at": j["started_at"],
        "ended_at": j.get("ended_at"),
        "exit_code": j.get("exit_code"),
        "got_allotment": j.get("got_allotment", False),
        "joined": j.get("joined", False),
        "nickname": j.get("nickname") or "",
        "region": j.get("region") or "",
        "account_id": j.get("account_id") or "",
        "log_tail": j.get("logs", [])[-80:],
    }


def _parse_accounts(raw: str) -> List[tuple]:
    """Parse uid:pass / uid|pass / uid pass lines."""
    out: List[tuple] = []
    seen = set()
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        uid, pwd = "", ""
        if ":" in line:
            uid, pwd = line.split(":", 1)
        elif "|" in line:
            uid, pwd = line.split("|", 1)
        else:
            parts = line.split()
            if len(parts) >= 2:
                uid, pwd = parts[0], parts[1]
        uid, pwd = uid.strip(), pwd.strip()
        if not uid or not pwd:
            continue
        key = f"{uid}:{pwd}"
        if key in seen:
            continue
        seen.add(key)
        out.append((uid, pwd))
    return out


async def _stream_job(job: Dict[str, Any], proc: asyncio.subprocess.Process) -> None:
    assert proc.stdout is not None
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            try:
                text = line.decode("utf-8", errors="replace").rstrip()
            except Exception:
                text = str(line)
            if not text:
                continue
            logs = job.setdefault("logs", [])
            logs.append(text)
            if len(logs) > MAX_LOG_LINES:
                del logs[: len(logs) - MAX_LOG_LINES]

            low = text.lower()
            if "match allotment" in low or "MATCH ALLOTMENT" in text:
                job["got_allotment"] = True
                job["status"] = "ALLOTTED"
            if (
                "JOIN_MATCH_FINISHED" in text
                or "Match Fully Loaded into Clash Squad" in text
                or "joined match" in low
            ):
                job["joined"] = True
                job["status"] = "IN_MATCH"
            if text.startswith("[CS_PROFILE]"):
                # guest_uid=..|account_id=..|nickname=..|region=..
                payload = text[len("[CS_PROFILE]") :].strip()
                for part in payload.split("|"):
                    if "=" not in part:
                        continue
                    k, v = part.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k == "nickname":
                        job["nickname"] = v
                    elif k == "region":
                        job["region"] = v
                    elif k == "account_id":
                        job["account_id"] = v
            if "looking for" in low or "matchmaking" in low:
                if job["status"] in ("STARTING", "RUNNING"):
                    job["status"] = "SEARCHING"
    finally:
        code = await proc.wait()
        job["exit_code"] = int(code if code is not None else 0)
        job["ended_at"] = _now()
        if job.get("stop_requested"):
            job["status"] = "STOPPED"
        elif job.get("joined") or job.get("got_allotment"):
            job["status"] = "DONE"
        else:
            job["status"] = "FAILED"
        job["proc"] = None


async def _spawn_job(uid: str, password: str) -> Dict[str, Any]:
    running = sum(1 for j in JOBS.values() if j["status"] not in ("DONE", "FAILED", "STOPPED"))
    if running >= CS_NODE_MAX:
        raise RuntimeError(f"max concurrent CS jobs reached ({CS_NODE_MAX})")

    if not os.path.isfile(CS_ENGINE):
        raise RuntimeError(f"cs_engine missing: {CS_ENGINE}")

    job_id = uuid.uuid4().hex[:10]
    job: Dict[str, Any] = {
        "id": job_id,
        "uid": str(uid),
        "password": str(password),
        "status": "STARTING",
        "started_at": _now(),
        "ended_at": None,
        "exit_code": None,
        "got_allotment": False,
        "joined": False,
        "nickname": "",
        "region": "",
        "account_id": "",
        "logs": [],
        "stop_requested": False,
        "proc": None,
        "task": None,
    }
    JOBS[job_id] = job

    env = os.environ.copy()
    env["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["CS_AFK_POST_JOIN_S"] = str(CS_AFK_POST_JOIN_S)
    env["CS_STACK"] = "0"

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        CS_ENGINE,
        str(uid),
        str(password),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=CS_DIR,
        env=env,
    )
    job["proc"] = proc
    job["status"] = "RUNNING"
    job["logs"].append(f"[UI] spawned cs_engine pid={proc.pid} afk={CS_AFK_POST_JOIN_S}s")

    async def _runner():
        try:
            await asyncio.wait_for(_stream_job(job, proc), timeout=CS_MATCH_TIMEOUT)
        except asyncio.TimeoutError:
            job["logs"].append(f"[UI] match timeout ({int(CS_MATCH_TIMEOUT)}s) — killing")
            try:
                proc.kill()
            except Exception:
                pass
            try:
                await proc.wait()
            except Exception:
                pass
            job["status"] = "TIMEOUT"
            job["ended_at"] = _now()
            job["proc"] = None
        except asyncio.CancelledError:
            try:
                proc.kill()
            except Exception:
                pass
            raise

    job["task"] = asyncio.create_task(_runner())
    return job


async def _stop_job(job_id: str) -> bool:
    job = JOBS.get(job_id)
    if not job:
        return False
    job["stop_requested"] = True
    proc = job.get("proc")
    if proc and proc.returncode is None:
        job["logs"].append("[UI] stop requested — killing engine")
        try:
            proc.kill()
        except Exception:
            pass
    else:
        job["status"] = "STOPPED"
        job["ended_at"] = job.get("ended_at") or _now()
    return True


# ---------- HTTP handlers ----------

async def handle_index(request: web.Request) -> web.Response:
    return web.FileResponse(os.path.join(TEMPLATES, "index.html"))


async def api_status(request: web.Request) -> web.Response:
    jobs = sorted(JOBS.values(), key=lambda j: j["started_at"], reverse=True)
    active = sum(1 for j in jobs if j["status"] not in ("DONE", "FAILED", "STOPPED", "TIMEOUT"))
    return web.json_response(
        {
            "ok": True,
            "active": active,
            "max": CS_NODE_MAX,
            "afk_s": CS_AFK_POST_JOIN_S,
            "engine_ok": os.path.isfile(CS_ENGINE),
            "jobs": [_public_job(j) for j in jobs[:100]],
        }
    )


async def api_start(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw = str(body.get("accounts") or body.get("text") or "").strip()
    uid = str(body.get("uid") or "").strip()
    password = str(body.get("password") or "").strip()

    accounts = _parse_accounts(raw) if raw else []
    if uid and password:
        accounts.insert(0, (uid, password))
    # dedupe again
    seen = set()
    uniq = []
    for u, p in accounts:
        k = f"{u}:{p}"
        if k in seen:
            continue
        seen.add(k)
        uniq.append((u, p))

    if not uniq:
        return web.json_response({"ok": False, "error": "no accounts"}, status=400)

    started = []
    errors = []
    for u, p in uniq:
        try:
            job = await _spawn_job(u, p)
            started.append(_public_job(job))
        except Exception as e:
            errors.append({"uid": u, "error": str(e)})

    return web.json_response({"ok": True, "started": started, "errors": errors})


async def api_stop(request: web.Request) -> web.Response:
    job_id = request.match_info.get("job_id", "")
    if not await _stop_job(job_id):
        return web.json_response({"ok": False, "error": "not found"}, status=404)
    return web.json_response({"ok": True})


async def api_stop_all(request: web.Request) -> web.Response:
    n = 0
    for jid, j in list(JOBS.items()):
        if j["status"] not in ("DONE", "FAILED", "STOPPED", "TIMEOUT"):
            await _stop_job(jid)
            n += 1
    return web.json_response({"ok": True, "stopped": n})


async def api_clear_done(request: web.Request) -> web.Response:
    remove = [
        jid
        for jid, j in JOBS.items()
        if j["status"] in ("DONE", "FAILED", "STOPPED", "TIMEOUT")
    ]
    for jid in remove:
        JOBS.pop(jid, None)
    return web.json_response({"ok": True, "cleared": len(remove)})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/start", api_start)
    app.router.add_post("/api/stop/{job_id}", api_stop)
    app.router.add_post("/api/stop_all", api_stop_all)
    app.router.add_post("/api/clear_done", api_clear_done)
    return app


def main() -> None:
    print(f"[CS Match Starter] http://127.0.0.1:{PORT}")
    print(f"  engine: {CS_ENGINE}")
    web.run_app(create_app(), host=HOST, port=PORT, print=None)


if __name__ == "__main__":
    main()
