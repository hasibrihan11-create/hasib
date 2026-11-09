"""Standalone CS Engine — no xHeaders / Azure / parent-udp imports."""
import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import sys
import ssl
import json
import time
import uuid
import random
import socket
import asyncio
import urllib3
import aiohttp

# Windows console often uses cp1252 — force UTF-8 so logs/print don't crash
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser

from helpers import *
from Pb2 import (
    DEcwHisPErMsG_pb2,
    MajoRLoGinrEs_pb2,
    PorTs_pb2,
    MajoRLoGinrEq_pb2,
    sQ_pb2,
    Team_msg_pb2,
)

def render(text, colors=None, align=None):
    """ASCII-safe banner (cfonts breaks on Windows cp1252 pipes)."""
    return f"===== {text} ====="

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Local config (replaces xHeaders.AuToUpDaTE — no remote panel)
LOGIN_BASE_URL = "https://clientbp.ggpolarbear.com/"
OB_VERSION = "OB55"
CLIENT_VERSION = "1.132.9"
login_url, ob, version = LOGIN_BASE_URL, OB_VERSION, CLIENT_VERSION

Chat_Leave = False
joining_team = False

# Persistent device fingerprints (local devices.json next to this engine)
_DEVICES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "devices.json")
_PARENT_DEVICES = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "devices.json")
)


def get_device_for_account(account_identifier: str) -> dict:
    """OB55-safe persistent device fingerprint per guest UID."""
    devices = {}
    for path in (_DEVICES_FILE, _PARENT_DEVICES):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    devices = raw
                    break
            except Exception:
                pass
    acc_key = str(account_identifier)
    safe = {
        "brand": "asus",
        "model": "ASUS_Z01QD",
        "gpu_renderer": "Adreno (TM) 640",
        "system_software": "Android OS 9 / API-28 (PQ3A.190705.09121607/G9700FXXU1APFO)",
        "screen_width": 1280,
        "screen_height": 720,
        "screen_dpi": "240",
        "memory": 3943,
        "processor_details": "x86-64 SSE3 SSE4.1 SSE4.2 AVX | 2865 | 4",
        "country_code": "BD",
    }
    if acc_key in devices and isinstance(devices.get(acc_key), dict):
        dev = dict(devices[acc_key])
        for k, v in safe.items():
            dev[k] = v
        if not str(dev.get("client_ip") or "").startswith("103."):
            dev["client_ip"] = f"103.{random.randint(10, 250)}.{random.randint(10, 250)}.{random.randint(10, 250)}"
        if not dev.get("unique_device_id"):
            dev["unique_device_id"] = f"Google|{uuid.uuid4()}"
        return dev
    return {
        "unique_device_id": f"Google|{uuid.uuid4()}",
        **safe,
        "client_ip": f"103.{random.randint(10, 250)}.{random.randint(10, 250)}.{random.randint(10, 250)}",
    }


def lag(_jwt):
    """No-op: original hit clientbp RequestJoinClan via shared JWT. Not needed for CS."""
    return None


Hr = {
    'User-Agent': "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    'Connection': "Keep-Alive",
    'Accept-Encoding': "gzip",
    'Content-Type': "application/x-www-form-urlencoded",
    'X-Unity-Version': "2018.4.12f1",
    'X-GA-SV': "1790622759",
    'X-GA': "v1 1",
    'ReleaseVersion': ob}

# ---- Random Colores ----

def get_random_color():
    colors = [
        "[FF0000]", "[00FF00]", "[0000FF]", "[FFFF00]", "[FF00FF]", "[00FFFF]", "[FFFFFF]", "[FFA500]",
        "[A52A2A]", "[800080]", "[000000]", "[808080]", "[C0C0C0]", "[FFC0CB]", "[FFD700]", "[ADD8E6]",
        "[90EE90]", "[D2691E]", "[DC143C]", "[00CED1]", "[9400D3]", "[F08080]", "[20B2AA]", "[FF1493]",
        "[7CFC00]", "[B22222]", "[FF4500]", "[DAA520]", "[00BFFF]", "[00FF7F]", "[4682B4]", "[6495ED]",
        "[5F9EA0]", "[DDA0DD]", "[E6E6FA]", "[B0C4DE]", "[556B2F]", "[8FBC8F]", "[2E8B57]", "[3CB371]",
        "[6B8E23]", "[808000]", "[B8860B]", "[CD5C5C]", "[8B0000]", "[FF6347]", "[FF8C00]", "[BDB76B]",
        "[9932CC]", "[8A2BE2]", "[4B0082]", "[6A5ACD]", "[7B68EE]", "[4169E1]", "[1E90FF]", "[191970]",
        "[00008B]", "[000080]", "[008080]", "[008B8B]", "[B0E0E6]", "[AFEEEE]", "[E0FFFF]", "[F5F5DC]",
        "[FAEBD7]"
    ]
    return random.choice(colors)

async def encrypted_proto(encoded_hex):
    key = b'Yg&tc%DEuh6%Zc^8'
    iv = b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_message = pad(encoded_hex, AES.block_size)
    encrypted_payload = cipher.encrypt(padded_message)
    return encrypted_payload
    
async def GeNeRaTeAccEss(uid , password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B Build/SP1A.210812.016)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close"}
    data = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as response:
            if response.status != 200: return await response.read()
            data = await response.json()
            open_id = data.get("open_id")
            access_token = data.get("access_token")
            return (open_id, access_token) if open_id and access_token else (None, None)

async def EncryptMajorLogin(open_id, access_token, guest_uid=None):
    """OB55 MajorLogin — same fingerprint/device path as LW UDP SOURCE Main.py."""
    device = get_device_for_account(guest_uid or open_id or "default")
    major_login = MajoRLoGinrEq_pb2.MajorLogin()

    major_login.open_id = open_id
    major_login.access_token = access_token
    major_login.client_version = version or "1.132.9"
    major_login.client_version_code = "2019121229"

    major_login.event_time = time.strftime("%Y-%m-%d %H:%M:%S")
    major_login.game_name = "free fire"
    major_login.platform_id = 1
    major_login.system_software = device.get(
        "system_software", "Android OS 9 / API-28 (PQ3A.190705.09121607/G9700FXXU1APFO)"
    )
    major_login.system_hardware = "Handheld"
    major_login.telecom_operator = "Grameenphone"
    major_login.network_type = "WIFI"
    major_login.screen_width = int(device.get("screen_width", 1280))
    major_login.screen_height = int(device.get("screen_height", 720))
    major_login.screen_dpi = str(device.get("screen_dpi", "240"))
    major_login.processor_details = device.get(
        "processor_details", "x86-64 SSE3 SSE4.1 SSE4.2 AVX | 2865 | 4"
    )
    major_login.memory = int(device.get("memory", 3943))
    major_login.gpu_renderer = device.get("gpu_renderer", "Adreno (TM) 640")
    major_login.gpu_version = "OpenGL ES 3.1 v1"
    major_login.unique_device_id = device.get(
        "unique_device_id", "Google|fedc018f-fe4d-43a8-b493-b3162ffafc70"
    )
    major_login.client_ip = device.get("client_ip", "103.187.94.223")
    major_login.language = "en"
    major_login.open_id_type = "4"
    major_login.device_type = "Handheld"
    major_login.platform_sdk_id = 1
    major_login.network_operator_a = "Grameenphone"
    major_login.network_type_a = "WIFI"
    major_login.client_using_version = "7428b253defc164018c604a1ebbfebdf"
    major_login.external_storage_total = 50504
    major_login.external_storage_available = 47719
    major_login.internal_storage_total = 2519
    try:
        major_login.internal_storage_available = 706
    except Exception:
        pass
    major_login.game_disk_storage_available = 24444
    major_login.game_disk_storage_total = 30991
    major_login.external_sdcard_avail_storage = 49956
    major_login.external_sdcard_total_storage = 50504
    major_login.login_by = 3
    lib_pkg = "com.dts.freefireth-S6nAl6aL5_IDwqf7qM9vFg=="
    major_login.library_path = f"/data/app/{lib_pkg}/lib/arm64"
    major_login.reg_avatar = 1
    major_login.library_token = f"b8e0cd5e295eee42f5860d3c86e483dd|/data/app/{lib_pkg}/base.apk"
    major_login.channel_type = 3
    major_login.cpu_type = 2
    major_login.cpu_architecture = "64"
    major_login.graphics_api = "OpenGLES2"
    major_login.supported_astc_bitset = 4095
    major_login.login_open_id_type = 4
    major_login.loading_time = 6718
    major_login.release_channel = "android"
    major_login.extra_info = (
        "KqsHTwEkaznrGCTsBph7lEkzDC0Jox79o5PgkV+Z1x9zcGZIwi8el7h5rEOwuXuHNQkDPATUZ1TeXY7qhvXH8mP/Cvn9LuSr9Crsa9pg92SdxONV"
    )
    major_login.android_engine_init_flag = 111207
    major_login.if_push = 1
    major_login.origin_platform_type = "4"
    major_login.primary_platform_type = "4"

    brand = str(device.get("brand", "asus"))
    model = str(device.get("model", "ASUS_Z01QD"))
    try:
        major_login.device_model = f"{brand} {model}".strip()
        major_login.country_code = str(device.get("country_code") or "BD")
    except Exception:
        pass
    try:
        major_login.field_96 = json.dumps({"cur_rate": None, "support_etc2": False}, separators=(",", ":"))
    except Exception:
        pass
    try:
        major_login.field_102 = bytes.fromhex("4501154f075f09041a0659465e51420b43675f510c515c75545a740b000b390f5730")
        major_login.field_104 = 33695
        major_login.field_105 = 1
        major_login.field_106 = (
            "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/|"
            "https://core-bs.ggpolarbear.com/live/ABHotUpdates/|"
            "211c933168f55902c7dfbfd8c4e2957d"
        )
        major_login.field_107 = "1.27aa7af0fc56d172"
    except Exception:
        pass

    return await encrypted_proto(major_login.SerializeToString())


async def MajorLogin(payload):
    url = f"https://loginbp.ppmainecoonghj.com/MajorLogin"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=Hr, ssl=ssl_context) as response:
            if response.status == 200:
                return await response.read()
            return None


async def GetLoginData(base_url, payload, token):
    url = f"{base_url}/GetLoginData"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    Hr["Authorization"] = f"Bearer {token}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=Hr, ssl=ssl_context) as response:
            if response.status == 200:
                return await response.read()
            return None


async def DecRypTMajoRLoGin(MajoRLoGinResPonsE):
    """Parse MajorLoginRes — try offset 0, 64, then scan (LW Main OB55 logic)."""
    body = MajoRLoGinResPonsE or b""
    for offset in [0, 64] + list(range(1, min(128, len(body)))):
        if offset in (0, 64) or offset > 64:
            try:
                proto = MajoRLoGinrEs_pb2.MajorLoginRes()
                proto.ParseFromString(body[offset:] if offset else body)
                if getattr(proto, "token", None):
                    return proto
            except Exception:
                pass
    proto = MajoRLoGinrEs_pb2.MajorLoginRes()
    proto.ParseFromString(body[64:] if len(body) > 64 else body)
    return proto

async def DecRypTLoGinDaTa(LoGinDaTa):
    proto = PorTs_pb2.GetLoginData()
    proto.ParseFromString(LoGinDaTa)
    return proto

async def DecodeWhisperMessage(hex_packet):
    packet = bytes.fromhex(hex_packet)
    proto = DEcwHisPErMsG_pb2.DecodeWhisper()
    proto.ParseFromString(packet)
    return proto
    
async def decode_team_packet(hex_packet):
    packet = bytes.fromhex(hex_packet)
    proto = sQ_pb2.recieved_chat()
    proto.ParseFromString(packet)
    return proto
    
async def aes_encrypt(payload, key, iv):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(payload, AES.block_size))

async def build_tcp_startup_packet(account_id, token, server_time, key, iv, region="BD", typ='OnLine'):
    uid_hex = f"{int(account_id):016x}"
    timestamp_hex = f"{int(server_time):08x}"
    encode_token = token.encode()
    encrypted_packet = (await aes_encrypt(encode_token, key, iv)).hex()
    encrypted_packet_length = f"{len(encrypted_packet) // 2:08x}"
    reg = str(region).upper() if region else "BD"
    if typ == 'OnLine':
        # WORKING LW UDP SOURCE Main.py magics (LD "dynamic" bytes were mid-stream noise)
        prefix = '7119' if reg == 'BD' else ('7114' if reg == 'IND' else '7115')
        return f"{prefix}{uid_hex}{timestamp_hex}00000000{encrypted_packet_length}{encrypted_packet}"
    else:  # ChaT / Informational
        prefix = '9219' if reg == 'BD' else ('9214' if reg == 'IND' else '9215')
        return f"{prefix}{uid_hex}{timestamp_hex}{encrypted_packet_length}{encrypted_packet}"

async def send_keep_alive(region="BD"):
    """Send 2-byte keep-alive pulse to maintain connection in OB55"""
    try:
        reg = str(region).upper() if region else "BD"
        ka_hex = "0219" if reg == "BD" else ("0214" if reg == "IND" else "0215")
        return bytes.fromhex(ka_hex)
    except Exception:
        return bytes.fromhex("0219")   
     

