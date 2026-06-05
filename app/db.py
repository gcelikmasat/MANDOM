"""Local SQLite store (SQLAlchemy 2.0): bookmarks + download jobs.

Single-user, single-process local app, so a plain synchronous engine is plenty;
SQLite writes are sub-millisecond. The schema mirrors PLAN.md section 9 (trimmed
to what Phase 2 needs); more tables/columns get added as later phases land.
"""

from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

_engine = None
_SessionFactory: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Bookmark(Base):
    __tablename__ = "bookmark"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(300))
    cover_url: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str | None] = mapped_column(String(40), default=None)
    # New-chapter detection: last_seen_sort is the high-water mark the user has
    # "seen"; latest_sort/total_chapters come from the most recent feed check;
    # unread = chapters newer than last_seen_sort.
    last_seen_sort: Mapped[float] = mapped_column(default=0.0)
    latest_sort: Mapped[float] = mapped_column(default=0.0)
    total_chapters: Mapped[int] = mapped_column(default=0)
    unread: Mapped[int] = mapped_column(default=0)
    last_checked: Mapped[dt.datetime | None] = mapped_column(default=None)
    created_at: Mapped[dt.datetime] = mapped_column(default=_now)


class DownloadJob(Base):
    __tablename__ = "download_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(40))
    manga_external_id: Mapped[str] = mapped_column(String(80))
    manga_title: Mapped[str] = mapped_column(String(300))
    chapter_external_id: Mapped[str] = mapped_column(String(80), index=True)
    chapter_label: Mapped[str] = mapped_column(String(40))  # e.g. "1" or "10.5"
    state: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|done|error
    progress_done: Mapped[int] = mapped_column(default=0)
    progress_total: Mapped[int] = mapped_column(default=0)
    out_path: Mapped[str | None] = mapped_column(Text, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(default=_now)


def init_db(data_dir: Path) -> None:
    """Create the engine + tables. Call once at startup."""
    global _engine, _SessionFactory
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "mandom.sqlite3"
    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    _migrate(_engine)


def _migrate(engine) -> None:
    """Add any columns missing from an older DB (SQLite has no DDL migrations).

    Keeps a user's existing bookmarks instead of forcing a DB wipe when the
    schema grows. Only handles additive column changes, which is all we need.
    """
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns("bookmark")}
    additions = {
        "latest_sort": "FLOAT NOT NULL DEFAULT 0",
        "total_chapters": "INTEGER NOT NULL DEFAULT 0",
        "unread": "INTEGER NOT NULL DEFAULT 0",
        "last_checked": "DATETIME",
    }
    with engine.begin() as conn:
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE bookmark ADD COLUMN {name} {ddl}"))


@contextmanager
def get_session() -> Iterator[Session]:
    if _SessionFactory is None:
        raise RuntimeError("init_db() must be called before using the database.")
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
