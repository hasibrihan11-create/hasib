# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════
#  TEAM AVI — Squad Bot + Flask Token Extractor  (FIXED)
#  • Homer (skill 5506) equip via homor_rudp, safe proto wrapper
#  • In-match UDP delegated to toolsudp.run_match (movement+skill)
#  • Use_Auth_Packet = False (stops "handshake failed")
#  • Squad create→invite→ready→start flow intact
# ═══════════════════════════════════════════════════════════════════
import sys, asyncio, httpx, random, json, socket, struct, time, os, uuid
import itertools, secrets, traceback, base64, threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import logging, urllib3
from flask import Flask, Response, request
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

from google_play_scraper import app as play_scraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser
from message_ids import MESSAGE_ID_TO_NAME
import thunderFF_pb2

# AVI modules
import config
import autoupdate
import tools
import toolsudp
import ff_udp
import ff_match
import homor_rudp
from ffcore import encrypt_api as ff_encrypt_api, create_protobuf_packet
from dashboard_server import start_web_dashboard

# ── CRITICAL: disable raw auth datagram (root cause of "handshake failed") ──
try:
    config.Use_Auth_Packet = False
except Exception: pass
try:
    config.LIVE.set_skill(skill_id=homor_rudp.SKILL_HOMOR)
except Exception: pass


# ═══════════════════════ BOT STATE ═══════════════════════
class RBCBotState:
    def __init__(self):
        self.accounts = {}
        self.account_credentials = {}
        self.auth_to_game_id = {}
        self.account_workers = {}
        self.refresh_callbacks = {}
        self.paused_accounts = set()
        self.total_matches = 0
        self.matches_started = 0
        self.total_exp_gained = 0
        self.start_time = time.time()
        self.creating = False
    def log(self, message, level='info'): return None
    def register_account(self, uid, nickname='Unknown', region='ID', level=1, exp=0, likes=0):
        key = str(uid)
        self.accounts[key] = {
            'uid': key, 'nickname': str(nickname or 'Unknown'),
            'region': str(region or 'ID'), 'level': int(level or 1),
            'exp': int(exp or 0), 'gained_exp': 0, 'likes': int(likes or 0),
            'status': 'ONLINE', 'matches': 0,
        }
        return self.accounts[key]
    def update_status(self, uid, status, remaining=0):
        key = str(uid); game_id = self.auth_to_game_id.get(key, key)
        if game_id in self.accounts:
            self.accounts[game_id]['status'] = str(status)
            self.accounts[game_id]['remaining'] = int(remaining or 0)
    def update_exp(self, uid, exp, level):
        key = str(uid)
        if key not in self.accounts: self.register_account(key)
        account = self.accounts[key]
        old_exp = int(account.get('exp', 0) or 0)
        new_exp = int(exp or 0)
        delta = max(0, new_exp - old_exp)
        account['exp'] = new_exp
        account['level'] = int(level or account.get('level', 1))
        account['gained_exp'] = int(account.get('gained_exp', 0) or 0) + delta
        self.total_exp_gained += delta
    def increment_match(self, uid):
        key = str(uid); game_id = self.auth_to_game_id.get(key, key)
        if game_id in self.accounts:
            self.accounts[game_id]['matches'] = int(self.accounts[game_id].get('matches', 0)) + 1
        self.total_matches += 1; self.matches_started += 1
    def is_paused(self, uid): return str(uid) in self.paused_accounts


bot_state = RBCBotState()
ACTIVE_GROUPS = {}

# ═══════════════════════ CONFIG ═══════════════════════
WEB_HOST = "0.0.0.0"; WEB_PORT = 20333
ACCOUNTS_FILE = "accounts.json"
TOKEN_CACHE_FILE = "token_cache.json"
DEVICES_FILE = "devices.json"
TOKEN_CACHE_TTL = 4500
API_PORT = 6293; API_BIND = '0.0.0.0'
API_KEY = b'Yg&tc%DEuh6%Zc^8'; API_IV = b'6oyZDr22E3ychjM%'
ApiTimeout = 15.0; ApiRetry = 2

START_MATCH_INTERVAL    = 4.0
NEW_MATCH_DELAY         = 6.0
MAX_MATCH_DURATION      = 3000
MATCH_IDLE_TIMEOUT      = 90.0
EXP_REFRESH_INTERVAL    = 30.0
EXP_REFRESH_AFTER_MATCH_DELAY = 9.0
MAX_CONSECUTIVE_PARSE_FAILURES = 5
NON_MATCH_RECONNECT_DELAY      = 1.0

BR_MODE_ID             = 1
BR_MAP_ID              = 1

ANTI_AFK_MIN_INTERVAL  = 1.8
ANTI_AFK_MAX_INTERVAL  = 3.5

MATCH_SEARCH_TIMEOUT   = 90.0
MATCH_WATCHDOG_CHECK   = 30.0
REGION_ROTATION_LIST   = ["ID", "SG", "TH", "MY", "VN", "PH"]
REGION_ROTATE_EVERY_N  = 2
MAX_SEARCH_ATTEMPTS    = 25

SAFE_PLAY_MODE        = True
BYPASS_TIMING_JITTER  = True
BYPASS_PACKET_JITTER  = True
BYPASS_HELLO_DELAY    = True
BYPASS_KA_JITTER      = True

# (movement constants kept for compat; real movement handled by ff_match)
ENABLE_SPEED_MOVEMENT       = True
MOVEMENT_PATTERN            = "circle"
MOVEMENT_TICK_MS            = 100
MOVEMENT_RADIUS             = 180

ENABLE_HTTP_PING = True
PING_INTERVAL    = 20.0
PING_TIMEOUT     = 8.0
PING_URL         = "https://loginbp.ppmainecoonghj.com/Ping"
PING_REAL_IP     = "103.109.214.211"

FALLBACK_UID = ""
FALLBACK_PASSWORD = ""

TEAM_MODE               = True
TEAM_SIZE               = 4
TEAM_PEER_WAIT_TIMEOUT  = 90.0
TEAM_CREATE_WAIT        = 4.0
TEAM_INVITE_CYCLE_WAIT  = 4.0
TEAM_INVITE_MAX_TIME    = 120.0
TEAM_HEARTBEAT_INTERVAL = 3.0
TEAM_IDLE_ITERS_TEAM    = 1800
TEAM_MEMBER_START_DELAY = 20.0
TEAM_FINAL_WAIT         = 8.0
TEAM_READY_DELAY        = 5.0
_accept_friend_request  = True
DEBUG_TEAM_PACKETS      = True


def bypass_jitter(base, spread=0.35):
    if not (SAFE_PLAY_MODE and BYPASS_TIMING_JITTER): return base
    return max(0.05, base + random.uniform(-spread, spread))
def bypass_packet_jitter(base, spread_ratio=0.35):
    if not (SAFE_PLAY_MODE and BYPASS_PACKET_JITTER): return base
    return max(0.1, base + random.uniform(-base * spread_ratio, base * spread_ratio))
def bypass_hello_delay():
    if not (SAFE_PLAY_MODE and BYPASS_HELLO_DELAY): return 0.0
    return random.uniform(0.05, 0.45)
def bypass_ka_jitter(base=5.0):
    if not (SAFE_PLAY_MODE and BYPASS_KA_JITTER): return base
    return max(3.0, base + random.uniform(-0.8, 1.2))
def bypass_human_reconnect_delay(attempt):
    if not (SAFE_PLAY_MODE and BYPASS_TIMING_JITTER): return min(attempt * 0.5, 2.0)
    return max(0.05, min(attempt * 0.5, 2.0) + random.uniform(-0.4, 0.7))


def get_device_for_account(account_identifier):
    devices = {}
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                devices = json.load(f)
        except Exception: pass
    key = str(account_identifier)
    if key in devices: return devices[key]
    dev_list = [
        ("Samsung", "SM-G998B", "Adreno (TM) 660", "Android OS 12 / API-31"),
        ("Xiaomi", "2201122G", "Adreno (TM) 730", "Android OS 13 / API-33"),
        ("Realme", "RMX3700", "Mali-G710", "Android OS 14 / API-34"),
        ("OnePlus", "CPH2451", "Adreno (TM) 740", "Android OS 13 / API-33"),
        ("OPPO", "CPH2611", "Adreno (TM) 720", "Android OS 14 / API-34"),
    ]
    brand, model, gpu, os_ver = random.choice(dev_list)
    dev = {
        "unique_device_id": f"Google|{uuid.uuid4()}",
        "brand": brand, "model": model, "gpu_renderer": gpu, "system_software": os_ver,
        "screen_width": random.choice([1080, 1440, 720]),
        "screen_height": random.choice([2400, 3200, 1600]),
        "screen_dpi": str(random.randint(300, 420)),
        "memory": random.randint(2800, 6500),
        "processor_details": f"ARM64 FP ASIMD AES | {random.randint(2200, 3200)} | {random.randint(6, 12)}",
        "client_ip": f"{random.randint(103, 223)}.{random.randint(10, 250)}.{random.randint(10, 250)}.{random.randint(10, 250)}",
    }
    devices[key] = dev
    try:
        with open(DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(devices, f, indent=2)
    except Exception: pass
    return dev


_DNS_CACHE: Dict[str, Tuple[str, float]] = {}
_DNS_CACHE_TTL = 300.0
async def resolve_host_cloudflare(hostname):
    if not hostname: return hostname
    parts = hostname.split('.')
    if len(parts) == 4 and all(p.isdigit() for p in parts): return hostname
    now = time.time()
    if hostname in _DNS_CACHE:
        ip, exp = _DNS_CACHE[hostname]
        if now < exp: return ip
    try:
        loop = asyncio.get_running_loop()
        info = await loop.getaddrinfo(hostname, None, family=socket.AF_INET)
        if info:
            ip = info[0][4][0]
            _DNS_CACHE[hostname] = (ip, now + _DNS_CACHE_TTL)
            return ip
    except Exception: pass
    return hostname

def optimize_tcp_socket(sock):
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
    except Exception: pass
def optimize_udp_socket(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
    except Exception: pass

client = httpx.AsyncClient(verify=False, timeout=10.0,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=50))
headers = {
    'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection': 'Keep-Alive', 'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-Unity-Version': '2018.4.12f1', 'X-GA-SV': '1789535859',
    'X-GA': 'v1 1', 'ReleaseVersion': 'OB55'
}

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

# ═══════════════════════ LOGGING ═══════════════════════
class Colors:
    GREEN='\033[92m'; FAIL='\033[91m'; WARNING='\033[93m'
    CYAN='\033[96m'; MAGENTA='\033[95m'; WHITE='\033[97m'
    GOLD='\033[38;5;220m'; BOLD='\033[1m'; DIM='\033[2m'; ENDC='\033[0m'
RBC_TAG = f"{Colors.GOLD}[AVI-GLORY]{Colors.ENDC}"

def _rbc_banner():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{Colors.GOLD}════════════════════════════════════════════════════════════════════{Colors.ENDC}", flush=True)
    print(f"{Colors.GOLD}[AVI] TEAM AVI SQUAD · HOMER 5506 · TOKEN API · {now}{Colors.ENDC}", flush=True)
    print(f"{Colors.GOLD}════════════════════════════════════════════════════════════════════{Colors.ENDC}\n", flush=True)

def print_colored(t, c=Colors.WHITE):
    try: print(f"{c}{t}{Colors.ENDC}", flush=True)
    except Exception: pass
def print_success(t):
    try:
        print(f"{RBC_TAG} {Colors.GREEN}[+] {t}{Colors.ENDC}", flush=True)
        if bot_state is not None and hasattr(bot_state, "log"): bot_state.log(t, "success")
    except Exception: pass
def print_error(t):
    try:
        print(f"{RBC_TAG} {Colors.FAIL}[-] {t}{Colors.ENDC}", flush=True)
        if bot_state is not None and hasattr(bot_state, "log"): bot_state.log(t, "error")
    except Exception: pass
def print_warning(t):
    try:
        print(f"{RBC_TAG} {Colors.WARNING}[!] {t}{Colors.ENDC}", flush=True)
        if bot_state is not None and hasattr(bot_state, "log"): bot_state.log(t, "warning")
    except Exception: pass
def print_info(t):
    try:
        print(f"{RBC_TAG} {Colors.CYAN}[i] {t}{Colors.ENDC}", flush=True)
        if bot_state is not None and hasattr(bot_state, "log"): bot_state.log(t, "info")
    except Exception: pass

# ═══════════════════════ PROTOBUF / CRYPTO ═══════════════════════
def get_proto_field(d, key, default=None):
    if not d or not isinstance(d, dict): return default
    if key in d:
        v = d[key].get('data') if isinstance(d[key], dict) else d[key]
        return v if v is not None else default
    if str(key) in d:
        v = d[str(key)].get('data') if isinstance(d[str(key)], dict) else d[str(key)]
        return v if v is not None else default
    return default

def encode_varint(n):
    if n < 0: return b''
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def build_proto(fields):
    parts = []
    for k, v in fields.items():
        if isinstance(v, dict):
            nested = build_proto(v)
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(nested)) + nested)
        elif isinstance(v, int):
            parts.append(encode_varint((k << 3) | 0) + encode_varint(v))
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(ev)) + ev)
    return b''.join(parts)

