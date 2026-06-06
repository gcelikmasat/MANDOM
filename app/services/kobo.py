"""Detect a connected Kobo and copy exported books onto it.

A Kobo mounts as USB mass storage with a ``.kobo`` directory at the drive root;
that's how we recognise it (same signal Calibre uses). We copy each manga's
exported files into a folder on the device named after the manga. Because the
KEPUBs already carry series metadata, the Kobo groups a manga's chapters by
series on its own — no need to touch the device database.
"""

from __future__ import annotations

import os
import shutil
import string
from pathlib import Path

# A KEPUB's path suffix is ".epub" (it's named *.kepub.epub).
BOOK_EXTS = {".epub", ".cbz"}


def _is_kobo(root: Path) -> bool:
    try:
        return (root / ".kobo").is_dir()
    except OSError:
        return False


def _safe_iter(path: Path) -> list[Path]:
    try:
        return list(path.iterdir())
    except OSError:
        return []


def find_kobo_devices(extra: str | None = None) -> list[Path]:
    """Return mount roots of connected Kobo devices.

    ``extra`` is an optional user-configured path checked first (handy if
    auto-detection misses, or for a non-standard mount).
    """
    found: list[Path] = []
    if extra:
        p = Path(extra)
        if _is_kobo(p) or p.exists():
            found.append(p)

    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:\\")
            if _is_kobo(root):
                found.append(root)
    else:
        for base in ("/Volumes", "/media", "/run/media", "/mnt"):
            b = Path(base)
            if not b.is_dir():
                continue
            for child in _safe_iter(b):
                if _is_kobo(child):
                    found.append(child)
                else:  # some distros nest under /media/<user>/<label>
                    for sub in _safe_iter(child):
                        if _is_kobo(sub):
                            found.append(sub)

    # De-dupe, preserve order.
    seen: set[str] = set()
    out: list[Path] = []
    for p in found:
        key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def copy_folder_to_kobo(device_root: Path, source_dir: Path) -> tuple[int, Path]:
    """Copy book files from ``source_dir`` into ``device_root/<source name>/``."""
    dest = device_root / source_dir.name
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in sorted(source_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in BOOK_EXTS:
            shutil.copy2(f, dest / f.name)
            count += 1
    return count, dest


def send_manga(device_root: Path, export_dir: Path, manga_folder: str) -> tuple[int, Path]:
    src = export_dir / manga_folder
    if not src.is_dir():
        return 0, src
    return copy_folder_to_kobo(device_root, src)


def send_all(device_root: Path, export_dir: Path) -> tuple[int, int]:
    """Copy every downloaded manga folder. Returns (files copied, manga count)."""
    total_files = 0
    total_manga = 0
    if not export_dir.is_dir():
        return 0, 0
    for sub in sorted(export_dir.iterdir()):
        if sub.is_dir():
            n, _ = copy_folder_to_kobo(device_root, sub)
            if n:
                total_files += n
                total_manga += 1
    return total_files, total_manga
