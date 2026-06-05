"""Filesystem-safe naming: slugs, zero-padded chapter numbers, filename templates.

This is what replaces the old manual "rename so chapters sort 1..N" script.
"""

from __future__ import annotations

import re

from app.providers.base import ChapterInfo

_UNSAFE = re.compile(r"[^a-z0-9]+")
# Characters Windows forbids in filenames, plus control chars.
_WIN_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def slugify(text: str, *, max_len: int = 80) -> str:
    """Lowercase, hyphenated, ASCII-ish slug safe on Windows and Kobo."""
    text = text.strip().lower()
    slug = _UNSAFE.sub("-", text).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "untitled"


def safe_filename(text: str) -> str:
    """Like a slug but preserves spaces/case for human-readable folder names."""
    cleaned = _WIN_FORBIDDEN.sub("", text).strip().rstrip(". ")
    return cleaned or "untitled"


def pad_number(number: str | None, width: int) -> str:
    """Zero-pad the integer part of a chapter number so files sort correctly.

    "7" -> "0007", "10.5" -> "0010.5", None (oneshot) -> "0000".
    Falls back to a slug of the raw value if it isn't numeric.
    """
    if number is None or number == "":
        return "0".zfill(width)
    try:
        if "." in number:
            int_part, frac = number.split(".", 1)
            return f"{int(int_part):0{width}d}.{frac}"
        return f"{int(number):0{width}d}"
    except ValueError:
        return slugify(number)


def render_filename(
    template: str,
    chapter: ChapterInfo,
    *,
    manga_title: str,
    padding: int,
) -> str:
    """Render the configured filename template into a safe stem (no extension)."""
    tokens = {
        "num": chapter.number or "0",
        "num_padded": pad_number(chapter.number, padding),
        "manga": slugify(manga_title),
        "title": slugify(chapter.title) if chapter.title else "",
        "volume": chapter.volume or "",
        "group": slugify(chapter.group) if chapter.group else "",
        "lang": chapter.language,
    }
    try:
        stem = template.format(**tokens)
    except (KeyError, IndexError):
        # Bad template token -> fall back to the safe default rather than crash.
        stem = f"{tokens['num_padded']}_{tokens['manga']}"
    # Collapse any doubled separators left by empty tokens (e.g. missing title).
    stem = re.sub(r"[_-]{2,}", "_", stem).strip("_-")
    return safe_filename(stem)