def _pb_varint(fn, val): return encode_varint((fn << 3) | 0) + encode_varint(val)
def _pb_length(fn, val):
    enc = val.encode('utf-8') if isinstance(val, str) else val
    return encode_varint((fn << 3) | 2) + encode_varint(len(enc)) + enc

def create_proto(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(field, str): field = int(field)
        if isinstance(value, dict):
            packet.extend(_pb_length(field, bytes(create_proto(value))))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    packet.extend(_pb_length(field, bytes(create_proto(item))))
                elif isinstance(item, str): packet.extend(_pb_length(field, item))
                elif isinstance(item, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(item)))
                elif isinstance(item, bool): packet.extend(_pb_varint(field, 1 if item else 0))
                elif isinstance(item, int): packet.extend(_pb_varint(field, item))
        elif isinstance(value, bool): packet.extend(_pb_varint(field, 1 if value else 0))
        elif isinstance(value, int): packet.extend(_pb_varint(field, value))
        elif isinstance(value, str): packet.extend(_pb_length(field, value))
        elif isinstance(value, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(value)))
    return bytes(packet)

# Safe wrapper for homor_rudp — fixes "str << int" error
def _roles_proto(fields):
    try:
        return create_proto(fields)
    except Exception:
        try:
            return create_protobuf_packet(fields)
        except Exception:
            return b""

def encrypt_api(plain_hex):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(
        pad(bytes.fromhex(plain_hex), AES.block_size)).hex()
def encrypt_api_bytes(plain_bytes):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain_bytes, AES.block_size))

def decode_protobuf_dict_safe(data):
    try:
        parsed = Parser().parse(data)
        return _recursive_dict(parsed)
    except Exception: return {}
def _recursive_dict(results):
    out = {}
    for r in results:
        fd = {"wire_type": r.wire_type}
        if r.wire_type in ("varint", "string", "bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            if hasattr(r.data, "results"): fd["data"] = _recursive_dict(r.data.results)
            elif isinstance(r.data, list): fd["data"] = _recursive_dict(r.data)
            else: fd["data"] = str(r.data)
        out[str(r.field)] = fd
    return out
async def parse_results(parsed):
    out = {}
    for r in parsed:
        fd = {"wire_type": r.wire_type}
        if r.wire_type in ("varint", "string", "bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            fd["data"] = await parse_results(r.data.results)
        out[r.field] = fd
    return out
async def decode_protobuf(data):
    parsed = Parser().parse(data)
    return json.dumps(await parse_results(parsed))

def _decode_proto_manual(data):
    result = {}; offset = 0; data_len = len(data)
    while offset < data_len:
        header = 0; shift = 0
        while offset < data_len:
            b = data[offset]; offset += 1
            header |= (b & 0x7F) << shift
            if not (b & 0x80): break
            shift += 7
            if shift > 28: break
        if header == 0: break
        fn = header >> 3; wt = header & 0x7
        if fn == 0: break
        if wt == 0:
            v = 0; shift = 0
            while offset < data_len:
                b = data[offset]; offset += 1
                v |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
                if shift > 63: break
            result[fn] = v
        elif wt == 2:
            length = 0; shift = 0
            while offset < data_len:
                b = data[offset]; offset += 1
                length |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
                if shift > 28: break
            if length > data_len - offset: break
            value = data[offset:offset+length]; offset += length
            try:
                s = value.decode('utf-8')
                if s and all(31 < ord(c) < 127 or ord(c) in (9,10,13) for c in s):
                    result[fn] = s
                else:
                    nested = _decode_proto_manual(value)
                    result[fn] = nested if nested else value.hex()
            except UnicodeDecodeError:
                nested = _decode_proto_manual(value)
                result[fn] = nested if nested else value.hex()
        elif wt == 5: offset += 4
        elif wt == 1: offset += 8
        else: break
    return result

def _wrap_manual(inner):
    try:
        alt = _decode_proto_manual(inner)
        if alt and len(alt) > 0:
            return {str(k): {"data": v} for k, v in alt.items()}
    except Exception: pass
    return None

# ═══════════════════════ JWT EXTRACTION ═══════════════════════
def _rd_var(B, Pos, End):
    V = 0; Sh = 0
    while Pos < End:
        X = B[Pos]; Pos += 1
        V |= (X & 0x7F) << Sh
        if not (X & 0x80): break
        Sh += 7
        if Sh > 63: break
    return V, Pos

def _walk_proto(B, Pos=0, End=None, depth=0):
    import struct as _st
    if depth > 20: return {}
    if End is None: End = len(B)
    Out = {}
    while Pos < End:
        try:
            Tag, Pos = _rd_var(B, Pos, End)
            F = Tag >> 3; W = Tag & 7
            if F == 0: break
            if W == 0:
                V, Pos = _rd_var(B, Pos, End)
                Out.setdefault(F, []).append(V)
            elif W == 2:
                Ln, Pos = _rd_var(B, Pos, End)
                if Pos + Ln > End: break
                Raw = B[Pos:Pos + Ln]; Pos += Ln
                DecOk = False
                try:
                    S = Raw.decode("utf-8")
                    if all(C.isprintable() or C in "\n\r\t" for C in S):
                        Out.setdefault(F, []).append(S); DecOk = True
                except Exception: pass
                if not DecOk:
                    Sub = None
                    try:
                        Sub = _walk_proto(Raw, 0, len(Raw), depth + 1)
                        if not Sub: Sub = None
                    except Exception: Sub = None
                    Out.setdefault(F, []).append(Sub if Sub else Raw.hex())
            elif W == 5:
                V = _st.unpack_from("<f", B, Pos)[0]; Pos += 4
                Out.setdefault(F, []).append(V)
            elif W == 1:
                V = _st.unpack_from("<d", B, Pos)[0]; Pos += 8
                Out.setdefault(F, []).append(V)
            else: break
        except Exception: break
    return Out

def _find_proto_root(Raw):
    for I in range(min(len(Raw) - 10, 256)):
        if Raw[I] in (0x08, 0x12):
            try:
                T = _walk_proto(Raw, I, len(Raw))
                if 1 in T and isinstance(T[1][0], int) and T[1][0] > 100000000: return I, T
                if 2 in T and isinstance(T[2][0], str) and T[2][0].isalpha(): return I, T
            except Exception: continue
    return 0, {}

def _search_jwt_in_vals(Vals):
    if not isinstance(Vals, list): Vals = [Vals]
    for V in Vals:
        if isinstance(V, str):
            if V.startswith("eyJ") and V.count(".") == 2 and len(V) > 100: return V
            if len(V) > 20 and all(C in "0123456789abcdefABCDEF" for C in V):
                try:
                    Dec = bytes.fromhex(V)
                    Idx = Dec.find(b"eyJ")
                    if Idx != -1:
                        Allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_."
                        End = Idx
                        while End < len(Dec) and Dec[End] in Allowed: End += 1
                        Cand = Dec[Idx:End].decode("ascii", errors="ignore")
                        if Cand.count(".") == 2 and len(Cand) > 100: return Cand
                except Exception: pass
        elif isinstance(V, dict):
            Found = _extract_jwt_from_tree(V)
            if Found: return Found
        elif isinstance(V, list):
            Found = _search_jwt_in_vals(V)
            if Found: return Found
    return None

def _extract_jwt_from_tree(Tree):
    if not isinstance(Tree, dict): return None
    V8 = Tree.get(8) or Tree.get("8")
    if V8:
        F = _search_jwt_in_vals(V8)
        if F: return F
    for Fnum, Vals in Tree.items():
        F = _search_jwt_in_vals(Vals)
        if F: return F
    return None

def extract_jwt_from_raw(Raw: bytes) -> Optional[str]:
    if not Raw: return None
    Off, Tree = _find_proto_root(Raw)
    Jwt = _extract_jwt_from_tree(Tree)
    if Jwt: return Jwt
    Marker = b"eyJ"; Start = Raw.find(Marker)
    while Start != -1:
        Allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_."
        End = Start
        while End < len(Raw) and Raw[End] in Allowed: End += 1
        Cand = Raw[Start:End].decode("utf-8", errors="ignore")
        if Cand.count(".") == 2 and len(Cand) > 100: return Cand
        Start = Raw.find(Marker, Start + 1)
    return None

def tree_flat(Tree):
    Out = {}
    for K, V in Tree.items():
        if isinstance(V, list) and len(V) == 1: Out[str(K)] = V[0]
        else: Out[str(K)] = V
    return Out

# ═══════════════════════ TOKEN CACHE ═══════════════════════
_token_cache_memo = {}; _token_cache_memo_time = 0.0
_TOKEN_CACHE_MEMO_TTL = 5.0

def _json_serializer(obj):
    if isinstance(obj, (bytes, bytearray)): return {"__bytes_hex__": bytes(obj).hex()}
    raise TypeError(f"not serializable: {type(obj)}")
def _json_deserializer(obj):
    if isinstance(obj, dict):
        if "__bytes_hex__" in obj and len(obj) == 1:
            try: return bytes.fromhex(obj["__bytes_hex__"])
            except Exception: return b""
        return {k: _json_deserializer(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_json_deserializer(x) for x in obj]
    return obj

def _load_token_cache():
    global _token_cache_memo, _token_cache_memo_time
    now = time.time()
    if _token_cache_memo and (now - _token_cache_memo_time) < _TOKEN_CACHE_MEMO_TTL: return _token_cache_memo
    if not os.path.exists(TOKEN_CACHE_FILE): return {}
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content: return {}
        data = json.loads(content)
        if not isinstance(data, dict): raise ValueError("root must be dict")
        parsed = _json_deserializer(data)
        _token_cache_memo = parsed; _token_cache_memo_time = now
        return parsed
    except Exception as e:
        print_error(f"Token cache corrupt: {e}")
        try: os.remove(TOKEN_CACHE_FILE)
        except Exception: pass
        return {}

def _save_token_cache(cache):
    global _token_cache_memo, _token_cache_memo_time
    try:
        tmp = TOKEN_CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, default=_json_serializer)
        os.replace(tmp, TOKEN_CACHE_FILE)
        _token_cache_memo = cache; _token_cache_memo_time = time.time()
    except Exception as e: print_error(f"Cache save: {e}")

def cache_get(uid):
    cache = _load_token_cache()
    e = cache.get(str(uid))
    if not e: return None
    if time.time() - e.get("cached_at", 0) > TOKEN_CACHE_TTL:
        cache_invalidate(uid); return None
    if str(e.get("account_id", "")).isdigit(): e["account_id"] = int(e["account_id"])
    if not isinstance(e.get("login_payload_data"), (bytes, bytearray)):
        cache_invalidate(uid); return None
    return e

def cache_set(uid, data):
    cache = _load_token_cache()
    e = dict(data); e["cached_at"] = time.time()
    cache[str(uid)] = e; _save_token_cache(cache)
    print_success(f"[CACHE] Saved UID {uid}")

def cache_invalidate(uid):
    cache = _load_token_cache()
    if str(uid) in cache:
        del cache[str(uid)]; _save_token_cache(cache)

def _update_cache_profile(data, level, exp):
    try:
        keys = []
        if data.get('auth_uid'): keys.append(str(data['auth_uid']))
        if data.get('auth_token'): keys.append(f"tok_{data['auth_token'][:20]}")
        if not keys: return
        cache = _load_token_cache(); ch = False
        for k in keys:
            if k in cache and isinstance(cache[k], dict):
                cache[k]['level'] = level; cache[k]['exp'] = exp; ch = True
        if ch: _save_token_cache(cache)
    except Exception: pass

# ═══════════════════════ AES / VERSION ═══════════════════════
async def aes_encrypt(payload, key, iv):
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(payload, AES.block_size))

async def get_playstore_version():
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, lambda: play_scraper('com.dts.freefireth', lang='hi', country='id'))
    return res.get("version")

