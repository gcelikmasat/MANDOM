<div align="center">

# 🩸 Mandom

### *pull manga into your world*

A personal manga **downloader, library, and reader** — browse and search
[MangaDex](https://mangadex.org), bookmark your favourites and get told when
new chapters drop, download chapters as **Kobo-ready EPUBs** (or CBZ), send them
straight to your e-reader, and read right inside the app.

Runs as a **web app**, a **native desktop app**, *and* an **installable phone app**.

*<sub>Named after Ringo Roadagain's Stand in JoJo's Bizarre Adventure: Steel Ball Run — the app icon is Ringo himself.</sub>*

</div>

> [!IMPORTANT]
> **Personal use only.** Mandom is for reading manga you'd otherwise read on the
> site, on your own devices. It's built to respect MangaDex's API (polite rate
> limiting, English-only, crediting the @Home network). Please don't use it to
> redistribute or pirate anything. Bring your own MangaDex account/keys.

---

## ✨ What it does

| | Feature | Details |
|---|---|---|
| 🔎 | **Discover & search** | Browse MangaDex's Popular / Latest / Top-rated, or search any title. English chapters only. |
| ⭐ | **Library & bookmarks** | Save manga to a local library. |
| 🔔 | **New-chapter detection** | "Update all" re-checks every bookmark and badges the ones with new chapters. Opening a manga marks it caught up. |
| 🔐 | **MangaDex account sync** | Sign in with a MangaDex API client and import your existing follows. |
| ⬇️ | **Downloading** | Per-chapter downloads via a background queue with live progress. Resumable. |
| 📚 | **Kobo KEPUB export** | Fixed-layout, device-sized `.kepub.epub` with embedded **series metadata** so chapters auto-group & sort on the Kobo. CBZ also supported. |
| ⇪ | **Send to Kobo** | Auto-detects a plugged-in Kobo and copies books straight onto it. |
| 📖 | **In-app reader** | Immersive paged reader — click zones + arrow keys, configurable page direction, chapter-to-chapter flow. |
| ⚙️ | **Settings page** | Change download folder, export format, reader direction, device profile, Kobo path — saved to `config.toml`. |
| 🖼️ | **Shuffling wallpapers** | Two full-height wallpaper panels in the side gutters that conveyor through your images, with artist credits. |
| 📱 | **Installable (PWA)** | Add to your phone's home screen and run it fullscreen like a native app. |

---

## 🧠 How it works

Mandom talks to the **official MangaDex API** (`api.mangadex.org`) — no scraping,
no fragile HTML parsing. That's the whole reason it's reliable where scraper-based
tools break:

```
You ──▶ Mandom (FastAPI server) ──▶ MangaDex API ──▶ chapter images (MangaDex@Home)
                  │
                  ├─ local SQLite (bookmarks, download jobs)
                  ├─ download queue ─▶ images ─▶ CBZ / Kobo KEPUB  ─▶ downloads/
                  └─ OS keychain (your MangaDex tokens, never plaintext)
```

- **Search / browse / chapter lists / page images** are public MangaDex endpoints — no login needed.
- **Account sync** uses MangaDex's OAuth2 *personal client*: we do the password grant **once**, then keep only the refresh token (in your OS keychain) and refresh silently. Your password is never stored.
- **Downloads** pull each page from the **MangaDex@Home** image network with polite rate limiting, then bundle them.
- **KEPUB export** downscales pages to your device profile (default **Kobo Clara Colour**, 1072×1448), lays them out one-per-page (right-to-left for manga), and embeds series metadata so the Kobo sorts a series automatically. (Approach inspired by Kindle Comic Converter.)
- **A provider-plugin interface** (`app/providers/base.py`) keeps everything source-agnostic, so other manga sources can be added later behind the same contract.

---

## 🛠️ Tech stack

**Python 3.11+** · **FastAPI** + **Uvicorn** · **HTMX** front-end · **SQLAlchemy/SQLite** ·
**httpx** (async) · **Pillow** (image sizing) · **keyring** (secrets) ·
**pywebview** (desktop window) · **PyInstaller** (the `.exe`).

---

## 🚀 Quick start

```powershell
# 1. Clone, then create a virtual environment (Python 3.11+, 3.13 recommended)
py -3.13 -m venv .venv
.venv\Scripts\activate

# 2. Install
pip install -e ".[web]"          # add ",desktop" too if you want the native window

# 3. Run
python run.py                    # opens http://127.0.0.1:8000 in your browser
```

On Windows you can also just double-click **`start-mandom.bat`**.

---

## 💻 Ways to run it

### Web app (default)
```powershell
python run.py
```
Search → bookmark (★) → open a manga → download chapters → read or send to Kobo.

### Native desktop app
The exact same UI in its own window (no browser tab):
```powershell
pip install -e ".[web,desktop]"
python desktop.py                # or double-click start-desktop.bat
```

### CLI
```powershell
mandom search "chainsaw man"
mandom chapters <manga_id>
mandom download <manga_id> --chapter 1     # or --all
```

---

## ⚙️ Settings

Open **Settings** in the app to change (saved to `config.toml`):

- **Download folder** — where books are written (one subfolder per manga, e.g. `downloads/Chainsaw Man/`).
- **Export format** — Kobo KEPUB (default), CBZ, or both.
- **Reader advance side** — which side / arrow key turns to the *next* page.
- **EPUB page direction** — right-to-left (manga) or left-to-right (webtoons).
- **Device profile** & **Kobo path**.

Filenames are zero-padded (`0001_…`, `0002_…`) so chapters sort 1→N on disk and on the device.

---

## 🔐 MangaDex account (optional)

To import your follows: go to **mangadex.org → Settings → API Clients**, create a
**personal client** (it needs approval, which can take a while), then in Mandom's
**Account** page enter the client ID/secret + your login and hit **Sync follows**.
Credentials live in your OS keychain — never in the repo or in plaintext.

---

## ⇪ Send to Kobo

Plug your Kobo in via USB and open the **Library** page — Mandom auto-detects it
(by its `.kobo` folder) and shows **"Send entire library → Kobo"**, or use the
**Send to Kobo** button on any manga. Because each KEPUB carries series metadata,
chapters group and sort by series on the device automatically.

---

## 🖼️ Wallpapers

Drop images into the **`wallpapers/`** folder. Two full-height panels in the left
and right gutters conveyor through them (wide screens), while the centre stays
the clean dark theme. To credit the artists, map filenames to handles in
**`wallpapers/credits.json`**:

```json
{ "jolyne.jpg": "springbloomed26", "yoruichi.jpg": "PRIxMAL786" }
```

The handle shows as a clickable **"art by @…"** at the bottom of each panel.

---

## 📱 Use it on your phone

Mandom is an installable **PWA** — your phone runs the *UI*, talking to the server
on your PC (or a host). The in-app reader is great on a phone; Send-to-Kobo is
desktop-only.

**On the same Wi-Fi:**
```powershell
python run.py --host 0.0.0.0     # or double-click start-mandom-lan.bat
```
- Allow **inbound TCP 8000** through Windows Firewall and set the Wi-Fi to a **Private** network.
- Find your PC's IPv4 (`ipconfig`), then on the phone open `http://<PC-IP>:8000`.
- **iPhone:** Safari → **Share → Add to Home Screen** (works over LAN HTTP).
- **Android:** full install needs HTTPS — use a tunnel (below).

**From anywhere (off your home network):**
- **Tailscale** (recommended) — a free personal VPN. Install it on the PC and phone, sign into the same account, and reach the PC at its `100.x` address from anywhere. Private, so no extra login needed.
- **Cloudflare Tunnel** — `cloudflared tunnel --url http://localhost:8000` gives a public `https://…` URL (works on any phone, no VPN). ⚠️ Public, so only do this if you add a password.

Your PC must be on and running the server (or host the Docker image on a small server).

---

## 📦 Build a standalone `.exe` (no Python needed)

For a true double-click app you can hand to a friend:

```powershell
build-exe.bat                    # produces dist\Mandom\Mandom.exe
```

Zip the **`dist\Mandom`** folder to share it. First launch may show Windows
SmartScreen ("unknown publisher") → **More info → Run anyway** (normal for
unsigned apps). Requires the **WebView2 runtime** (preinstalled on Windows 11 and
most updated Windows 10).

---

## 🐳 Docker (for self-hosting / sharing)

```bash
docker compose up --build        # http://localhost:8000
```

In a container there's no OS keychain (secrets fall back to a file under `data/`,
`MANDOM_SECRET_BACKEND=file`) and **Send-to-Kobo is unavailable** (no USB).
Everything else works.

