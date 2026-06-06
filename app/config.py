"""Application configuration.

Non-secret settings live here with sane defaults and can be overridden by a
``config.toml`` in the repo root. Secrets (API keys/tokens) are handled
separately in a later phase and never stored in plaintext config.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    """Target e-reader screen geometry (used by the KEPUB exporter, Phase 5)."""

    name: str
    width: int       # pixels (portrait)
    height: int      # pixels (portrait)
    color: bool


# Built-in profiles. The user's device is the default; more can be added later.
DEVICE_PROFILES: dict[str, DeviceProfile] = {
    # Kobo Clara Colour — 6" E Ink Kaleido 3, 1448x1072 px panel.
    "clara_colour": DeviceProfile("Kobo Clara Colour", width=1072, height=1448, color=True),
}


@dataclass(frozen=True, slots=True)
class Config:
    # Where finished books are written (one subfolder per manga).
    export_dir: Path = ROOT / "downloads"
    # Working area for the raw downloaded page images + local DB/cache.
    data_dir: Path = ROOT / "data"

    # Always fetch English; always best-available image quality (no toggle by design).
    language: str = "en"
    image_quality: str = "data"  # "data" = original; "data-saver" exists but we don't use it

    # Output naming. Default fixes filesystem sort by zero-padding the chapter number,
    # so 0002 < 0010 < 0100. Replaces the old manual rename script.
    filename_template: str = "{num_padded}_{manga}"
    number_padding: int = 4

    # Bundling: per-chapter is the default; volume bundling is an optional toggle.
    bundling: str = "chapter"  # "chapter" | "volume"

    # Export format(s) produced per chapter.
    #   "kepub" -> Kobo-optimized fixed-layout .kepub.epub (default; best on the Clara Colour)
    #   "cbz"   -> plain comic zip
    #   "both"  -> emit both
    export_format: str = "kepub"
    # Reading direction for the EPUB. Manga is right-to-left; set "ltr" for
    # webtoons / manhwa.
    reading_direction: str = "rtl"  # "rtl" | "ltr"

    # Download politeness.
    max_concurrency: int = 4
    requests_per_second: float = 4.0  # stay under MangaDex's ~5 req/s global ceiling

    device_profile: str = "clara_colour"

    # Optional explicit Kobo mount path (e.g. "K:\\" or "/media/you/KOBOeReader").
    # Leave None to auto-detect a connected device by its ".kobo" folder.
    kobo_path: str | None = None

    user_agent: str = "manga-downloader-app/0.1 (personal use; +https://github.com/)"

    def profile(self) -> DeviceProfile:
        return DEVICE_PROFILES[self.device_profile]


def load_config(path: Path | None = None) -> Config:
    """Load ``config.toml`` if present, overlaying onto defaults."""
    cfg = Config()
    path = path or (ROOT / "config.toml")
    if path.exists():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        # Only override keys the user actually set; coerce paths.
        overrides: dict = {}
        for key, value in data.items():
            if not hasattr(cfg, key):
                continue
            if key in {"export_dir", "data_dir"}:
                value = Path(value).expanduser()
            overrides[key] = value
        cfg = replace(cfg, **overrides)
    return cfg
