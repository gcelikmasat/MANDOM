# Manga Downloader App — Plan & Specification

> **Status:** Draft for review. No application code yet.
> **Goal:** A reliable, personal-use manga downloader that pulls English chapters from
> provider APIs (MangaDex first), tracks bookmarks with new-chapter detection, and exports
> Kobo-ready files (CBZ + KEPUB). Stretch goal: an in-app reader.

---

## 1. Verdict & Guiding Principles

**Feasible: yes.** Unlike HakuNeko, which *scrapes* provider websites (and breaks whenever a site
redesigns or adds Cloudflare protection), we start with **MangaDex's official public JSON API**.
No scraping, no bot-protection fight, English filtering built in.

**Principles**

1. **API over scraping.** Prefer official documented APIs. Scraper-based providers are isolated
   behind the same interface and treated as best-effort.
2. **Provider-plugin architecture.** Keep HakuNeko's one good idea — pluggable per-site connectors —
   behind a single stable interface so the UI and download engine never know which site a manga came from.
3. **Polite by default.** Built-in rate limiting, retries with backoff, and MangaDex@Home reporting.
   Respect the network we depend on.
4. **Personal use.** This is a "download what I'd otherwise read on the site, for my own Kobo" tool.
   Not a redistribution/piracy tool. Keep that line.
5. **Bring-your-own-key.** No secrets in the repo. On first run the app asks for any optional
   credentials and stores them locally (encrypted). Others can clone from GitHub and run with their own.

---

## 2. Tech Stack (decided)

| Layer            | Choice                                    | Why |
|------------------|-------------------------------------------|-----|
| Language         | **Python 3.11+**                          | Matches your setup; best-in-class image/EPUB libs |
| API server       | **FastAPI + Uvicorn**                     | Async (great for parallel downloads), typed, auto OpenAPI docs |
| HTTP client      | **httpx** (async)                         | Async requests, connection pooling, HTTP/2 |
| DB / ORM         | **SQLite + SQLAlchemy**                   | Zero-config, single file, perfect for a local app |
| Background work  | FastAPI background tasks + **asyncio** queue | Download queue & bookmark checker without extra infra |
| Images           | **Pillow**                                | Resize/recolor/split spreads for device optimization |
| EPUB/KEPUB       | Custom builder (zip + XHTML templates), KCC logic as reference | Full control over fixed-layout output |
| Secrets          | **keyring** (OS keychain) or encrypted file fallback | Tokens/keys never in plaintext repo |
| Frontend         | Local **web UI** served by FastAPI        | Rich UI (wallpaper shuffle, reader) with low effort |
| Frontend tooling | Start: vanilla + **HTMX**/Alpine or a light Vite+Svelte app | Decide at Phase 2; keep v1 minimal |
| Packaging        | `pip`/venv + `run.py`; later optional PyInstaller | Easy for others to run from GitHub |

> **Frontend note:** v1 (thin slice) can ship with a deliberately ugly single HTML page.
> We pick the "real" frontend approach (HTMX vs a Svelte SPA) when we start Phase 2 (the dope UI).

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Web UI (browser)                       │
│  Library · Bookmarks · Search · Download Queue · Reader ·      │
│  Settings · Shuffling wallpaper background                     │
└───────────────────────────────┬──────────────────────────────┘
                                 │ HTTP/JSON (localhost)
┌───────────────────────────────▼──────────────────────────────┐
│                       FastAPI Core Engine                      │
│                                                                │
│  Routers:  /search  /manga  /chapters  /bookmarks  /downloads  │
│            /export  /settings  /wallpapers                     │
│                                                                │
│  Services:                                                     │
│   • ProviderRegistry  → Provider interface (search/chapters/   │
│                          pages/login)                          │
│   • DownloadManager   → async queue, rate limiter, retries     │
│   • Library/Bookmarks → SQLite via SQLAlchemy                  │
│   • UpdateChecker      → re-polls feeds for new EN chapters     │
│   • ExportPipeline    → CBZ + Kobo KEPUB builders              │
│   • SecretsStore      → encrypted creds/tokens                 │
└───────────────────────────────┬──────────────────────────────┘
                       ┌─────────┴──────────┐
                 ┌─────▼─────┐        ┌──────▼──────┐
                 │ MangaDex   │        │  (future)   │
                 │ provider   │        │  providers  │
                 └────────────┘        └─────────────┘
