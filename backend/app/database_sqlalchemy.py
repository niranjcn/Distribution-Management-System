"""Async SQLAlchemy engine and session factory, plus Alembic migration runner."""

import asyncio
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.core.cache_version import CACHE_VERSION_BUMP_FLAG


ASYNC_DB_URL = (
    f"mysql+aiomysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

engine = create_async_engine(
    ASYNC_DB_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=21600,
    echo=False,
)


class CacheAwareAsyncSession(AsyncSession):
    """AsyncSession that keeps the in-memory CacheVersionManager in sync.

    When a transaction that bumped cache_version (flagged by
    `bump_cache_version`) commits successfully, re-read the newly committed
    version from MySQL and update the in-memory manager. Reading the committed
    value back (rather than doing `version += 1`) guarantees the in-memory
    value can never drift from the database, even with interleaved writers.
    """

    async def commit(self) -> None:
        await super().commit()
        if self.info.get(CACHE_VERSION_BUMP_FLAG):
            self.info[CACHE_VERSION_BUMP_FLAG] = False
            # Lazy import breaks the module cycle: cache_version_manager
            # imports async_session_factory from this module.
            from app.core.cache_version_manager import cache_version_manager
            await cache_version_manager.refresh_from_db()


async_session_factory = async_sessionmaker(
    engine, class_=CacheAwareAsyncSession, expire_on_commit=False
)


async def get_async_session():
    """Yield an async SQLAlchemy session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def run_alembic_migrations():
    """Run pending Alembic migrations synchronously in a thread pool."""
    from alembic.config import Config
    from alembic import command

    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.attributes['configure_logger'] = False

    def _upgrade():
        command.upgrade(alembic_cfg, "head")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _upgrade)
