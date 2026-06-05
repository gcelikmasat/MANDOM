"""MangaDex provider.

Uses MangaDex's official public JSON API — no scraping, no login needed for
search / chapter listing / page images. English is enforced via
``translatedLanguage=en``. See PLAN.md section 5 for the endpoint map.
"""

from __future__ import annotations

import asyncio

import httpx

from app.providers.base import (
    ChapterInfo,
    MangaDetail,
    MangaSummary,
    PageBatch,
)
from app.services.ratelimit import RateLimiter

API_BASE = "https://api.mangadex.org"
UPLOADS_BASE = "https://uploads.mangadex.org"

# Include every rating so anything the user legitimately reads is findable.
CONTENT_RATINGS = ["safe", "suggestive", "erotica", "pornographic"]

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class MangaDexProvider:
    id = "mangadex"
    name = "MangaDex"
    requires_auth = False  # read operations are public

    def __init__(
        self,
        *,
        user_agent: str,
        requests_per_second: float = 4.0,
        image_quality: str = "data",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._quality = "data" if image_quality == "data" else "data-saver"
        self._limiter = RateLimiter(requests_per_second)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=API_BASE,
            headers={"User-Agent": user_agent},
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "MangaDexProvider":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # ---- HTTP helper -----------------------------------------------------

    async def _get(self, path: str, params: dict | None = None, *, retries: int = 4) -> dict:
        attempt = 0
        while True:
            await self._limiter.acquire()
            try:
                resp = await self._client.get(path, params=params)
            except httpx.TransportError:
                if attempt >= retries:
                    raise
                await asyncio.sleep(2**attempt)
                attempt += 1
                continue
            if resp.status_code in _RETRYABLE_STATUS and attempt < retries:
                delay = float(resp.headers.get("Retry-After", 2**attempt))
                await asyncio.sleep(delay)
                attempt += 1
                continue
            resp.raise_for_status()
            return resp.json()

    # ---- Interface -------------------------------------------------------

    async def search(
        self, query: str, *, language: str = "en", limit: int = 20, offset: int = 0
    ) -> list[MangaSummary]:
        data = await self._get(
            "/manga",
            {
                "title": query,
                "limit": limit,
                "offset": offset,
                "includes[]": ["cover_art"],
                "contentRating[]": CONTENT_RATINGS,
                "availableTranslatedLanguage[]": [language],
                "order[relevance]": "desc",
            },
        )
        return [self._to_summary(item) for item in data.get("data", [])]

    async def get_manga(self, manga_id: str) -> MangaDetail:
        data = await self._get(
            f"/manga/{manga_id}",
            {"includes[]": ["cover_art", "author", "artist"]},
        )
        item = data["data"]
        attrs = item.get("attributes", {})
        authors = [
            rel.get("attributes", {}).get("name", "")
            for rel in item.get("relationships", [])
            if rel.get("type") in {"author", "artist"} and rel.get("attributes")
        ]
        tags = [
            t.get("attributes", {}).get("name", {}).get("en", "")
            for t in attrs.get("tags", [])
        ]
        return MangaDetail(
            provider_id=self.id,
            external_id=item["id"],
            title=_pick_lang(attrs.get("title", {})),
            description=_pick_lang(attrs.get("description", {})),
            cover_url=self._cover_url(item),
            status=attrs.get("status"),
            authors=[a for a in dict.fromkeys(authors) if a],
            tags=[t for t in tags if t],
        )

    async def get_chapters(
        self, manga_id: str, *, language: str = "en", dedupe: bool = True
    ) -> list[ChapterInfo]:
        chapters: list[ChapterInfo] = []
        offset = 0
        limit = 500
        while True:
            data = await self._get(
                f"/manga/{manga_id}/feed",
                {
                    "translatedLanguage[]": [language],
                    "limit": limit,
                    "offset": offset,
                    "includes[]": ["scanlation_group"],
                    "contentRating[]": CONTENT_RATINGS,
                    "order[volume]": "asc",
                    "order[chapter]": "asc",
                },
            )
            for item in data.get("data", []):
                ch = self._to_chapter(item)
                if ch is not None:
                    chapters.append(ch)
            total = data.get("total", 0)
            offset += limit
            if offset >= total:
                break

        if dedupe:
            chapters = _dedupe_by_number(chapters)
        return chapters

    async def get_pages(self, chapter_id: str) -> PageBatch:
        data = await self._get(f"/at-home/server/{chapter_id}")
        base = data["baseUrl"]
        chapter = data["chapter"]
        chap_hash = chapter["hash"]
        files = chapter["data"] if self._quality == "data" else chapter["dataSaver"]
        urls = [f"{base}/{self._quality}/{chap_hash}/{name}" for name in files]
        return PageBatch(chapter_external_id=chapter_id, urls=urls)

    # ---- Parsing helpers -------------------------------------------------

    def _to_summary(self, item: dict) -> MangaSummary:
        attrs = item.get("attributes", {})
        return MangaSummary(
            provider_id=self.id,
            external_id=item["id"],
            title=_pick_lang(attrs.get("title", {})),
            cover_url=self._cover_url(item),
        )

    def _to_chapter(self, item: dict) -> ChapterInfo | None:
        attrs = item.get("attributes", {})
        # Skip chapters hosted off-site (no downloadable pages here).
        if attrs.get("externalUrl") or not attrs.get("pages"):
            return None
        number = attrs.get("chapter")
        group = next(
            (
                rel.get("attributes", {}).get("name")
                for rel in item.get("relationships", [])
                if rel.get("type") == "scanlation_group" and rel.get("attributes")
            ),
            None,
        )
        return ChapterInfo(
            provider_id=self.id,
            external_id=item["id"],
            number=number,
            number_sort=_parse_number(number),
            volume=attrs.get("volume"),
            title=attrs.get("title") or None,
            group=group,
            language=attrs.get("translatedLanguage", "en"),
            published_at=attrs.get("publishAt"),
            page_count=int(attrs.get("pages") or 0),
        )

    def _cover_url(self, item: dict) -> str | None:
        for rel in item.get("relationships", []):
            if rel.get("type") == "cover_art":
                file_name = rel.get("attributes", {}).get("fileName")
                if file_name:
                    return f"{UPLOADS_BASE}/covers/{item['id']}/{file_name}"
        return None


def _pick_lang(localized: dict, prefer: str = "en") -> str:
    """MangaDex titles/descriptions are {lang: text}; prefer English."""
    if not localized:
        return ""
    if prefer in localized:
        return localized[prefer]
    return next(iter(localized.values()), "")


def _parse_number(number: str | None) -> float:
    if not number:
        return 0.0
    try:
        return float(number)
    except ValueError:
        return 0.0


def _dedupe_by_number(chapters: list[ChapterInfo]) -> list[ChapterInfo]:
    """Keep one chapter per number (first seen after ordering = preferred group)."""
    seen: dict[str, ChapterInfo] = {}
    for ch in chapters:
        key = ch.number if ch.number is not None else f"oneshot:{ch.external_id}"
        if key not in seen:
            seen[key] = ch
    return sorted(seen.values(), key=lambda c: c.number_sort)
