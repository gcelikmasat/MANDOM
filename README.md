# Manga Downloader App

Personal-use manga downloader. Pulls **English** chapters from provider APIs
(**MangaDex** first), and exports reader-ready files. Built to reliably do what
HakuNeko did, without the scraping fragility — and to ship clean files to a
**Kobo Clara Colour**.

> See **[PLAN.md](PLAN.md)** for the full specification, architecture, and roadmap.
> **Personal use only** — download what you'd otherwise read on the site, for your own device.

## Status

**Phase 1 — thin slice (CLI).** Proves the end-to-end pipeline:
search → list English chapters → download a chapter → output a CBZ.
The web UI, bookmarks, KEPUB export, and in-app reader come in later phases.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .
```

## Usage

```bash
# Find a manga
manga search "chainsaw man"

# List its English chapters (use an id from the search output)
manga chapters <manga_id>

# Download one chapter (or everything) -> downloads/<Manga Title>/0001_<manga>.cbz
manga download <manga_id> --chapter 1
manga download <manga_id> --all
```

Files land in `downloads/<Manga Title>/` with zero-padded names
(`0001_…`, `0002_…`) so they sort 1→N on disk and on the device.

## Config

Optional `config.toml` in the repo root overrides defaults (export folder,
filename template, concurrency, etc.). See `config.example.toml`.
