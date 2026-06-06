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

## Deployment

**Native (recommended for daily use):** double-click **`start-mandom.bat`** — it
launches the server and opens your browser. Keeps the OS keychain (secure
secrets) and Send-to-Kobo (USB) working. One-time setup is the venv above.

**Docker (for sharing / self-hosting):**

```bash
docker compose up --build      # http://localhost:8000
```

In a container there's no OS keychain, so secrets fall back to a file under
`data/` (`MANDOM_SECRET_BACKEND=file`), and **Send-to-Kobo is unavailable**
(no USB access). Everything else — browse, download, KEPUB export, account
sync — works. Bring your own MangaDex client/credentials via the Account page.
