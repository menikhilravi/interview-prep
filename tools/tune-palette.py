#!/usr/bin/env python3
"""OKLCh surgery on a palette: change chroma/hue while HOLDING lightness.

Holding OKLab L means every contrast ratio is preserved to within rounding, so
a palette that passed its constraints still passes after the tune. Used to fix
the one measured defect in the winning palette (dark neutrals carried no more
chroma than the palette they replaced) without disturbing anything else.
"""
import json, math, sys

def _s2l(c): return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
def _l2s(c):
    c = 0.0 if c < 0 else (1.0 if c > 1 else c)
    return 12.92*c if c <= 0.0031308 else 1.055*(c**(1/2.4)) - 0.055

def hex_to_oklab(h):
    h = h.lstrip("#")
    r,g,b = (_s2l(int(h[i:i+2],16)/255) for i in (0,2,4))
    l = (0.4122214708*r + 0.5363325363*g + 0.0514459929*b) ** (1/3)
    m = (0.2119034982*r + 0.6806995451*g + 0.1073969566*b) ** (1/3)
    s = (0.0883024619*r + 0.2817188376*g + 0.6299787005*b) ** (1/3)
    return (0.2104542553*l + 0.7936177850*m - 0.0040720468*s,
            1.9779984951*l - 2.4285922050*m + 0.4505937099*s,
            0.0259040371*l + 0.7827717662*m - 0.8086757660*s)

def oklab_to_rgb(L,a,b):
    l = (L + 0.3963377774*a + 0.2158037573*b)**3
    m = (L - 0.1055613458*a - 0.0638541728*b)**3
    s = (L - 0.0894841775*a - 1.2914855480*b)**3
    return (+4.0767416621*l - 3.3077115913*m + 0.2309699292*s,
            -1.2684380046*l + 2.6097574011*m - 0.3413193965*s,
            -0.0041960863*l - 0.7034186147*m + 1.7076147010*s)

def in_gamut(rgb, eps=1e-4):
    return all(-eps <= c <= 1+eps for c in rgb)

def lch_to_hex(L, C, h):
    """Reduce chroma until the colour fits sRGB — lightness and hue are never touched."""
    for i in range(240):
        c = C * (1 - i/240.0)
        a, b = c*math.cos(h), c*math.sin(h)
        rgb = oklab_to_rgb(L, a, b)
        if in_gamut(rgb):
            return "#" + "".join("%02X" % round(max(0,min(1,_l2s(x)))*255) for x in rgb), c
    return "#000000", 0.0

def to_lch(hx):
    L,a,b = hex_to_oklab(hx)
    return L, math.hypot(a,b), math.atan2(b,a)

def tune(hx, chroma=None, scale=None, hue_deg=None):
    L, C, h = to_lch(hx)
    if hue_deg is not None: h = math.radians(hue_deg)
    if chroma is not None:  C = chroma
    elif scale is not None: C = C * scale
    return lch_to_hex(L, C, h)

if __name__ == "__main__":
    pal = json.load(open(sys.argv[1], encoding="utf-8"))
    spec = json.load(open(sys.argv[2], encoding="utf-8"))
    for theme, edits in spec.items():
        if theme not in pal: continue
        for key, op in edits.items():
            before = pal[theme][key]
            after, got = tune(before, **op)
            _,cb,_ = to_lch(before)
            print(f"  {theme:5} {key:11} {before} -> {after}   C {cb:.4f} -> {got:.4f}")
            pal[theme][key] = after
    json.dump(pal, open(sys.argv[3], "w"), indent=1)
    print("wrote", sys.argv[3])
