"""Provider plugins. Each provider implements the interface in ``base.py``.

Adding a new manga source = writing one class that satisfies ``Provider``.
"""

from app.providers.base import (
    ChapterInfo,
    MangaDetail,
    MangaSummary,
    PageBatch,
    Provider,
)

__all__ = [
    "ChapterInfo",
    "MangaDetail",
    "MangaSummary",
    "PageBatch",
    "Provider",
]
