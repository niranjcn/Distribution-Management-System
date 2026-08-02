"""Integration tests: CacheAwareAsyncSession keeps the manager in sync.

Uses an in-memory aiosqlite engine so no MySQL is required.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database_sqlalchemy import CacheAwareAsyncSession


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE cache_version (id INT PRIMARY KEY, version BIGINT NOT NULL)"))
        await conn.execute(text("INSERT INTO cache_version (id, version) VALUES (1, 1)"))
        await conn.execute(text("CREATE TABLE app_data (id INT PRIMARY KEY, value TEXT NOT NULL)"))
    yield engine
    await engine.dispose()


@pytest.fixture
def factory(engine):
    return async_sessionmaker(engine, class_=CacheAwareAsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_commit_without_bump_does_not_refresh_manager(factory):
    from app.core.cache_version import bump_cache_version

    with patch(
        "app.core.cache_version_manager.cache_version_manager.refresh_from_db",
        new=AsyncMock(),
    ) as refresh:
        async with factory() as session:
            await session.execute(
                text("INSERT INTO app_data (id, value) VALUES (1, 'x')")
            )
            await session.commit()
        refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_bump_commit_refreshes_manager_with_new_version(factory):
    from app.core.cache_version import bump_cache_version

    with patch(
        "app.core.cache_version_manager.cache_version_manager.refresh_from_db",
        new=AsyncMock(),
    ) as refresh:
        async with factory() as session:
            await session.execute(
                text("INSERT INTO app_data (id, value) VALUES (1, 'x')")
            )
            await bump_cache_version(session)
            await session.commit()
        refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_rolled_back_bump_does_not_refresh_manager(factory):
    from app.core.cache_version import bump_cache_version

    with patch(
        "app.core.cache_version_manager.cache_version_manager.refresh_from_db",
        new=AsyncMock(),
    ) as refresh:
        async with factory() as session:
            await session.execute(
                text("INSERT INTO app_data (id, value) VALUES (1, 'x')")
            )
            await bump_cache_version(session)
            await session.rollback()
        refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_commit_syncs_actual_db_value(factory):
    """After a bump+commit, the DB holds the new value and manager mirrors it."""
    from app.core.cache_version import bump_cache_version, get_cache_version
    from app.core.cache_version_manager import cache_version_manager

    # Simulate the real refresh_from_db (which reads MySQL) against the
    # in-memory aiosqlite DB so no real MySQL connection is needed.
    async def _fake_refresh():
        async with factory() as session:
            version = await get_cache_version(session)
        cache_version_manager.update(version)

    async with factory() as session:
        original = await get_cache_version(session)
    assert original is not None

    with patch(
        "app.core.cache_version_manager.cache_version_manager.refresh_from_db",
        new=_fake_refresh,
    ):
        async with factory() as session:
            await session.execute(
                text("INSERT INTO app_data (id, value) VALUES (1, 'x')")
            )
            await bump_cache_version(session)
            await session.commit()

    async with factory() as session:
        db_version = await get_cache_version(session)

    assert db_version == original + 1
    assert cache_version_manager.get_version() == db_version
