"""Kobo KEPUB exporter.

Builds a fixed-layout, image-based EPUB3 sized for the target device and named
``*.kepub.epub`` so Kobo's enhanced renderer kicks in. Each page is one
pre-paginated XHTML whose viewport matches the (downscaled) image, so the device
shows one manga page at a time, edge to edge.

Embeds **series metadata** (series = manga title, index = chapter number) via
both EPUB3 ``belongs-to-collection`` and the ``calibre:series`` fields, so the
Kobo groups and orders a manga's chapters by series automatically.
"""

from __future__ import annotations

import datetime as dt
import io
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

from app.config import DeviceProfile

_CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

_STYLE_CSS = (
    "html,body{margin:0;padding:0;}"
    ".page{margin:0;padding:0;text-align:center;}"
    "img{display:block;margin:0 auto;}"
)


def _numeric_index(series_index: str | None) -> str:
    """group-position / calibre_series_index must be a number; fall back to 0."""
    if not series_index:
        return "0"
    try:
        float(series_index)
        return series_index
    except ValueError:
        return "0"


def _prepare_image(src: Path, profile: DeviceProfile, quality: int = 90) -> tuple[bytes, int, int]:
    """Downscale to fit the device (never upscale) and re-encode as JPEG."""
    with Image.open(src) as im:
        im = im.convert("RGB")
        # Only shrink; keep small pages crisp.
        im.thumbnail((profile.width, profile.height), Image.LANCZOS)
        w, h = im.size
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), w, h


def _page_xhtml(img_name: str, w: int, h: int, label: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        f"<head><meta charset=\"utf-8\"/><title>{escape(label)}</title>"
        f'<meta name="viewport" content="width={w}, height={h}"/>'
        '<link rel="stylesheet" type="text/css" href="../style.css"/></head>\n'
        f'<body><div class="page" style="width:{w}px;height:{h}px;">'
        f'<img src="../images/{img_name}" alt="" style="width:{w}px;height:{h}px;"/>'
        "</div></body>\n</html>\n"
    )


def _content_opf(
    *, book_id: str, title: str, series: str, index: str, language: str,
    direction: str, pages: list[tuple[str, str]],
) -> str:
    """pages: list of (image_filename, page_xhtml_filename)."""
    modified = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    idx = _numeric_index(index)

    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
    ]
    spine = []
    for i, (img_name, page_name) in enumerate(pages, 1):
        img_id = f"img{i:04d}"
        page_id = f"page{i:04d}"
        cover_prop = ' properties="cover-image"' if i == 1 else ""
        manifest.append(
            f'<item id="{img_id}" href="images/{img_name}" media-type="image/jpeg"{cover_prop}/>'
        )
        manifest.append(
            f'<item id="{page_id}" href="text/{page_name}" media-type="application/xhtml+xml"/>'
        )
        spine.append(f'<itemref idref="{page_id}"/>')

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" '
        'prefix="rendition: http://www.idpf.org/vocab/rendition/#">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:identifier id="bookid">urn:uuid:{book_id}</dc:identifier>\n'
        f"<dc:title>{escape(title)}</dc:title>\n"
        f"<dc:language>{escape(language)}</dc:language>\n"
        f'<meta property="dcterms:modified">{modified}</meta>\n'
        # Series (Kobo reads belongs-to-collection; calibre:* for broad compatibility).
        f'<meta property="belongs-to-collection" id="series-id">{escape(series)}</meta>\n'
        '<meta refines="#series-id" property="collection-type">series</meta>\n'
        f'<meta refines="#series-id" property="group-position">{idx}</meta>\n'
        f'<meta name="calibre:series" content="{escape(series)}"/>\n'
        f'<meta name="calibre:series_index" content="{idx}"/>\n'
        # Fixed-layout, one page at a time.
        '<meta property="rendition:layout">pre-paginated</meta>\n'
        '<meta property="rendition:orientation">portrait</meta>\n'
        '<meta property="rendition:spread">none</meta>\n'
        '<meta name="cover" content="img0001"/>\n'
        "</metadata>\n"
        "<manifest>\n" + "\n".join(manifest) + "\n</manifest>\n"
        f'<spine page-progression-direction="{direction}">\n' + "\n".join(spine) + "\n</spine>\n"
        "</package>\n"
    )


def _nav_xhtml(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        f"<head><meta charset=\"utf-8\"/><title>{escape(title)}</title></head>\n"
        '<body><nav epub:type="toc" id="toc"><ol>'
        f'<li><a href="text/p0001.xhtml">{escape(title)}</a></li>'
        "</ol></nav></body>\n</html>\n"
    )


def build_kepub(
    image_paths: list[Path],
    out_path: Path,
    *,
    title: str,
    series: str,
    series_index: str,
    profile: DeviceProfile,
    language: str = "en",
    direction: str = "rtl",
) -> Path:
    """Assemble ``image_paths`` (ordered) into a Kobo ``.kepub.epub`` at out_path."""
    if not image_paths:
        raise ValueError("Cannot build a KEPUB with no pages.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    book_id = str(uuid.uuid4())

    # Process images first so the OPF/spine match exactly what we write.
    processed: list[tuple[str, bytes, int, int]] = []  # (img_name, jpeg_bytes, w, h)
    for i, src in enumerate(image_paths, 1):
        data, w, h = _prepare_image(src, profile)
        processed.append((f"p{i:04d}.jpg", data, w, h))

    pages = [(name, f"p{i:04d}.xhtml") for i, (name, _, _, _) in enumerate(processed, 1)]
    opf = _content_opf(
        book_id=book_id, title=title, series=series, index=series_index,
        language=language, direction=direction, pages=pages,
    )

    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w") as zf:
        # mimetype MUST be first and stored uncompressed (EPUB OCF requirement).
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", _CONTAINER_XML, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/nav.xhtml", _nav_xhtml(title), compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/style.css", _STYLE_CSS, compress_type=zipfile.ZIP_DEFLATED)
        for i, (img_name, data, w, h) in enumerate(processed, 1):
            page_name = f"p{i:04d}.xhtml"
            # JPEGs are already compressed -> store; markup -> deflate.
            zf.writestr(f"OEBPS/images/{img_name}", data, compress_type=zipfile.ZIP_STORED)
            zf.writestr(
                f"OEBPS/text/{page_name}",
                _page_xhtml(img_name, w, h, f"{series} {series_index} - {i}"),
                compress_type=zipfile.ZIP_DEFLATED,
            )
    tmp.replace(out_path)
    return out_path
