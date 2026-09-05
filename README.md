# ML Platform Prep Log

A 21-week interview prep log — one 45-minute session a day, a spaced-repetition
review queue, timed behavioural story reps, and a design rep log.

Two builds, one source:

| | |
|---|---|
| `prep-log.html` | the **source of truth**. Published as a Claude Artifact; storage is the `db` capability, so data syncs across every signed-in device. |
| `docs/` | the **installable PWA**, generated from that file. Storage is IndexedDB on the device; works fully offline. |

## Rebuild

```
python3 tools/make-icons.py     # only when the icon changes
python3 tools/build-pwa.py      # regenerates docs/ from prep-log.html
```

`build-pwa.py` swaps exactly three things and leaves the app code alone: storage
(`db` → IndexedDB), downloads (capability → Blob), and the page chrome (artifact
wrapper → full HTML document, manifest, service worker). It fails loudly if any
of its anchors move, so a rename in `prep-log.html` can't silently produce a
half-converted app.

## Run it locally

```
python3 -m http.server 8731 --directory docs
```

Then open <http://localhost:8731>. Service workers need HTTP — opening
`docs/index.html` as a `file://` URL will render but won't install or go offline.

## Deploy

The built site is plain static files with no build step, so any static host works.

**GitHub Pages** — already set up and live at
**<https://menikhilravi.github.io/interview-prep/>**.

Pages source here is **GitHub Actions**, so `.github/workflows/pages.yml` does the
deploy: it uploads `docs/` as a static artifact on every push to `main`. No build
step, no Jekyll. (With the Actions source and *no* workflow present, nothing ever
deploys and every URL 404s — that is what the workflow exists to fix.)

**Cloudflare Pages / Netlify** — both deploy from a *private* GitHub repo on their
free tier. Same push; the source stays private and only the built site is reachable.

### Privacy note

The app's seed — positioning, target-company tiers, compensation bands, story
prompts — ships inside `docs/index.html`. Anyone with the site URL can read it,
on any host. `robots.txt` and a `noindex` meta keep it out of search, but that is
obscurity, not access control. Everything you *log* — checks, grades, notes, gap
notes — lives in IndexedDB on the device and is never uploaded anywhere.

## Install on Android

Open <https://menikhilravi.github.io/interview-prep/> in Chrome → the in-app **Install** bar appears, or use ⋮ → *Install
app*. It gets its own icon, opens full screen with no browser bar, and works with
no connection. Updates land on the next launch after a deploy.

Back up from **Settings → Export → JSON backup**; restore with **Settings →
Restore**. That is also how you move data between the PWA and the artifact.

## Updating

```
python3 tools/build-pwa.py && git add -A && git commit -m "..." && git push
```

Pages redeploys in about a minute. The installed app picks the new version up on
its next launch — the service worker serves the cached copy first, then refreshes
in the background, so it never blocks on the network.
