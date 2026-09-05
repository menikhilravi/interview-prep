#!/usr/bin/env python3
"""Build the installable PWA from prep-log.html (the artifact source).

The app code is identical; only three things are swapped:
  · storage      Claude `db` capability  ->  IndexedDB
  · downloads    `downloads` capability  ->  a real Blob download
  · chrome       artifact wrapper        ->  a full HTML document + manifest + service worker
Keeping one source means a change to the artifact is one rebuild away from the app.
"""
import re, os, sys, hashlib, json

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC  = os.path.join(ROOT, "prep-log.html")
OUT  = os.path.join(ROOT, "docs")   # GitHub Pages serves from root or /docs
src  = open(SRC, encoding="utf-8").read()

# ── the artifact source is a body fragment: pull the pieces out ───────────
title = re.search(r"<title>(.*?)</title>", src).group(1)
body  = re.sub(r"^\s*<title>.*?</title>\s*", "", src, flags=re.S)

def sub(pattern_or_literal, new, *, regex=False, count=1, label=""):
    global body
    if regex:
        body, n = re.subn(pattern_or_literal, new, body, count=count, flags=re.S)
    else:
        n = body.count(pattern_or_literal)
        if n: body = body.replace(pattern_or_literal, new, count)
    if not n:
        sys.exit("build-pwa: pattern not found -> " + (label or str(pattern_or_literal)[:70]))
    return n

# ── 1. storage: swap the whole Claude-db block for IndexedDB ─────────────
start = body.index('const LS_KEY = "prep-log-fallback-v1";')
end   = body.index("async function reconcile(){")
end   = body.index("\n}\n", end) + 3
IDB = '''const IDB_NAME = "prep-log", IDB_STORE = "state", IDB_VER = 1;
const DOCS = {
  progress: () => ({ checks:S.checks, grades:S.grades }),
  queue:    () => ({ items:S.queue }),
  banks:    () => ({ stories:S.stories, designs:S.designs, customStories:S.customStories, customDesigns:S.customDesigns }),
  plan:     () => ({ dayOverrides:S.dayOverrides, settings:S.settings, seq:S.seq })
};
const DOC_NAMES = Object.keys(DOCS);
let idb = null, mode = "init", dirty = new Set(), touched = new Set(), flushT = null, persisted = false;

function setSave(kind, text){
  const el = $("#save"); if(!el) return;
  el.className = "save " + kind;
  el.innerHTML = '<i></i>' + esc(text);
}
function markDirty(name){
  dirty.add(name); touched.add(name);
  setSave("busy","saving");
  clearTimeout(flushT); flushT = setTimeout(flush, 400);
}
function idbOpen(){
  return new Promise((res, rej) => {
    let r; try{ r = indexedDB.open(IDB_NAME, IDB_VER); }catch(e){ return rej(e); }
    r.onupgradeneeded = () => { const d = r.result; if(!d.objectStoreNames.contains(IDB_STORE)) d.createObjectStore(IDB_STORE); };
    r.onsuccess = () => res(r.result);
    r.onerror   = () => rej(r.error);
    r.onblocked = () => rej(new Error("blocked"));
  });
}
function idbGet(d, k){
  return new Promise((res, rej) => { const q = d.transaction(IDB_STORE,"readonly").objectStore(IDB_STORE).get(k);
    q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); });
}
function idbPut(d, k, v){
  return new Promise((res, rej) => { const t = d.transaction(IDB_STORE,"readwrite");
    t.objectStore(IDB_STORE).put(v, k); t.oncomplete = () => res(); t.onerror = () => rej(t.error); });
}
async function flush(){
  if(!dirty.size) return;
  const names = [...dirty]; dirty.clear();
  if(mode !== "idb" || !idb){ names.forEach(n => dirty.add(n)); return; }
  try{
    await Promise.all(names.map(n => idbPut(idb, n, Object.assign({ v:1, at:new Date().toISOString() }, DOCS[n]()))));
    setSave(dirty.size ? "busy" : "ok", dirty.size ? "saving" : "saved");
  }catch(err){
    names.forEach(n => dirty.add(n));
    setSave("bad", (err && err.name === "QuotaExceededError") ? "storage full" : "not saved");
  }
}
function snapshot(){ const o = {}; DOC_NAMES.forEach(n => o[n] = DOCS[n]()); return o; }
function absorb(name, data){
  if(!data || touched.has(name)) return;
  if(name === "progress"){ S.checks = data.checks || {}; S.grades = data.grades || {}; }
  else if(name === "queue"){ S.queue = data.items || {}; }
  else if(name === "banks"){
    S.stories = data.stories || {}; S.designs = data.designs || {};
    S.customStories = data.customStories || []; S.customDesigns = data.customDesigns || [];
  } else if(name === "plan"){
    S.dayOverrides = data.dayOverrides || {};
    S.settings = Object.assign({ startDate: DEFAULT_START }, data.settings || {});
    S.seq = data.seq || 1;
  }
}
async function connect(){
  try{
    idb = await idbOpen(); mode = "idb";
    const vals = await Promise.all(DOC_NAMES.map(n => idbGet(idb, n)));
    vals.forEach((v,i) => { if(v) absorb(DOC_NAMES[i], v); });
    setSave(dirty.size ? "busy" : "ok", dirty.size ? "saving" : "saved");
  }catch(e){ mode = "none"; setSave("bad","storage unavailable"); }
  // ask the browser not to evict this data under storage pressure
  try{
    if(navigator.storage && navigator.storage.persist)
      persisted = (await navigator.storage.persisted()) || (await navigator.storage.persist());
  }catch(e){}
  render();
  if(dirty.size) flush();
}
async function reconcile(){
  if(mode !== "idb" || !idb || dirty.size) return;
  try{
    const vals = await Promise.all(DOC_NAMES.map(n => idbGet(idb, n)));
    touched.clear();
    vals.forEach((v,i) => { if(v) absorb(DOC_NAMES[i], v); });
    render();
  }catch(e){}
}
'''
body = body[:start] + IDB + body[end:]