async def version_config():
    app_version = await get_playstore_version()
    url = ("https://version.ggwhitehawk.com/live/ver.php"
           f"?version={app_version}&lang=hi&device=android&channel=android"
           "&appstore=googleplay&region=ID&whitelist_version=1.3.0&whitelist_sp_version=1.0.0")
    try:
        r = await client.get(url); r.raise_for_status()
        d = r.json()
        su = d.get("server_url"); rv = d.get("remote_version"); lr = d.get("latest_release_version")
        if not su or not rv or not lr: return None
        return lr, rv, su
    except Exception: return None

async def get_access_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br", "Connection": "close"
    }
    data = {
        "uid": uid, "password": password, "response_type": "token", "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    for attempt in range(5):
        try:
            r = await client.post(url, headers=hdrs, data=data)
            if r.status_code == 200:
                d = r.json()
                oid = d.get("open_id"); at = d.get("access_token"); pf = d.get("platform", 4)
                if oid and at: return oid, at, pf
            if r.status_code == 429: await asyncio.sleep(1); continue
        except Exception: pass
        await asyncio.sleep(0.5)
    return None

# ═══════════════════════ MAJORLOGIN ═══════════════════════
async def build_majorlogin_payload(open_id, access_token, platform, client_version, dev):
    try:
        arch = str(dev.get("cpu_architecture", "64"))
        if arch == "32":
            lib_path = "/data/app/com.dts.freefireth-XXXXXXXX==/lib/arm"
            lib_token = f"{secrets.token_hex(16)}|/data/app/com.dts.freefireth-XXXXXXXX==/base.apk"
        else:
            lib_path = "/data/app/~~6Cw028g_ld-8Z0z2qhrOLA==/com.dts.freefireth-i3wiaEmpx8CbiRVhUMx_ag==/lib/arm64"
            lib_token = f"b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~6Cw028g_ld-8Z0z2qhrOLA==/com.dts.freefireth-i3wiaEmpx8CbiRVhUMx_ag==/base.apk"
        p = {
            3: str(int(time.time())),
            4: "free fire", 5: "1",
            7: str(client_version) if client_version else "1.132.16",
            8: str(dev.get("system_software", "Android OS 14 / API-34")),
            9: "Handheld",
            10: str(dev.get("telecom_operator", "airtel")),
            11: "CarrierDataNetwork",
            12: str(dev.get("screen_width", 1600)),
            13: str(dev.get("screen_height", 720)),
            14: str(dev.get("screen_dpi", 320)),
            15: str(dev.get("processor_details", "ARMv7 VFPv3 NEON | 2001 | 8")),
            16: str(dev.get("memory", 3790)),
            17: str(dev.get("gpu_renderer", "PowerVR Rogue GE8320")),
            18: "OpenGL ES 3.2 build 1.11@5425693",
            19: str(dev.get("unique_device_id", f"Google|{uuid.uuid4()}")),
            20: str(dev.get("client_ip", "106.202.108.146")),
            21: str(dev.get("language", "en")),
            22: str(open_id), 23: str(platform),
            24: "Handheld",
            25: str(dev.get("model", "Xiaomi M2006C3LII")),
            26: str(dev.get("country_code", "IN")),
            29: str(access_token), 30: "1",
            41: str(dev.get("telecom_operator", "airtel")),
            42: str(dev.get("network_type_a", "4G")),
            57: "1ac4b80ecf0478a44203bf8fac6120f5",
            60: str(dev.get("external_storage_total", 53041)),
            61: str(dev.get("external_storage_available", 7291)),
            62: str(dev.get("internal_storage_total", 2176)),
            64: str(dev.get("game_disk_storage_available", 7395)),
            65: str(dev.get("game_disk_storage_total", 53041)),
            66: str(dev.get("external_sdcard_avail_storage", 7395)),
            67: str(dev.get("external_sdcard_total_storage", 53041)),
            70: 4, 73: 2, 74: lib_path, 76: 1, 77: lib_token,
            78: 6, 79: 1, 81: arch,
            83: "2019121227", 85: 3, 86: "OpenGLES2", 87: 3071,
            88: 4, 89: 9329, 93: "3rd_party",
            94: str(dev.get("extra_info", "KqsHT3r+fXQIu/dyZrEa8fJBhbJ5uqDES7YsAUfu+Mck9A+Bly6lFfYk7Q7Nj68pqI8I3g4Oz3gLxWef6Eh/jKyzHug=")),
            95: "111207",
            96: '{"cur_rate":null,"support_etc2":false}',
            97: "1", 98: str(platform), 99: str(platform), 100: str(platform),
            103: "1", 104: "47591", 105: "1",
            106: "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/|https://core-bs.ggpolarbear.com/live/ABHotUpdates/|1c2462939e53942fc995400436a3dc7b",
            107: "c8e41b7a93f02d56e1a94c7b8203f5d1",
        }
        return encrypt_api_bytes(build_proto(p))
    except Exception as e:
        print_error(f"build_majorlogin_payload: {e}")
        return None

async def send_majorlogin(data, release_version, server_url):
    try:
        url = f"{server_url}MajorLogin" if server_url.endswith('/') else f"{server_url}/MajorLogin"
        hdrs = headers.copy(); hdrs["ReleaseVersion"] = str(release_version)
        r = await client.post(url, headers=hdrs, data=data)
        if r.status_code != 200: return None
        c = r.content
        if len(c) < 40: return None
        for off in [0, 64] + list(range(128)):
            try:
                m = thunderFF_pb2.MajorLoginRes(); m.ParseFromString(c[off:])
                if m.region and m.token:
                    jwt = extract_jwt_from_raw(c)
                    if jwt:
                        try: setattr(m, 'jwt_token', jwt)
                        except Exception: pass
                    return m
            except Exception: continue
        off, tree = _find_proto_root(c)
        flat = tree_flat(tree)
        jwt = extract_jwt_from_raw(c)
        acc_id = flat.get("1") or flat.get(1)
        region = flat.get("2") or flat.get(2)
        token  = flat.get("8") or flat.get(8) or jwt
        if acc_id and token:
            m = thunderFF_pb2.MajorLoginRes()
            try: m.account_id = int(acc_id)
            except Exception: pass
            try: m.region = str(region or "ID")
            except Exception: pass
            try: m.token = str(token)
            except Exception: pass
            for attr, keys in (("aes_ak", [6, 12]), ("iv_i", [7, 13]),
                               ("server_time", [3, 14]), ("url", [10, 15])):
                for kk in keys:
                    v = flat.get(str(kk)) or flat.get(kk)
                    if v is not None:
                        try: setattr(m, attr, v if isinstance(v, (int, bytes)) else str(v))
                        except Exception: pass
                        break
            return m
        return None
    except Exception as e:
        print_error(f"[MAJORLOGIN] {e}"); return None

async def send_getlogin(data, base_url, token, release_version):
    try:
        url = f"{base_url.rstrip('/')}/GetLoginData"
        hdrs = headers.copy()
        hdrs["ReleaseVersion"] = release_version
        hdrs['Authorization'] = f"Bearer {token}"
        hdrs['Host'] = "clientbp.ppmainecoonghj.com"
        r = await client.post(url, headers=hdrs, data=data)
        if r.status_code != 200: return None
        c = r.content
        rp = thunderFF_pb2.GetLoginDataRes(); ok = False
        try:
            rp.ParseFromString(c)
            if rp.functional_addrs or rp.informational_addrs: ok = True
        except Exception: pass
        if not ok:
            for off in range(min(128, len(c))):
                try:
                    cand = thunderFF_pb2.GetLoginDataRes(); cand.ParseFromString(c[off:])
                    if cand.functional_addrs or cand.informational_addrs:
                        rp = cand; ok = True; break
                except Exception: continue
        dd = {}
        try:
            off, tree = _find_proto_root(c)
            dd_raw = tree_flat(tree)
            dd = {str(k): {"data": v} for k, v in dd_raw.items()}
            if not ok and (dd_raw.get("14") or dd_raw.get(14)):
                rp.functional_addrs = str(dd_raw.get("14") or dd_raw.get(14)); ok = True
        except Exception: pass
        if not dd:
            try:
                parsed = Parser().parse(c.hex())
                dd = await parse_results(parsed)
            except Exception: pass
        return rp, dd
    except Exception: return None

# ═══════════════════════ HTTP PING ═══════════════════════
async def send_ping(account_id, token, release_version):
    try:
        try: acc = int(account_id)
        except Exception: acc = 0
        now_ms = int(time.time() * 1000)
        payload = struct.pack("<Q", acc & 0xFFFFFFFFFFFFFFFF) + struct.pack("<Q", now_ms & 0xFFFFFFFFFFFFFFFF)
        req_id = secrets.token_urlsafe(18)[:22]
        hdrs = {
            'accept': '*/*', 'accept-encoding': 'deflate, gzip',
            'authorization': f'Bearer {token}',
            'content-type': 'application/x-www-form-urlencoded',
            'releaseversion': release_version,
            'user-agent': 'UnityPlayer/2018.4.12f1',
            'x-ga': 'v1 1', 'x-ga-sv': str(int(time.time())),
            'x-railway-edge': 'sin1', 'x-railway-request-id': req_id,
            'x-real-ip': PING_REAL_IP, 'x-request-start': str(now_ms),
            'x-unity-version': '2018.4.12f1',
        }
        r = await client.post(PING_URL, headers=hdrs, content=payload, timeout=PING_TIMEOUT)
        return r.status_code == 200
    except Exception: return False

async def ping_worker(account_id, token, release_version, region="ID"):
    if not ENABLE_HTTP_PING: return
    uid_str = str(account_id); ok_count = 0; fails = 0
    try:
        await asyncio.sleep(5.0 + random.uniform(0, 2.0))
        while True:
            ok = await send_ping(uid_str, token, release_version)
            if ok:
                ok_count += 1; fails = 0
                if ok_count % 10 == 0: print_info(f"[PING] {uid_str} OK total={ok_count}")
            else:
                fails += 1
                if fails <= 3: print_warning(f"[PING] {uid_str} fail #{fails}")
            await asyncio.sleep(max(5.0, PING_INTERVAL + random.uniform(-3.0, 3.0)))
    except asyncio.CancelledError: pass

# ═══════════════════════ TCP STARTUP / KEEPALIVE ═══════════════════════
async def build_tcp_startup_packet(account_id, token, server_time, key, iv, region="ID", typ='OnLine'):
    uid_hex = f"{int(account_id):016x}"
    ts_hex = f"{int(server_time):08x}"
    enc = (await aes_encrypt(token.encode(), key, iv)).hex()
    enc_len = f"{len(enc)//2:08x}"
    reg = str(region).upper() if region else "ID"
    if typ == 'OnLine':
        pfx = '7119' if reg == 'ID' else ('7114' if reg == 'IND' else '7115')
        return f"{pfx}{uid_hex}{ts_hex}00000000{enc_len}{enc}"
    pfx = '9219' if reg == 'ID' else ('9214' if reg == 'IND' else '9215')
    return f"{pfx}{uid_hex}{ts_hex}{enc_len}{enc}"

async def send_keep_alive(region="ID"):
    try:
        reg = str(region).upper() if region else "ID"
        return bytes.fromhex("0219" if reg == "ID" else ("0214" if reg == "IND" else "0215"))
    except Exception:
        return bytes.fromhex("0219")

# ═══════════════════════ TEAM PACKETS ═══════════════════════
def create_packet(Pk, N, K, V):
    if isinstance(K, str): K = bytes.fromhex(K) if len(K) == 32 else K.encode()
    if isinstance(V, str): V = bytes.fromhex(V) if len(V) == 32 else V.encode()
    PkEnc = AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(Pk), 16)).hex()
    L = len(PkEnc) // 2
    hexlen = hex(L)[2:]
    if len(hexlen) % 2 != 0: hexlen = '0' + hexlen
    pad_len = 12 - len(N) - len(hexlen)
    if pad_len < 0: pad_len = 0
    return bytes.fromhex(N + ('0' * pad_len) + hexlen + PkEnc)

