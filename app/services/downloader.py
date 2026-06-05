"""Chapter page downloader.

Downloads a chapter's page images to disk with bounded concurrency, retries,
and — crucially — re-resolution of the page batch when MangaDex@Home URLs
expire mid-download (HTTP 403), as the API docs warn they can after ~15 min.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from app.providers.base import Provider

_IMG_RETRYABLE = {429, 500, 502, 503, 504}


async def download_chapter(
    provider: Provider,
    chapter_id: str,
    dest_dir: Path,
    *,
    client: httpx.AsyncClient,
    concurrency: int = 4,
    progress: "callable | None" = None,
) -> list[Path]:
    """Download all pages of ``chapter_id`` into ``dest_dir``.

    Returns the saved image paths in reading order. Pages already present on
    disk (same size > 0) are skipped, so re-runs are cheap and resumable.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    batch = await provider.get_pages(chapter_id)
    total = len(batch.urls)
    if total == 0:
        return []

    width = len(str(total))
    paths: list[Path | None] = [None] * total
    sem = asyncio.Semaphore(concurrency)
    done = 0
    lock = asyncio.Lock()

    async def fetch(index: int) -> None:
        nonlocal done, batch
        url = batch.urls[index]
        ext = url.rsplit(".", 1)[-1].split("?")[0].lower() or "jpg"
        out = dest_dir / f"{index + 1:0{width}d}.{ext}"
        if out.exists() and out.stat().st_size > 0:
            paths[index] = out
        else:
            async with sem:
                data = await _fetch_image(
                    provider, batch, index, client=client
                )
            out.write_bytes(data)
            paths[index] = out
        async with lock:
            done += 1
            if progress:
                progress(done, total)

    await asyncio.gather(*(fetch(i) for i in range(total)))
    return [p for p in paths if p is not None]


async def _fetch_image(
    provider: Provider,
    batch,
    index: int,
    *,
    client: httpx.AsyncClient,
    retries: int = 4,
) -> bytes:
    """Fetch one page; on 403 re-resolve the batch once and retry the fresh URL."""
    attempt = 0
    reresolved = False
    while True:
        url = batch.urls[index]
        try:
            # NOTE: never send auth headers to MangaDex@Home image servers.
            resp = await client.get(url, headers=batch.headers or None)
        except httpx.TransportError:
            if attempt >= retries:
                raise
            await asyncio.sleep(2**attempt)
            attempt += 1
            continue

        if resp.status_code == 403 and not reresolved:
            fresh = await provider.get_pages(batch.chapter_external_id)
            batch.urls = fresh.urls  # mutate in place so all workers see fresh URLs
            batch.headers = fresh.headers
            reresolved = True
            continue
        if resp.status_code in _IMG_RETRYABLE and attempt < retries:
            await asyncio.sleep(float(resp.headers.get("Retry-After", 2**attempt)))
            attempt += 1
            continue
        resp.raise_for_status()
        return resp.content