# ── 2. downloads: a real file, not the capability ────────────────────────
old_offer = body[body.index("async function offerFile(name, text, title){"):]
old_offer = old_offer[:old_offer.index("\n}\n")+3]
sub(old_offer, '''async function offerFile(name, text, title){
  try{
    const blob = new Blob([text], { type: /\\.json$/.test(name) ? "application/json" : "text/plain;charset=utf-8" });
    const url  = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = name; a.style.display = "none";
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 2000);
    return;
  }catch(e){}
  sheet = { kind:"export", title:title, text:text }; renderSheet();
}
''', label="offerFile")

# ── 3. mode branches + storage copy ──────────────────────────────────────
sub('const save = mode==="init" ? ["","connecting"] : mode==="local" ? ["busy","this device only"] : [dirty.size?"busy":"ok", dirty.size?"saving":"saved"];',
    'const save = mode==="init" ? ["","opening"] : mode==="none" ? ["bad","storage unavailable"] : [dirty.size?"busy":"ok", dirty.size?"saving":"saved"];',
    label="topbar save")
# render() has no mode branch — topbar() recomputes the save chip on every render.
sub('''  const line = mode==="db" ? "Saved to your Claude account. The same link on any signed-in device shows the same data."
    : mode==="local" ? "Cloud storage is unavailable in this view, so progress is being kept in this browser only."
    : "Connecting…";''',
    '''  const line = mode==="idb"
      ? "Stored on this device, in this app" + (persisted ? ", and marked as persistent so the browser will not evict it." : ". The browser has not granted persistent storage yet — export a backup now and then.")
    : mode==="none" ? "This browser will not give the app storage, so nothing is being saved. Export before you close it."
    : "Opening…";''', label="settings storage copy")
sub('(mode==="local"?\'<div class="banner w"><b>Local-only storage.</b> \'+esc(line)+" Export a backup before you close this tab.</div>":"")',
    '(mode==="none"?\'<div class="banner w"><b>No storage.</b> \'+esc(line)+"</div>":"")', label="settings banner")
sub('      if(mode === "local"){ try{ localStorage.removeItem(LS_KEY); }catch(e){} }\n', "", label="reset localStorage")

# ── 4. PWA runtime: service worker, install prompt ───────────────────────
sub("</script>", '''
/* ══════════════════════════════════════════════════════════════════════════
   PWA RUNTIME
   ══════════════════════════════════════════════════════════════════════ */
if("serviceWorker" in navigator){
  window.addEventListener("load", () => { navigator.serviceWorker.register("./sw.js").catch(()=>{}); });
}
let deferredInstall = null;
window.addEventListener("beforeinstallprompt", e => { e.preventDefault(); deferredInstall = e; installBar(true); });
window.addEventListener("appinstalled", () => { deferredInstall = null; installBar(false); });
function installBar(show){
  let el = document.getElementById("installbar");
  if(!show){ if(el) el.remove(); return; }
  if(el) return;
  el = document.createElement("div");
  el.id = "installbar";
  el.innerHTML = '<span>Install Prep Log for offline use</span>' +
    '<button data-i="go">Install</button><button data-i="no" aria-label="Dismiss">\\u2715</button>';
  el.addEventListener("click", async ev => {
    const b = ev.target.closest("button"); if(!b) return;
    if(b.dataset.i === "no"){ installBar(false); return; }
    if(!deferredInstall) return;
    const p = deferredInstall; deferredInstall = null;
    installBar(false); p.prompt(); try{ await p.userChoice; }catch(e){}
  });
  document.body.appendChild(el);
}
</script>''', label="pwa runtime")