# Use live client version (OB55 = 1.132.16 typically)
def _team_game_version():
    try:
        return str(config.LIVE.client_version or "1.132.16")
    except Exception:
        return "1.132.16"

def create_team(key, iv, game_version=None):
    if game_version is None: game_version = _team_game_version()
    fields = {
        1: 1, 2: {2: bytes.fromhex("01"), 3: 1, 4: 3, 5: "en",
            8: {1: "IDC3", 2: 123, 3: "ID"}, 9: 1,
            10: bytes.fromhex("01090a0b1219202729"), 11: 2, 13: 1,
            14: {1: "08FBA33B4BABE2790205390333330000009700050092005F72697EB2134DCBB2467625142201040e38e848dc0e748c3f6aa04d81000000ff1113090dcacfa16d",
                 2: 478, 3: "7e585d55", 4: "y[Z]", 6: 12, 7: "15686677735a7506101c",
                 8: str(game_version), 9: 3, 10: 1, 11: "03626253513637754174"},
            19: 329, 21: bytes.fromhex("374f521955"), 24: {1: 21},
            27: "a_6534489873065906362"}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def team_fresh(account_id, key, iv):
    return create_packet(create_proto({1: 72, 2: {1: int(account_id)}}).hex(), "0515", key, iv)

def invite_player_in_team(target_uid, key, iv, region="ID"):
    return create_packet(create_proto({1: 2, 2: {1: int(target_uid), 2: region, 4: 1}}).hex(),
                         "0515", key, iv)

def start_match_team(account_id, key, iv, region="ID"):
    fields = {1: 9, 2: {1: int(account_id), 7: {1: "IDC3", 2: 410, 3: region}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def ready_for_game(uid, key, iv):
    return create_packet(create_proto({1: 15, 2: {1: int(uid), 2: 1}}).hex(), "0519", key, iv)

def accept_team_invite(target_uid, group_id, key, iv):
    gv = _team_game_version()
    fields = {1: 4, 2: {1: int(target_uid), 3: int(target_uid),
        4: bytes.fromhex("0107090a0b120f19202729"), 8: 1,
        9: {1: "08FBA33B0522052002041B0222220007000C00010004000547E265AE1080779546762514110104076fa2e8770e748c3f6a68ed75000000ff08080500cacfa16d",
            2: 235, 3: {14: 80, 11: 86}, 4: "{Y\\R", 6: 13, 7: {2: 4},
            8: gv, 9: 2, 10: 1, 11: "0362625351"},
        10: str(group_id),
        11: {"1": "IDC3", "2": 107, "3": "ID"}, 13: "en", 16: "374f5219",
        20: {1: 21}, 23: "a_6534489873065906362",
        24: "https://dl-sg-production.freefiremobile.com/",
        27: {1: 2, 2: 4}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

# ═══════════════════════ BR SEARCH ═══════════════════════
BR_HEX = (
    "080112800a0a010110013a110a044944433110aa011a064555524f50453a100a044944433210311a064555524f5045"
    "40014a0801090a0b1219202758016291090a80013038384638324246303241393637363730323031303130303030"
    "30303030303030303031363030303130303135303030323232463937454545304630303030303034363736323531"
    "34303030303030303030303030303030303030303030303030303030303030303030303030306666303030303030"
    "3030636163666131366410241afb02735d5e571400024a775d45414d1a041b1c001f11010449715f4243481a001e"
    "1d071c1703004b1a4066785c524570735c51486775421b5c5a4c07504042685a63610816054e19025e7519600147"
    "7c015165406370195f5547404e4550640103020f1304064863754268676c755f65576e40467e5f0a417a4701026d"
    "675d6e73670b1108495a4c6a0b78470b740065645e525a057258425f584a447d4e6759440c11044e7c596d7f4b62"
    "5f7d04055a47505c4e1d6b5b4107447d7201057d7f0f14084e430457674f7e517d72015172415d027473577c4d61"
    "5f79535256780911030f4d5e027a797f614165067806505d53777750475e75064257076500460817014e741e7e50"
    "78487e7a7c465e7669767153497064605a7376677773550d160148037e18675966787f4c42607a645f577e7b44"
    "1b460776026b18685d0b110205490060020f70676175654674706671797f41067346677c4e06585e780f15074c57"
    "047b40517075415f6364027259674b5b0166407f7340600407770a22047a5d5c52300b3a0a167305067162727516"
    "134208312e3133302e3232480350015ae90403626253513635686e556f4e36416456324b796f566c636f47777648"
    "4f624e56526c4d727073504b4f43654177616848494176795556497273743752737149734a7a786b324752526837"
    "7a2f637664626d504f6a73552f79626d38547a4c69586d2f474351696d494b53486833447955726f39515152756c"
    "34545350626d6d624b7949565937545671577059455372323646572f59624578507338514f706d317372785455736c"
    "30796a434144444d4f34616a654b615753366361496c554b4963797a494e396d52516f715277687939797257476d"
    "337a644345337a6a61436f492f5a585233656f65365a42647a64677654636b6b665733356e4d4c6a6a56507256"
    "4b6433523172756174394e50514150724a5546627859696c4c5a3859707336654d5447666b6649793574666a526c"
    "314d4648706b51774c6373374439656378566c41636f374e664f6d2b30654756466c443474447870677138553359"
    "5973587645384842502f70666c767a737138316a32524f4d7857437556445442492f684735625462773166456e42"
    "49725162762b636144775147696f74554e316d4c4b77734379456f4766706746614251457645672b736a764c4c78"
    "704743334c304a5344532f74526169504354553344374e6249306547516651622f5a466f4c36455630775a324d6f"
    "583932414c572f5049752f56634663584e70596b356f7966326151416a536971486a2f363276354843644f525551"
    "303578754e6171795251625653704654303137655237675255636b4966366c6f447476342b514e4a4670766d7475"
    "7077707774396a5a5974437a4b56743657726d6e36785837706658456251555434684f3758a201050803108703a2"
    "01050804108103a20105080510c001a20105081d10cc01a2010408161078a20105080e10af01a201020815"
)
async def start_game_battle_royale(region, client_version, writer, key, iv):
    packet = bytes.fromhex(BR_HEX)
    try:
        enc = (await aes_encrypt(packet, key, iv)).hex()
        plen = len(enc) // 2
        hl = hex(plen)[2:]
        hl = hl if len(hl) > 1 else "0" + hl
        reg = str(region).upper() if region else "BD"
        pfx = "031500" if reg == "ID" else ("031400" if reg == "IND" else "031500")
        final = pfx + "0" * (6 - len(hl)) + hl + enc
        writer.write(bytes.fromhex(final)); await writer.drain()
        print_info(f"[BR] search sent ({plen}B) R={reg}")
    except Exception as e:
        print_warning(f"[BR] search error: {e}")

# ═══════════════════════ MATCH COUNTERS ═══════════════════════
_match_counters: Dict[str, int] = {}
_match_counter_lock = asyncio.Lock()
async def _inc_match(uid):
    async with _match_counter_lock:
        _match_counters[uid] = _match_counters.get(uid, 0) + 1
        return _match_counters[uid]
async def _dec_match(uid):
    async with _match_counter_lock:
        if uid in _match_counters and _match_counters[uid] > 0: _match_counters[uid] -= 1
        return _match_counters.get(uid, 0)
async def _get_match_count(uid):
    async with _match_counter_lock: return _match_counters.get(uid, 0)
async def _get_total_match_count():
    async with _match_counter_lock: return sum(_match_counters.values())

# ═══════════════════════ TEAM STATE ═══════════════════════
_team_state = {
    "peers": {}, "leader_uid": None, "team_code": None, "pk_code": None,
    "members": set(), "members_lock": asyncio.Lock(), "lock": asyncio.Lock(),
}
async def _team_member_join(uid):
    uid = str(uid)
    async with _team_state["members_lock"]:
        before = len(_team_state["members"])
        _team_state["members"].add(uid)
        after = len(_team_state["members"])
    if after != before:
        print_success(f"[TEAM] 👥 In team ({after}/{TEAM_SIZE}) | joined: {uid}")
    return after
async def _team_member_leave(uid):
    async with _team_state["members_lock"]:
        _team_state["members"].discard(str(uid))
async def _team_member_count():
    async with _team_state["members_lock"]: return len(_team_state["members"])
async def _team_member_reset(keep_leader=True):
    async with _team_state["members_lock"]:
        _team_state["members"].clear()
        if keep_leader and _team_state["leader_uid"]:
            _team_state["members"].add(_team_state["leader_uid"])

# ═══════════════════════ HOMER ROLE SETUP ═══════════════════════
async def prepare_homer_roles(ad: dict):
    token = ad.get("token")
    server_url = ad.get("server_url")
    release = ad.get("release_version", "OB55")
    if not token or not server_url:
        print_warning("[HOMER] missing token/server")
        return False
    try:
        ok = await homor_rudp.init_homor_roles(
            token, server_url, release,
            encrypt_aes_fn=encrypt_api,
            create_proto_fn=_roles_proto,   # ← FIX: safe wrapper
        )
        if ok:
            try: config.LIVE.set_skill(skill_id=homor_rudp.SKILL_HOMOR)
            except Exception: pass
            print_success(f"[HOMER] skill {homor_rudp.SKILL_HOMOR} armed")
        return ok
    except Exception as e:
        print_warning(f"[HOMER] role setup failed: {e}")
        return False

# ═══════════════════════ MATCH PLAY (delegate to toolsudp) ═══════════════════════
async def play_game(server_ip_port, udp_token, udp_key, real_match_id,
                    account_id, player_region, client_version,
                    key, iv, match_index,
                    on_match_complete=None, account_data=None):
    """
    In-match UDP is fully handled by toolsudp.run_match():
      • raw AES auth packet (disabled via config.Use_Auth_Packet=False)
      • TEA HELLO handshake
      • Cmd 447 / 448 join (uses match_id NOT match_code)
      • MovementPlanner (follow-mode movement)
      • ActiveSession.use_skill → Homer skill 5506 via cmd 248
      • Fire / pickup / switch weapon
      • Cmd 2000 server-time sync
      • End-of-match claim + lobby calls
    """
    uid_str = str(account_id)
    loop = asyncio.get_running_loop()
    game_mode = getattr(config, "Clash_Mode", 15)
    # toolsudp.run_match expects (host, port, ... udp_jwt ...)
    host, port_s = server_ip_port.split(":")
    port = int(port_s)

    def _blocking_run():
        try:
            toolsudp.run_match(
                host, port,
                int(account_id),
                udp_key,
                udp_token,      # full UDP JWT
                "",             # sharma is empty — ff_match splits internally
                suffix="0",
                game_mode=game_mode,
                map_id=1,
                match_mode=1,
                sleep_ms=0,
                timeout=6.0,
                api_token=(account_data or {}).get('access_token', ''),
                match_id=int(real_match_id or 0),
                verbose=True,
            )
            return True
        except Exception as e:
            print_error(f"[MATCH #{match_index}] {e}")
            return False

    try:
        print_colored(
            f"[MATCH #{match_index}] toolsudp -> {server_ip_port} "
            f"(match_id={real_match_id} mode={game_mode})",
            Colors.MAGENTA)
        ok = await loop.run_in_executor(None, _blocking_run)
        if ok:
            try: bot_state.increment_match(uid_str)
            except Exception: pass
            if on_match_complete:
                try: await on_match_complete()
                except Exception: pass
        return f"match #{match_index} {'finished' if ok else 'failed'}"
    except asyncio.CancelledError: raise
    except Exception as e:
        print_error(f"[MATCH #{match_index}] {e}")
        return f"match #{match_index} error"

# ═══════════════════════ SOCIAL / FRIEND ═══════════════════════
async def _process_social_packet(raw_bytes, account_data, tag="MAIN"):
    try:
        hex_data = raw_bytes.hex()
        candidates = []
        if len(raw_bytes) >= 6:
            plen = raw_bytes[4]
            if 0 < plen <= (len(raw_bytes) - 5):
                try:
                    inner = bytes(raw_bytes[5:5 + plen])
                    d0 = decode_protobuf_dict_safe(inner) or _wrap_manual(inner)
                    if d0: candidates.append((5, d0))
                except Exception: pass
        for off in [5, 6, 10, 8, 12, 4, 0]:
            if off >= len(hex_data): continue
            try: inner = bytes.fromhex(hex_data[off:])
            except Exception: continue
            decoded = decode_protobuf_dict_safe(inner) or _wrap_manual(inner)
            if decoded: candidates.append((off, decoded))
        if not candidates: return
        candidates.sort(key=lambda x: len(x[1]) if isinstance(x[1], dict) else 0, reverse=True)
        _, decoded = candidates[0]
        def _v(c, k):
            if not isinstance(c, dict): return None
            v = c.get(k) if k in c else c.get(str(k))
            if isinstance(v, dict) and "data" in v: return v["data"]
            return v
        f5w = decoded.get("5") or decoded.get(5) if isinstance(decoded, dict) else None
        f5 = f5w["data"] if isinstance(f5w, dict) and "data" in f5w else f5w
        target = None
        if isinstance(f5, dict):
            for fk in [1, 2, 3, 4, 6]:
                c = _v(f5, fk)
                if c and str(c).isdigit() and 6 <= len(str(c)) <= 15:
                    target = str(c); break
        if not target: return
        own = str(account_data.get('account_id', '')) if account_data else ''
        if own and target == own: return
        if not _accept_friend_request or not account_data: return
        jwt = account_data.get('token'); srv = account_data.get('server_url')
        rel = account_data.get('release_version'); own_id = account_data.get('account_id')
        if not (jwt and srv and rel and own_id): return
        url = f"{srv.rstrip('/')}/ConfirmFriendRequest"
        fields = {1: int(target), 2: int(own_id)}
        try:
            payload = bytes.fromhex(encrypt_api(create_proto(fields).hex()))
            hdrs = {
                "authorization": f"Bearer {jwt}",
                "host": srv.replace("https://", "").replace("http://", "").split("/")[0],
                "x-ga": "v1 1", "content-type": "application/x-www-form-urlencoded",
                "accept-encoding": "deflate, gzip", "releaseversion": f"{rel}",
                "user-agent": "UnityPlayer/2022.3.47f1", "accept": "*/*",
                "x-unity-version": "2022.3.47f1",
            }
            async with httpx.AsyncClient(verify=False, timeout=8.0) as s:
                r = await s.post(url, headers=hdrs, content=payload)
                if r.status_code == 200 and len(r.content) > 0:
                    print_success(f"[FRIEND-{tag}] ✅ {target}")
        except Exception: pass
    except Exception: pass

async def _handle_team_invite(hex_data, pl, uid_str, current_account_data,
                              current_key, current_iv, writer):
    try:
        candidates = []
        for off in [10, 8, 6, 12, 14, 4, 16, 0, 20, 2]:
            if off >= len(hex_data) or len(hex_data) - off < 4: continue
            try: inner = bytes.fromhex(hex_data[off:])
            except Exception: continue
            dec = decode_protobuf_dict_safe(inner)
            if dec and isinstance(dec, dict) and len(dec) > 0:
                candidates.append((off, dec)); continue
        if not candidates: return False
        candidates.sort(key=lambda x: len(x[1]) if isinstance(x[1], dict) else 0, reverse=True)
        _, dec = candidates[0]
        def _g(d, k):
            if not isinstance(d, dict): return None
            v = d.get(k) if k in d else d.get(str(k))
            if isinstance(v, dict) and "data" in v: return v["data"]
            return v
        group_id = None
        for k in list(dec.keys()):
            c = _g(dec, k)
            if isinstance(c, str) and 20 <= len(c) <= 40:
                group_id = c; break
        own_acc = str(current_account_data.get('account_id')) if current_account_data else None
        inviter = None
        for k in list(dec.keys()):
            c = _g(dec, k)
            if c and str(c).isdigit() and 6 <= len(str(c)) <= 15:
                if str(c) != uid_str and str(c) != own_acc:
                    inviter = str(c); break
        is_member = (_team_state["leader_uid"] != uid_str)
        if inviter and group_id and is_member:
            async with _team_state["members_lock"]:
                if uid_str in _team_state["members"]: return True
            print_success(f"[TEAM-IN {uid_str}] accept invite from {inviter}")
            for attempt in range(3):
                try:
                    acc = accept_team_invite(int(inviter), group_id, current_key, current_iv)
                    if writer and not writer.is_closing():
                        writer.write(acc); await writer.drain()
                        await _team_member_join(uid_str)
                        return True
                except Exception as e:
                    print_warning(f"[TEAM-IN] err: {e}")
                await asyncio.sleep(0.8)
        return False
    except Exception as e:
        print_warning(f"[TEAM-IN] error: {e}"); return False

# ═══════════════════════ INFORMATIONAL ═══════════════════════
async def informational(addrs, starter_packet, key, iv, region="ID", max_reconnects=3):
    reconnects = 0
    ip, port = addrs.split(":")
    while True:
        writer = None; ping_task = None
        try:
            rip = await resolve_host_cloudflare(ip)
            reader, writer = await asyncio.open_connection(rip, int(port))
            rs = writer.get_extra_info('socket')
            if rs: optimize_tcp_socket(rs)
            writer.write(bytes.fromhex(starter_packet)); await writer.drain()
            reconnects = 0
            try:
                ka = await send_keep_alive(region)
                if ka and not writer.is_closing():
                    writer.write(ka); await asyncio.wait_for(writer.drain(), timeout=3)
            except Exception: pass
            async def info_ka():
                ka = await send_keep_alive(region)
                while True:
                    await asyncio.sleep(bypass_ka_jitter(5.0))
                    try:
                        if writer and not writer.is_closing():
                            writer.write(ka); await writer.drain()
                    except Exception: break
            ping_task = asyncio.create_task(info_ka())
            while True:
                data = await reader.read(8192)
                if not data: raise ConnectionError("closed")
        except asyncio.CancelledError:
            if ping_task: ping_task.cancel()
            if writer:
                try: writer.close(); await writer.wait_closed()
                except Exception: pass
            raise
        except Exception:
            if ping_task: ping_task.cancel()
            if writer:
                try: writer.close(); await writer.wait_closed()
                except Exception: pass
            reconnects += 1
            if reconnects > max_reconnects:
                await asyncio.sleep(3); reconnects = 0
            else: await asyncio.sleep(1)

# ═══════════════════════ FUNCTIONAL BATTLE ROYALE (squad) ═══════════════════════
async def functional_battle_royale(addrs, starter_packet, account_region, client_version,
                                    key, iv, account_id="", account_data=None,
                                    account_level=2, max_reconnects=10):
    ip, port = addrs.split(":")
    play_matches: List[asyncio.Task] = []
    no_response_count = 0
    search_attempts = 0
    uid_str = str(account_id)
    current_level = int(account_level or 2)
    consecutive_parse_failures = 0
    current_token = starter_packet
    current_key = key; current_iv = iv
    current_account_data = account_data
    reconnect_count_total = 0
    region_index = 0
    current_search_region = REGION_ROTATION_LIST[0]
    _writer_ref = {"w": None}
    _team_active = {"flag": True}

    async def trigger_post_match_refresh():
        await asyncio.sleep(EXP_REFRESH_AFTER_MATCH_DELAY)
        try:
            cd = bot_state.account_credentials.get(uid_str)
            if cd: await refresh_account_profile(cd)
        except Exception: pass

    async def _team_coordinator():
        """Leader: create team → invite → ready → start."""
        try:
            deadline = time.time() + TEAM_PEER_WAIT_TIMEOUT
            while time.time() < deadline:
                async with _team_state["lock"]:
                    n = len(_team_state["peers"])
                if n >= TEAM_SIZE: break
                if bot_state.is_paused(uid_str): return
                await asyncio.sleep(0.5)
            async with _team_state["lock"]:
                n = len(_team_state["peers"])
                is_leader = (_team_state["leader_uid"] == uid_str)
                peers_snapshot = dict(_team_state["peers"])
            if not is_leader:
                print_info(f"[TEAM] {uid_str} is member (waiting)")
                return
            if n < TEAM_SIZE:
                print_warning(f"[TEAM] Only {n}/{TEAM_SIZE} peers online")
            else:
                print_success(f"[TEAM] ✅ {n} peers online")
            await asyncio.sleep(TEAM_READY_DELAY)

            # create team
            print_success(f"[TEAM] 👑 {uid_str} creating team...")
            own_id_num = current_account_data.get('account_id', uid_str) if current_account_data else uid_str
            try:
                pkt = create_team(current_key, current_iv)
                if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                    _writer_ref["w"].write(pkt); await _writer_ref["w"].drain()
                    print_info(f"[TEAM] create_team sent ({len(pkt)}B)")
                    await _team_member_reset(keep_leader=False)
                    await _team_member_join(uid_str)
            except Exception as e:
                print_error(f"[TEAM] create_team: {e}")

            await asyncio.sleep(TEAM_CREATE_WAIT)

            peer_uids = []
            for peer_uid, info in peers_snapshot.items():
                if peer_uid == uid_str: continue
                pa = None
                try: pa = info["data"].get("account_id")
                except Exception: pass
                if not pa: pa = peer_uid
                peer_uids.append(int(pa))
            print_info(f"[TEAM] invite list: {peer_uids}")

            heartbeat_stop = asyncio.Event()
            async def heartbeat_loop():
                while not heartbeat_stop.is_set():
                    try:
                        if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                            pkt = team_fresh(int(own_id_num), current_key, current_iv)
                            _writer_ref["w"].write(pkt); await _writer_ref["w"].drain()
                    except Exception: pass
                    try: await asyncio.wait_for(heartbeat_stop.wait(), timeout=TEAM_HEARTBEAT_INTERVAL)
                    except asyncio.TimeoutError: pass
            hb_task = asyncio.create_task(heartbeat_loop())

            print_success(f"[TEAM] 🎯 invite loop (max {int(TEAM_INVITE_MAX_TIME)}s)")
            invite_start = time.time(); cycle = 0
            while time.time() - invite_start < TEAM_INVITE_MAX_TIME:
                if not _team_active["flag"]: break
                cnt = await _team_member_count()
                if cnt >= TEAM_SIZE:
                    print_success(f"[TEAM] 🎉 Full ({cnt}/{TEAM_SIZE})")
                    break
                cycle += 1
                for tuid in peer_uids:
                    async with _team_state["members_lock"]:
                        joined = str(tuid) in _team_state["members"]
                    if joined: continue
                    try:
                        inv = invite_player_in_team(tuid, current_key, current_iv, region=account_region)
                        if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                            _writer_ref["w"].write(inv); await _writer_ref["w"].drain()
                            print_success(f"[TEAM] 📨 invite {tuid} cyc#{cycle}")
                    except Exception as e:
                        print_warning(f"[TEAM] invite err: {e}")
                    await asyncio.sleep(0.5)
                try: await asyncio.wait_for(heartbeat_stop.wait(), timeout=TEAM_INVITE_CYCLE_WAIT)
                except asyncio.TimeoutError: pass

            final_cnt = await _team_member_count()
            print_colored(f"[TEAM] FINAL in team ({final_cnt}/{TEAM_SIZE})", Colors.MAGENTA)
            heartbeat_stop.set()
            try: hb_task.cancel(); await hb_task
            except Exception: pass
            if final_cnt < TEAM_SIZE:
                print_error(f"[TEAM] only {final_cnt}/{TEAM_SIZE} — abort")
                return
            await asyncio.sleep(TEAM_FINAL_WAIT)

            print_success(f"[TEAM] 🚀 {uid_str} ready→start loop")
            while _team_active["flag"]:
                try:
                    oid = current_account_data.get('account_id', own_id_num) if current_account_data else own_id_num
                    try:
                        rdy = ready_for_game(int(oid), current_key, current_iv)
                        if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                            _writer_ref["w"].write(rdy); await _writer_ref["w"].drain()
                    except Exception as e: print_warning(f"[TEAM] ready: {e}")
                    await asyncio.sleep(1.0)
                    sm = start_match_team(int(oid), current_key, current_iv, region=account_region)
                    if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                        _writer_ref["w"].write(sm); await _writer_ref["w"].drain()
                except Exception as e: print_warning(f"[TEAM] start: {e}")
                try: await asyncio.wait_for(asyncio.sleep(5.0), timeout=5.5)
                except asyncio.TimeoutError: pass
        except asyncio.CancelledError: raise
        except Exception as e:
            print_error(f"[TEAM] coordinator: {e}")
            traceback.print_exc()

    async def _member_match_trigger():
        try:
            await asyncio.sleep(TEAM_READY_DELAY + TEAM_MEMBER_START_DELAY)
            async with _team_state["lock"]:
                if _team_state["leader_uid"] == uid_str: return
            print_success(f"[TEAM] 🚀 Member {uid_str} ready→start loop")
            my_id = current_account_data.get('account_id', uid_str) if current_account_data else uid_str
            while _team_active["flag"]:
                try:
                    if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                        try:
                            rdy = ready_for_game(int(my_id), current_key, current_iv)
                            _writer_ref["w"].write(rdy); await _writer_ref["w"].drain()
                        except Exception as e: print_warning(f"[TEAM] member ready: {e}")
                        await asyncio.sleep(1.0)
                        sm = start_match_team(int(my_id), current_key, current_iv, region=account_region)
                        _writer_ref["w"].write(sm); await _writer_ref["w"].drain()
                except Exception as e: print_warning(f"[TEAM] member start: {e}")
                try: await asyncio.wait_for(asyncio.sleep(5.0), timeout=5.5)
                except asyncio.TimeoutError: pass
        except asyncio.CancelledError: raise
        except Exception as e: print_warning(f"[TEAM] member: {e}")

    try:
        while True:
            writer = None; gateway_ping_task = None
            team_coord_task = None; member_trigger_task = None
            try:
                if current_account_data:
                    fresh = None
                    if current_account_data.get('auth_type') == 'guest' and current_account_data.get('auth_uid'):
                        fresh = cache_get(str(current_account_data['auth_uid']))
                    elif current_account_data.get('auth_type') == 'token' and current_account_data.get('auth_token'):
                        fresh = cache_get(f"tok_{current_account_data['auth_token'][:20]}")
                    if fresh:
                        current_account_data = fresh
                        current_key = fresh['aes_ak']; current_iv = fresh['iv_i']
                        current_token = await build_tcp_startup_packet(
                            fresh['account_id'], fresh['token'], fresh['server_time'],
                            current_key, current_iv,
                            region=fresh.get('region', account_region), typ='OnLine')
                        try:
                            lv = int(fresh.get('level', current_level) or current_level)
                            if lv != current_level: current_level = lv
                        except Exception: pass
                    else:
                        print_warning(f"[FUNC] Cache miss {uid_str} -> re-login")
                        try:
                            if current_account_data.get('auth_uid'):
                                cache_invalidate(str(current_account_data['auth_uid']))
                            if current_account_data.get('auth_token'):
                                cache_invalidate(f"tok_{current_account_data['auth_token'][:20]}")
                        except Exception: pass
                        raise ConnectionError("Cache expired")

                rip = await resolve_host_cloudflare(ip)
                reader, writer = await asyncio.open_connection(rip, int(port))
                _writer_ref["w"] = writer
                raw_sock = writer.get_extra_info('socket')
                if raw_sock: optimize_tcp_socket(raw_sock)
                await asyncio.sleep(bypass_hello_delay())
                writer.write(bytes.fromhex(current_token)); await writer.drain()
                try:
                    ka = await send_keep_alive(account_region)
                    if ka and not writer.is_closing():
                        writer.write(ka); await asyncio.wait_for(writer.drain(), timeout=3)
                except Exception: pass
                async def func_gateway_keepalive():
                    ka_bytes = await send_keep_alive(account_region)
                    while True:
                        await asyncio.sleep(bypass_ka_jitter(5.0))
                        try:
                            if writer and not writer.is_closing():
                                writer.write(ka_bytes); await writer.drain()
                        except Exception: break
                gateway_ping_task = asyncio.create_task(func_gateway_keepalive())
                connection_start_time = asyncio.get_running_loop().time()
                last_watchdog_check = connection_start_time
                search_attempts = 0
                if reconnect_count_total > 0 and (reconnect_count_total % REGION_ROTATE_EVERY_N == 0):
                    region_index = (region_index + 1) % len(REGION_ROTATION_LIST)
                    current_search_region = REGION_ROTATION_LIST[region_index]
                    print_warning(f"[REGION ROTATE] {uid_str} -> {current_search_region}")
                else:
                    current_search_region = REGION_ROTATION_LIST[region_index]
                print_success(f"[FUNC] TCP connected {uid_str} (DNS:{rip} Lvl:{current_level} R:{current_search_region})")

                async with _team_state["lock"]:
                    _team_state["peers"][uid_str] = {
                        "writer": writer, "data": current_account_data,
                        "key": current_key, "iv": current_iv}
                    if _team_state["leader_uid"] is None:
                        _team_state["leader_uid"] = uid_str
                        print_success(f"[TEAM] 👑 {uid_str} is leader")

                if TEAM_MODE:
                    team_coord_task = asyncio.create_task(_team_coordinator())
                    member_trigger_task = asyncio.create_task(_member_match_trigger())
                else:
                    await start_game_battle_royale(current_search_region, client_version, writer, current_key, current_iv)

                while True:
                    play_matches[:] = [m for m in play_matches if not m.done()]
                    active = await _get_match_count(uid_str)
                    try: bot_state.update_status(uid_str, "ONLINE" if active == 0 else "IN_MATCH", active)
                    except Exception: pass
                    now = asyncio.get_running_loop().time()
                    if now - last_watchdog_check >= MATCH_WATCHDOG_CHECK:
                        last_watchdog_check = now
                        sd = now - connection_start_time
                        if sd > 30: print_warning(f"[WATCHDOG] {uid_str} {int(sd)}s att={search_attempts}")
                        if sd > MATCH_SEARCH_TIMEOUT: raise ConnectionError("Search watchdog")
                    if search_attempts >= MAX_SEARCH_ATTEMPTS: raise ConnectionError("Max attempts")
                    try:
                        data = await asyncio.wait_for(reader.read(8192), timeout=0.5)
                    except asyncio.TimeoutError:
                        no_response_count += 1
                        if TEAM_MODE:
                            if no_response_count > TEAM_IDLE_ITERS_TEAM: raise ConnectionError("Team idle")
                        else:
                            if no_response_count > 80: raise ConnectionError("idle")
                        continue
                    if not data: raise ConnectionError("closed")
                    hex_data = data.hex(); pl = len(data)
                    no_response_count = 0
                    if DEBUG_TEAM_PACKETS and not hex_data.startswith("0300") and not hex_data.startswith("0600"):
                        print_info(f"[RAW-IN {uid_str}] len={pl} prefix={hex_data[:24]}")
                    if hex_data.startswith("0600") and pl > 20:
                        await _process_social_packet(data, current_account_data, tag="MAIN"); continue
                    if hex_data.startswith("05") and pl > 10:
                        await _handle_team_invite(hex_data, pl, uid_str, current_account_data,
                                                  current_key, current_iv, writer); continue
                    if hex_data.startswith("0300") and 10 < pl < 30: continue
                    if hex_data.startswith("0300") and pl >= 300:
                        print_colored("=" * 60, Colors.GREEN)
                        print_colored("MATCH FOUND! Loading...", Colors.GREEN)
                        print_colored("=" * 60, Colors.GREEN)
                        for tk in (team_coord_task, member_trigger_task):
                            if tk and not tk.done():
                                tk.cancel()
                                try: await tk
                                except asyncio.CancelledError: pass
                        team_coord_task = None; member_trigger_task = None
                        _team_active["flag"] = False
                        try:
                            res = json.loads(await decode_protobuf(hex_data[10:]))
                            token = udp_key = match_code = server_ip_port = None
                            match_account_id = block_val = None
                            real_match_id = 0
                            if '42' in res and 'data' in res['42']:
                                match_code = str(res['42']['data'])
                            if '5' in res and 'data' in res['5']:
                                r5 = res['5']['data']
                                server_ip_port = r5.get('2', {}).get('data')
                                udp_key = r5.get('3', {}).get('data')
                                token = r5.get('4', {}).get('data')
                                block_val = r5.get('1', {}).get('data')
                                if '42' in r5 and not match_code:
                                    match_code = str(r5['42']['data'])
                                try:
                                    if block_val and int(block_val) > 1000000000000:
                                        real_match_id = int(block_val)
                                except Exception: pass
                            if '1' in res and 'data' in res['1']:
                                match_account_id = res['1']['data']
                                try:
                                    if int(match_account_id) > 1000000000000:
                                        real_match_id = int(match_account_id)
                                except Exception: pass
                            effective = match_account_id or account_id or "BD_BOT"
                            if token and udp_key and match_code and server_ip_port:
                                try:
                                    async with _team_state["lock"]:
                                        _team_state["pk_code"] = str(match_code)
                                except Exception: pass
                                print_colored(f"[PK] 🎯 Match ID: {real_match_id} (code={match_code})", Colors.MAGENTA)
                                print_colored(f"[PK] 🌐 Server: {server_ip_port}", Colors.MAGENTA)
                                print_colored(f"[PK] 🔑 UDP Key: {udp_key}", Colors.MAGENTA)
                                match_index = await _inc_match(uid_str)
                                print_colored(f"[MATCH #{match_index}] UDP -> {server_ip_port}", Colors.CYAN)
                                new_match = asyncio.create_task(play_game(
                                    server_ip_port, token, udp_key, real_match_id,
                                    effective, current_search_region, client_version,
                                    current_key, current_iv,
                                    match_index=match_index,
                                    on_match_complete=trigger_post_match_refresh,
                                    account_data=current_account_data))
                                play_matches.append(new_match)
                                consecutive_parse_failures = 0
                                async def drain_gw():
                                    while not new_match.done():
                                        try:
                                            dg = await asyncio.wait_for(reader.read(4096), timeout=1.0)
                                            if not dg: break
                                            gh = dg.hex()
                                            if gh.startswith("0600") and len(dg) > 20:
                                                await _process_social_packet(dg, current_account_data, tag="DRAIN")
                                        except asyncio.TimeoutError: continue
                                        except Exception: break
                                drain_task = asyncio.create_task(drain_gw())
                                try: await new_match
                                except Exception as e: print_error(f"[MATCH #{match_index}] {e}")
                                finally:
                                    drain_task.cancel()
                                    try: await drain_task
                                    except asyncio.CancelledError: pass
                                play_matches[:] = [m for m in play_matches if not m.done()]
                                async with _team_state["lock"]:
                                    _team_state["peers"].pop(uid_str, None)
                                    if _team_state["leader_uid"] == uid_str:
                                        _team_state["leader_uid"] = None
                                    _team_state["pk_code"] = None
                                await _team_member_leave(uid_str)
                                _team_active["flag"] = True
                                try: writer.close(); await writer.wait_closed()
                                except Exception: pass
                                print_info(f"[FUNC] {uid_str} reconnect in {NEW_MATCH_DELAY}s...")
                                await asyncio.sleep(NEW_MATCH_DELAY)
                                reconnect_count_total += 1
                                break
                            else:
                                consecutive_parse_failures += 1
                                print_warning(f"[FUNC] Non-match big pkt #{consecutive_parse_failures}")
                                try: writer.close(); await writer.wait_closed()
                                except Exception: pass
                                await asyncio.sleep(NON_MATCH_RECONNECT_DELAY)
                                break
                        except Exception as e:
                            print_error(f"[FUNC] Match parse: {e}")
                            consecutive_parse_failures += 1
                            try: writer.close(); await writer.wait_closed()
                            except Exception: pass
                            await asyncio.sleep(NON_MATCH_RECONNECT_DELAY)
                            break
                    if 30 <= pl <= 40: continue

            except asyncio.CancelledError:
                print_warning(f"[FUNC] Cancelled — {len(play_matches)} UDP")
                for m in play_matches:
                    if not m.done(): m.cancel()
                if play_matches: await asyncio.gather(*play_matches, return_exceptions=True)
                play_matches.clear()
                if gateway_ping_task: gateway_ping_task.cancel()
                async with _team_state["lock"]:
                    _team_state["peers"].pop(uid_str, None)
                    if _team_state["leader_uid"] == uid_str:
                        _team_state["leader_uid"] = None
                await _team_member_leave(uid_str)
                raise

            except Exception as e:
                if gateway_ping_task: gateway_ping_task.cancel()
                print_error(f"[FUNC] TCP {uid_str}: {e}")
                play_matches[:] = [m for m in play_matches if not m.done()]
                if writer:
                    try: writer.close(); await writer.wait_closed()
                    except Exception: pass
                if "Cache expired" in str(e):
                    print_warning(f"[FUNC] re-login {uid_str}")
                    break
                reconnect_count_total += 1
                await asyncio.sleep(bypass_human_reconnect_delay(1))

            finally:
                _team_active["flag"] = False
                for tk in (team_coord_task, member_trigger_task):
                    if tk and not tk.done():
                        tk.cancel()
                        try: await tk
                        except (asyncio.CancelledError, Exception): pass
                if gateway_ping_task: gateway_ping_task.cancel()
                if writer:
                    try: writer.close(); await writer.wait_closed()
                    except Exception: pass
                async with _team_state["lock"]:
                    _team_state["peers"].pop(uid_str, None)
                    if _team_state["leader_uid"] == uid_str:
                        _team_state["leader_uid"] = None
                await _team_member_leave(uid_str)
                _team_active["flag"] = True
    except asyncio.CancelledError:
        for m in play_matches:
            if not m.done(): m.cancel()
        if play_matches: await asyncio.gather(*play_matches, return_exceptions=True)
        play_matches.clear()
        raise

# ═══════════════════════ CREDENTIALS / REFRESH ═══════════════════════
def _register_credentials(ad):
    try:
        acc_id = str(ad['account_id'])
        bot_state.account_credentials[acc_id] = ad
        if ad.get('auth_uid'): bot_state.account_credentials[str(ad['auth_uid'])] = ad
        if ad.get('auth_token'): bot_state.account_credentials[f"tok_{ad['auth_token'][:20]}"] = ad
    except Exception: pass

async def refresh_account_profile(ad_or_uid):
    try:
        if isinstance(ad_or_uid, str):
            uid = str(ad_or_uid); ad = bot_state.account_credentials.get(uid)
        else:
            ad = ad_or_uid; uid = str(ad.get('account_id')) if ad else "?"
        if not ad: return
        url = ad.get('server_url'); token = ad.get('token')
        rel = ad.get('release_version'); payload = ad.get('login_payload_data')
        if not (url and token and rel and payload): return
        res = await send_getlogin(payload, url, token, rel)
        if not res: return
        rp, dd = res
        def _si(v, d):
            try:
                if v is None or v == "": return d
                return int(v)
            except Exception: return d
        level = _si(get_proto_field(dd, 6, None), None)
        exp = _si(get_proto_field(dd, 7, None), None)
        likes = _si(get_proto_field(dd, 8, None), None)
        try: nick = rp.nickname or get_proto_field(dd, 4, "") or ""
        except Exception: nick = ""
        if level is None and exp is None: return
        level = level if level is not None else 1
        exp = exp if exp is not None else 0
        likes = likes if likes is not None else 0
        acc_id = str(ad['account_id'])
        old_lv = 0; old_ex = 0
        try:
            if acc_id in bot_state.accounts:
                old_lv = int(bot_state.accounts[acc_id].get('level', 0) or 0)
                old_ex = int(bot_state.accounts[acc_id].get('exp', 0) or 0)
        except Exception: pass
        try: bot_state.update_exp(acc_id, exp, level)
        except Exception: pass
        if likes > 0 and acc_id in bot_state.accounts:
            bot_state.accounts[acc_id]["likes"] = likes
        if nick and acc_id in bot_state.accounts:
            bot_state.accounts[acc_id]["nickname"] = nick
        _update_cache_profile(ad, level, exp)
        ad['level'] = level; ad['exp'] = exp
        if likes > 0: ad['likes'] = likes
        if nick: ad['nickname'] = nick
        if old_lv > 0 and level > old_lv:
            print_success(f"[LEVEL UP] {acc_id}: {old_lv} -> {level}")
        elif old_ex != exp:
            print_success(f"[EXP] {acc_id} Lvl{level} +{exp - old_ex}")
    except Exception: pass

# ═══════════════════════ LOGIN ═══════════════════════
async def process_account_uid_pass(uid, password):
    cached = cache_get(uid)
    if cached:
        print_success(f"[CACHE] {uid} loaded")
        acc_id = str(cached['account_id'])
        bot_state.register_account(uid=acc_id,
            nickname=cached.get('nickname', f"Player_{acc_id}"),
            region=cached.get('region', 'ID'),
            level=cached.get('level', 1), exp=cached.get('exp', 0),
            likes=cached.get('likes', 0))
        _register_credentials(cached); return cached
    print_info(f"[LOGIN] UID {uid}...")
    try:
        vc = await version_config()
        if not vc: return None
        rel, cv, su = vc
        tg = await get_access_token(uid, password)
        if not tg: return None
        oid, at, pf = tg
        dev = get_device_for_account(uid)
        lpd = await build_majorlogin_payload(oid, at, pf, cv, dev)
        if not lpd: return None
        mresp = await send_majorlogin(lpd, rel, su)
        if mresp is None: return None
        gl = await send_getlogin(lpd, mresp.url, mresp.token, rel)
        if gl is None: return None
        rp, dd = gl
        acc_id = str(mresp.account_id)
        level = int(get_proto_field(dd, 6, 1) or 1)
        exp = int(get_proto_field(dd, 7, 0) or 0)
        likes = int(get_proto_field(dd, 8, 0) or 0)
        nick = rp.nickname or get_proto_field(dd, 4, f"Player_{acc_id}")
        region = mresp.region or get_proto_field(dd, 3, "ID")
        bot_state.register_account(uid=acc_id, nickname=nick, region=region,
                                    level=level, exp=exp, likes=likes)
        print_success(f"[OK] {acc_id} | {nick} | Lvl{level}")
        ad = {
            'account_id': mresp.account_id, 'nickname': nick, 'region': region,
            'level': level, 'exp': exp, 'likes': likes,
            'open_id': oid, 'access_token': at, 'platform': str(pf),
            'token': mresp.token, 'server_time': mresp.server_time,
            'aes_ak': mresp.aes_ak, 'iv_i': mresp.iv_i,
            'functional_addrs': rp.functional_addrs or get_proto_field(dd, 14),
            'informational_addrs': rp.informational_addrs or get_proto_field(dd, 32),
            'release_version': rel, 'client_version': cv, 'server_url': mresp.url,
            'login_payload_data': lpd,
            'auth_type': 'guest', 'auth_uid': uid, 'auth_password': password,
        }
        _register_credentials(ad); cache_set(uid, ad); return ad
    except Exception as e:
        print_error(f"process_account_uid_pass: {e}")
        traceback.print_exc(); return None

async def process_account_token(access_token):
    cache_key = f"tok_{access_token[:20]}"
    cached = cache_get(cache_key)
    if cached:
        acc_id = str(cached['account_id'])
        bot_state.register_account(uid=acc_id,
            nickname=cached.get('nickname', f"Player_{acc_id}"),
            region=cached.get('region', 'ID'),
            level=cached.get('level', 1), exp=cached.get('exp', 0),
            likes=cached.get('likes', 0))
        _register_credentials(cached); return cached
    print_info("[LOGIN] Token...")
    try:
        vc = await version_config()
        if not vc: return None
        rel, cv, su = vc
        import requests
        url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
        hdrs = {"User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)"}
        resp = await asyncio.to_thread(requests.get, url, headers=hdrs, timeout=10)
        d = resp.json()
        if 'error' in d: return None
        oid = d.get('open_id'); pf = d.get('platform', 4)
        if not oid: return None
        dev = get_device_for_account(oid)
        lpd = await build_majorlogin_payload(oid, access_token, str(pf), cv, dev)
        if not lpd: return None
        mresp = await send_majorlogin(lpd, rel, su)
        if mresp is None: return None
        gl = await send_getlogin(lpd, mresp.url, mresp.token, rel)
        if gl is None: return None
        rp, dd = gl
        acc_id = str(mresp.account_id)
        level = int(get_proto_field(dd, 6, 1) or 1)
        exp = int(get_proto_field(dd, 7, 0) or 0)
        likes = int(get_proto_field(dd, 8, 0) or 0)
        nick = rp.nickname or get_proto_field(dd, 4, f"Player_{acc_id}")
        region = mresp.region or get_proto_field(dd, 3, "ID")
        bot_state.register_account(uid=acc_id, nickname=nick, region=region,
                                    level=level, exp=exp, likes=likes)
        ad = {
            'account_id': mresp.account_id, 'nickname': nick, 'region': region,
            'level': level, 'exp': exp, 'likes': likes,
            'open_id': oid, 'access_token': access_token, 'platform': str(pf),
            'token': mresp.token, 'server_time': mresp.server_time,
            'aes_ak': mresp.aes_ak, 'iv_i': mresp.iv_i,
            'functional_addrs': rp.functional_addrs or get_proto_field(dd, 14),
            'informational_addrs': rp.informational_addrs or get_proto_field(dd, 32),
            'release_version': rel, 'client_version': cv, 'server_url': mresp.url,
            'login_payload_data': lpd,
            'auth_type': 'token', 'auth_token': access_token,
        }
        _register_credentials(ad); cache_set(cache_key, ad); return ad
    except Exception as e:
        print_error(f"process_account_token: {e}"); return None

# ═══════════════════════ ACCOUNT WORKER ═══════════════════════
async def run_account_worker(ad, label):
    acc_id = str(ad['account_id'])
    info_task = None; exp_task = None; ping_task = None
    try:
        # ── 1. Homer role setup (skill 5506) ──
        await prepare_homer_roles(ad)

        reg = ad.get('region', 'ID')
        try:
            config.LIVE.set_login(
                region=reg,
                country=ad.get('country_code') or reg[:2],
                client_host=ad.get('server_url'),
            )
            config.LIVE.set_versions(
                client=ad.get('client_version'),
                release=ad.get('release_version'),
            )
            config.LIVE.set_skill(skill_id=homor_rudp.SKILL_HOMOR)
        except Exception: pass

        tcp_online = await build_tcp_startup_packet(
            ad['account_id'], ad['token'], ad['server_time'],
            ad['aes_ak'], ad['iv_i'], region=reg, typ='OnLine')
        tcp_chat = await build_tcp_startup_packet(
            ad['account_id'], ad['token'], ad['server_time'],
            ad['aes_ak'], ad['iv_i'], region=reg, typ='ChaT')
        info_task = asyncio.create_task(informational(ad['informational_addrs'], tcp_chat,
                                                      ad['aes_ak'], ad['iv_i'], region=reg))
        if ENABLE_HTTP_PING:
            ping_task = asyncio.create_task(ping_worker(acc_id, ad['token'], ad['release_version'], region=reg))
            print_success(f"[PING] Started {acc_id}")
        async def exp_refresher():
            try:
                f = bot_state.account_credentials.get(acc_id)
                if f: await refresh_account_profile(f)
            except Exception: pass
            while True:
                await asyncio.sleep(EXP_REFRESH_INTERVAL + random.uniform(-3.0, 3.0))
                try:
                    f = bot_state.account_credentials.get(acc_id)
                    if f: await refresh_account_profile(f)
                except Exception: pass
        exp_task = asyncio.create_task(exp_refresher())
        await functional_battle_royale(ad['functional_addrs'], tcp_online, ad['region'], ad['client_version'],
            ad['aes_ak'], ad['iv_i'], account_id=acc_id, account_data=ad,
            account_level=int(ad.get('level', 2) or 2))
    except asyncio.CancelledError: raise
    except Exception as e: print_error(f"run_account_worker {label}: {e}")
    finally:
        for t in (info_task, exp_task, ping_task):
            if t and not t.done(): t.cancel()
        for t in (info_task, exp_task, ping_task):
            if t:
                try: await t
                except Exception: pass

async def account_loop_guest(uid, password):
    while True:
        try:
            print_info(f"[LOGIN] Guest {uid}...")
            try: bot_state.update_status(str(uid), "CONNECTING")
            except Exception: pass
            ad = await process_account_uid_pass(uid, password)
            if not ad:
                print_error(f"Login failed {uid}, retry 15s")
                try: bot_state.update_status(str(uid), "ERROR")
                except Exception: pass
                await asyncio.sleep(15); continue
            await run_account_worker(ad, uid)
            print_warning(f"Session end {uid}, reconnect 3s")
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            print_warning(f"Worker {uid} stopped")
            try: bot_state.update_status(str(uid), "OFFLINE")
            except Exception: pass
            break
        except Exception as e:
            print_error(f"Error {uid}: {e}, retry 10s")
            await asyncio.sleep(10)

async def account_loop_token(token):
    label = token[:10]
    while True:
        try:
            ad = await process_account_token(token)
            if not ad:
                print_error("Login token fail, retry 15s")
                await asyncio.sleep(15); continue
            acc_id = str(ad['account_id'])
            await run_account_worker(ad, acc_id)
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            print_warning(f"Token {label} stopped"); break
        except Exception as e:
            print_error(f"Token error: {e}, retry 10s")
            await asyncio.sleep(10)

def load_accounts():
    accounts = []
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list): accounts = data
        except Exception as e: print_error(f"load: {e}")
    if not accounts and FALLBACK_UID and FALLBACK_PASSWORD:
        accounts.append({"uid": FALLBACK_UID, "password": FALLBACK_PASSWORD})
    return accounts

# ═══════════════════════ FLASK TOKEN API ═══════════════════════
api_app = Flask(__name__)
logging.getLogger('werkzeug').disabled = True
api_app.logger.disabled = True
logging.getLogger('flask.app').disabled = True
Err = "<html><body><h1>503 Service Unavailable</h1>\nNo server is available to handle this request.\n</body></html>"
def ErrBlocked(): return Response(Err, status=503, mimetype="text/html")
def Pretty(obj): return Response(json.dumps(obj, indent=2, ensure_ascii=False), mimetype="application/json")

def GetLocalIp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]
    except Exception: ip = "127.0.0.1"
    finally: s.close()
    return ip

def Veraddr():
    r = httpx.get(
        "https://version.ggwhitehawk.com/live/ver.php",
        params={
            "version": "1.132.16", "lang": "hi", "device": "android",
            "channel": "android", "appstore": "googleplay", "region": "IND",
            "whitelist_version": "1.3.0", "whitelist_sp_version": "1.0.0",
        },
        timeout=15, verify=False,
    )
    d = r.json()
    return d["latest_release_version"], d["remote_version"], d["server_url"]

def OAuth(Uid, Pass):
    Hdr = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/5.5.2P3(SM-A515F;Android 12;en-US;IND;)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br", "Connection": "close",
    }
    Data = {
        "uid": Uid, "password": Pass, "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067",
    }
    for Attempt in range(ApiRetry + 1):
        try:
            R = httpx.post("https://100067.connect.garena.com/oauth/guest/token/grant",
                           headers=Hdr, data=Data, timeout=ApiTimeout, verify=False)
            if R.status_code == 200:
                J = R.json()
                return J.get("open_id"), J.get("access_token"), J.get("platform", 4), None
            if R.status_code == 429: return None, None, None, "Rate limited"
            if Attempt < ApiRetry:
                time.sleep(1); continue
            return None, None, None, f"HTTP {R.status_code}"
        except Exception as E:
            if Attempt < ApiRetry:
                time.sleep(1); continue
            return None, None, None, str(E)
    return None, None, None, "Unknown"

def Ins(Tok):
    for _ in range(ApiRetry + 1):
        try:
            R = httpx.get(f"https://100067.connect.garena.com/oauth/token/inspect?token={Tok}",
                          headers={"User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)"},
                          timeout=ApiTimeout, verify=False)
            return R.json()
        except Exception: time.sleep(1)
    return {}

def MjrLgn(Pay, Rls, Srv):
    if not Srv.endswith("/"): Srv = Srv + "/"
    url = f"{Srv}MajorLogin"
    Hdr = {
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*", "Authorization": "Bearer",
        "X-GA": "v1 1", "ReleaseVersion": Rls,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "Host": "loginbp.ppmainecoonghj.com",
        "X-GA-SV": str(int(time.time())),
    }
    Last = None
    for Attempt in range(ApiRetry + 1):
        try:
            R = httpx.post(url, headers=Hdr, content=Pay, timeout=ApiTimeout, verify=False)
            if R.status_code == 200: return R
            Last = f"HTTP {R.status_code}"
        except Exception as E: Last = str(E)
        if Attempt < ApiRetry: time.sleep(1)
    raise Exception(f"MajorLogin failed: {Last}")

@api_app.errorhandler(404)
def HandleNotFound(E): return ErrBlocked()
@api_app.errorhandler(405)
def HandleMethodNotAllowed(E): return ErrBlocked()
@api_app.errorhandler(500)
def HandleServerError(E): return ErrBlocked()

@api_app.route('/Ver', methods=['GET'])
@api_app.route('/ver', methods=['GET'])
@api_app.route('/addr', methods=['GET'])
@api_app.route('/Veraddr', methods=['GET'])
def Ver():
    try: Ver_, Ob_, LoginBp = Veraddr()
    except Exception: return ErrBlocked()
    if not Ver_ or not Ob_ or not LoginBp: return ErrBlocked()
    return Pretty({"Ob": Ob_, "Ver": Ver_, "LoginUrl": LoginBp}), 200

@api_app.route('/Tok', methods=['GET', 'POST'])
@api_app.route('/tok', methods=['GET', 'POST'])
@api_app.route('/Token', methods=['GET', 'POST'])
def Tok():
    params = (request.json or request.form.to_dict()) if request.method == 'POST' else request.args.to_dict()
    uid = params.get("uid", "").strip()
    password = params.get("pw", "").strip()
    accs = params.get("accs", "").strip()
    if not accs and (not uid or not password): return ErrBlocked()
    try: release, client, server_url = Veraddr()
    except Exception: return ErrBlocked()
    if not release or not client or not server_url: return ErrBlocked()
    Ob = release; Ver_ = client
    if accs:
        inf = Ins(accs)
        if not inf or 'error' in inf or not inf.get("open_id"): return ErrBlocked()
        oid = inf.get("open_id"); plat = inf.get("platform", 4); AccsTok = accs
    else:
        oid, AccsTok, plat, err = OAuth(uid, password)
        if err: return ErrBlocked()
    # Use async builder via asyncio.run
    dev = get_device_for_account(oid)
    try:
        payload = asyncio.run(build_majorlogin_payload(oid, AccsTok, str(plat), Ver_, dev))
    except Exception:
        return ErrBlocked()
    if not payload: return ErrBlocked()
    try: rsp = MjrLgn(payload, Ob, server_url)
    except Exception: return ErrBlocked()
    if rsp.status_code != 200: return ErrBlocked()
    raw = rsp.content
    off, tree = _find_proto_root(raw)
    flat = tree_flat(tree)
    Tok_ = extract_jwt_from_raw(raw)
    addr = flat.get("10") or server_url
    Uid = flat.get("1") or uid or ""
    if not Tok_:
        return Pretty({
            "AccsTok": AccsTok, "OpenId": oid, "addr": addr,
            "Tok": "Acc Banned", "Ver": Ver_, "Ob": Ob, "Uid": Uid, "Err": "Acc Ban",
        }), 200
    return Pretty({
        "AccsTok": AccsTok, "OpenId": oid, "addr": addr,
        "Tok": Tok_, "Ver": Ver_, "Ob": Ob, "Uid": Uid,
    }), 200

def run_api_server():
    def _serve():
        try:
            api_app.run(host=API_BIND, port=API_PORT, debug=False,
                        use_reloader=False, threaded=True)
        except Exception: pass
    threading.Thread(target=_serve, daemon=True).start()
    time.sleep(1.2)
    try: LanIp = GetLocalIp()
    except Exception: LanIp = "127.0.0.1"
    try: PublicIp = httpx.get("https://api.ipify.org", timeout=10, verify=False).text.strip()
    except Exception: PublicIp = "Unknown"
    print_success(f"[TOKEN-API] http://{PublicIp}:{API_PORT}  (local {LanIp}:{API_PORT})")
    return PublicIp

# ═══════════════════════ MAIN ═══════════════════════
async def main():
    _rbc_banner()
    try:
        autoupdate.shared().check(force=True)
        print_info(f"Server: {autoupdate.server_url()} | release {autoupdate.release_version()} | remote {autoupdate.remote_version()}")
    except Exception as e:
        print_warning(f"autoupdate: {e}")

    print_info(f"Match interval: {START_MATCH_INTERVAL}s | Offline: {NEW_MATCH_DELAY}s")
    print_info("Mode: SQUAD 4/4 · HOMER 5506 · MOVEMENT")
    print_info(f"Use_Auth_Packet = {getattr(config, 'Use_Auth_Packet', '?')} (must be False)")
    if TEAM_MODE:
        print_success(f"[SQUAD] size={TEAM_SIZE} peer_wait={TEAM_PEER_WAIT_TIMEOUT}s")
    print_colored("=" * 60, Colors.CYAN)

    try: run_api_server()
    except Exception as e: print_error(f"Token API: {e}")

    try:
        await start_web_dashboard(
            host=WEB_HOST, port=WEB_PORT, bot_state_arg=bot_state,
            active_groups=ACTIVE_GROUPS, create_accounts_func=None,
        )
        print_success(f"Dashboard: http://localhost:{WEB_PORT}")
    except Exception as e: print_error(f"Dashboard: {e}")

    async def on_account_added(data):
        if "token" in data and data["token"]:
            t = str(data["token"]).strip()
            task = asyncio.create_task(account_loop_token(t))
            bot_state.account_workers[t[:10]] = task
        elif "uid" in data and "password" in data:
            u = str(data["uid"]).strip(); p = str(data["password"]).strip()
            task = asyncio.create_task(account_loop_guest(u, p))
            bot_state.account_workers[u] = task
    async def on_refresh_account(uid): await refresh_account_profile(uid)
    try:
        bot_state.refresh_callbacks["on_account_added"] = on_account_added
        bot_state.refresh_callbacks["on_refresh_account"] = on_refresh_account
    except Exception: pass

    accounts = load_accounts()
    if not accounts: print_warning(f"No accounts in {ACCOUNTS_FILE}. Add via dashboard.")
    for acc in accounts:
        if acc.get("token"):
            t = asyncio.create_task(account_loop_token(acc["token"]))
            bot_state.account_workers[acc["token"][:10]] = t
        elif acc.get("uid") and acc.get("password"):
            u = str(acc["uid"])
            t = asyncio.create_task(account_loop_guest(u, acc["password"]))
            bot_state.account_workers[u] = t

    try:
        while True: await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print_warning("Shutting down...")
        for t in list(bot_state.account_workers.values()): t.cancel()
        await asyncio.gather(*bot_state.account_workers.values(), return_exceptions=True)
        print_success("Closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_warning("stopped")