"""Mandom FastAPI server + HTMX routes.

Serves a single-page-ish UI: search MangaDex, bookmark favourites locally, open a
manga to see its English chapters, and queue chapter downloads (-> CBZ) with live
progress. A shuffling wallpaper background reads from the ``wallpapers/`` folder.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.config import ROOT, load_config
from app.db import Bookmark, DownloadJob, get_session, init_db
from app.providers.mangadex import MangaDexProvider
from app.services.updates import check_all, record_seen, set_baseline
from app.web.queue import DownloadManager

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(WEB_DIR / "templates"))

# Only proxy images from MangaDex hosts (avoid open SSRF proxy).
_ALLOWED_IMAGE_HOSTS = {"uploads.mangadex.org", "mangadex.org"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    init_db(cfg.data_dir)
    provider = MangaDexProvider(
        user_agent=cfg.user_agent,
        requests_per_second=cfg.requests_per_second,
        image_quality=cfg.image_quality,
    )
    img_client = httpx.AsyncClient(
        headers={"User-Agent": cfg.user_agent},
        timeout=httpx.Timeout(60.0),
        follow_redirects=True,
    )
    manager = DownloadManager(cfg, provider, img_client)
    manager.start()

    app.state.cfg = cfg
    app.state.provider = provider
    app.state.img_client = img_client
    app.state.manager = manager
    try:
        yield
    finally:
        await manager.stop()
        await provider.aclose()
        await img_client.aclose()


app = FastAPI(title="Mandom", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
app.mount("/wallpapers", StaticFiles(directory=str(ROOT / "wallpapers")), name="wallpapers")


# ---- helpers -------------------------------------------------------------

def _bookmarked_ids() -> set[str]:
    with get_session() as s:
        rows = s.execute(select(Bookmark.external_id)).scalars().all()
    return set(rows)


# ---- pages ---------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return TEMPLATES.TemplateResponse(request, "home.html", {})


@app.get("/library", response_class=HTMLResponse)
async def library_page(request: Request):
    return TEMPLATES.TemplateResponse(request, "library.html", {"library": _library_rows()})


@app.post("/library/check-all", response_class=HTMLResponse)
async def library_check_all(request: Request):
    await check_all(app.state.provider, language=app.state.cfg.language)
    return TEMPLATES.TemplateResponse(
        request, "partials/_library_grid.html", {"library": _library_rows()}
    )


def _library_rows():
    with get_session() as s:
        # Show manga with new chapters first, then most recently added.
        return s.execute(
            select(Bookmark).order_by(Bookmark.unread.desc(), Bookmark.created_at.desc())
        ).scalars().all()


@app.get("/browse", response_class=HTMLResponse)
async def browse(request: Request, sort: str = "popular"):
    results = await app.state.provider.browse(
        sort=sort, language=app.state.cfg.language, limit=32
    )
    return TEMPLATES.TemplateResponse(
        request, "partials/_grid.html",
        {"results": results, "bookmarked": _bookmarked_ids(),
         "empty": "Nothing to show right now."},
    )


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = ""):
    q = q.strip()
    if not q:
        return HTMLResponse("")
    results = await app.state.provider.search(q, language=app.state.cfg.language, limit=18)
    return TEMPLATES.TemplateResponse(
        request, "partials/_grid.html",
        {"results": results, "bookmarked": _bookmarked_ids(),
         "empty": "No results. Try another title."},
    )


@app.get("/manga/{provider_id}/{external_id}", response_class=HTMLResponse)
async def manga_detail(request: Request, provider_id: str, external_id: str):
    provider = app.state.provider
    detail = await provider.get_manga(external_id)
    chapters = await provider.get_chapters(external_id, language=app.state.cfg.language)
    is_bookmarked = external_id in _bookmarked_ids()
    # Opening the manga counts as catching up: clear its unread badge.
    if is_bookmarked:
        latest = max((c.number_sort for c in chapters), default=0.0)
        record_seen(external_id, latest, len(chapters))
    return TEMPLATES.TemplateResponse(
        request, "manga.html",
        {
            "manga": detail,
            "chapters": chapters,
            "bookmarked": is_bookmarked,
        },
    )


# ---- library (local bookmarks) ------------------------------------------

@app.post("/library/add", response_class=HTMLResponse)
async def library_add(
    request: Request,
    provider_id: str = Form(...),
    external_id: str = Form(...),
    title: str = Form(...),
    cover_url: str = Form(""),
):
    newly_added = False
    with get_session() as s:
        exists = s.execute(
            select(Bookmark).where(Bookmark.external_id == external_id)
        ).scalar_one_or_none()
        if exists is None:
            s.add(Bookmark(
                provider_id=provider_id, external_id=external_id,
                title=title, cover_url=cover_url or None,
            ))
            newly_added = True
    # Baseline the chapter count so only future releases register as unread.
    if newly_added:
        try:
            await set_baseline(app.state.provider, external_id, language=app.state.cfg.language)
        except Exception:
            pass
    return _bookmark_button(request, provider_id, external_id, title, cover_url, True)


@app.post("/library/remove", response_class=HTMLResponse)
async def library_remove(
    request: Request,
    provider_id: str = Form(...),
    external_id: str = Form(...),
    title: str = Form(...),
    cover_url: str = Form(""),
    source: str = Form("button"),
):
    with get_session() as s:
        row = s.execute(
            select(Bookmark).where(Bookmark.external_id == external_id)
        ).scalar_one_or_none()
        if row is not None:
            s.delete(row)
    # From the library grid, the card itself is swapped out (return nothing).
    if source == "grid":
        return HTMLResponse("")
    return _bookmark_button(request, provider_id, external_id, title, cover_url, False)


def _bookmark_button(request, provider_id, external_id, title, cover_url, is_bookmarked):
    return TEMPLATES.TemplateResponse(
        request, "partials/_bookmark_button.html",
        {
            "m": {
                "provider_id": provider_id, "external_id": external_id,
                "title": title, "cover_url": cover_url,
            },
            "is_saved": is_bookmarked,
        },
    )


# ---- downloads -----------------------------------------------------------

@app.post("/download", response_class=HTMLResponse)
async def download_chapter(
    request: Request,
    provider_id: str = Form(...),
    manga_external_id: str = Form(...),
    manga_title: str = Form(...),
    chapter_external_id: str = Form(...),
    chapter_label: str = Form(...),
):
    _queue_jobs(request, [(provider_id, manga_external_id, manga_title,
                           chapter_external_id, chapter_label)])
    return await _downloads_partial(request)


@app.post("/download-all", response_class=HTMLResponse)
async def download_all(
    request: Request,
    provider_id: str = Form(...),
    manga_external_id: str = Form(...),
    manga_title: str = Form(...),
):
    chapters = await app.state.provider.get_chapters(
        manga_external_id, language=app.state.cfg.language
    )
    rows = [
        (provider_id, manga_external_id, manga_title, c.external_id, c.number or "0")
        for c in chapters
    ]
    _queue_jobs(request, rows)
    return await _downloads_partial(request)


def _queue_jobs(request: Request, rows: list[tuple]) -> None:
    manager: DownloadManager = request.app.state.manager
    with get_session() as s:
        jobs = [
            DownloadJob(
                provider_id=p, manga_external_id=mid, manga_title=mt,
                chapter_external_id=cid, chapter_label=clabel, state="queued",
            )
            for (p, mid, mt, cid, clabel) in rows
        ]
        s.add_all(jobs)
        s.flush()
        ids = [j.id for j in jobs]
    for jid in ids:
        manager.enqueue(jid)


@app.get("/downloads", response_class=HTMLResponse)
async def downloads(request: Request):
    return await _downloads_partial(request)


async def _downloads_partial(request: Request) -> HTMLResponse:
    with get_session() as s:
        jobs = s.execute(
            select(DownloadJob).order_by(DownloadJob.created_at.desc()).limit(30)
        ).scalars().all()
    active = any(j.state in {"queued", "running"} for j in jobs)
    return TEMPLATES.TemplateResponse(
        request, "partials/_downloads.html", {"jobs": jobs, "active": active}
    )


# ---- image proxy + wallpapers -------------------------------------------

@app.get("/cover")
async def cover(url: str):
    try:
        parsed = httpx.URL(url)
    except Exception:
        return Response(status_code=400)
    if parsed.host not in _ALLOWED_IMAGE_HOSTS:
        return Response(status_code=403)
    client: httpx.AsyncClient = app.state.img_client
    r = await client.get(url)
    if r.status_code != 200:
        return Response(status_code=r.status_code)
    return Response(content=r.content, media_type=r.headers.get("content-type", "image/jpeg"))


@app.get("/api/wallpapers")
async def wallpapers():
    folder = ROOT / "wallpapers"
    files = sorted(
        f"/wallpapers/{p.name}"
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS
    )
    return JSONResponse(files)