# ── assemble the document ────────────────────────────────────────────────
INSTALL_CSS = """
#installbar{position:fixed;left:10px;right:10px;bottom:calc(66px + env(safe-area-inset-bottom));z-index:35;
  max-width:540px;margin:0 auto;display:flex;align-items:center;gap:9px;padding:11px 12px;border-radius:12px;
  background:var(--surface);border:1px solid var(--run-edge);box-shadow:var(--e3);font-size:13px}
#installbar span{flex:1;min-width:0;line-height:1.35}
#installbar button{flex:none;min-height:38px;padding:9px 13px;border-radius:9px;border:1px solid var(--run);
  background:var(--run);color:var(--onfill);font-family:var(--mono);font-size:11px;font-weight:700;
  letter-spacing:.07em;text-transform:uppercase}
#installbar button[data-i="no"]{background:none;color:var(--ink-faint);border-color:var(--line);padding:9px 11px}
"""
body = body.replace("</style>", INSTALL_CSS + "</style>", 1)

doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,interactive-widget=resizes-content">
<meta name="robots" content="noindex,nofollow">
<title>{title}</title>
<meta name="description" content="A 21-week ML-platform interview prep log.">
<link rel="manifest" href="./manifest.webmanifest">
<meta name="theme-color" content="#EFF3F8" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#080C12" media="(prefers-color-scheme: dark)">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Prep Log">
<link rel="icon" href="./icons/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="./icons/apple-touch-icon.png">
<style>
:root{{color-scheme:light dark}}
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0}}
body{{-webkit-font-smoothing:antialiased;min-height:100vh;min-height:100dvh}}
img{{max-width:100%}}
[hidden]{{display:none!important}}
</style>
</head>
<body>
{body}
</body>
</html>
"""

os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(doc)

ver = hashlib.sha256(doc.encode("utf-8")).hexdigest()[:12]
manifest = {
  "name": "ML Platform Prep Log", "short_name": "Prep Log",
  "description": "A 21-week ML-platform interview prep log: today's session, a spaced-repetition review queue, timed story reps and a design rep log.",
  "start_url": "./", "scope": "./", "id": "./",
  "display": "standalone", "display_override": ["standalone", "minimal-ui"],
  "orientation": "portrait", "background_color": "#080C12", "theme_color": "#080C12",
  "categories": ["productivity", "education"],
  "icons": [
    {"src": "./icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
    {"src": "./icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    {"src": "./icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
  ]
}
open(os.path.join(OUT, "manifest.webmanifest"), "w", encoding="utf-8").write(json.dumps(manifest, indent=2) + "\n")

SW = """/* Prep Log service worker — generated by tools/build-pwa.py, do not edit by hand. */
const V = "prep-log-%s";
const FONTS = "prep-log-fonts-v1";
const SHELL = ["./","./index.html","./manifest.webmanifest",
  "./icons/icon-192.png","./icons/icon-512.png","./icons/maskable-512.png",
  "./icons/favicon-32.png","./icons/apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== V && k !== FONTS).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if(req.method !== "GET") return;
  const url = new URL(req.url);

  /* Google Fonts: stale-while-revalidate, so the app keeps its type offline */
  if(/^fonts\\.(googleapis|gstatic)\\.com$/.test(url.hostname)){
    e.respondWith(caches.open(FONTS).then(async c => {
      const hit = await c.match(req);
      const net = fetch(req).then(r => { if(r && r.ok) c.put(req, r.clone()); return r; }).catch(() => hit);
      return hit || net;
    }));
    return;
  }
  if(url.origin !== location.origin) return;

  /* navigation: cache-first so it opens instantly, refreshed in the background */
  if(req.mode === "navigate"){
    e.respondWith((async () => {
      const cached = await caches.match("./index.html");
      const net = fetch(req).then(r => {
        if(r && r.ok) caches.open(V).then(c => c.put("./index.html", r.clone()));
        return r;
      }).catch(() => null);
      return cached || (await net) || new Response("Offline", {status:503, headers:{"Content-Type":"text/plain"}});
    })());
    return;
  }
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => {
    if(r && r.ok && r.type === "basic"){ const cl = r.clone(); caches.open(V).then(c => c.put(req, cl)); }
    return r;
  })));
});
""" % ver
open(os.path.join(OUT, "sw.js"), "w", encoding="utf-8").write(SW)
open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8").write("User-agent: *\nDisallow: /\n")
open(os.path.join(OUT, ".nojekyll"), "w", encoding="utf-8").write("")

print("built docs/  ·  index.html %d KB  ·  cache version %s" % (len(doc)//1024, ver))
