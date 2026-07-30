"""Async SQLAlchemy engine and session factory, plus Alembic migration runner."""

import asyncio
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings


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

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
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
