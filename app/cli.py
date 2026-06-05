"""Phase 1 thin-slice CLI.

Proves the whole pipeline end to end:

    manga search "chainsaw man"
    manga chapters <manga_id>
    manga download <manga_id> --chapter 1
    manga download <manga_id> --all

Each downloaded chapter becomes one CBZ in ``downloads/<Manga Title>/`` with a
zero-padded, templated filename so chapters sort 1..N on disk and on the device.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

from app.config import Config, load_config
from app.providers.base import ChapterInfo, MangaDetail
from app.providers.mangadex import MangaDexProvider
from app.services.downloader import download_chapter
from app.services.export import build_cbz
from app.services.naming import pad_number, render_filename, safe_filename, slugify


def _make_provider(cfg: Config) -> MangaDexProvider:
    return MangaDexProvider(
        user_agent=cfg.user_agent,
        requests_per_second=cfg.requests_per_second,
        image_quality=cfg.image_quality,
    )


async def cmd_search(cfg: Config, query: str, limit: int) -> int:
    async with _make_provider(cfg) as provider:
        results = await provider.search(query, language=cfg.language, limit=limit)
    if not results:
        print("No results.")
        return 0
    print(f"{len(results)} result(s):\n")
    for i, m in enumerate(results, 1):
        print(f"  {i:>2}. {m.title}")
        print(f"      id: {m.external_id}")
    print("\nList chapters with:  manga chapters <id>")
    return 0


async def cmd_chapters(cfg: Config, manga_id: str) -> int:
    async with _make_provider(cfg) as provider:
        detail = await provider.get_manga(manga_id)
        chapters = await provider.get_chapters(manga_id, language=cfg.language)
    print(f"{detail.title} - {len(chapters)} English chapter(s):\n")
    for ch in chapters:
        num = ch.number if ch.number is not None else "oneshot"
        title = f"  {ch.title}" if ch.title else ""
        group = f"  [{ch.group}]" if ch.group else ""
        print(f"  ch.{num:<8} ({ch.page_count}p){group}{title}")
    print("\nDownload with:  manga download <id> --chapter <num>   (or --all)")
    return 0


async def cmd_download(
    cfg: Config, manga_id: str, chapter_arg: str | None, all_chapters: bool
) -> int:
    async with _make_provider(cfg) as provider:
        detail = await provider.get_manga(manga_id)
        chapters = await provider.get_chapters(manga_id, language=cfg.language)

        targets = _select_chapters(chapters, chapter_arg, all_chapters)
        if not targets:
            print(f"No matching chapter for '{chapter_arg}'.", file=sys.stderr)
            return 1

        out_dir = cfg.export_dir / safe_filename(detail.title)
        # Dedicated image client: absolute CDN URLs, no base_url, no auth headers.
        async with httpx.AsyncClient(
            headers={"User-Agent": cfg.user_agent},
            timeout=httpx.Timeout(60.0),
            follow_redirects=True,
        ) as img_client:
            for ch in targets:
                await _download_one(cfg, provider, detail, ch, out_dir, img_client)

    print(f"\nDone. Files in: {out_dir}")
    return 0


async def _download_one(
    cfg: Config,
    provider: MangaDexProvider,
    detail: MangaDetail,
    ch: ChapterInfo,
    out_dir: Path,
    img_client: httpx.AsyncClient,
) -> None:
    num = ch.number if ch.number is not None else "oneshot"
    padded = pad_number(ch.number, cfg.number_padding)
    cache_dir = cfg.data_dir / "cache" / slugify(detail.title) / f"ch-{padded}"

    print(f"Downloading ch.{num} ...")

    def progress(done: int, total: int) -> None:
        print(f"\r  pages {done}/{total}", end="", flush=True)

    images = await download_chapter(
        provider,
        ch.external_id,
        cache_dir,
        client=img_client,
        concurrency=cfg.max_concurrency,
        progress=progress,
    )
    print()
    if not images:
        print("  (no downloadable pages — skipped)")
        return

    stem = render_filename(
        cfg.filename_template, ch, manga_title=detail.title, padding=cfg.number_padding
    )
    out_path = out_dir / f"{stem}.cbz"
    build_cbz(images, out_path)
    print(f"  -> {out_path.name}")


def _select_chapters(
    chapters: list[ChapterInfo], chapter_arg: str | None, all_chapters: bool
) -> list[ChapterInfo]:
    if all_chapters:
        return chapters
    if chapter_arg is None:
        return []
    matches = [c for c in chapters if c.number == chapter_arg]
    if not matches:
        try:
            want = float(chapter_arg)
            matches = [c for c in chapters if c.number_sort == want]
        except ValueError:
            matches = []
    return matches[:1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="manga", description="Manga downloader (Phase 1 CLI)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="search MangaDex for a title")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=15)

    p_chapters = sub.add_parser("chapters", help="list English chapters for a manga id")
    p_chapters.add_argument("manga_id")

    p_dl = sub.add_parser("download", help="download chapter(s) to CBZ")
    p_dl.add_argument("manga_id")
    g = p_dl.add_mutually_exclusive_group(required=True)
    g.add_argument("--chapter", help="chapter number, e.g. 1 or 10.5")
    g.add_argument("--all", action="store_true", help="download every English chapter")

    args = parser.parse_args(argv)
    cfg = load_config()

    if args.command == "search":
        return asyncio.run(cmd_search(cfg, args.query, args.limit))
    if args.command == "chapters":
        return asyncio.run(cmd_chapters(cfg, args.manga_id))
    if args.command == "download":
        return asyncio.run(cmd_download(cfg, args.manga_id, args.chapter, args.all))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
