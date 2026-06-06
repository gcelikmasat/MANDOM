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


# Mutable so the Settings page can update it in place (all holders see changes).
@dataclass(slots=True)
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

    # In-app reader: which side / arrow key turns to the NEXT page.
    # "right" (default) = tap right edge or press → to advance.
    reader_advance_side: str = "right"  # "right" | "left"

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


def _toml_literal(value: object) -> str:
    """TOML single-quoted literal string (no escape processing — safe for Windows
    paths with backslashes). Strips any embedded single quotes."""
    return "'" + str(value).replace("'", "") + "'"


def save_config(cfg: Config, path: Path | None = None) -> None:
    """Persist the user-editable settings to config.toml (written by the
    Settings page) so they survive restarts."""
    path = path or (ROOT / "config.toml")
    lines = [
        "# Mandom settings - written by the Settings page. Safe to edit by hand.",
        f"export_dir = {_toml_literal(cfg.export_dir)}",
        f"export_format = {_toml_literal(cfg.export_format)}",
        f"reading_direction = {_toml_literal(cfg.reading_direction)}",
        f"reader_advance_side = {_toml_literal(cfg.reader_advance_side)}",
        f"device_profile = {_toml_literal(cfg.device_profile)}",
    ]
    if cfg.kobo_path:
        lines.append(f"kobo_path = {_toml_literal(cfg.kobo_path)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