```

---

## 4. Provider Interface (the extension point)

Every provider implements one async interface. Adding a site later = writing one class.

```python
class Provider(Protocol):
    id: str            # "mangadex"
    name: str          # "MangaDex"
    requires_auth: bool # False for MangaDex read operations

    async def search(self, query: str, *, language="en", limit=20, offset=0) -> list[MangaSummary]: ...
    async def get_manga(self, manga_id: str) -> MangaDetail: ...
    async def get_chapters(self, manga_id: str, *, language="en") -> list[ChapterInfo]: ...
    async def get_pages(self, chapter_id: str) -> list[PageRef]: ...   # resolved image URLs + headers
    async def login(self, creds: Credentials) -> AuthSession | None: ...   # optional
```

Shared DTOs (`MangaSummary`, `ChapterInfo`, `PageRef`, …) keep the UI provider-agnostic.

---

## 5. MangaDex Provider — Concrete Spec

Base URL: `https://api.mangadex.org` (read endpoints are **public, no auth**).

| Need | Endpoint | Notes |
|------|----------|-------|
| Search manga | `GET /manga?title=...&availableTranslatedLanguage[]=en` | Include cover art via `includes[]=cover_art` |
| Manga details | `GET /manga/{id}?includes[]=cover_art&includes[]=author` | Title, description, status, tags |
| Cover image | `https://uploads.mangadex.org/covers/{mangaId}/{coverFile}` | From cover_art relationship |
| Chapter list | `GET /manga/{id}/feed?translatedLanguage[]=en&order[chapter]=asc&limit=500` | Paginate; filter EN; dedupe scanlation groups |
| Page metadata | `GET /at-home/server/{chapterId}` | Returns `baseUrl`, `chapter.hash`, `data[]`, `dataSaver[]` |
| Page image URL | `{baseUrl}/data/{hash}/{filename}` (or `/data-saver/`) | **No auth headers on image requests** |
| (optional) report | `POST https://api.mangadex.org/report` (@Home) | Report success/bytes/duration — good citizenship |

**Critical rules**
- `baseUrl` from `/at-home/server` is valid ~15 min; on **403** re-fetch metadata mid-download.
- **Rate limits:** ~5 req/s global; the `/at-home/server` endpoint is stricter. Throttle + backoff.
- **English only:** always send `translatedLanguage[]=en` (and `availableTranslatedLanguage[]=en` for search).
- **Quality toggle:** `data` (original) vs `dataSaver` (smaller) — expose as a setting.
- **Duplicate chapters:** MangaDex often has multiple EN scanlations of the same chapter number.
  v1 strategy: prefer the user's chosen group if set, else the most recent / most-viewed; let the user override per-manga.

**Authentication (Phase 4, for account sync only)**
- OAuth2 personal client: user registers a client at mangadex.org/settings → client ID + secret.
- Password grant → access token (15 min) + refresh token. App refreshes silently.
- Used only for: reading your follows list, marking chapters read. **Never** sent to image servers.

---

## 6. Bookmarks & Library (both modes)

Decided: **local now, MangaDex sync later.**

- **Local bookmarks (Phase 1+):** app's own table. Add any manga (from search) to your library. No login.
- **MangaDex sync (Phase 4):** after OAuth login, import your MangaDex follows; reconcile with local
  by `(provider_id, external_manga_id)`. Sync is additive/opt-in; local stays the source of truth.

**New-chapter detection (UpdateChecker)**
- Periodically (and on-demand "Update all") re-poll each bookmarked manga's EN feed.
- Compare latest chapter number / count against last-seen stored value.
- Surface an **unread badge** + a "new chapters" list in the UI. One-click "queue all new".

---

## 7. Download Pipeline

```
queue chapter
  → GET /at-home/server/{id}         (metadata, cache 15 min)
  → for each page (bounded concurrency, e.g. 4):
        GET image  → retry/backoff → on 403 re-fetch metadata
        save to  data/cache/{manga}/{chapter}/{NNN.ext}
  → mark chapter downloaded in DB
  → (optional) report success to @Home
```

