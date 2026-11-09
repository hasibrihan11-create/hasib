# ============================================================
# RASIN  X  MEHEDI  —  homor_rudp.py  (ALL BUGS FIXED)
# TEA-CBC + USE_ACTIVE_SKILL (cmd 248) + role equip
# ============================================================
import asyncio
import math
import random
import struct
import socket
import time
import aiohttp
from typing import Optional, Dict, List, Tuple

# ------------------------------------------------------------------ #
#  TEA-CBC
# ------------------------------------------------------------------ #
_DELTA  = 0x9E3779B9
_ROUNDS = 16

# Placeholder only — never use. Always pass real match UDP key.
_TEA_KEY_PLACEHOLDER = bytes.fromhex("ed0aed93020fc6fbe77da0c9d3b7e813")


def _key_words(key: bytes):
    return tuple(struct.unpack_from("<I", key, o)[0] for o in (0, 4, 8, 12))


def _tea_dec_block(v0: int, v1: int, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (
            (((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF
            ^ ((v0 + s) & 0xFFFFFFFF)
            ^ (((v0 >> 5) + k3) & 0xFFFFFFFF)
        )) & 0xFFFFFFFF
        v0 = (v0 - (
            (((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF
            ^ ((v1 + s) & 0xFFFFFFFF)
            ^ (((v1 >> 5) + k1) & 0xFFFFFFFF)
        )) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1


def _tea_enc_block(v0: int, v1: int, k0, k1, k2, k3):
    s = 0
    for _ in range(_ROUNDS):
        s = (s + _DELTA) & 0xFFFFFFFF
        v0 = (v0 + (
            (((v1 << 4) + k0) & 0xFFFFFFFF)
            ^ ((v1 + s) & 0xFFFFFFFF)
            ^ (((v1 >> 5) + k1) & 0xFFFFFFFF)
        )) & 0xFFFFFFFF
        v1 = (v1 + (
            (((v0 << 4) + k2) & 0xFFFFFFFF)
            ^ ((v0 + s) & 0xFFFFFFFF)
            ^ (((v0 >> 5) + k3) & 0xFFFFFFFF)
        )) & 0xFFFFFFFF
    return v0, v1


def _tea_cbc_decrypt(data: bytes, key: bytes) -> bytes:
    k0, k1, k2, k3 = _key_words(key)
    out = bytearray(len(data))
    pi = bytearray(8)
    pc = bytearray(8)
    for i in range(0, len(data), 8):
        x = bytearray(8)
        for j in range(8):
            x[j] = data[i + j] ^ pi[j]
        d0, d1 = _tea_dec_block(
            struct.unpack_from("<I", x, 0)[0],
            struct.unpack_from("<I", x, 4)[0],
            k0, k1, k2, k3,
        )
        dec = bytearray(8)
        struct.pack_into("<I", dec, 0, d0)
        struct.pack_into("<I", dec, 4, d1)
        for j in range(8):
            out[i + j] = dec[j] ^ pc[j]
        pc[:] = data[i: i + 8]
        pi[:] = dec
    return bytes(out)


def _tea_cbc_encrypt(data: bytes, key: bytes) -> bytes:
    if len(data) % 8:
        data += b"\x00" * (8 - len(data) % 8)
    k0, k1, k2, k3 = _key_words(key)
    out = bytearray(len(data))
    pi = bytearray(8)
    pc = bytearray(8)
    for i in range(0, len(data), 8):
        block = bytearray(8)
        for j in range(8):
            block[j] = data[i + j] ^ pc[j]
        e0, e1 = _tea_enc_block(
            struct.unpack_from("<I", block, 0)[0],
            struct.unpack_from("<I", block, 4)[0],
            k0, k1, k2, k3,
        )
        enc = bytearray(8)
        struct.pack_into("<I", enc, 0, e0)
        struct.pack_into("<I", enc, 4, e1)
        for j in range(8):
            out[i + j] = enc[j] ^ pi[j]
        pi[:] = data[i: i + 8]
        pc[:] = out[i: i + 8]
    return bytes(out)


def _oicq_pad(payload: bytes) -> bytes:
    """FIXED: deterministic OICQ padding — [pad_len][0][0][pad][payload][7 zero]."""
    pad_len = (8 - (len(payload) + 10) % 8) % 8
    return bytes([pad_len, 0, 0]) + b"\x00" * pad_len + payload + b"\x00" * 7


def _oicq_unpad(padded: bytes) -> Optional[bytes]:
    if not padded or len(padded) < 10:
        return None
    if any(padded[-1 - i] != 0 for i in range(7)):
        return None
    pad_len = padded[0] & 0x07
    s = 3 + pad_len
    e = len(padded) - 7
    return padded[s:e] if s < e else b""


def tea_encode(payload: bytes, key: bytes) -> bytes:
    if not key or len(key) != 16:
        raise ValueError("tea_encode requires a 16-byte key")
    return _tea_cbc_encrypt(_oicq_pad(payload), key)


def tea_decode(data: bytes, key: bytes) -> Optional[bytes]:
    if not key or len(key) != 16:
        return None
    if len(data) < 8 or len(data) % 8 != 0:
        return None
    return _oicq_unpad(_tea_cbc_decrypt(data, key))


# ------------------------------------------------------------------ #
#  VARINT / ZIGZAG
# ------------------------------------------------------------------ #
def _uleb(n: int) -> bytes:
    out = bytearray()
    n &= 0xFFFFFFFFFFFFFFFF
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _zigzag(n: int) -> bytes:
    zz = (n << 1) ^ (n >> 63)
    return _uleb(zz & 0xFFFFFFFFFFFFFFFF)


# ------------------------------------------------------------------ #
#  CRC-7
# ------------------------------------------------------------------ #
def _crc7_table():
    t = []
    for b in range(256):
        c = 0
        for i in range(8):
            top = ((c >> 6) & 1) ^ ((b >> (7 - i)) & 1)
            c = (c << 1) & 0x7F
            if top:
                c ^= 0x09
        t.append(c)
    return t


_CRC7 = _crc7_table()


def _crc7_buf(data: bytes) -> int:
    crc = 0
    for b in data:
        crc = _CRC7[((crc << 1) ^ b) & 0xFF]
    return crc


# ------------------------------------------------------------------ #
#  USE_ACTIVE_SKILL
# ------------------------------------------------------------------ #
CMD_USE_ACTIVE_SKILL = 248
SKILL_HOMOR = 5506   # FIXED: was 706, now 5506 (from capture decode)
SEND_OPTION_SKILL = 1


def build_skill_payload(skill_id: int, target_uid: int,
                        tick: int, x: int, y: int, z: int) -> bytes:
    return (
        _uleb(skill_id)
        + _uleb(target_uid)
        + _zigzag(tick)
        + _zigzag(x)
        + _zigzag(y)
        + _zigzag(z)
    )


def _build_rudp_frame(key_bytes: bytes, msg_key: int, order_id: int,
                      cmd: int, enc_payload: bytes) -> bytes:
    k = key_bytes[0]
    kk = (k << 8) | k

    plen = len(enc_payload)
    frame = bytearray()
    frame.append(msg_key)
    frame.append(0x00)
    frame += struct.pack("<H", order_id ^ kk)
    frame += struct.pack("<H", cmd ^ kk)
    frame += struct.pack("<H", plen ^ kk)
    frame += enc_payload
    frame[1] = _crc7_buf(bytes(frame[2:]))
    return bytes(frame)


def build_skill_packet(key_bytes: bytes, msg_key: int, order_id: int,
                       skill_id: int, target_uid: int,
                       tick: int, x: int, y: int, z: int) -> bytes:
    raw_payload = build_skill_payload(skill_id, target_uid, tick, x, y, z)
    enc_payload  = tea_encode(raw_payload, key_bytes)
    return _build_rudp_frame(key_bytes, msg_key, order_id,
                              CMD_USE_ACTIVE_SKILL, enc_payload)


# ------------------------------------------------------------------ #
#  RUDPChannel
# ------------------------------------------------------------------ #
class RUDPChannel:
    """Async UDP channel for cmd 248 skill packets."""

    _MSG_KEY_MIN = 0x6E
    _MSG_KEY_MAX = 0x75
    _MSG_KEY_COUNT = _MSG_KEY_MAX - _MSG_KEY_MIN + 1

    def __init__(self, server_host: str, server_port: int, key: bytes):
        if not key or len(key) != 16:
            raise ValueError("RUDPChannel requires a valid 16-byte match key")
        self.server_addr = (server_host, server_port)
        self.key = key
        self._sock: Optional[socket.socket] = None
        self._order_id = random.randint(0x8000, 0xFFF0) & 0xFFFF
        self._msg_key = random.randint(self._MSG_KEY_MIN, self._MSG_KEY_MAX)
        self._lock = asyncio.Lock()

    def connect(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setblocking(False)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
        except Exception:
            pass
        self._sock = s

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _next_order(self) -> int:
        self._order_id = (self._order_id + 1) & 0xFFFF
        return self._order_id

    def _next_msg_key(self) -> int:
        """FIXED: return current value first, then advance."""
        cur = self._msg_key
        self._msg_key = self._MSG_KEY_MIN + ((self._msg_key - self._MSG_KEY_MIN + 1) % self._MSG_KEY_COUNT)
        return cur

    async def send_skill(self, skill_id: int, target_uid: int,
                         tick: int, x: int, y: int, z: int) -> bool:
        if not self._sock:
            return False
        async with self._lock:
            pkt = build_skill_packet(
                self.key, self._next_msg_key(), self._next_order(),
                skill_id, target_uid, tick, x, y, z,
            )
            loop = asyncio.get_event_loop()
            try:
                await loop.sock_sendto(self._sock, pkt, self.server_addr)
                return True
            except Exception:
                return False

    async def send_homor(self, tick: int, x: int, y: int, z: int,
                          target_uid: int = 0) -> bool:
        return await self.send_skill(SKILL_HOMOR, target_uid, tick, x, y, z)


# ------------------------------------------------------------------ #
#  CircleMovement / EnemyStickSwarm — DEPRECATED
# ------------------------------------------------------------------ #
class CircleMovement:
    """DEPRECATED — movement handled by toolsudp.run_match()."""
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "CircleMovement is deprecated. Use toolsudp.run_match()."
        )


class EnemyStickSwarm:
    """DEPRECATED — not used in current flow."""
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "EnemyStickSwarm is deprecated. Use toolsudp.run_match()."
        )


# ------------------------------------------------------------------ #
#  COLORAMA fallback
# ------------------------------------------------------------------ #
try:
    from colorama import Style as _Style, Fore as _Fore
except ImportError:
    class _Fore:
        GREEN = ""
        RED = ""
    class _Style:
        BRIGHT = ""


# ------------------------------------------------------------------ #
#  NEWBIE ROLES — FIXED (body validation added)
# ------------------------------------------------------------------ #
async def get_newbie_roles(jwt_token: str, server_url: str,
                           release_version: str,
                           encrypt_aes_fn, create_proto_fn) -> bool:
    try:
        url = f"{server_url}/GiveAccountNewbieRoles"
        fields = {"1": 1}
        proto_bytes = create_proto_fn(fields).hex()
        payload = bytes.fromhex(encrypt_aes_fn(proto_bytes))
        host = server_url.replace("https://", "").replace("http://", "").split("/")[0]
        headers = {
            "authorization":   f"Bearer {jwt_token}",
            "host":            host,
            "x-ga":            "v1 1",
            "content-type":    "application/x-www-form-urlencoded",
            "accept-encoding": "deflate, gzip",
            "releaseversion":  release_version,
            "user-agent":      "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "accept":          "*/*",
            "x-unity-version": "2022.3.47f1",
        }
        timeout = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.post(url, headers=headers, data=payload) as resp:
                body = await resp.read()
                if resp.status == 200:
                    print(f"{_Style.BRIGHT}{_Fore.GREEN}[ROLE] GiveNewbieRoles OK")
                    return True
                print(f"{_Style.BRIGHT}{_Fore.RED}[ROLE] GiveNewbieRoles FAILED {resp.status} — {body[:200]}")
                return False
    except asyncio.TimeoutError:
        print("[ROLE] GiveNewbieRoles TIMEOUT")
        return False
    except Exception as e:
        print(f"[ROLE] GiveNewbieRoles err: {e}")
        return False


async def set_newbie_roles(jwt_token: str, server_url: str,
                           release_version: str,
                           encrypt_aes_fn, create_proto_fn) -> bool:
    try:
        url = f"{server_url}/SelectPresetLoadout"
        fields = {
            "1": {"1": 102000037},
            "2": {"1": 102000037, "2": 50462976,
                  "3": 414929892933512066, "4": 0},
            "6": {"1": {"1": 1, "2": 102000037,
                        "3": {"1": 3, "2": SKILL_HOMOR},
                        "6": "PRESET 1", "7": 1}},
            "11": 1,
        }
        proto_bytes = create_proto_fn(fields).hex()
        payload = bytes.fromhex(encrypt_aes_fn(proto_bytes))
        host = server_url.replace("https://", "").replace("http://", "").split("/")[0]
        headers = {
            "authorization":   f"Bearer {jwt_token}",
            "host":            host,
            "x-ga":            "v1 1",
            "content-type":    "application/x-www-form-urlencoded",
            "accept-encoding": "deflate, gzip",
            "releaseversion":  release_version,
            "user-agent":      "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "accept":          "*/*",
            "x-unity-version": "2022.3.47f1",
        }
        timeout = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.post(url, headers=headers, data=payload) as resp:
                body = await resp.read()
                if resp.status == 200:
                    print(f"{_Style.BRIGHT}{_Fore.GREEN}[ROLE] SelectPreset OK (skill={SKILL_HOMOR})")
                    return True
                print(f"{_Style.BRIGHT}{_Fore.RED}[ROLE] SelectPreset FAILED {resp.status} — {body[:200]}")
                return False
    except asyncio.TimeoutError:
        print("[ROLE] SelectPreset TIMEOUT")
        return False
    except Exception as e:
        print(f"[ROLE] SelectPreset err: {e}")
        return False


async def init_homor_roles(jwt_token: str, server_url: str,
                           release_version: str,
                           encrypt_aes_fn, create_proto_fn) -> bool:
    ok1 = await get_newbie_roles(jwt_token, server_url, release_version,
                                 encrypt_aes_fn, create_proto_fn)
    await asyncio.sleep(0.4)
    ok2 = await set_newbie_roles(jwt_token, server_url, release_version,
                                 encrypt_aes_fn, create_proto_fn)
    return ok1 and ok2