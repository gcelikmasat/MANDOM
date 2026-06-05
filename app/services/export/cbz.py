"""CBZ exporter — a ZIP of page images in reading order.

Universal comic format; reads via KOReader on Kobo. The Kobo-native KEPUB
builder (fixed-layout, device-sized, with embedded series metadata) lands in
Phase 5; this proves the end-to-end pipeline now.
"""

from __future__ import annotations

import zipfile
from pathlib import Path


def build_cbz(image_paths: list[Path], out_path: Path) -> Path:
    """Bundle ``image_paths`` (already ordered) into a .cbz at ``out_path``."""
    if not image_paths:
        raise ValueError("Cannot build a CBZ with no pages.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    width = len(str(len(image_paths)))

    # Write to a temp file then rename, so a crash never leaves a half-written .cbz.
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as zf:
        # ZIP_STORED: images are already compressed; re-zipping wastes CPU for ~0 gain.
        for i, src in enumerate(image_paths, start=1):
            arcname = f"{i:0{width}d}{src.suffix.lower()}"
            zf.write(src, arcname)
    tmp.replace(out_path)
    return out_path
