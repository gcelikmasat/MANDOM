"""Provider interface + shared DTOs.

The UI and download engine only ever touch these types, never a provider's
raw API shapes. That keeps every manga source interchangeable behind one
contract (the lesson kept from HakuNeko's connector design).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class MangaSummary:
    """Lightweight result item from a search."""

    provider_id: str
    external_id: str
    title: str
    cover_url: str | None = None


@dataclass(slots=True)
class MangaDetail:
    """Full manga metadata."""

    provider_id: str
    external_id: str
    title: str
    description: str = ""
    cover_url: str | None = None
    status: str | None = None
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ChapterInfo:
    """A single translated chapter."""

    provider_id: str
    external_id: str
    # ``number`` is the source string (e.g. "10.5", or None for a oneshot) so we
    # never lose precision; ``number_sort`` is the parsed value used for ordering.
    number: str | None
    number_sort: float
    volume: str | None = None
    title: str | None = None
    group: str | None = None
    language: str = "en"
    published_at: str | None = None
    page_count: int = 0


@dataclass(slots=True)
class PageBatch:
    """Resolved, ready-to-download pages for one chapter.

    ``urls`` are absolute image URLs in reading order. Because a provider's CDN
    URLs can expire (MangaDex@Home guarantees only ~15 min), the downloader can
    ask the provider to re-resolve a batch mid-download via ``get_pages``.
    """

    chapter_external_id: str
    urls: list[str]
    # Per-request headers, if the CDN needs them. MangaDex images need NONE
    # (and must not receive auth headers), but other providers might.
    headers: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class Provider(Protocol):
    """The one interface every manga source implements."""

    id: str
    name: str
    requires_auth: bool

    async def search(
        self, query: str, *, language: str = "en", limit: int = 20, offset: int = 0
    ) -> list[MangaSummary]: ...

    async def get_manga(self, manga_id: str) -> MangaDetail: ...

    async def get_chapters(
        self, manga_id: str, *, language: str = "en"
    ) -> list[ChapterInfo]: ...

    async def get_pages(self, chapter_id: str) -> PageBatch: ...
