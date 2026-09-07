#!/usr/bin/env python3
"""Rewrite the app's colour tokens from a JSON palette.

The tokens are declared three times by design — bare :root (light), the
prefers-color-scheme block, and the [data-theme="dark"] block — so that an
explicit theme choice wins in both directions. Hand-editing 46 values across
three blocks is how you get a half-applied palette; this does all three or
fails loudly.

    python3 tools/set-palette.py palette.json
"""
import json, re, sys, os

KEYS = [
    ("ground","--ground"), ("surface","--surface"), ("surface2","--surface-2"),
    ("surface3","--surface-3"), ("sunken","--sunken"),
    ("ink","--ink"), ("inkSoft","--ink-soft"), ("inkFaint","--ink-faint"),
    ("line","--line"), ("lineStrong","--line-strong"), ("grid","--grid"),
    ("run","--run"), ("runBg","--run-bg"), ("runEdge","--run-edge"),
    ("done","--done"), ("doneBg","--done-bg"), ("doneEdge","--done-edge"),
    ("fall","--fall"), ("fallBg","--fall-bg"), ("fallEdge","--fall-edge"),
    ("alert","--alert"), ("alertBg","--alert-bg"), ("alertEdge","--alert-edge"),
]
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

def block_bounds(css, opener):
    i = css.index(opener) + len(opener)
    depth, j = 1, i
    while depth:
        if css[j] == "{": depth += 1
        elif css[j] == "}": depth -= 1
        j += 1
    return i, j - 1

def apply(css, opener, theme, label):
    a, b = block_bounds(css, opener)
    body, missing = css[a:b], []
    for key, tok in KEYS:
        val = theme.get(key)
        if not val or not HEX.match(val):
            sys.exit(f"{label}: '{key}' missing or not a #rrggbb hex: {val!r}")
        pat = re.compile(r"(" + re.escape(tok) + r"\s*:\s*)(#[0-9A-Fa-f]{3,8})")
        body, n = pat.subn(lambda m: m.group(1) + val, body)
        if n != 1:
            missing.append(f"{tok} matched {n} times")
    # derived: text on a filled chip is the ground; the ring track is the hairline
    for tok, val in (("--onfill", theme["ground"]), ("--ringtrack", theme["line"])):
        body, n = re.compile(r"(" + re.escape(tok) + r"\s*:\s*)(#[0-9A-Fa-f]{3,8})").subn(
            lambda m: m.group(1) + val, body)
        if n != 1: missing.append(f"{tok} matched {n} times")
    if missing:
        sys.exit(f"{label}: " + "; ".join(missing))
    return css[:a] + body + css[b:]

def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    src  = os.path.join(root, "prep-log.html")
    pal  = json.load(open(sys.argv[1], encoding="utf-8"))
    for t in ("dark", "light"):
        if t not in pal: sys.exit(f"palette json has no '{t}' theme")
    s = open(src, encoding="utf-8").read()
    head = s[:s.index("</style>")]
    tail = s[s.index("</style>"):]
    head = apply(head, ":root{\n", pal["light"], "light / :root")
    head = apply(head, '@media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){', pal["dark"], "dark / media")
    head = apply(head, ':root[data-theme="dark"]{', pal["dark"], "dark / data-theme")
    open(src, "w", encoding="utf-8").write(head + tail)
    print(f"applied '{pal.get('name','palette')}' — {len(KEYS)*3 + 6} declarations rewritten across 3 blocks")

if __name__ == "__main__":
    main()