async def ArohiAccepted(uid, code, K, V, region="BD", client_ver=None):
    """Real Accept Packet - OB55 Dynamic Version & Region Fixed"""
    app_version = client_ver or version or "1.132.1"
    fields = {
        1: 4,
        2: {
            1: int(uid), 
            3: int(uid), 
            4: bytes.fromhex("01090a0b121920"), 
            8: 1,
            9: {
                2: 161, 
                4: "y[WW", 
                5: 1, 
                6: 11, 
                8: str(app_version), 
                9: 5, 
                10: 1 
            },
            10: str(code),
        }
    }
    reg = str(region).lower()
    pkt_type = '0519' if reg == 'bd' else ('0514' if reg == 'ind' else '0515')
    proto_hex = (await CrEaTe_ProTo(fields)).hex()
    return await GeneRaTePk(proto_hex, pkt_type, K, V)




async def create_workshop_squad(
    workshop_code: str,
    workshop_name: str,
    key: bytes,
    iv: bytes,
    region: str = "IND",
    game_mode: int = 46,
    group_mode: int = 3,
    match_mode: int = 1
) -> bytes:
    fields = {
        1: 1,
        2: {
            2: b"\x01",
            3: game_mode,
            4: group_mode,
            5: "en",
            9: match_mode,
            11: 1,
            13: 1,
            14: {2: 5756, 6: 11, 8: "1.126.16", 9: 2, 10: 4},
            17: str(workshop_code),
            18: str(workshop_name)
        }
    }
    if region.lower() == "ind":
        pkt_type = '0514'
    elif region.lower() == "bd":
        pkt_type = '0519'
    else:
        pkt_type = '0515'
    proto_hex = (await CrEaTe_ProTo(fields)).hex()
    return await GeneRaTePk(proto_hex, pkt_type, key, iv)

async def group_start_workshop_minimal(group_id: int, workshop_code: str, key: bytes, iv: bytes, region: str = "IND") -> bytes:
    fields = {
        1: 9,
        2: {
            1: int(group_id),
            3: [str(workshop_code)]
        }
    }
    if region.lower() == "ind": pkt_type = '0514'
    elif region.lower() == "bd": pkt_type = '0519'
    else: pkt_type = '0515'
    proto_hex = (await CrEaTe_ProTo(fields)).hex()
    return await GeneRaTePk(proto_hex, pkt_type, key, iv)


async def Create_Custom_Room_Packet(room_name, password, key, iv, region="BD"):
    fields = {
        1: 2,
        2: {
            1: 1,
            2: 15,
            3: 3,
            4: str(room_name),
            5: str(password),
            6: 8,
            7: 30,
            8: 1,
            9: 1,
            11: 1,
            14: 35670336,
            15: {
                1: "IDC3",
                2: 101,
                3: str(region)
            },
            18: 10757192,
            27: 1,
            40: "en",
            46: 1104,
            48: 1,
            49: {
                1: 21
            },
            50: {
                1: 35670336,
                2: 10757192,
                3: 80
            },
            56: 1
        }
    }
    proto_hex = (await CrEaTe_ProTo(fields)).hex()
    return await GeneRaTePk(proto_hex, '0E15', key, iv)


async def Craftland_Start_Packet(map_code, key, iv, region="BD"):
    fields = {
        1: 51,
        2: {
            1: 1,
            2: str(map_code),
            6: 26,
            7: 1,
            8: "en",
            14: 1,
            15: {
                1: "08FBA33C5DDE648E02052802222200000068000300650018CA7A4CB00DB66858467625140000000bf4925ecb0e748c3f6a3a8f75000000ff0a000600cacfa16d",
                2: 257,
                3: "p]XT\x15\x05\x06D\x04\x07U\x01PRWWUWZR\x02RT\x03\x07\x01\x06\x05U\n\x06VS\x04\x07\x04\tTR\x03\x1b\x01\x02LsYDEO\x1c\x06\x14\x01\x1a\x13\x07\x06H\x1aDd|TWCtwZRHcwF\x13Y\\H\x03VCBlXgi\r\x0010\x01J\x1f\x01^q\x1bd\tBz\x05UcCct\x1b[]BFJAVg\x01\x07\x00\x0b\x1b\x01\x00LpD\x02sLFtz|gh\\\x06VGc}PSz\x07BX`z\x7f{\t\x15\x00L\\Hn\r{G\x0fv\x04maXV^\x03qXF]\\BA{Jc_G\f\x15\x06J`cwdDE\x1b\\LP\x0fi\\\x01qq\x02@[c\x00\x03B@rC\x7f\t\x17\bJ\x07\x01\x00\x01\x04R\x02\x07CpD\x02w\x00|\n~SA\\Yu`wY|@\r\x015\x05\fM\x19~xv\x02\x02\bLZ\x1frDY\x07P\x06JE\x07\x06yK|Zt}G\x0e\x013\x05Hw\x1ezR|@{|xBXuirsWAubd^uugsqQ\x05\x013\x07L\x07x\x1bg]d|wIDd~b\\Wzy@\x013C\x01r\x06m\x1bhY\t\x15\n\x00O\x04d\x04\fpccqmCrtbwz\x7fE\x04wNbzJ\x02^]x\x0b\x17\x03DR\x02\x7fDWsuE]gl\x07t]cMX\x01bB{{Ef\x00\x03q\t",
                4: "~YZQ",
                6: 11,
                8: "1.126.17",
                9: 6,
                10: 1
            },
            17: {
                1: "CLPlatform_Recommended",
                2: "Most Popular"
            }
        }
    }
    if str(region).lower() == "ind":
        pkt_type = '0514'
    elif str(region).lower() == "bd":
        pkt_type = '0519'
    else:
        pkt_type = '0515'
    proto_hex = (await CrEaTe_ProTo(fields)).hex()
    return await GeneRaTePk(proto_hex, pkt_type, key, iv)


async def Create_My_Fav_Room_Packet(room_name, password="", key=None, iv=None, region="BD"):
    fields = {
        1: 2,
        2: {
            1: 1, # Bermuda / Map
            2: 15, # Clash Squad
            3: 3, # Squad
            4: str(room_name),
            5: str(password),
            6: 8, # 8 Players
            7: 30, # 30 Specs
            8: 1,
            9: 1,
            11: 1,
            14: 572541418,
            15: {
                1: "IDC2",
                2: 133,
                3: str(region)
            },
            18: 547628104,
            21: 1,
            22: {},
            27: 1,
            34: { 0: 2 },
            40: "en",
            43: 1,
            46: 1104,
            48: 1,
            49: { 1: 21 },
            50: { 1: 35670336, 2: 10757192, 3: 80 },
            56: 1
        }
    }
    proto_hex = (await CrEaTe_ProTo(fields)).hex()
    return await GeneRaTePk(proto_hex, '0E15', key, iv)

