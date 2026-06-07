# Mandom

> _manga downloader app_

Personal-use manga downloader. Pulls **English** chapters from provider APIs
(**MangaDex** first), and exports reader-ready files. Built to reliably do what
HakuNeko did, without the scraping fragility — and to ship clean files to a
**Kobo Clara Colour**. (Named after Ringo Roadagain's Stand in JoJo's SBR.)

> See **[PLAN.md](PLAN.md)** for the full specification, architecture, and roadmap.
> **Personal use only** — download what you'd otherwise read on the site, for your own device.

## Status

- **Phase 1 (CLI)** ✅ search → list English chapters → download → CBZ.
- **Phase 2 (web UI)** ✅ FastAPI + HTMX: Discover/browse, search with covers,
  local bookmarks, manga detail + chapter list, background download queue with
  live progress, shuffling wallpaper background.
- **Phase 3 (new-chapter detection)** ✅ "Update all" re-polls bookmarks; unread
  badges; opening a manga marks it caught up.
- **Phase 4 (MangaDex account sync)** ✅ OAuth2 personal-client login (creds in
  the OS keychain), import your follows into the library.
- **Phase 5 (Kobo KEPUB export)** ✅ fixed-layout, device-sized `.kepub.epub`
  with embedded series metadata (auto-sorts on the Kobo), RTL, per-chapter.
  Set `export_format` to `kepub` (default), `cbz`, or `both`.
- **Send to Kobo** ✅ auto-detects the mounted device and copies books onto it,
  per-manga or the whole library.
- **Phase 6 (in-app reader)** ✅ immersive paged reader (click zones + arrow
  keys, configurable advance side, chapter-to-chapter navigation).
- **Settings page** ✅ change the download folder, export format, reader
  advance side, EPUB direction, device profile, and Kobo path in-app
  (persisted to `config.toml`).

## Wallpapers

Drop images into `wallpapers/`; they rotate as the header banner (with the
artist credit), and the ASCII mascot sits in the footer. To credit artists, map
filenames to Twitter/X handles in `wallpapers/credits.json`, e.g.:

```json
{ "jolyne.jpg": "the_artist_handle" }
```

## Setup

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -e ".[web]"
```

## Web UI (recommended)

```powershell
python run.py          # opens http://127.0.0.1:8000
```

Search a title, bookmark favourites (★), open a manga, and download chapters —
each becomes a CBZ in `downloads/<Manga Title>/`. Drop images into `wallpapers/`
and the background shuffles through them.

## CLI

```powershell
mandom search "chainsaw man"
mandom chapters <manga_id>
mandom download <manga_id> --chapter 1     # or --all
```

Files land in `downloads/<Manga Title>/` with zero-padded names
(`0001_…`, `0002_…`) so they sort 1→N on disk and on the device.

## Config

Optional `config.toml` in the repo root overrides defaults (export folder,
filename template, concurrency, etc.). See `config.example.toml`. Most of these
are editable from the in-app **Settings** page.

## Desktop app

Run the exact same UI in a native window instead of a browser tab:

```powershell
pip install -e ".[web,desktop]"
python desktop.py            # or double-click start-desktop.bat
```

To ship a **single double-click `.exe`** (no Python needed by the user),
package it with PyInstaller:

```powershell
pip install pyinstaller
pyinstaller --noconfirm --windowed --name Mandom ^
  --add-data "app/web/templates;app/web/templates" ^
  --add-data "app/web/static;app/web/static" ^
  --collect-all webview ^
  desktop.py
```

The resulting `dist/Mandom/Mandom.exe` writes its `data/`, `downloads/`, and
`wallpapers/` folders next to itself.

## Deployment

**Native (recommended for daily use):** double-click **`start-mandom.bat`** (web
UI) or **`start-desktop.bat`** (native window). Keeps the OS keychain (secure
secrets) and Send-to-Kobo (USB) working. One-time setup is the venv above.

**Docker (for sharing / self-hosting):**

```bash
docker compose up --build      # http://localhost:8000
```

In a container there's no OS keychain, so secrets fall back to a file under
`data/` (`MANDOM_SECRET_BACKEND=file`), and **Send-to-Kobo is unavailable**
(no USB access). Everything else — browse, download, KEPUB export, account
sync — works. Bring your own MangaDex client/credentials via the Account page.

## Use on your phone (PWA)

Mandom is an installable PWA (app icon, fullscreen). The phone talks to the
server running on your PC (or a hosted instance) — it doesn't run the backend
itself.

1. Start the server so other devices can reach it:
   ```powershell
   python run.py --host 0.0.0.0
   ```
   Allow the port through Windows Firewall, and find your PC's LAN IP
   (`ipconfig`).
2. On your phone (same Wi-Fi), open `http://<PC-LAN-IP>:8000`.
3. **iPhone (Safari):** Share → *Add to Home Screen* — runs fullscreen. Works
   over plain LAN HTTP.
4. **Android (Chrome):** full install needs **HTTPS**. Easiest is a tunnel like
   `cloudflared tunnel --url http://localhost:8000` or Tailscale Serve, which
   gives an `https://…` URL you can install from anywhere.

The in-app reader works great on a phone; Send-to-Kobo is desktop-only.
