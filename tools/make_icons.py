"""Generate the PWA / favicon icon set from a source image.

    python tools/make_icons.py path/to/ringo.webp

Writes icon-192.png, icon-512.png, and icon-512-maskable.png into
app/web/static/. Any format Pillow can read works (webp, png, jpg, ...).
The maskable variant gets safe-zone padding on the app's dark background.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

STATIC = Path(__file__).resolve().parent.parent / "app" / "web" / "static"
BG = (12, 10, 18, 255)  # matches the app background (#0c0a12)


def square(im: Image.Image, size: int, pad: float = 0.0) -> Image.Image:
    """Center-crop to a square, then fit onto a `size` canvas with `pad` margin."""
    im = im.convert("RGBA")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    inner = int(size * (1 - pad * 2))
    im = im.resize((inner, inner), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), BG)
    off = (size - inner) // 2
    canvas.paste(im, (off, off), im)
    return canvas.convert("RGB")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python tools/make_icons.py <source-image>")
        raise SystemExit(2)
    src = Image.open(sys.argv[1])
    square(src, 512).save(STATIC / "icon-512.png")
    square(src, 512, pad=0.12).save(STATIC / "icon-512-maskable.png")
    square(src, 192).save(STATIC / "icon-192.png")
    print("wrote icon-192.png, icon-512.png, icon-512-maskable.png to", STATIC)


if __name__ == "__main__":
    main()
