"""In-process download queue.

A single asyncio worker drains a queue of DownloadJob ids, downloading each
chapter's pages and bundling them into a CBZ (KEPUB export arrives in Phase 5).
Job state + per-page progress are persisted to SQLite so the UI can poll them.
"""

from __future__ import annotations

import asyncio

import httpx

from app.config import Config
from app.db import DownloadJob, get_session
from app.providers.mangadex import MangaDexProvider
from app.services.downloader import download_chapter
from app.services.export import build_exports
from app.services.naming import pad_number, render_filename, safe_filename, slugify


class DownloadManager:
    def __init__(self, cfg: Config, provider: MangaDexProvider, img_client: httpx.AsyncClient):
        self._cfg = cfg
        self._provider = provider
        self._img = img_client
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._worker: asyncio.Task | None = None

    def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run(), name="mandom-download-worker")

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._worker = None

    def enqueue(self, job_id: int) -> None:
        self._queue.put_nowait(job_id)

    async def _run(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                await self._process(job_id)
            except Exception as exc:  # keep the worker alive across job failures
                _update(job_id, state="error", error=str(exc))
            finally:
                self._queue.task_done()

    async def _process(self, job_id: int) -> None:
        with get_session() as s:
            job = s.get(DownloadJob, job_id)
            if job is None:
                return
            data = {
                "manga_title": job.manga_title,
                "chapter_external_id": job.chapter_external_id,
                "chapter_label": job.chapter_label,
            }
        _update(job_id, state="running", error=None)

        cache_dir = (
            self._cfg.data_dir
            / "cache"
            / slugify(data["manga_title"])
            / f"ch-{pad_number(data['chapter_label'], self._cfg.number_padding)}"
        )

        def progress(done: int, total: int) -> None:
            _update(job_id, progress_done=done, progress_total=total)

        images = await download_chapter(
            self._provider,
            data["chapter_external_id"],
            cache_dir,
            client=self._img,
            concurrency=self._cfg.max_concurrency,
            progress=progress,
        )
        if not images:
            _update(job_id, state="error", error="No downloadable pages.")
            return

        # Build the chapter filename via the configured template (zero-padded sort).
        from app.providers.base import ChapterInfo

        ch = ChapterInfo(
            provider_id=self._provider.id,
            external_id=data["chapter_external_id"],
            number=data["chapter_label"],
            number_sort=0.0,
        )
        stem = render_filename(
            self._cfg.filename_template, ch,
            manga_title=data["manga_title"], padding=self._cfg.number_padding,
        )
        out_dir = self._cfg.export_dir / safe_filename(data["manga_title"])
        # CPU-bound (Pillow) -> run off the event loop.
        primary = await asyncio.to_thread(
            build_exports,
            images, out_dir, stem,
            export_format=self._cfg.export_format,
            manga_title=data["manga_title"],
            chapter_label=data["chapter_label"],
            profile=self._cfg.profile(),
            language=self._cfg.language,
            direction=self._cfg.reading_direction,
        )
        _update(job_id, state="done", out_path=str(primary) if primary else None)


def _update(job_id: int, **fields) -> None:
    """Persist a partial update to a job row."""
    with get_session() as s:
        job = s.get(DownloadJob, job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)
