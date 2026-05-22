# GIOAI Protobuf Decoder
import struct, json

T_VARINT, T_FIXED64, T_LENDELIM, T_FIXED32 = 0, 1, 2, 5

def _v(v):
    b = bytearray()
    while True:
        b.append(v & 0x7F); v >>= 7
        if v == 0: break; b[-1] |= 0x80
    return bytes(b)

def enc(parts):
    o = bytearray()
    for i, t, v in parts:
        o.extend(_v((i << 3) | t))
        if t == T_VARINT: o.extend(_v(v))
        elif t == T_LENDELIM:
            e = v if isinstance(v, bytes) else v.encode() if isinstance(v, str) else enc(v) if isinstance(v, list) else str(v).encode()
            o.extend(_v(len(e))); o.extend(e)
        elif t == T_FIXED32: o.extend(struct.pack('<I', int(v)))
        elif t == T_FIXED64: o.extend(struct.pack('<Q', int(v) & 0xFFFFFFFFFFFFFFFF))
    return bytes(o)

def _dv(d, o):
    v = s = 0
    while True:
        b = d[o]; o += 1; v |= (b & 0x7F) << s; s += 7
        if not (b & 0x80): break
    return v, o

def dec(data, off=0):
    p = []
    if off < len(data) and data[off] == 0 and len(data) - off >= 5: off += 5
    while off < len(data):
        k, off = _dv(data, off); idx, typ = k >> 3, k & 7
        if typ == 0: v, off = _dv(data, off); p.append((idx, typ, v))
        elif typ == 2:
            l, off = _dv(data, off); r = data[off:off+l]; off += l
            try:
                t = r.decode()
                if not any(b < 0x20 and b not in (9, 10, 13) for b in r): p.append((idx, typ, t))
                else: p.append((idx, typ, dec(r, 0) or r))
            except: p.append((idx, typ, dec(r, 0) or r))
        elif typ == 5: p.append((idx, typ, struct.unpack('<I', data[off:off+4])[0])); off += 4
        elif typ == 1: p.append((idx, typ, struct.unpack('<Q', data[off:off+8])[0])); off += 8
        else: break
    return p

async def grpc(cl, ep, pr, tok, sid, cok):
    b = enc(pr)
    f = b'\x00' + struct.pack('>I', len(b)) + b
    headers = {
        "Authorization": tok,
        "Content-Type": "application/grpc-web+proto",
        "x-grpc-web": "1",
        "x-server-offset": "0",
        "x-session-id": sid,
        "Cookie": "; ".join(f"{k}={v}" for k, v in cok.items()),
    }
    r = await cl.post(ep, content=f, headers=headers)
    if r.status_code != 200 or r.headers.get("grpc-status") is not None: return None
    return dec(r.content)
