import struct

UDP_KEY     = bytes.fromhex("7a803a9c7b32503edaa1b7ddc53c5a79")
CONTENT_HEX = "e453b492398568fe75e32380eb462f9cc621546e415fc12cd554b85cf3cc3e21"

_DELTA = 0x9E3779B9
_ROUNDS = 16

def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^
                      ((v0+s)&0xFFFFFFFF) ^
                      (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF
        v0 = (v0 - (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^
                      ((v1+s)&0xFFFFFFFF) ^
                      (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1

def tea_cbc_decrypt(body, key):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key, o)[0] for o in (0,4,8,12))
    out = bytearray(len(body))
    pi = bytearray(8); pc = bytearray(8); dec = bytearray(8)
    for i in range(0, len(body), 8):
        x = bytearray(8)
        for j in range(8): x[j] = body[i+j] ^ pi[j]
        d0,d1 = tea_dec(struct.unpack_from("<I",x,0)[0],
                        struct.unpack_from("<I",x,4)[0], k0,k1,k2,k3)
        struct.pack_into("<I",dec,0,d0); struct.pack_into("<I",dec,4,d1)
        for j in range(8): out[i+j] = dec[j] ^ pc[j]
        pc[:] = body[i:i+8]; pi[:] = dec
    return bytes(out)

def unpad(dec):
    pad_len = dec[0] & 0x07
    s = 3 + pad_len
    e = len(dec) - 7
    if s >= e: return None
    return dec[s:e]

def read_varint(data, off):
    r = 0; shift = 0
    while off < len(data):
        b = data[off]; r |= (b & 0x7F) << shift; off += 1
        if not (b & 0x80): return r, off
        shift += 7
    return None, off

content = bytes.fromhex(CONTENT_HEX)
dec     = tea_cbc_decrypt(content, UDP_KEY)
plain   = unpad(dec)

print(f"RAW DEC : {dec.hex()}")
print(f"tail 7  : {dec[-7:].hex()}  {'✅ zeros=good' if all(b==0 for b in dec[-7:]) else '❌ not zeros=wrong key'}")
print()

if plain is None:
    print("UNPAD FAILED")
else:
    print(f"PLAIN hex : {plain.hex()}")
    print(f"PLAIN len : {len(plain)} bytes")
    print()

    # All varints with byte positions
    print("─── VARINT FIELDS ───────────────────────────────")
    off = 0; idx = 0
    while off < len(plain):
        start = off
        v, off2 = read_varint(plain, off)
        if v is None or off2 == off: break
        span = plain[start:off2].hex()
        print(f"  [{idx}] offset={start:2d}  bytes={span:<16s}  value={v}")
        off = off2; idx += 1

    print()
    print("─── UINT32 LE scan ──────────────────────────────")
    for i in range(len(plain)-3):
        v = struct.unpack_from("<I", plain, i)[0]
        print(f"  offset={i:2d}  LE={v:10d}  0x{v:08x}")

    print()
    print("─── UINT64 LE scan ──────────────────────────────")
    for i in range(len(plain)-7):
        v = struct.unpack_from("<Q", plain, i)[0]
        if v > 1_000_000_000:
            print(f"  offset={i:2d}  LE64={v}  0x{v:016x}")

    print()
    print("─── cmd=248 interpretation ──────────────────────")
    print("  ⚠️  uid should be ~10 digits (e.g. 3xxxxxxxx)")
    print("  ⚠️  skill_id should match a known skill (e.g. 5506=Homer)")
    print()
    print("  To get a valid decode: run a match, then copy BOTH:")
    print("  1) [SESSION KEY] line  →  UDP_KEY")
    print("  2) cmd=248 CONTENT_HEX from that SAME match session")