async def Change_Room_Slot_Packet(room_id, uid, squad_num, slot_num, key, iv):
    fields = {
        1: 20,
        2: {
            1: int(room_id),
            2: int(uid),
            3: 1,
            4: int(squad_num),
            5: int(slot_num),
            6: 1
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0E15', key, iv)

async def Spectate_Room_Packet(room_id, uid, key, iv):
    fields = {
        1: 20,
        2: {
            1: int(room_id),
            2: int(uid),
            3: 2,
            6: 1
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0E15', key, iv)

async def Room_Recruit_Packet(room_id, key, iv):
    fields = {
        1: 87,
        2: {
            1: int(room_id),
            2: 1
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0E15', key, iv)

async def Room_Stop_Recruit_Packet(room_id, key, iv):
    fields = {
        1: 85,
        2: {
            1: int(room_id),
            2: 1
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0E15', key, iv)

async def Start_Room_Match_Packet(room_id, key, iv):
    fields = {
        1: 39,
        2: {
            1: int(room_id),
            2: 3
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0E15', key, iv)


async def Squad_Recruit_Start_Packet(uid, key, iv, region="BD"):
    fields = {
        1: 66,
        2: {
            1: int(uid),
            5: {},
            9: "",
            10: 1
        }
    }
    pkt_type = '0519' if str(region).lower() == 'bd' else '0514' if str(region).lower() == 'ind' else '0515'
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), pkt_type, key, iv)

async def Squad_Recruit_Broadcast_Packet(uid, key, iv, region="BD"):
    fields = {
        1: 17,
        2: {
            1: int(uid),
            2: 1,
            3: 3,
            4: 15,
            5: {},
            8: 1,
            10: "0;0"
        }
    }
    pkt_type = '0519' if str(region).lower() == 'bd' else '0514' if str(region).lower() == 'ind' else '0515'
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), pkt_type, key, iv)




async def CS_Solo_Start_Matchmaking_Packet(key, iv, region="BD"):
    raw_proto_hex = (
        
    
    "080112960b0a0101100f3a0a0a04494443311a0242443a0a0a04494443321a0242443a0a0a044944"
    "43331a02424440014a0901090a0b1219202729580162a70a0a800130384642413333423433323244"
    "43323230323033323030313232323130303031303038453030303330303841303032344235383634"
    "39423431333032443742343436373632353134303030313034303765306130643834383065373438"
    "633366366161303439643430303030303066663038306130353031636163666131366410c6011ab9"
    "037e585c541303054d51000b5c545102560057050309525a0852070853030057550101545600000b"
    "051204014f7d5c4045491a051d04191009034c01567c77025a6842627e7a63494477675b79770e77"
    "08647b007c7c081302447b5d635174567c4f7f677f76565074744c5a7b515c5a5b51506345081253"
    "5f5d4c1e63791d754541044c646a6640014346504b594564134b7849470b6c7e7d5b466a1e46090d"
    "11040249085950785761007e7e45067e410f5e0066567e427f520502734b000c130a494502601c53"
    "62621e6a0b71426f5a405343795a49197b1a5a4840790c13034c197349517642174051597f5c6f43"
    "42435e5a030008644a05435c790e1b084c606973791e40646217505d687b484c7f707a1852690579"
    "43400005081302004d0700640a007370405d714943584261057a6655016c70797c6a7f7c0c16034f"
    "701a015563610475431b015e0558670553401a5a037413771b66000f160549564a7f50477b697304"
    "606c0541696876046346561e464a047f74750c1300054d447705135059437e5579435e65674a4345"
    "00074a7b0240597c4f700d12054e5a4746597b5e5f5b704250405c1e64745041537b61451a08616a"
    "440522047b5f5d5d300c3a1a1101404b4202020201041511647b7163746e7c5b57725d5550534207"
    "312e3133322e39480650015ab105036262535136334c707a475133416456324b796f566c6646484e"
    "4861775a57523441737574496d41506233706a4666667465554a722b7a58592b466f2f432f58304b"
    "526636765a7631747943545a6e77314f7a307a7a554532636561556f61552b41483563492b424a6d"
    "4234556d654b54776f4c34656569657a5345536c79332b6a627163486b4f4156456a4b2b634c4776"
    "3141652b68773749586f4e785137344d55716f544b4450557a4971564e584c463533764177563670"
    "6f684c47345738387a5132627739466773496a564a4b6a48397538796e55354f51305746632f434b"
    "764c2b6b31617a2b6977576e34397044386c4b775253453846714b6d6c5061395963474e456b646d"
    "55562f55446d643045334d74516c353230567a332b4c55754765344b5136653148336f69466f5647"
    "615058417a4a75474c6b62734a48412b537676504d4144416842676a502b364f6f49362b31445a59"
    "4664644371736a67546762436c5674555a466156726a3130617377584b7936744365503735353967"
    "57444b65586c6170745369495a73636d3376667051467165436252316c552f686639495163313634"
    "594d373553695a6765346979516c36514933434571556e754a4b426e635855523739303635654951"
    "624674377773546b6f6737384552786e6f4c484756392b59336662656d50316e4a3650385252394f"
    "673532587746706f3759646265556a6854666c4c4c6a415a782b4a696375694a2f685234652f676c"
    "7674553533585849374a373462543770677761377054766a66514b696530516a79654b466f72794b"
    "6255354f46386771616a3334644359616269335454704339435838326f36653462742f704a4a4458"
    "643855796a6757393075692b695a56434c703944775261737a6e7a567858654f3734617464413871"
    "4956477943524239467145575a77384b755a536339593da20105080310e802a201050804108703a2"
    "01050805109c01a20105081d10cc01a2010408161076a20105080e108b01a201020815"
    )
    reg = str(region).upper() if region else "BD"
    pkt_prefix = '0319' if reg == 'BD' else ('0314' if reg == 'IND' else '0315')
    packet_bytes = bytes.fromhex(raw_proto_hex)
    encrypted_packet = (await aes_encrypt(packet_bytes, key, iv)).hex()
    packet_length = len(encrypted_packet) // 2
    hex_length = f"{packet_length:08x}"
    return bytes.fromhex(pkt_prefix + hex_length + encrypted_packet)

async def CS_Solo_Cancel_Matchmaking_Packet(uid, key, iv, region="BD"):
    fields = {
        1: 11,
        2: {
            1: int(uid)
        }
    }
    pkt_type = '0319' if str(region).lower() == 'bd' else '0314' if str(region).lower() == 'ind' else '0315'
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), pkt_type, key, iv)


async def Send_Room_Ping_Packet(key, iv):
    """Room Keep-Alive Ping Packet (Type 24)"""
    fields = {
        1: 24,
        2: {
            1: 1
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0E15', key, iv)


















# ==================== UDP MATCH ENGINE & CRYPTO ====================
CRC7_TABLE = bytes([
    0, 9, 18, 27, 36, 45, 54, 63, 72, 65, 90, 83, 108, 101, 126, 119,
    25, 16, 11, 2, 61, 52, 47, 38, 81, 88, 67, 74, 117, 124, 103, 110,
    50, 59, 32, 41, 22, 31, 4, 13, 122, 115, 104, 97, 94, 87, 76, 69,
    43, 34, 57, 48, 15, 6, 29, 20, 99, 106, 113, 120, 71, 78, 85, 92,
    100, 109, 118, 127, 64, 73, 82, 91, 44, 37, 62, 55, 8, 1, 26, 19,
    125, 116, 111, 102, 89, 80, 75, 66, 53, 60, 39, 46, 17, 24, 3, 10,
    86, 95, 68, 77, 114, 123, 96, 105, 30, 23, 12, 5, 58, 51, 40, 33,
    79, 70, 93, 84, 107, 98, 121, 112, 7, 14, 21, 28, 35, 42, 49, 56,
    65, 72, 83, 90, 101, 108, 119, 126, 9, 0, 27, 18, 45, 36, 63, 54,
    88, 81, 74, 67, 124, 117, 110, 103, 16, 25, 2, 11, 52, 61, 38, 47,
    115, 122, 97, 104, 87, 94, 69, 76, 59, 50, 41, 32, 31, 22, 13, 4,
    106, 99, 120, 113, 78, 71, 92, 85, 34, 43, 48, 57, 6, 15, 20, 29,
    37, 44, 55, 62, 1, 8, 19, 26, 109, 100, 127, 118, 73, 64, 91, 82,
    60, 53, 46, 39, 24, 17, 10, 3, 116, 125, 102, 111, 80, 89, 66, 75,
    23, 30, 5, 12, 51, 58, 33, 40, 95, 86, 77, 68, 123, 114, 105, 96,
    14, 7, 28, 21, 42, 35, 56, 49, 70, 79, 84, 93, 98, 107, 112, 121,
])
_DELTA = 0x9E3779B9
_ROUNDS = 16
_FIELD_SIZES = {0: 1, 1: 2, 2: 2, 3: 1, 4: 2}
_FIELD_NAMES = {0: "sendOption", 1: "cmd", 2: "orderId", 3: "flags", 4: "length"}

try:
    from message_ids import MESSAGE_ID_TO_NAME
except Exception:
    MESSAGE_ID_TO_NAME = {
        1: "UDP_HELLO",
        2: "UDP_ACK",
        3: "UDP_PING",
        10: "RUDP_JOIN_MATCH"
    }

async def _udp_sendto(loop, sock, data, addr):
    """UDP send on Python 3.10 and 3.11+.

    loop.sock_sendto exists only on 3.11+. Workers 1–9 run Python 3.10, so a
    direct call raises: '_UnixSelectorEventLoop' object has no attribute 'sock_sendto'.
    The socket is non-blocking — do not run sock.sendto in a thread pool
    (BlockingIOError). Send inline, and wait for writable only if the buffer is full.
    """
    sendto = getattr(loop, "sock_sendto", None)
    if sendto is not None:
        await sendto(sock, data, addr)
        return
    try:
        sock.sendto(data, addr)
        return
    except (BlockingIOError, InterruptedError):
        pass
    fut = loop.create_future()
    fd = sock.fileno()

    def _on_writable():
        try:
            sock.sendto(data, addr)
        except (BlockingIOError, InterruptedError):
            return
        except Exception as exc:
            try:
                loop.remove_writer(fd)
            except Exception:
                pass
            if not fut.done():
                fut.set_exception(exc)
            return
        try:
            loop.remove_writer(fd)
        except Exception:
            pass
        if not fut.done():
            fut.set_result(None)

    loop.add_writer(fd, _on_writable)
    try:
        await fut
    finally:
        try:
            loop.remove_writer(fd)
        except Exception:
            pass


async def _udp_recvfrom(loop, sock, nbytes):
    """Python 3.10 SelectorEventLoop has no sock_recvfrom (added in 3.11)."""
    if hasattr(loop, "sock_recvfrom"):
        return await loop.sock_recvfrom(sock, nbytes)
    fut = loop.create_future()
    fd = sock.fileno()

    def _on_ready():
        try:
            data_addr = sock.recvfrom(nbytes)
        except (BlockingIOError, InterruptedError):
            return
        except Exception as exc:
            try:
                loop.remove_reader(fd)
            except Exception:
                pass
            if not fut.done():
                fut.set_exception(exc)
            return
        try:
            loop.remove_reader(fd)
        except Exception:
            pass
        if not fut.done():
            fut.set_result(data_addr)

    loop.add_reader(fd, _on_ready)
    try:
        return await fut
    finally:
        try:
            loop.remove_reader(fd)
        except Exception:
            pass


def optimize_udp_socket(sock: socket.socket):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
        if hasattr(socket, 'SIO_UDP_CONNRESET') and os.name == 'nt':
            try:
                sock.ioctl(socket.SIO_UDP_CONNRESET, False)
            except Exception:
                pass
    except Exception:
        pass

async def crc7_buff(crc, buf):
    c = crc & 0x7F
    for b in buf:
        c = CRC7_TABLE[((2 * (c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F

async def has_ssan_zig(n):
    z = (n << 1) & 0xFFFFFFFFFFFFFFFF
    out = bytearray()
    while z >= 0x80:
        out.append((z & 0x7F) | 0x80)
        z >>= 7
    out.append(z)
    return bytes(out)

async def uleb_encode(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)

async def tea_enc(v0, v1, k0, k1, k2, k3):
    s = 0
    for _ in range(_ROUNDS):
        s = (s + _DELTA) & 0xFFFFFFFF
        v0 = (v0 + (((((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF ^ ((v1 + s) & 0xFFFFFFFF) ^ (((v1 >> 5) + k1) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        v1 = (v1 + (((((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF ^ ((v0 + s) & 0xFFFFFFFF) ^ (((v0 >> 5) + k3) & 0xFFFFFFFF)))) & 0xFFFFFFFF
    return v0, v1

async def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (((((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF ^ ((v0 + s) & 0xFFFFFFFF) ^ (((v0 >> 5) + k3) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        v0 = (v0 - (((((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF ^ ((v1 + s) & 0xFFFFFFFF) ^ (((v1 >> 5) + k1) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1

async def tea_cbc_encrypt(padded, key_bytes):
    import struct
    k0, k1, k2, k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0, 4, 8, 12))
    out = bytearray(len(padded))
    prev_cipher = bytearray(8)
    prev_intermediate = bytearray(8)
    for i in range(0, len(padded), 8):
        xored = bytearray(8)
        for j in range(8):
            xored[j] = padded[i + j] ^ prev_cipher[j]
        e0, e1 = await tea_enc(struct.unpack_from("<I", xored, 0)[0], struct.unpack_from("<I", xored, 4)[0], k0, k1, k2, k3)
        enc = bytearray(8)
        struct.pack_into("<I", enc, 0, e0)
        struct.pack_into("<I", enc, 4, e1)
        for j in range(8):
            out[i + j] = enc[j] ^ prev_intermediate[j]
        prev_cipher[:] = out[i:i + 8]
        prev_intermediate[:] = xored
        if i % 64 == 0:
            await asyncio.sleep(0)
    return bytes(out)

async def tea_cbc_decrypt(body, key_bytes):
    import struct
    k0, k1, k2, k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0, 4, 8, 12))
    out = bytearray(len(body))
    prev_intermediate = bytearray(8)
    prev_cipher = bytearray(8)
    xored = bytearray(8)
    dec = bytearray(8)
    for i in range(0, len(body), 8):
        for j in range(8):
            xored[j] = body[i + j] ^ prev_intermediate[j]
        d0, d1 = await tea_dec(struct.unpack_from("<I", xored, 0)[0], struct.unpack_from("<I", xored, 4)[0], k0, k1, k2, k3)
        struct.pack_into("<I", dec, 0, d0)
        struct.pack_into("<I", dec, 4, d1)
        for j in range(8):
            out[i + j] = dec[j] ^ prev_cipher[j]
        prev_cipher[:] = body[i:i + 8]
        prev_intermediate[:] = dec
        if i % 64 == 0:
            await asyncio.sleep(0)
    return bytes(out)

async def build_padded(content):
    pad_len = (8 - (len(content) + 10) % 8) % 8
    return bytes([pad_len, 0, 0]) + b"\x00" * pad_len + content + b"\x00" * 7

async def oicq_unpad(padded):
    if not padded or len(padded) < 8:
        return None
    if not all(padded[-1 - i] == 0 for i in range(7)):
        return None
    pad_len = padded[0] & 0x07
    s = 3 + pad_len
    e = len(padded) - 7
    return padded[s:e] if s < e else b""

async def encode_header(layout, send_option, cmd, order_id, flags, length, k, v80):
    out = bytearray()
    for code in layout:
        value = {0: send_option, 1: cmd, 2: order_id, 3: flags, 4: length}[code]
        if _FIELD_SIZES[code] == 1:
            out.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            out.append(v & 0xFF)
            out.append((v >> 8) & 0xFF)
    return bytes(out)

async def produce_xor_key(secret_key):
    k = secret_key[0] if secret_key and len(secret_key) > 0 else 10
    return k, ((k << 8) | k) & 0xFFFF

async def parse_layout(layout):
    if isinstance(layout, str):
        return [int(ch) for ch in layout.strip()]
    return list(layout)

async def layouts_from_mask(mask):
    ru = [int(c) for c in str(mask).strip()]
    nr = [c for c in ru if c != 2]
    return ru, nr

async def sv_frame(msg_key, layout, send_option, cmd, order_id, flags, content, key, encrypted=True):
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0]) + await encode_header(layout, send_option, cmd, order_id, flags, len(body), k, v80)
    packet = bytearray(hdr + body)
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet)

async def build_packet(msg_key, layout, send_option, cmd, order_id, flags, content, key, encrypted=True):
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0])
    for code in layout:
        value = {0: send_option, 1: cmd, 2: order_id, 3: flags, 4: len(body)}[code]
        if _FIELD_SIZES[code] == 1:
            hdr.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            hdr.append(v & 0xFF)
            hdr.append((v >> 8) & 0xFF)
    packet = bytearray(hdr + body)
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet)

async def build_hello_packet(text, key, layout):
    data = text.encode("utf-8")
    if len(data) > 25:
        data = data[:25]
    content = len(data).to_bytes(4, "little") + data + b"\x00" * (30 - 4 - len(data))
    k, v80 = await produce_xor_key(key)
    layout = await parse_layout(layout)
    padded = await build_padded(content)
    enc_body = await tea_cbc_encrypt(padded, key)
    header_bytes = await encode_header(layout, 1, 1, 0, 1, len(enc_body), k, v80)
    packet = bytearray([0x63, 0x00]) + header_bytes + enc_body
    packet[1] = await crc7_buff(0, packet[2:]) & 0x7F
    return bytes(packet).hex()

async def build_match_startup_packets(token, udp_key, match_code, account_id, block_val,
                                      server_ip="", region="BD", client_version="1.132.1",
                                      client_version_code="2019121227", access_token=""):
    token = token.strip()
    udp_key = bytes.fromhex(udp_key)
    match_code = [int(ch) for ch in str(match_code).strip()]
    encoded_token = token.encode() if isinstance(token, str) else token

    # Official Client Chunk Size = 1060 bytes
    CHUNK_SIZE = 1060
    chunks = [encoded_token[i:i + CHUNK_SIZE] for i in range(0, len(encoded_token), CHUNK_SIZE)] or [b""]
    thunder_chunks = chunks[:-1]
    encoded_sharma_jwt = chunks[-1]

    thunder_packets = []
    for idx, chunk in enumerate(thunder_chunks):
        garena420 = await has_ssan_zig(len(chunk)) + chunk
        process = await sv_frame(0x5E, match_code, 2, 447, idx, 1, garena420, udp_key)
        thunder_packets.append(process.hex())

    reg = str(region).upper() if region else "BD"
    # Exact csoversea block verified from official capture
    csoversea_block = bytes.fromhex(
        "ca0163736f7665727365612e7374726f6e67686f6c642e66726565666972656d6f62696c652e636f6d"
        "3b302e302e302e303b33342e3132362e37362e34353b33342e38372e3137372e31343b33342e38372e"
        "3137302e3233303b33352e3138352e3138332e35370000010000000100000000000000000000000001"
        "00000000000100010000030100b0e5e4a487da8cdf110200"
    )
    mid = bytes.fromhex('0000000000000101060101') + await has_ssan_zig(len(reg)) + reg.encode()
    mid += bytes.fromhex('0001030001000004')
    mid += await has_ssan_zig(len(client_version)) + client_version.encode()
    mid += await has_ssan_zig(len(client_version_code)) + client_version_code.encode()
    mid += csoversea_block

    clean_ip = server_ip.split(':')[0] if server_ip else "0.0.0.0"
    mid += await has_ssan_zig(len(clean_ip)) + clean_ip.encode()

    # Raw access_token string without md5 hash
    clean_acc_tok = access_token.strip() if access_token else ""
    if clean_acc_tok:
        mid += await has_ssan_zig(len(clean_acc_tok)) + clean_acc_tok.encode()

    # Dynamic has_ssan_zig length prefix + raw sharma chunk
    mid += await has_ssan_zig(len(encoded_sharma_jwt)) + encoded_sharma_jwt

    tg_garena420 = (
        await uleb_encode(int(account_id)) +
        await uleb_encode(int(block_val)) +
        await uleb_encode(1) +
        await uleb_encode(15) +
        await uleb_encode(int(block_val)) +
        await uleb_encode(1) +
        mid
    )
    loading = await sv_frame(0x5A, match_code, 2, 448, len(thunder_packets), 1, tg_garena420, udp_key)
    return thunder_packets, loading.hex()

async def classify(frame):
    cmd = frame["cmd"]
    msg_name = MESSAGE_ID_TO_NAME.get(cmd, f"UNKNOWN_{cmd}")
    if msg_name == "UDP_HELLO": return "HELLO"
    if msg_name == "UDP_ACK": return "ACK"
    if msg_name == "UDP_PING": return "PING"
    if msg_name == "RUDP_JOIN_MATCH": return "JOIN_MATCH"
    return "DATA"

async def reply_for(frame, key, mask, ack_key=0x68, ping_key=0x6D, hello_key=0x5B, ack_style="short"):
    ru, nr = await layouts_from_mask(mask)
    typ = await classify(frame)
    if typ == "HELLO":
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x01\x00", key)
    if typ == "ACK":
        content = frame["content"] if frame["content"] else b"\x01\x00"
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, content, key)
    if typ == "PING":
        c = frame["content"]
        counter = c[:4] if len(c) >= 4 else c
        return typ, await build_packet(ping_key, nr, 0, 3, None, 0, counter + b"\x00\x00\x00", key, encrypted=False)
    if typ == "JOIN_MATCH":
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x02\x00", key)
    return typ, None

async def keepalive_ping(sock, ip, port, key_bytes, mask, stop_event):
    import struct
    nr = (await layouts_from_mask(mask))[1]
    ping_keys = [0x66, 0x6D, 0x69, 0x6C, 0x6B, 0x6E, 0x6F, 0x70]
    loop = asyncio.get_event_loop()
    i = 0
    while not stop_event.is_set():
        pk = ping_keys[i % len(ping_keys)]
        counter = int(time.time() * 1000) & 0xFFFFFFFF
        pkt = await build_packet(pk, nr, 0, 3, None, 0, struct.pack("<I", counter) + b"\x00\x00\x00", key_bytes, encrypted=False)
        try:
            await _udp_sendto(loop, sock, pkt, (ip, port))
        except Exception:
            pass
        i += 1
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            pass


# ---------------------------------------------------------------------------
# Forward walk — CS capture 2026-10-03, cmd 2001, flags=0.
# Straight-walk bodies keep every byte still except a uint16 LE at offset 28,
# which climbs about 7 per packet, and the last 2 bytes (packet seq).
# ---------------------------------------------------------------------------
CMD_PLAYER_STATE_SYNC = 2001
CMD_START_FIRE = 104
CMD_STOP_FIRE = 105
MOVEMENT_MSG_KEYS = [0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D]
FORWARD_POS_OFF = 28
FORWARD_STEP = 7

# One steady forward step from the phone CS match (len 47).
FORWARD_WALK_BODY = bytes.fromhex(
    "8180800896ef138e1d84f8299d01007c00000000000000"
    "d7c5a6fa0bd7e3c3e50baac4f6f80300001100000087c208"
)

# Captured fire state-sync (len=43, byte[22]=1)
FIRE_STATE_TEMPLATES = [
    bytes.fromhex(
        "81808008e6c617ea128ae121c501001100000000000001d9ed83f70b00f8ed97fb03000012000000a0c30a"
    ),
    bytes.fromhex(
        "81808008c8bf17a413cae621a301007200000000000001d9ed83f70b00f8ed97fb0300001200000089d10a"
    ),
]


def build_movement_body(seq: int, step: int = 0) -> bytes:
    """Replay the captured forward walk, advancing the position axis each step."""
    base = bytearray(FORWARD_WALK_BODY)
    origin = int.from_bytes(base[FORWARD_POS_OFF:FORWARD_POS_OFF + 2], "little")
    pos = (origin + (int(step) * FORWARD_STEP)) & 0xFFFF
    base[FORWARD_POS_OFF] = pos & 0xFF
    base[FORWARD_POS_OFF + 1] = (pos >> 8) & 0xFF
    if len(base) >= 3:
        base[-3] = (seq * 3) & 0xFF
    if len(base) >= 2:
        base[-2] = seq & 0xFF
        base[-1] = (seq >> 8) & 0xFF
    return bytes(base)


def build_fire_state_body(seq: int, step: int = 0) -> bytes:
    """State-sync body with fire flag set (byte[22]=1 from live capture)."""
    import random

    base = bytearray(FIRE_STATE_TEMPLATES[step % len(FIRE_STATE_TEMPLATES)])
    if len(base) > 22:
        base[22] = 1
    if len(base) >= 2:
        base[-2] = seq & 0xFF
        base[-1] = (seq >> 8) & 0xFF
    for off in (4, 5, 7, 10):
        if off < len(base) - 4:
            base[off] = (base[off] + random.randint(-1, 1)) & 0xFF
    return bytes(base)


async def anti_afk_movement_worker(
    sock,
    ip,
    port,
    key_bytes,
    mask,
    stop_event,
    activity_touch=None,
    interval: float = 0.35,
    account_id: int = 0,
):
    """
    After JOIN_MATCH_FINISHED, send forward walk state-sync (cmd 2001).
    Each tick advances the captured forward axis. Fire bodies are not mixed
    in — those templates are a different pose and would snap the position back.
    """
    nr = (await layouts_from_mask(mask))[1]
    loop = asyncio.get_event_loop()
    seq = int(time.time() * 1000) & 0xFFFF
    step = 0
    move_sent = 0
    addr = (ip, port)
    print(
        f"[+] [AFK] forward walk armed "
        f"(cmd={CMD_PLAYER_STATE_SYNC}, step={FORWARD_STEP}, interval={interval}s)"
    )
    while not stop_event.is_set():
        try:
            msg_key = MOVEMENT_MSG_KEYS[step % len(MOVEMENT_MSG_KEYS)]
            body = build_movement_body(seq, step)
            pkt = await build_packet(
                msg_key, nr, 0, CMD_PLAYER_STATE_SYNC, None, 0,
                body, key_bytes, encrypted=False,
            )
            await _udp_sendto(loop, sock, pkt, addr)
            move_sent += 1
            seq = (seq + 1) & 0xFFFF
            step += 1
            if activity_touch is not None:
                activity_touch()
            if move_sent == 1 or move_sent % 40 == 0:
                pos = int.from_bytes(body[FORWARD_POS_OFF:FORWARD_POS_OFF + 2], "little")
                print(
                    f"[+] [AFK] forward move={move_sent} pos={pos} "
                    f"seq={seq} body_len={len(body)}"
                )
        except Exception as exc:
            if move_sent < 3:
                print(f"[-] [AFK] send error: {exc}")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
    print(f"[+] [AFK] worker stopped (move={move_sent})")


async def try_header(buf, layout, k, v80):
    off = 2
    out = {}
    for code in layout:
        size = _FIELD_SIZES[code]
        if off + size > len(buf):
            return None
        out[_FIELD_NAMES[code]] = (buf[off] ^ k) if size == 1 else ((buf[off] | (buf[off + 1] << 8)) ^ v80) & 0xFFFF
        off += size
    out["headerLen"] = off
    return out

async def decode_packet(packet, key, mask=None):
    import itertools
    data = bytes(packet) if isinstance(packet, bytes) else bytes.fromhex(packet)
    if len(data) < 8: return None
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    crc_ok = (data[1] & 0x7F) == await crc7_buff(0, data[2:])
    candidates = []
    if mask:
        ru, nr = await layouts_from_mask(mask)
        layouts = [("RUDP", ru), ("nonRUDP", nr)]
    else:
        layouts = [("RUDP", list(p)) for p in itertools.permutations([0, 1, 2, 3, 4])]
        layouts += [("nonRUDP", list(p)) for p in itertools.permutations([0, 1, 3, 4])]
    for kind, layout in layouts:
        await asyncio.sleep(0)
        f = await try_header(data, layout, k, v80)
        if not f or f["flags"] > 7 or f["sendOption"] > 7 or f["length"] != len(data) - f["headerLen"]:
            continue
        body = data[f["headerLen"]:f["headerLen"] + f["length"]]
        content = None
        padded = None
        if f["flags"] & 1:
            if len(body) < 8 or len(body) % 8 != 0: continue
            padded = await tea_cbc_decrypt(body, key)
            content = await oicq_unpad(padded)
            if content is None: continue
        else:
            content = body
        score = (1 if crc_ok else 0) + (1 if content is not None else 0)
        candidates.append({
            "kind": kind, "layout": layout, "headerLen": f["headerLen"],
            "msgKey": data[0], "cmd": f["cmd"], "flags": f["flags"],
            "sendOption": f["sendOption"], "orderId": f.get("orderId"),
            "length": f["length"], "content": content, "crcOk": crc_ok,
            "padded": padded, "score": score, "total": len(data),
        })
    if not candidates: return None
    candidates.sort(key=lambda c: (c["kind"] == "RUDP" or c["kind"] == "nonRUDP", c["score"]), reverse=True)
    return candidates[0]


UDP_DEBUG_FILE = "debug.json"
UDP_SESSION_LOG = {
    "match_id": 0,
    "server_addr": "",
    "secret": "",
    "field_42": "",
    "layout_mask": [],
    "total_packets": 0,
    "decoded_ok": 0,
    "decoded_fail": 0,
    "cmd_stats": {},
    "packets": []
}

def init_udp_debug_session(server_ip, udp_key, match_code):
    global UDP_SESSION_LOG
    mask_list = [int(c) for c in str(match_code).strip()]
    UDP_SESSION_LOG = {
        "match_id": int(time.time() * 1000),
        "server_addr": server_ip,
        "secret": udp_key,
        "field_42": str(match_code),
        "layout_mask": mask_list,
        "total_packets": 0,
        "decoded_ok": 0,
        "decoded_fail": 0,
        "cmd_stats": {},
        "packets": []
    }
    try:
        with open(UDP_DEBUG_FILE, "w") as f:
            json.dump(UDP_SESSION_LOG, f, indent=2)
    except Exception:
        pass

def udp_debug(direction, source, hex_data, decoded_frame=None):
    global UDP_SESSION_LOG
    try:
        UDP_SESSION_LOG["total_packets"] += 1
        decoded_obj = None
        if decoded_frame:
            UDP_SESSION_LOG["decoded_ok"] += 1
            cmd = decoded_frame.get("cmd", 0)
            cmd_name = MESSAGE_ID_TO_NAME.get(cmd, f"CMD_{cmd}")
            UDP_SESSION_LOG["cmd_stats"][cmd_name] = UDP_SESSION_LOG["cmd_stats"].get(cmd_name, 0) + 1
            content = decoded_frame.get("content")
            content_hex = content.hex() if isinstance(content, (bytes, bytearray)) else None
            decoded_obj = {
                "type": decoded_frame.get("kind", "RUDP"),
                "kind": decoded_frame.get("kind", "RUDP"),
                "layout": decoded_frame.get("layout", []),
                "msgKey": f"0x{decoded_frame.get('msgKey', 0):02X}",
                "cmd": cmd,
                "cmdName": cmd_name,
                "flags": decoded_frame.get("flags", 0),
                "sendOption": decoded_frame.get("sendOption", 0),
                "orderId": decoded_frame.get("orderId"),
                "crcOk": decoded_frame.get("crcOk", True),
                "headerLen": decoded_frame.get("headerLen", 10),
                "payloadLen": decoded_frame.get("length", 0),
                "contentHex": content_hex,
                "contentText": None,
                "contentJson": None
            }
        else:
            UDP_SESSION_LOG["decoded_fail"] += 1

        entry = {
            "index": len(UDP_SESSION_LOG["packets"]),
            "direction": direction,
            "source": source,
            "time": time.time(),
            "length": len(hex_data) // 2,
            "hex": hex_data,
            "decoded": decoded_obj
        }
        UDP_SESSION_LOG["packets"].append(entry)
        with open(UDP_DEBUG_FILE, "w") as f:
            json.dump(UDP_SESSION_LOG, f, indent=2)
    except Exception:
        pass


async def play_game(server_ip_port, thunder, sharma, udp_key, match_code,
                    account_id, player_region, client_version, key, iv):
    match_start_time = time.time()
    ping_task = None
    move_task = None
    sock = None
    ping_stop = asyncio.Event()
    move_stop = asyncio.Event()

    try:
        ip, port = server_ip_port.split(":")
        port = int(port)
        resolved_ip = socket.gethostbyname(ip)

        init_udp_debug_session(server_ip_port, udp_key, match_code)

        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        optimize_udp_socket(sock)
        sock.setblocking(False)

        udp_key_bytes = bytes.fromhex(udp_key)
        hello_text = f"{account_id}_2585"
        hello_packet = await build_hello_packet(hello_text, udp_key_bytes, match_code)
        
        decoded_hello = await decode_packet(bytes.fromhex(hello_packet), udp_key_bytes, match_code)
        udp_debug("request", "client", hello_packet, decoded_hello)
        await _udp_sendto(loop, sock, bytes.fromhex(hello_packet), (resolved_ip, port))

        ack_state = "waiting_for_hello_reply"
        thunder_sent = False
        sharma_sent = False
        local_closed = False
        send_lock = asyncio.Lock()

        ping_task = asyncio.create_task(
            keepalive_ping(sock, resolved_ip, port, udp_key_bytes, match_code, ping_stop)
        )
        # PING/keepalive must NOT refresh this — otherwise idle never fires and
        # the outer CS_MATCH_TIMEOUT kills the process mid-"looking for" reconnect.
        # Movement anti-AFK DOES refresh it (counts as real game activity).
        last_game_activity = time.time()

        def touch_activity():
            nonlocal last_game_activity
            last_game_activity = time.time()

        join_finished_at = None
        # Once loaded, stay briefly so the server counts the player, then
        # disconnect. The CS round finishes on auto-gameplay while we are AFK.
        # Level/exp lands a little after the UDP close — caller peeks later.
        POST_JOIN_MAX_S = float(os.environ.get("CS_AFK_POST_JOIN_S", "45"))
        print(f"\n[+] 🎮 UDP Session Started -> {resolved_ip}:{port}")

        async def send_thunder_sharma():
            nonlocal ack_state, thunder_sent, sharma_sent, last_game_activity
            if thunder_sent: return
            async with send_lock:
                if thunder_sent: return
                try:
                    for i, t_pkt in enumerate(thunder):
                        dec_t = await decode_packet(bytes.fromhex(t_pkt), udp_key_bytes, match_code)
                        udp_debug("request", "client", t_pkt, dec_t)
                        await _udp_sendto(loop, sock, bytes.fromhex(t_pkt), (resolved_ip, port))
                        await asyncio.sleep(0.05)
                    thunder_sent = True
                    await asyncio.sleep(0.1)

                    # Handshake ACK (cmd 6 / 2 with 0100)
                    prepare_ack = await build_packet(0x68, (await layouts_from_mask(match_code))[1], 0, 2, None, 1, b"\x01\x00", udp_key_bytes)
                    dec_ack = await decode_packet(prepare_ack, udp_key_bytes, match_code)
                    udp_debug("request", "client", prepare_ack.hex(), dec_ack)
                    await _udp_sendto(loop, sock, prepare_ack, (resolved_ip, port))
                    await asyncio.sleep(0.2)

                    dec_sharma = await decode_packet(bytes.fromhex(sharma), udp_key_bytes, match_code)
                    udp_debug("request", "client", sharma, dec_sharma)
                    await _udp_sendto(loop, sock, bytes.fromhex(sharma), (resolved_ip, port))
                    sharma_sent = True
                    ack_state = "thunder_sharma_sent"
                    last_game_activity = time.time()
                    print(f"[+] 🚀 [UDP] Thunder ({len(thunder)} parts) + Sharma Loaded Successfully into Game Room!")
                except Exception as e:
                    print(f"[-] [UDP] Send error: {e}")

        def start_movement_afk():
            nonlocal move_task
            if move_task is not None:
                return
            move_task = asyncio.create_task(
                anti_afk_movement_worker(
                    sock,
                    resolved_ip,
                    port,
                    udp_key_bytes,
                    match_code,
                    move_stop,
                    activity_touch=touch_activity,
                    interval=float(os.environ.get("CS_AFK_MOVE_INTERVAL", "0.15")),
                    account_id=int(account_id) if account_id else 0,
                )
            )
            print("[+] [AFK] forward walk started (continuous)")

        while not local_closed:
            if time.time() - match_start_time > 700: break
            if join_finished_at is not None and (time.time() - join_finished_at) > POST_JOIN_MAX_S:
                print(
                    f"[+] [UDP] In match {int(POST_JOIN_MAX_S)}s — disconnecting. "
                    "Auto gameplay finishes the round; level check comes after."
                )
                break
            try:
                response, server_addr = await asyncio.wait_for(_udp_recvfrom(loop, sock, 65535), timeout=1.5)
                if response:
                    resp_hex = response.hex()
                    frame = await decode_packet(response, udp_key_bytes, match_code)
                    udp_debug("response", f"{server_addr[0]}:{server_addr[1]}", resp_hex, frame)

                    if frame:
                        cmd = frame.get('cmd')
                        order_id = frame.get('orderId')
                        flags = frame.get('flags', 0)
                        nr_layout = (await layouts_from_mask(match_code))[1]
                        ptype = await classify(frame)

                        # Keepalive traffic must not count as match progress.
                        if ptype != "PING":
                            last_game_activity = time.time()

                        if cmd in [103, 107]:
                            print(f"[+] 🏁 [UDP] Match Finished (Command: {cmd})")
                            local_closed = True
                            continue

                        if cmd == 130:
                            print(f"[+] ✅ [UDP] JOIN_MATCH_FINISHED - Match Fully Loaded into Clash Squad!")
                            if join_finished_at is None:
                                join_finished_at = time.time()
                            start_movement_afk()
                            try:
                                next_id = ((order_id or 0) + 1) & 0xFFFF
                                fin_ack = await build_packet(0x68, nr_layout, 0, 2, None, 1, next_id.to_bytes(2, "little"), udp_key_bytes)
                                dec_fa = await decode_packet(fin_ack, udp_key_bytes, match_code)
                                udp_debug("request", "client", fin_ack.hex(), dec_fa)
                                await _udp_sendto(loop, sock, fin_ack, server_addr)
                            except Exception: pass
                            continue

                        # Crucial Fix: Cumulative ACK (orderId + 1) for all incoming reliable packets
                        if (flags & 1) and order_id is not None:
                            try:
                                next_expected_id = (order_id + 1) & 0xFFFF
                                data_ack = await build_packet(0x68, nr_layout, 0, 2, None, 1, next_expected_id.to_bytes(2, "little"), udp_key_bytes)
                                dec_da = await decode_packet(data_ack, udp_key_bytes, match_code)
                                udp_debug("request", "client", data_ack.hex(), dec_da)
                                await _udp_sendto(loop, sock, data_ack, server_addr)
                            except Exception: pass

                        if ptype == "HELLO" and ack_state == "waiting_for_hello_reply":
                            _, reply = await reply_for(frame, udp_key_bytes, match_code, ack_style="short")
                            if reply:
                                dec_rep = await decode_packet(reply, udp_key_bytes, match_code)
                                udp_debug("request", "client", reply.hex(), dec_rep)
                                await _udp_sendto(loop, sock, reply, server_addr)
                            ack_state = "ready_to_send_thunder"
                        elif ptype == "ACK":
                            if ack_state in ["waiting_for_hello_reply", "ack_sent_waiting"]:
                                ack_state = "ready_to_send_thunder"
                        elif ptype == "PING":
                            _, reply = await reply_for(frame, udp_key_bytes, match_code)
                            if reply:
                                dec_rep = await decode_packet(reply, udp_key_bytes, match_code)
                                udp_debug("request", "client", reply.hex(), dec_rep)
                                await _udp_sendto(loop, sock, reply, server_addr)
            except asyncio.TimeoutError:
                if ack_state == "ready_to_send_thunder" and not thunder_sent:
                    await send_thunder_sharma()
                elif ack_state == "thunder_sharma_sent":
                    # Ignore PING-only keepalive; real game silence ends the session.
                    idle = time.time() - last_game_activity
                    if idle > 90.0:
                        print(f"[+] [UDP] No game packets for {int(idle)}s after join — ending session")
                        break
                continue
            except Exception:
                await asyncio.sleep(0.5)

            if ack_state == "ready_to_send_thunder" and not thunder_sent:
                await send_thunder_sharma()

    except Exception as e:
        print(f"[-] [UDP Error]: {e}")
    finally:
        move_stop.set()
        ping_stop.set()
        if move_task:
            move_task.cancel()
            try:
                await move_task
            except (asyncio.CancelledError, Exception):
                pass
        if ping_task: ping_task.cancel()
        if sock:
            try: sock.close()
            except Exception: pass
        print(f"[+] [UDP Closed] Socket cleaned up.")
        print(f"[+] 🏁 [CS-ENGINE] Match Completed cleanly! Exiting engine...")
        await asyncio.sleep(1)
        os._exit(0)
# ===================================================================
























class CLIENT:
    def __init__(self):
        self.whisper_writer = None
        self.online_writer = None
        self.uid = None
        self.room_uid = None
        self.response = None
        self.inPuTMsG = None
        self.chat_id = None
        self.data = None
        self.data2 = None
        self.key = None
        self.iv = None
        self.STATUS = None
        self.AutHToKen = None
        self.OnLineiP = None
        self.OnLineporT = None
        self.ChaTiP = None
        self.ChaTporT = None
        self.LoGinDaTaUncRypTinG = None

        self.response = None
        self.uid = None
        self.chat_id = None
        self.XX = None
        self.inPuTMsG = None
        self.insquad = None
        self.sent_inv = None
        self.ping_loop_started = False

    async def room_keep_alive_loop(self, key, iv):
        """Har 10 second me Room Ping Packet bhejega jab tak bot room me hai"""
        while True:
            try:
                await asyncio.sleep(10)
                if getattr(self, 'room_uid', None) and self.online_writer:
                    ping_pkt = await Send_Room_Ping_Packet(key, iv)
                    self.online_writer.write(ping_pkt)
                    await self.online_writer.drain()
            except Exception as e:
                pass
        self.ping_loop_started = False

    async def room_keep_alive_loop(self, key, iv):
        """Har 10 second me Room Ping Packet bhejega jab tak bot room me hai"""
        while True:
            try:
                await asyncio.sleep(10)
                if getattr(self, 'room_uid', None) and self.online_writer:
                    ping_pkt = await Send_Room_Ping_Packet(key, iv)
                    self.online_writer.write(ping_pkt)
                    await self.online_writer.drain()
            except Exception as e:
                pass
    async def cHTypE(self,H):
        if not H: return 'Squid'
        elif H == 1: return 'CLan'
        elif H == 2: return 'PrivaTe'
        
    async def SEndMsG(self,H , message , Uid , chat_id , key , iv):
        TypE = await self.cHTypE(H)
        if TypE == 'Squid': msg_packet = await xSEndMsgsQ(message , chat_id , key , iv)
        elif TypE == 'CLan': msg_packet = await xSEndMsg(message , 1 , chat_id , chat_id , key , iv)
        elif TypE == 'PrivaTe': msg_packet = await xSEndMsg(message , 2 , Uid , Uid , key , iv)
        return msg_packet

    async def SEndPacKeT(self,OnLinE , ChaT , TypE , PacKeT):
        if TypE == 'ChaT' and ChaT: self.whisper_writer.write(PacKeT) ; await self.whisper_writer.drain()
        elif TypE == 'OnLine': self.online_writer.write(PacKeT) ; await self.online_writer.drain()
        else: return 'UnsoPorTed TypE ! >> ErrrroR (:():)' 
           
    async def TcPOnLine(self,ip, port, key, iv, AutHToKen, region="BD", reconnect_delay=0.5):
        global  spam_room , spammer_uid , spam_chat_id , spam_uid , XX , uid , Spy, Chat_Leave , joining_team
        while True:
            gateway_ping_task = None
            try:
                self._cs_mm_sent_this_conn = False
                self._online_ok = False
                print(f"[+] [ONLINE] connecting {ip}:{port} ...")
                reader , writer = await asyncio.open_connection(ip, int(port))
                self.online_writer = writer
                try:
                    raw_sock = writer.get_extra_info("socket")
                    if raw_sock is not None:
                        raw_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                except Exception:
                    pass

                bytes_payload = bytes.fromhex(AutHToKen)
                self.online_writer.write(bytes_payload)
                await self.online_writer.drain()
                print(f"[+] [ONLINE] auth packet sent ({len(bytes_payload)} bytes)")

                # LW Main / working cs_boost: immediate KA right after auth (OB55)
                try:
                    init_ka = await send_keep_alive(region)
                    self.online_writer.write(init_ka)
                    await self.online_writer.drain()
                    print(f"[+] [ONLINE] init keepalive sent ({init_ka.hex()})")
                except Exception:
                    pass

                async def _gateway_keepalive():
                    await asyncio.sleep(5.0)
                    ka = await send_keep_alive(region)
                    while True:
                        try:
                            w = self.online_writer
                            if w is None or w.is_closing():
                                break
                            w.write(ka)
                            await w.drain()
                        except Exception:
                            break
                        await asyncio.sleep(5.0)

                gateway_ping_task = asyncio.create_task(_gateway_keepalive())

                if not getattr(self, 'ping_loop_started', False):
                    asyncio.create_task(self.room_keep_alive_loop(key, iv))
                    self.ping_loop_started = True

                print(f"[+] [ONLINE] TCP connected {ip}:{port} — reading (gateway keepalive on)")

                # Queue CS Solo after Online has a moment to accept auth
                async def _delayed_cs_mm():
                    await asyncio.sleep(2.0)
                    if getattr(self, "_cs_udp_match_running", False):
                        print("[i] [CS-ENGINE] TCP reconnect during UDP match — skip auto matchmaking")
                        return
                    if getattr(self, "_cs_mm_sent_this_conn", False):
                        print("[i] [CS-ENGINE] matchmaking already sent this TCP session")
                        return
                    if getattr(self, "_online_rejected", False):
                        print("[-] [CS-ENGINE] Online rejected (status 11) — skip matchmaking")
                        return
                    if self.online_writer is None or self.online_writer.is_closing():
                        print("[-] [CS-ENGINE] Online socket closed before matchmaking")
                        return
                    try:
                        cs_pkt = await CS_Solo_Start_Matchmaking_Packet(key, iv, region=region)
                        self.online_writer.write(cs_pkt)
                        await self.online_writer.drain()
                        self._cs_mm_sent_this_conn = True
                        print(f"\n[+] [CS-ENGINE] CS Solo matchmaking sent ({len(cs_pkt)} bytes, Online live)")
                    except Exception as e:
                        print(f"[-] [CS-ENGINE] Failed to send matchmaking packet: {e}")

                self._online_rejected = False
                asyncio.create_task(_delayed_cs_mm())

                while True:
                    self.data2 = await reader.read(9999)
                    data2 = self.data2
                    if not data2:
                        print("[-] [ONLINE] server closed TCP (empty read)")
                        break
                    
                    if self.data2:
                        hex_data = self.data2.hex()
                        
                        # --- DEBUG ALL INCOMING PACKETS ---
                        try:
                            if not hex_data.startswith("0200") and not hex_data.startswith("0300"): 
                                print(f"\n[DEBUG] 📥 INCOMING PACKET HEADER: {hex_data[:10]}")
                                decoded_response = await DeCode_PackEt(hex_data[10:])
                                if decoded_response and "{}" not in decoded_response:
                                    print(f"[DEBUG] 📥 INCOMING JSON PREVIEW:\n{decoded_response}\n")
                                    
                                    # --- GLOBAL CAPTAIN & SQUAD ID EXTRACTOR ---
                                    packet_json = json.loads(decoded_response)
                                    # 0b00 = Online gateway status / reject
                                    if hex_data.startswith("0b00"):
                                        st = packet_json.get("2", {}).get("data")
                                        if st == 11:
                                            self._online_rejected = True
                                            print("[-] [ONLINE] status=11 (session rejected / kick) — will reconnect")
                                        else:
                                            print(f"[+] [ONLINE] gateway status={st}")
                                            self._online_ok = True
                                            self._online_rejected = False
                                    if hex_data.startswith("0500"):
                                        sq_data = packet_json.get("5", {}).get("data", {})
                                        if sq_data:
                                            ow_uid = sq_data.get("1", {}).get("data")
                                            if isinstance(ow_uid, int) and ow_uid > 10000:
                                                self.captain_uid = ow_uid
                                            sq_code = sq_data.get("31", {}).get("data") or sq_data.get("8", {}).get("data")
                                            if isinstance(sq_code, int) and sq_code > 10000:
                                                self.group_id = sq_code

                                    elif hex_data.startswith("0f00"):
                                        self._online_ok = True
                                        st_data = packet_json.get("5", {}).get("data", {}).get("1", {}).get("data", {})
                                        if st_data and isinstance(st_data, dict):
                                            g_owner = st_data.get("8", {}).get("data")
                                            if isinstance(g_owner, int) and g_owner > 10000:
                                                self.captain_uid = g_owner
                                    # -------------------------------------------
                        except Exception as e:
                            pass 
                        # ----------------------------------

                        # --- 🔥 MATCH DETECT & AUTO UDP CONNECT ---
                        match_idx = hex_data.find("0300")
                        if match_idx != -1 and (len(hex_data) - match_idx) >= 100:
                            try:
                                match_hex = hex_data[match_idx:]
                                decoded_match = await DeCode_PackEt(match_hex[10:])
                                if decoded_match:
                                    res = json.loads(decoded_match)
                                    match_code = None
                                    server_ip_port = None
                                    udp_key = None
                                    match_token = None
                                    block_val = None
                                    match_account_id = None

                                    if '42' in res and 'data' in res['42']:
                                        match_code = res['42']['data']
                                    if '5' in res and 'data' in res['5']:
                                        res_field5 = res['5']['data']
                                        server_ip_port = res_field5.get('2', {}).get('data')
                                        udp_key = res_field5.get('3', {}).get('data')
                                        match_token = res_field5.get('4', {}).get('data')
                                        if '42' in res_field5:
                                            match_code = res_field5['42']['data']
                                        block_val = res_field5.get('1', {}).get('data')
                                    if '1' in res and 'data' in res['1']:
                                        match_account_id = res['1']['data']

                                    effective_acc_id = match_account_id or getattr(self, 'bot_uid', None) or uid
                                    cur_region = getattr(self, 'region', 'BD') or "BD"

                                    if match_token and udp_key and match_code and server_ip_port:
                                        print("\n" + "=" * 55)
                                        print(f"[+] 🎯 MATCH ALLOTMENT DETECTED FROM SERVER!")
                                        print(f"[+] Server: {server_ip_port} | Match Code: {match_code}")
                                        print("=" * 55)

                                        thunder, sharma = await build_match_startup_packets(
                                            match_token, udp_key, match_code, effective_acc_id, block_val or 0,
                                            server_ip=server_ip_port,
                                            region=cur_region,
                                            client_version=version,
                                            access_token=getattr(self, 'access_token', '') or ""
                                        )

                                        # Background UDP — mark in-match so TCP reconnect
                                        # does not spam Start Matchmaking again.
                                        self._cs_udp_match_running = True
                                        asyncio.create_task(
                                            play_game(
                                                server_ip_port, thunder, sharma, udp_key, match_code,
                                                effective_acc_id, cur_region, version,
                                                key, iv
                                            )
                                        )
                            except Exception as e:
                                print(f"[-] Match packet parsing error: {e}")

                        if self.data2.hex().startswith("0f00"):
                            info = await DeCode_PackEt(self.data2.hex()[10:])
                            #print(info)
                            self.STATUS = get_player_status(info)
                            
                            # Jab bot kick ho kar SOLO lobby me aa jaye toh insquad reset karein
                            if isinstance(self.STATUS, str) and "SOLO" in self.STATUS:
                                self.insquad = None

                            if isinstance(self.STATUS, dict) and "IN_ROOM" in self.STATUS:
                                room_uid = self.STATUS['room_uid']
                                await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , await SendRoomInfo(int(room_uid),key,iv))
                            else:
                                message = self.STATUS
                                P = await self.SEndMsG(2 , message , uid , chat_id , key , iv)
                                await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , P)

                        if self.data2.hex().startswith("0e00"):
                            info = await DeCode_PackEt(self.data2.hex()[10:])
                            try:
                                info_json = json.loads(info)
                                squad_data = info_json.get("5", {}).get("data", {})
                                
                                # Check if Room Created or Room Data Received
                                if isinstance(squad_data, dict) and "1" in squad_data:
                                    room_id = squad_data["1"].get("data") or squad_data.get("1", {}).get("data")
                                    if isinstance(room_id, int) and room_id > 1000:
                                        self.room_uid = room_id
                                        room_name = squad_data.get("2", {}).get("data", "CROWNX")
                                        password = squad_data.get("10", {}).get("data", "No Pass")

                                        # Success Message to Chat
                                        success_msg = f"[B][C][00FF00]✅ ROOM CREATED SUCCESSFULLY!\n\n[FFFFFF]Room ID: [FFFF00]{xMsGFixinG(room_id)}\n[FFFFFF]Name: [00FFFF]{room_name}\n[FFFFFF]Password: [FF00FF]{password}"
                                        if uid and chat_id:
                                            P = await self.SEndMsG(2, success_msg, uid, chat_id, key, iv)
                                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)

                                if "2" in info_json and info_json["2"].get("data") == 14:
                                    err_code = info_json.get("5", {}).get("data", {}).get("2", {}).get("data", "Unknown")
                                    err_msg = f"[B][C][FF0000]Room Create Failed!\nError Code: {err_code}\n(No Room Cards / Card Limit)"
                                    if uid and chat_id:
                                        P = await self.SEndMsG(2, err_msg, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                else:
                                    message = get_room_info(info)
                                    if message and uid and chat_id:
                                        P = await self.SEndMsG(2 , message , uid , chat_id , key , iv)
                                        await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , P)
                            except Exception as e:
                                pass



                            
                        # --- INCOMING SQUAD & INVITE HANDLING ---
                        if self.data2.hex().startswith("0500"):
                            try:
                                packet = await DeCode_PackEt(self.data2.hex()[10:])
                                if packet:
                                    packet_json = json.loads(packet)
                                    sq_f5 = packet_json.get('5', {}).get('data', {})

                                    action_id = sq_f5.get('1', {}).get('data') if isinstance(sq_f5, dict) else None
                                    err_msg = str(sq_f5.get('2', {}).get('data', '')) if isinstance(sq_f5, dict) else ''

                                    # 1. Kicked / Left / Disbanded / Abnormal Data Detection -> State Reset
                                    if action_id in [7, 8, 71] or "Abnormal" in err_msg:
                                        print(f"[!] Squad left/kicked/disbanded (Action: {action_id}). Resetting squad state...")
                                        self.insquad = None

                                    # 2. Invite Detection
                                    elif isinstance(sq_f5, dict):
                                        squad_owner = sq_f5.get('1', {}).get('data')
                                        squad_code = sq_f5.get('31', {}).get('data') or sq_f5.get('8', {}).get('data')

                                        # Real invite code me hamesha '_' hota hai
                                        is_real_invite = isinstance(squad_code, str) and "_" in squad_code

                                        # Agar bot squad me nahi hai YA naya invite aya hai tab accept karega
                                        if (not self.insquad or is_real_invite) and isinstance(squad_owner, int) and squad_owner > 10000 and squad_code:
                                            print(f"\n[+] 📩 SQUAD INVITE DETECTED from UID: {squad_owner} | Code: {squad_code}")
                                            join_pkt = await ArohiAccepted(squad_owner, squad_code, key, iv, region=getattr(self, 'region', 'BD'), client_ver=version)
                                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', join_pkt)
                                            print(f"[+] 🚀 Accept Packet Sent to Server Successfully!")
                                            self.insquad = True
                                            joining_team = True
                            except Exception as e:
                                pass

                        

                        if self.data2.hex().startswith('0500') and len(self.data2.hex()) > 1000 and joining_team:
                            try:

                                packet = await DeCode_PackEt(self.data2.hex()[10:])

                                packet = json.loads(packet)
                                OwNer_UiD , CHaT_CoDe , SQuAD_CoDe = await GeTSQDaTa(packet)
                                JoinCHaT = await AutH_Chat(3 , OwNer_UiD , CHaT_CoDe, key,iv)
                                await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , JoinCHaT)
                                message = f"[B][C]{get_random_color()}\n- WeLComE To Emote Bot ! \n\n{get_random_color()}- Commands : @a {xMsGFixinG('123456789')} {xMsGFixinG('909000001')}\n\n[00FF00]Dev : @{xMsGFixinG('redzedking')}"
                                P = await self.SEndMsG(0 , message , OwNer_UiD , OwNer_UiD , key , iv)
                                await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , P)
                            except:
                                if self.data2.hex().startswith('0500') and len(self.data2.hex()) > 1000:
                                    try:

                                        packet = await DeCode_PackEt(self.data2.hex()[10:])

                                        packet = json.loads(packet)
                                        OwNer_UiD , CHaT_CoDe , SQuAD_CoDe = await GeTSQDaTa(packet)
                                        self.captain_uid = OwNer_UiD # Auto Captain ID Fetch
                                        self.group_id = SQuAD_CoDe # Auto Group ID Fetch
                                        JoinCHaT = await AutH_Chat(3 , OwNer_UiD , CHaT_CoDe, key,iv)
                                        await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , JoinCHaT)
                                        message = f"[B][C]{get_random_color()}\n- WeLComE To Emote Bot ! \n\n{get_random_color()}- Commands : @a {xMsGFixinG('123456789')} {xMsGFixinG('909000001')}\n\n[00FF00]Dev : @{xMsGFixinG('redzedking')}"
                                        P = await self.SEndMsG(0 , message , OwNer_UiD , OwNer_UiD , key , iv)
                                        await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , P)
                                    except:
                                        pass
                        joining_team = False

                if self.whisper_writer is not None:
                    try:
                        self.whisper_writer.close()
                        await self.whisper_writer.wait_closed()
                    except Exception as e:
                        print(f"Error closing whisper_writer: {e}")
                    finally:
                        self.whisper_writer = None

                if self.online_writer is not None:
                    try:
                        self.online_writer.close()
                        await self.online_writer.wait_closed()
                    except Exception as e:
                        print(f"Error closing online_writer: {e}")
                    finally:
                        self.online_writer = None

                self.insquad = None




            except Exception as e: print(f"- ErroR With {ip}:{port} - {e}") ; self.online_writer = None
            finally:
                if gateway_ping_task is not None:
                    try:
                        gateway_ping_task.cancel()
                    except Exception:
                        pass
            await asyncio.sleep(max(reconnect_delay, 5.0))
                                
    async def TcPChaT(self,ip, port, AutHToKen, key, iv, LoGinDaTaUncRypTinG, ready_event, region="BD", reconnect_delay=0.5):

        global spam_room, spammer_uid , spam_chat_id , spam_uid , chat_id , uid , Spy, Chat_Leave , joining_team
        while True:
            try:
                reader , writer = await asyncio.open_connection(ip, int(port))
                self.whisper_writer = writer
                bytes_payload = bytes.fromhex(AutHToKen)
                self.whisper_writer.write(bytes_payload)
                await self.whisper_writer.drain()

                # Send initial keepalive pulse right after connecting in OB55
                try:
                    init_ka = await send_keep_alive(region)
                    self.whisper_writer.write(init_ka)
                    await self.whisper_writer.drain()
                except Exception:
                    pass
                ready_event.set()
                if LoGinDaTaUncRypTinG.Clan_ID:
                    clan_id = LoGinDaTaUncRypTinG.Clan_ID
                    clan_compiled_data = LoGinDaTaUncRypTinG.Clan_Compiled_Data
                    print('\n - TarGeT BoT in CLan ! ')
                    print(f' - Clan Uid > {clan_id}')
                    print(f' - BoT ConnEcTed WiTh CLan ChaT SuccEssFuLy ! ')
                    pK = await AuthClan(clan_id , clan_compiled_data , key , iv)
                    if self.whisper_writer: self.whisper_writer.write(pK) ; await self.whisper_writer.drain()
                while True:
                    self.data = await reader.read(9999)
                    data=self.data


                    if not data: break



                    if data.hex().startswith("120000"):

                        msg = await DeCode_PackEt(data.hex()[10:])
                        chatdata = json.loads(msg)
                        try:
                            self.response = await DecodeWhisperMessage(data.hex()[10:])
                            uid = self.response.Data.uid
                            chat_id = self.response.Data.Chat_ID
                            self.XX = self.response.Data.chat_type
                            self.inPuTMsG = self.response.Data.msg.lower()
                        except:
                            self.response = None


                        if self.response:
                            if self.inPuTMsG.startswith('/mq'):
                                for i in range(100):
                                    lag(self.JWT)
                                    await asyncio.sleep(0.00003)
                            if self.inPuTMsG.startswith('/room'):
                                parts = self.inPuTMsG.strip().split()

                                if len(parts) < 3:
                                    message = f"[B][C]{get_random_color()}Use The Command like this : /room uid {xMsGFixinG('password')} !"
                                    P = await self.SEndMsG(self.response.Data.chat_type , message , uid , chat_id , key , iv)
                                    await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , P)

                                uid_room = parts[1].strip()
                                self.room_uid = uid_room
                                password = parts[2].strip()

                                Join = await Join_Custom_Room_Packet(uid_room, password, key, iv)
                                await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine', Join)

                            if self.inPuTMsG.startswith('/join'):
                                try:
                                    parts = self.inPuTMsG.strip().split()
                                    if len(parts) < 2:
                                        message = f"[B][C]{get_random_color()}Usage: /join <room_id> <password>"
                                        P = await self.SEndMsG(self.response.Data.chat_type, message, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                    else:
                                        uid_room = parts[1].strip()
                                        password = parts[2].strip() if len(parts) > 2 else ""
                                        self.room_uid = uid_room

                                        message = f"[B][C]{get_random_color()}Joining Room: {uid_room}..."
                                        P = await self.SEndMsG(self.response.Data.chat_type, message, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)

                                        Join = await Join_Custom_Room_Packet(uid_room, password, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', Join)
                                except Exception as e:
                                    print(f"Error executing /join: {e}")

                            if self.inPuTMsG.startswith('/leave'):
                                uid_room = self.room_uid
                                leave = await RedZedLeaveRoom(uid_room,key,iv)
                                await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine', leave)

                            # --- NEW ROOM COMMAND (No Slash) ---
                            if self.inPuTMsG.startswith('room '):
                                try:
                                    parts = self.inPuTMsG.strip().split()
                                    room_name = parts[1].strip() if len(parts) > 1 else "CROWNX"
                                    password = parts[2].strip() if len(parts) > 2 else ""

                                    message = f"[B][C]{get_random_color()}Creating Custom Room...\nName: {room_name}\nPass: {password or 'None'}"
                                    P = await self.SEndMsG(self.response.Data.chat_type, message, uid, chat_id, key, iv)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)

                                    room_pkt = await Create_My_Fav_Room_Packet(room_name, password, key, iv)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', room_pkt)
                                except Exception as e:
                                    print(f"Error creating room: {e}")

                            # --- SLOT CHANGE COMMAND ---
                            if self.inPuTMsG.startswith('slot '):
                                try:
                                    parts = self.inPuTMsG.strip().split()
                                    if len(parts) >= 3 and getattr(self, 'room_uid', None):
                                        sq_num = int(parts[1]) - 1 # Squad 1 = 0, Squad 2 = 1
                                        slot_num = int(parts[2]) - 1 # Slot 1 = 0, Slot 2 = 1
                                        if sq_num < 0: sq_num = 0
                                        if slot_num < 0: slot_num = 0

                                        target_uid = self.bot_uid or uid
                                        slot_pkt = await Change_Room_Slot_Packet(self.room_uid, target_uid, sq_num, slot_num, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', slot_pkt)

                                        msg = f"[B][C]{get_random_color()}Success! Slot changed to Squad {parts[1]} Slot {parts[2]}"
                                        P = await self.SEndMsG(self.response.Data.chat_type, msg, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                    else:
                                        msg = f"[B][C]{get_random_color()}Usage: slot <squad_num> <slot_num>"
                                        P = await self.SEndMsG(self.response.Data.chat_type, msg, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                except Exception as e:
                                    print(f"Error changing slot: {e}")

                            # --- SUSPECT (SPECTATE) COMMAND ---
                            if self.inPuTMsG.strip() in ('suspect', '/suspect'):
                                try:
                                    if getattr(self, 'room_uid', None):
                                        target_uid = self.bot_uid or uid
                                        spec_pkt = await Spectate_Room_Packet(self.room_uid, target_uid, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', spec_pkt)

                                        msg = f"[B][C]{get_random_color()}Success! Moved to Spectator Mode."
                                        P = await self.SEndMsG(self.response.Data.chat_type, msg, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                    else:
                                        msg = f"[B][C]{get_random_color()}Error: Bot is not in a Custom Room!"
                                        P = await self.SEndMsG(self.response.Data.chat_type, msg, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                except Exception as e:
                                    print(f"Error moving to spectate: {e}")

                            # --- RECRUIT COMMAND ---
                            if self.inPuTMsG.strip() in ('recruit', '/recruit'):
                                try:
                                    target_uid = self.bot_uid or uid

                                    # 1. First Recruit Packet (Action 66)
                                    pkt1 = await Squad_Recruit_Start_Packet(target_uid, key, iv)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', pkt1)

                                    # 0.5 sec delay
                                    await asyncio.sleep(0.5)

                                    # 2. Second Recruit Broadcast Packet (Action 17)
                                    pkt2 = await Squad_Recruit_Broadcast_Packet(target_uid, key, iv)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', pkt2)

                                    # Custom Room Recruit (if in room)
                                    if getattr(self, 'room_uid', None):
                                        rec_pkt = await Room_Recruit_Packet(self.room_uid, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', rec_pkt)

                                    msg = f"[B][C]{get_random_color()}Success! Recruitment Started Successfully."
                                    P = await self.SEndMsG(self.response.Data.chat_type, msg, uid, chat_id, key, iv)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                except Exception as e:
                                    print(f"Error starting recruit: {e}")

                            # --- STOP RECRUIT COMMAND ---
                            if self.inPuTMsG.strip() in ('stoprecruit', '/stoprecruit'):
                                try:
                                    if getattr(self, 'room_uid', None):
                                        stop_rec_pkt = await Room_Stop_Recruit_Packet(self.room_uid, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', stop_rec_pkt)

                                        msg = f"[B][C]{get_random_color()}Success! Room Recruitment Stopped."
                                        P = await self.SEndMsG(self.response.Data.chat_type, msg, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                except Exception as e:
                                    print(f"Error stopping recruit: {e}")

                            # --- CANCEL MATCHMAKING COMMAND ---
                            if self.inPuTMsG.strip() in ('cancel', '/cancel'):
                                try:
                                    target_uid = self.bot_uid or uid
                                    cancel_pkt = await CS_Solo_Cancel_Matchmaking_Packet(target_uid, key, iv)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', cancel_pkt)

                                    msg = f"[B][C]{get_random_color()}Matchmaking Canceled Successfully."
                                    P = await self.SEndMsG(self.response.Data.chat_type, msg, uid, chat_id, key, iv)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                except Exception as e:
                                    print(f"Error canceling matchmaking: {e}")

                            # --- START / SPAM START COMMAND ---
                            if self.inPuTMsG.startswith(('start', '/start')):
                                try:
                                    parts = self.inPuTMsG.strip().split()
                                    target_uid = self.bot_uid or uid

                                    # agar 'start 10' jaisa count diya gaya ho
                                    if len(parts) > 1 and parts[1].isdigit():
                                        count = int(parts[1])
                                        if count > 50: count = 50 # safety limit

                                        msg = f"[B][C]{get_random_color()}Spamming Start & Cancel Matchmaking ({count} times)..."
                                        P = await self.SEndMsG(self.response.Data.chat_type, msg, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)

                                        for i in range(count):
                                            st_pkt = await CS_Solo_Start_Matchmaking_Packet(key, iv)
                                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', st_pkt)
                                            await asyncio.sleep(0.2)

                                            cn_pkt = await CS_Solo_Cancel_Matchmaking_Packet(target_uid, key, iv)
                                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', cn_pkt)
                                            await asyncio.sleep(0.2)

                                        msg_done = f"[B][C]{get_random_color()}Spam Completed ({count} times)!"
                                        P_done = await self.SEndMsG(self.response.Data.chat_type, msg_done, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P_done)

                                    elif getattr(self, 'room_uid', None):
                                        # Custom room start
                                        start_room_pkt = await Start_Room_Match_Packet(self.room_uid, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', start_room_pkt)

                                        msg = f"[B][C]{get_random_color()}Starting Custom Room Match..."
                                        P = await self.SEndMsG(self.response.Data.chat_type, msg, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                    else:
                                        # CS Solo Matchmaking Start
                                        st_pkt = await CS_Solo_Start_Matchmaking_Packet(key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', st_pkt)

                                        msg = f"[B][C]{get_random_color()}Clash Squad Solo Matchmaking Started!"
                                        P = await self.SEndMsG(self.response.Data.chat_type, msg, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                except Exception as e:
                                    print(f"Error executing start command: {e}")
                                
                                
                                
                            if self.inPuTMsG.strip().startswith('/craftstart'):
                                try:
                                    parts = self.inPuTMsG.strip().split()
                                    map_code = parts[1].strip() if len(parts) > 1 else "A26C60"

                                    message = f"[B][C]{get_random_color()}Starting Craftland Match...\nMap Code: {map_code}"
                                    P = await self.SEndMsG(self.response.Data.chat_type, message, uid, chat_id, key, iv)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)

                                    pkt = await Craftland_Start_Packet(map_code, key, iv)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', pkt)
                                except Exception as e:
                                    print(f"Error executing /craftstart: {e}")
                                
                                
                            if self.inPuTMsG.strip().startswith('/create'):
                                try:
                                    parts = self.inPuTMsG.strip().split()
                                    if len(parts) < 3:
                                        message = f"[B][C]{get_random_color()}Usage: /create <name> <password>"
                                        P = await self.SEndMsG(self.response.Data.chat_type, message, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                    else:
                                        room_name = parts[1].strip()
                                        password = parts[2].strip()

                                        message = f"[B][C]{get_random_color()}Creating Custom Room...\nName: {room_name}\nPass: {password}"
                                        P = await self.SEndMsG(self.response.Data.chat_type, message, uid, chat_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)

                                        room_pkt = await Create_Custom_Room_Packet(room_name, password, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', room_pkt)
                                except Exception as e:
                                    print(f"Error creating custom room: {e}")

                            if self.inPuTMsG.strip().startswith('/createroom'):
                                try:
                                    print(f"\n[DEBUG] 🟢 Command /createroom received from UID: {uid}")
                                    message = f"[B][C]{get_random_color()}Creating Regular Room...\nMap: Bermuda\nMode: Clash Squad\nPass: 1234"
                                    P = await self.SEndMsG(self.response.Data.chat_type , message , uid , chat_id , key , iv)
                                    await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , P)
                                    
                                    # Fixed Values (Name, Password)
                                    print(f"[DEBUG] 🟢 Calling Create_Room_Packet (Regular)...")
                                    room_pkt = await Create_Room_Packet("RedZed Room", "1234", key, iv)
                                    await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , room_pkt)
                                    print(f"[DEBUG] 🟢 Create_Room_Packet (Regular) Sent to Server Successfully!")
                                except Exception as e:
                                    print(f"[DEBUG] 🔴 Error creating room: {e}")

                            if self.inPuTMsG.strip().startswith('/send'):
                                try:
                                    parts = self.inPuTMsG.strip().split()
                                    # Custom Captain ID parse: /send 123456789 (optional)
                                    if len(parts) > 1 and parts[1].isdigit():
                                        cap_id = int(parts[1])
                                    else:
                                        # Auto fetch captain ID
                                        cap_id = getattr(self, 'captain_uid', 0)
                                        
                                    if not cap_id:
                                        err_msg = f"[B][C][FF0000]Captain ID not found!\nPlease use: /send <captain_uid>"
                                        P = await self.SEndMsG(self.response.Data.chat_type , err_msg , uid , chat_id , key , iv)
                                        await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , P)
                                    else:
                                        # In squad chat, chat_id is always the exact group_id!
                                        grp_id = chat_id 
                                        
                                        print(f"\n[DEBUG] 🟢 Sending CAPTAIN_START Remind to Captain: {cap_id} | Group: {grp_id}")
                                        remind_pkt = await Group_Remind_Packet(grp_id, cap_id, key, iv)
                                        await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , remind_pkt)
                                        print(f"[DEBUG] 🟢 Group_Remind_Packet Sent Successfully!")
                                        
                                        message = f"[B][C]{get_random_color()}Remind Sent to Captain: {xMsGFixinG(cap_id)}!"
                                        P = await self.SEndMsG(self.response.Data.chat_type , message , uid , chat_id , key , iv)
                                        await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , P)
                                except Exception as e:
                                    print(f"[DEBUG] 🔴 Error sending remind: {e}")

                            if self.inPuTMsG.startswith('/kick'):
                                try:
                                    for i in range(2111):
                                        C = await new_lag(key, iv)
                                        await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , C)
                                        await asyncio.sleep(0.003)
                                    print('finished')
                                except Exception as e:
                                    print(e)
                            if self.inPuTMsG.startswith(("/s5")):
                                try:
                                    dd = chatdata['5']['data']['16']
                                    print('msg in private')
                                    message = f"[B][C]{get_random_color()}\n\nAccepT My InV FasT\n\n"
                                    P = await self.SEndMsG(self.response.Data.chat_type , message , uid , chat_id , key , iv)
                                    await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , P)
                                    PAc = await OpEnSq(key , iv)
                                    await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , PAc)





                                    C = await cHSq(5, uid ,key, iv)
                                    await asyncio.sleep(0.5)
                                    await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , C)
                                    V = await SEnd_InV(5 , uid , key , iv)
                                    await asyncio.sleep(0.5)
                                    await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , V)
                                    E = await ExiT(None , key , iv)
                                    await asyncio.sleep(3)
                                    await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , E)
                                except Exception as e:
                                    print('msg in squad' , str(e))


                            if self.inPuTMsG.startswith('/inv'):
                                try:
                                    parts = self.inPuTMsG.strip().split()
                                    uid = int(parts[1])
                                except:
                                    pass
                                V = await SEnd_InV(5 , uid , key , iv)
                                await asyncio.sleep(0.5)
                                await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , V)
                            if self.inPuTMsG.startswith('/x/'):
                                CodE = self.inPuTMsG.split('/x/')[1]
                                print(CodE)
                                try:
                                    dd = chatdata['5']['data']['16']
                                    print('msg in private')
                                    EM = await GenJoinSquadsPacket(CodE , key , iv)
                                    joining_team = True
                                    #print(EM , list[key] , list[iv])
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine' , EM)


                                except Exception as e:
                                    print('msg in squad',str(e))

                            if self.inPuTMsG.startswith('leave'):
                               leave = await ExiT(uid,key,iv)
                               await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , leave)
                               self.insquad = None

                            if self.inPuTMsG.strip().startswith('/status'):
                                parts = self.inPuTMsG.strip().split()
                                uidINFO = parts[1]
                                if "***" in uidINFO:
                                    uidINFO = uidINFO.replace("***", "106")
                                await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'OnLine' , await SendInFoPaCKeT(uidINFO,key,iv))
                                

                            if self.inPuTMsG.strip().startswith('/s'):
                                EM = await FS(key , iv)
                                await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine' , EM)

                            if self.inPuTMsG.strip().startswith('@a'):

                                try:
                                    dd = chatdata['5']['data']['16']
                                    print('msg in private')
                                    message = f"[B][C]{get_random_color()}\n\nOnLy In SQuaD ! \n\n"
                                    P = await self.SEndMsG(self.response.Data.chat_type, message, uid, uid, key, iv)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)

                                except:
                                    print('msg in squad')

                                    parts = self.inPuTMsG.strip().split()

                                    message = f'[B][C]{get_random_color()}\nACITVE TarGeT -> {xMsGFixinG(uid)}\n'

                                    P = await self.SEndMsG(self.response.Data.chat_type, message, uid, chat_id, key, iv)

                                    uid2 = uid3 = uid4 = uid5 = None
                                    s = False

                                    try:
                                        uid = int(parts[1])
                                        uid2 = int(parts[2])
                                        uid3 = int(parts[3])
                                        uid4 = int(parts[4])
                                        uid5 = int(parts[5])
                                        idT = int(parts[5])

                                    except ValueError as ve:
                                        print("ValueError:", ve)
                                        s = True

                                    except Exception:
                                        idT = len(parts) - 1
                                        idT = int(parts[idT])
                                        print(idT)
                                        print(uid)

                                    if not s:
                                        try:
                                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)

                                            H = await Emote_k(uid, idT, key, iv)
                                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', H)

                                            if uid2:
                                                H = await Emote_k(uid2, idT, key, iv)
                                                await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', H)
                                            if uid3:
                                                H = await Emote_k(uid3, idT, key, iv)
                                                await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', H)
                                            if uid4:
                                                H = await Emote_k(uid4, idT, key, iv)
                                                await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', H)
                                            if uid5:
                                                H = await Emote_k(uid5, idT, key, iv)
                                                await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', H)
                                            

                                        except Exception as e:
                                            pass


                            if self.inPuTMsG in ("hi" , "hello" , "fin" , "fen" , "wach", "slm", "cc", "salam"):
                                uid = self.response.Data.uid
                                chat_id = self.response.Data.Chat_ID
                                message = 'Hello Im Dev RedZed\nTelegram : @RedZedKing'
                                P = await self.SEndMsG(self.response.Data.chat_type , message , uid , chat_id , key , iv)
                                await self.SEndPacKeT(self.whisper_writer , self.online_writer , 'ChaT' , P)
                            self.response = None





                if self.whisper_writer is not None:
                    try:
                        self.whisper_writer.close()
                        await self.whisper_writer.wait_closed()
                    except Exception as e:
                        print(f"Error closing whisper_writer: {e}")
                    finally:
                        self.whisper_writer = None

                if self.online_writer is not None:
                    try:
                        self.online_writer.close()
                        await self.online_writer.wait_closed()
                    except Exception as e:
                        print(f"Error closing online_writer: {e}")
                    finally:
                        self.online_writer = None

                self.insquad = None

#
#               self.whisper_writer.close() ; await self.whisper_writer.wait_closed() ; self.whisper_writer = None
#               self.online_writer.close() ; await self.online_writer.wait_closed() ; self.online_writer = None
#               self.insquad = None
                        
                            
                            
            except Exception as e: print(f"ErroR {ip}:{port} - {e}");self.whisper_writer = None
            await asyncio.sleep(reconnect_delay)


    async def restart(self,task1,task2):
        while True:
            if self.online_writer and self.whisper_writer == None:
                await asyncio.gather(task1 , task2)
    async def MaiiiinE(self, custom_uid=None, custom_pwd=None):
        Uid = custom_uid or (sys.argv[1] if len(sys.argv) > 1 else '4412197813')
        Pw = custom_pwd or (sys.argv[2] if len(sys.argv) > 2 else 'SK_F9O5M_BY_SPIDEERIO_GAMING_ED9LY')
        print(f"[+] [CS-ENGINE] Starting engine for UID: {Uid}")
        
        open_id , access_token = await GeNeRaTeAccEss(Uid , Pw)

        if not open_id or not access_token: print("ErroR - InvaLid AccounT") ; return None
        self.access_token = access_token
        
        PyL = await EncryptMajorLogin(open_id , access_token, guest_uid=Uid)
        MajoRLoGinResPonsE = await MajorLogin(PyL)
        if not MajoRLoGinResPonsE: print("TarGeT AccounT => BannEd / NoT ReGisTeReD ! ") ; return None
        
        MajoRLoGinauTh = await DecRypTMajoRLoGin(MajoRLoGinResPonsE)
        UrL = MajoRLoGinauTh.url
        ToKen = MajoRLoGinauTh.token
        print(f"[+] JWT OK (len={len(ToKen)})")
        self.JWT = ToKen
        TarGeT = MajoRLoGinauTh.account_uid
        self.bot_uid = int(TarGeT)
        key = MajoRLoGinauTh.key
        iv = MajoRLoGinauTh.iv
        timestamp = MajoRLoGinauTh.timestamp
        
        LoGinDaTa = await GetLoginData(UrL , PyL , ToKen)
        if not LoGinDaTa: print("ErroR - GeTinG PorTs From LoGin DaTa !") ; return None
        LoGinDaTaUncRypTinG = await DecRypTLoGinDaTa(LoGinDaTa)
        ReGioN = LoGinDaTaUncRypTinG.Region
        self.region = ReGioN
        AccountName = LoGinDaTaUncRypTinG.AccountName
        OnLinePorTs = LoGinDaTaUncRypTinG.Online_IP_Port
        ChaTPorTs = LoGinDaTaUncRypTinG.AccountIP_Port
        self.OnLineiP , self.OnLineporT = OnLinePorTs.split(":")
        ChaTiP , ChaTporT = ChaTPorTs.split(":")

        # LW Main magics: Online 7119 / Whisper 9219 (BD) — proven Online ACCEPTED
        auth_chat = await build_tcp_startup_packet(int(TarGeT), ToKen, int(timestamp), key, iv, region=ReGioN, typ='ChaT')
        auth_online = await build_tcp_startup_packet(int(TarGeT), ToKen, int(timestamp), key, iv, region=ReGioN, typ='OnLine')
        ready_event = asyncio.Event()

        print(f"[+] [ONLINE] auth magic={auth_online[:4]} whisper={auth_chat[:4]} -> {self.OnLineiP}:{self.OnLineporT}")
        task2 = asyncio.create_task(self.TcPOnLine(self.OnLineiP, self.OnLineporT, key, iv, auth_online, region=ReGioN))
        await asyncio.sleep(0.3)
        task1 = asyncio.create_task(self.TcPChaT(ChaTiP, ChaTporT, auth_chat,
                                        key, iv, LoGinDaTaUncRypTinG,
                                        ready_event, region=ReGioN))
        #os.system('cls') if os.name == 'nt' else os.system('clear')
        print(render("CS-ENGINE"))
        print(f" - SerVeR LoGiN UrL => {login_url} | SerVer Url => {UrL}")
        print(f" - GaMe sTaTus > Good | OB => {ob} | Version => {version}")
        print(f" - BoT STarTinG And OnLine on TarGet : {AccountName} , UiD : {TarGeT} | ReGioN => {ReGioN}")
        print(" - BoT sTaTus > GooD | OnLinE !")
        # Machine-readable profile for dashboard GUI
        print(
            f"[CS_PROFILE] guest_uid={Uid}|account_id={TarGeT}|nickname={AccountName}|region={ReGioN}"
        ) 

        await asyncio.gather(task1 , task2)
        await self.restart(self,task1,task2)



client = CLIENT()
async def StarTinG():
    target_uid = sys.argv[1] if len(sys.argv) > 1 else None
    target_pwd = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        await asyncio.wait_for(client.MaiiiinE(target_uid, target_pwd), timeout=700)
    except asyncio.TimeoutError:
        print("[-] [CS-ENGINE] Match / Connection Timeout! Exiting...")
        os._exit(1)
    except Exception as e:
        import traceback
        print(f"[-] [CS-ENGINE] Error: {e}")
        traceback.print_exc()
        os._exit(1)

if __name__ == '__main__':
    asyncio.run(StarTinG())