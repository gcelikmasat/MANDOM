"""New-chapter detection for bookmarks.

Re-polls a bookmarked manga's English feed and records the latest chapter, the
total count, and how many chapters are newer than what the user has "seen".
The UI turns ``unread`` into a badge and offers a one-click "Update all".
"""

from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import select

from app.db import Bookmark, get_session
from app.providers.base import Provider


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _summarize(chapters) -> tuple[float, int]:
    """Return (latest chapter sort value, total chapter count)."""
    latest = max((c.number_sort for c in chapters), default=0.0)
    return latest, len(chapters)


async def set_baseline(provider: Provider, external_id: str, *, language: str = "en") -> None:
    """Called when a manga is first bookmarked: treat everything available now
    as already seen, so only chapters released *after* this show up as unread."""
    chapters = await provider.get_chapters(external_id, language=language)
    latest, total = _summarize(chapters)
    with get_session() as s:
        bm = s.execute(
            select(Bookmark).where(Bookmark.external_id == external_id)
        ).scalar_one_or_none()
        if bm is None:
            return
        bm.latest_sort = latest
        bm.last_seen_sort = latest
        bm.total_chapters = total
        bm.unread = 0
        bm.last_checked = _now()


async def check_bookmark(provider: Provider, external_id: str, *, language: str = "en") -> int:
    """Re-check one bookmark; returns its unread count."""
    chapters = await provider.get_chapters(external_id, language=language)
    latest, total = _summarize(chapters)
    with get_session() as s:
        bm = s.execute(
            select(Bookmark).where(Bookmark.external_id == external_id)
        ).scalar_one_or_none()
        if bm is None:
            return 0
        bm.latest_sort = latest
        bm.total_chapters = total
        bm.unread = sum(1 for c in chapters if c.number_sort > bm.last_seen_sort)
        bm.last_checked = _now()
        return bm.unread


async def check_all(provider: Provider, *, language: str = "en", concurrency: int = 3) -> int:
    """Re-check every bookmark (bounded concurrency). Returns how many checked."""
    with get_session() as s:
        ids = s.execute(select(Bookmark.external_id)).scalars().all()
    sem = asyncio.Semaphore(concurrency)

    async def one(eid: str) -> None:
        async with sem:
            try:
                await check_bookmark(provider, eid, language=language)
            except Exception:
                pass  # one failing manga shouldn't abort the whole sweep

    await asyncio.gather(*(one(e) for e in ids))
    return len(ids)


def record_seen(external_id: str, latest_sort: float, total_chapters: int) -> None:
    """Mark a bookmark caught up using freshly-fetched feed numbers.

    Used when the user opens the manga's detail page (viewing == catching up)."""
    with get_session() as s:
        bm = s.execute(
            select(Bookmark).where(Bookmark.external_id == external_id)
        ).scalar_one_or_none()
        if bm is not None:
            bm.latest_sort = latest_sort
            bm.last_seen_sort = latest_sort
            bm.total_chapters = total_chapters
            bm.unread = 0
            bm.last_checked = _now()


def mark_seen(external_id: str) -> None:
    """Reset a bookmark's unread count (user has caught up)."""
    with get_session() as s:
        bm = s.execute(
            select(Bookmark).where(Bookmark.external_id == external_id)
        ).scalar_one_or_none()
        if bm is not None:
            bm.last_seen_sort = bm.latest_sort
            bm.unread = 0