- **Concurrency & rate limiting:** global async semaphore + token-bucket limiter so a 200-chapter
  binge never trips MangaDex limits.
- **Resumable:** skip pages/chapters already on disk; safe to re-run.
- **Progress:** per-chapter and per-queue progress streamed to UI (SSE/WebSocket or polling).

---

## 8. Export Pipeline (Kobo) — the careful part

MangaDex gives **images**, so we build the book.

**Findings**
- Plain EPUB works on Kobo but reads poorly for manga.
- The quality path is **fixed-layout, image-based EPUB** named `*.kepub.epub` (or `*.fxl.kepub.epub`)
  so Kobo's better rendering engine activates.
- **KCC (Kindle Comic Converter)** is the reference implementation (handles RTL order, spread
  splitting, per-device sizing). We replicate its relevant logic; optionally allow shelling out to KCC if installed.

**Outputs we'll support**
1. **CBZ** (Phase 1) — trivial: zip the page images in order. Universal, works with KOReader on Kobo.
2. **KEPUB** (Phase 5) — fixed-layout image EPUB, Kobo-optimized:
   - Resize/letterbox images to a target device profile (e.g., Kobo Clara/Libra/Sage).
   - Right-to-left reading order for manga; optional spread splitting.
   - Generate OPF + nav + per-page XHTML; name `*.kepub.epub`.

**Bundling (decided)**
- **Per-chapter is the DEFAULT** — one book per chapter, the way you like it.
- **Per-volume bundling is OPTIONAL** — a toggle for anyone who prefers fewer, larger books.

**Output layout & filenames (replaces the manual rename script)**
- One **folder per manga**, named after the manga, under your configured export folder.
- Files use a **configurable filename template**. The default fixes filesystem sort order by
  **zero-padding** the chapter number (otherwise `10` sorts before `2`):
  - Default: `{num_padded}_{manga}` → e.g. `0007_jojos-bizarre-adventure-part8.epub`
  - Tokens: `{num}`, `{num_padded}` (configurable width, default 4), `{manga}`, `{title}`,
    `{volume}`, `{group}`, `{lang}`.
  - Decimal chapters handled (`0010.5`); names slugified (safe across Windows/Kobo filesystems).
- This automates exactly what your old folder-name → rename script did, with no manual step.

**Embedded series metadata (auto-sorting on the device)**
- Each EPUB carries **series metadata** (series = manga name, series-index = chapter number) via
  the `calibre:series` / EPUB3 `belongs-to-collection` fields. Kobo reads this natively and will
  **group and order chapters by series on-device automatically** — solving "align 1 → latest"
  even before any manual foldering. Also embed a per-chapter cover/title so the library looks clean.

**Delivery to Kobo**
- v1: export to a folder you pick.
- Phase 5: **auto-detect the mounted Kobo USB drive** and copy each manga into its own
  subfolder on the device.
- Phase 5+ (advanced, opt-in): **auto-create on-device collections/shelves** by writing to the
  Kobo's `.kobo/KoboReader.sqlite` library DB (the same mechanism Calibre's Kobo plugin uses).
  This automates the manual "create folder on the device by hand" step you currently do.
  Guardrails: strictly opt-in, **back up the DB first**, only run while mounted, well-tested.

---

## 9. Data Model (SQLite, initial sketch)

```
provider(id, name, requires_auth)
manga(id, provider_id, external_id, title, description, cover_url, status, lang, added_at)
chapter(id, manga_id, external_id, number, volume, title, group, lang,
        published_at, downloaded_at NULL, page_count)
bookmark(id, manga_id, created_at, last_seen_chapter, unread_count, source['local'|'mangadex'])
download_job(id, chapter_id, state['queued'|'running'|'done'|'error'], progress, error, created_at)
export_job(id, scope['chapter'|'volume'], target_format['cbz'|'kepub'], path, state, created_at)
setting(key, value)              -- quality, device profile, concurrency, paths, group prefs
secret(key, value_encrypted)     -- via keyring/encrypted store, not plaintext
```

---

## 10. Configuration & Secrets

