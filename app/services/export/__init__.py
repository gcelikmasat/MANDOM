"""Export pipeline: CBZ and Kobo KEPUB."""

from __future__ import annotations

from pathlib import Path

from app.config import DeviceProfile
from app.services.export.cbz import build_cbz
from app.services.export.kepub import build_kepub

__all__ = ["build_cbz", "build_kepub", "build_exports"]


def build_exports(
    images: list[Path],
    out_dir: Path,
    stem: str,
    *,
    export_format: str,
    manga_title: str,
    chapter_label: str,
    profile: DeviceProfile,
    language: str = "en",
    direction: str = "rtl",
) -> Path | None:
    """Produce the configured format(s) for one chapter; return the primary file.

    ``export_format`` is "kepub", "cbz", or "both". When both are produced the
    KEPUB is treated as primary. CPU-bound (Pillow) — call via asyncio.to_thread
    from async code.
    """
    outputs: list[Path] = []
    if export_format in ("cbz", "both"):
        outputs.append(build_cbz(images, out_dir / f"{stem}.cbz"))
    if export_format in ("kepub", "both"):
        outputs.append(build_kepub(
            images,
            out_dir / f"{stem}.kepub.epub",
            title=f"{manga_title} - Ch. {chapter_label}",
            series=manga_title,
            series_index=chapter_label,
            profile=profile,
            language=language,
            direction=direction,
        ))
    return outputs[-1] if outputs else None