---

## 🗂️ Project structure

```
app/
├── config.py            # settings (mutable, persisted to config.toml)
├── db.py                # SQLite models (bookmarks, download jobs)
├── cli.py               # command-line interface
├── providers/           # source plugins behind one interface
│   ├── base.py          #   the Provider contract + DTOs
│   ├── mangadex.py      #   MangaDex API client
│   └── mangadex_auth.py #   OAuth2 login + follows sync
├── services/
│   ├── downloader.py    # page downloader (rate-limited, resumable)
│   ├── updates.py       # new-chapter detection
│   ├── kobo.py          # device detection + copy
│   ├── secrets.py       # OS keychain (file fallback)
│   ├── naming.py        # filename templating / slugs
│   ├── ratelimit.py     # token-bucket limiter
│   └── export/          # cbz.py + kepub.py builders
└── web/
    ├── server.py        # FastAPI routes
    ├── queue.py         # background download worker
    ├── templates/       # HTMX pages + partials
    └── static/          # CSS, JS, icons, service worker

desktop.py               # native window (pywebview)
run.py                   # web launcher
tools/make_icons.py      # generate app icons from a source image
*.bat                    # one-click launchers (web / desktop / LAN / build)
Dockerfile, docker-compose.yml
PLAN.md                  # the original design doc & roadmap
```

---

## 🙏 Credits

- **[MangaDex](https://mangadex.org)** and the **MangaDex@Home** network for the API and images.
- **Kindle Comic Converter** for the comic-EPUB approach the KEPUB exporter is modelled on.
- Wallpaper artists credited in `wallpapers/credits.json`.
- Built with [Claude Code](https://claude.com/claude-code).

---

<div align="center">
<sub>Personal-use project • not affiliated with MangaDex or any provider • support the artists and read legally 🩸</sub>
</div>