- `config.toml` (non-secret): export folder, image quality, device profile, concurrency, poll interval,
  wallpaper folder path, **bundling mode** (`chapter` default / `volume`), **filename template**
  (default `{num_padded}_{manga}`) and **number padding width** (default 4), Kobo drive path.
- **Secrets** (MangaDex client ID/secret, tokens): OS keychain via `keyring`, or an encrypted file
  fallback. First-run wizard prompts for optional credentials. **Nothing secret committed to GitHub.**
- `.env.example` documents what others need to supply.

---

## 11. UI Pages (Phase 2+)

- **Library** — bookmarked manga grid with covers, unread badges, "Update all".
- **Search** — query MangaDex, English results, "Add to library" / "Download".
- **Manga detail** — chapter list, per-chapter/volume download & export buttons, group preference.
- **Download Queue** — live progress, pause/resume/retry.
- **Reader** (Phase 6, stretch) — RTL/LTR toggle, single/double page, keyboard nav; reads downloaded images.
- **Settings** — quality, device profile, paths, credentials, concurrency.
- **Vibe** — shuffling background from a user `wallpapers/` folder (your anime-girl HakuNeko homage),
  drop images in, UI rotates them.

---

## 12. Phased Roadmap

| Phase | Deliverable | Outcome |
|-------|-------------|---------|
| **0** | This document | Reviewed & agreed scope |
| **1** | **Thin slice (CLI/script):** search MangaDex → list EN chapters → download a chapter → output CBZ (per-chapter, templated filename in a per-manga folder) | Proves the whole pipeline end-to-end |
| **2** | FastAPI + minimal web UI: search, library (local bookmarks), download queue | Usable app in the browser |
| **3** | Polish UI: covers, unread badges, "Update all", wallpaper shuffle | The "dope UI" |
| **4** | MangaDex OAuth login + follows sync (the "both" bookmark mode) | Mirrors your real account |
| **5** | KEPUB export (per-chapter default, embedded series metadata) + device profiles + optional volume bundling + auto-detect "send to Kobo" | Real Kobo-quality output |
| **5+** | Opt-in on-device collections via `KoboReader.sqlite` (backup-first) | Auto-creates shelves on the Kobo |
| **6** | In-app reader (stretch) | Read inside the app |
| **7** | Second provider behind the interface; packaging for GitHub release | Multi-provider + shareable |

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| MangaDex rate limits / bans | Token-bucket limiter, backoff, @Home reporting, conservative defaults |
| `baseUrl` expiry mid-download | Re-fetch `/at-home/server` on 403; cache only 15 min |
| Duplicate EN scanlations | Group preference per manga; sensible default (latest/most-viewed) |
| KEPUB quirks across Kobo models | Device profiles; lean on KCC's proven logic; test on your actual device |
| API/terms changes | Provider isolated behind interface; easy to patch one class |
| Secret leakage | keyring/encrypted store; `.env.example`; nothing secret in repo |

---

## 14. Open Questions (for later phases, not blocking Phase 1)

1. Which Kobo model do you have? (Sets the default device profile for KEPUB sizing.)
2. Default image quality — original (`data`) or data-saver? (Storage vs fidelity.)
3. Frontend flavor for Phase 2 — lightweight HTMX/Alpine vs a Svelte SPA?

*Settled:* per-chapter EPUBs are the default; volume bundling is an optional toggle.

---

## 15. Proposed Repo Layout (when we start coding)

```
manga_downloader_app/
├── PLAN.md                  ← this file
├── README.md
├── pyproject.toml
├── .env.example
├── run.py                   ← launches FastAPI + opens browser
├── app/
│   ├── main.py              ← FastAPI app & routers
│   ├── config.py
│   ├── db/                  ← models, session, migrations
│   ├── providers/
│   │   ├── base.py          ← Provider Protocol + DTOs
│   │   └── mangadex.py
│   ├── services/
│   │   ├── downloads.py     ← queue, rate limiter
│   │   ├── library.py       ← bookmarks, update checker
│   │   ├── export/          ← cbz.py, kepub.py, profiles.py
│   │   └── secrets.py
│   ├── api/                 ← routers
│   └── web/                 ← templates / static / frontend
├── wallpapers/              ← drop images here; UI shuffles them
└── data/                    ← sqlite db + image cache (gitignored)
```
