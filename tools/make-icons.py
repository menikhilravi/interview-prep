#!/usr/bin/env python3
"""Generate the prep-log app icons: the progress ring on the app's own ground.
Pure stdlib PNG encoder — no Pillow, no external deps."""
import zlib, struct, math, os

GROUND = (0x0F, 0x16, 0x20, 255)   # deep blue-black, the app ground
TRACK  = (0x22, 0x30, 0x40, 255)   # ring track
ARC    = (0x3F, 0xCF, 0x8E, 255)   # complete green
SWEEP  = 0.72                       # three-quarters round: work in progress

def png(path, w, h, px):
    raw = b"".join(b"\x00" + bytes(px[y*w*4:(y+1)*w*4]) for y in range(h))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    hdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", hdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))

def blend(dst, src):
    a = src[3] / 255.0
    return [round(dst[i]*(1-a) + src[i]*a) for i in range(3)] + [255]

def draw(size, ring_frac, ss=3):
    """ring_frac: outer ring radius as a fraction of the icon width."""
    W = size * ss
    cx = cy = W / 2.0
    r_out = W * ring_frac
    band  = r_out * 0.235
    r_in  = r_out - band
    r_mid = (r_out + r_in) / 2.0
    cap   = band / 2.0
    start = -math.pi / 2.0
    end   = start + 2 * math.pi * SWEEP
    caps  = [(cx + r_mid*math.cos(a), cy + r_mid*math.sin(a)) for a in (start, end)]

    big = bytearray()
    for y in range(W):
        for x in range(W):
            px, py = x + 0.5, y + 0.5
            dx, dy = px - cx, py - cy
            d = math.hypot(dx, dy)
            col = GROUND
            if r_in <= d <= r_out:
                col = TRACK
                a = math.atan2(dy, dx)
                sweep_to = end - start
                rel = (a - start) % (2*math.pi)
                if rel <= sweep_to:
                    col = ARC
            if col is TRACK or col is GROUND:
                for capx, capy in caps:                      # round arc ends
                    if math.hypot(px-capx, py-capy) <= cap:
                        col = ARC
                        break
            big += bytes(col)

    out = bytearray()                                        # box-downsample the supersample
    for y in range(size):
        for x in range(size):
            r=g=b=0
            for j in range(ss):
                for i in range(ss):
                    o = (((y*ss+j)*W) + (x*ss+i)) * 4
                    r += big[o]; g += big[o+1]; b += big[o+2]
            n = ss*ss
            out += bytes((r//n, g//n, b//n, 255))
    return out

here = os.path.join(os.path.dirname(__file__), "..", "docs", "icons")
os.makedirs(here, exist_ok=True)
for size, frac, name in [
    (192, 0.40, "icon-192.png"),
    (512, 0.40, "icon-512.png"),
    (512, 0.26, "maskable-512.png"),   # art inside Android's 80% safe zone
    (180, 0.40, "apple-touch-icon.png"),
    (32,  0.40, "favicon-32.png"),
]:
    png(os.path.join(here, name), size, size, draw(size, frac))
    print("wrote", name, size)
