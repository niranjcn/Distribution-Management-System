"""Unit tests for the in-memory CacheVersionManager."""

import asyncio
import threading

import pytest

from app.config import settings
from app.core.cache_version_manager import CacheVersionManager, cache_version_sync_loop


def _async_cm_factory(session):
    """Build a plain callable returning an async context manager."""

    class _CM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    return lambda: _CM()


class TestCacheVersionManager:
    def test_defaults_uninitialized_zero(self):
        mgr = CacheVersionManager()
        assert mgr.initialized is False
        assert mgr.get_version() == 0

    def test_update_replaces_version(self):
        mgr = CacheVersionManager()
        mgr.update(7)
        assert mgr.get_version() == 7
        assert mgr.initialized is False

    def test_update_coerces_to_int(self):
        mgr = CacheVersionManager()
        mgr.update("9")
        assert mgr.get_version() == 9

    def test_update_is_thread_safe(self):
        mgr = CacheVersionManager()
        barrier = threading.Barrier(2)

        def writer(value):
            barrier.wait()
            for _ in range(200):
                mgr.update(value)

        threads = [threading.Thread(target=writer, args=(v,)) for v in (1, 2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert mgr.get_version() in (1, 2)

    @pytest.mark.asyncio
    async def test_load_from_db_missing_row_raises(self, monkeypatch):
        mgr = CacheVersionManager()

        async def _missing(session):
            return None

        monkeypatch.setattr(
            "app.core.cache_version_manager.get_cache_version", _missing
        )
        monkeypatch.setattr(
            "app.core.cache_version_manager.async_session_factory",
            _async_cm_factory(session=object()),
        )

        with pytest.raises(RuntimeError, match="cache_version row"):
            await mgr.load_from_db()
        assert mgr.initialized is False

    @pytest.mark.asyncio
    async def test_load_from_db_sets_initialized(self, monkeypatch):
        mgr = CacheVersionManager()

        async def _fake_get(session):
            return 42

        monkeypatch.setattr(
            "app.core.cache_version_manager.get_cache_version", _fake_get
        )
        monkeypatch.setattr(
            "app.core.cache_version_manager.async_session_factory",
            _async_cm_factory(session=object()),
        )

        await mgr.load_from_db()
        assert mgr.initialized is True
        assert mgr.get_version() == 42

    @pytest.mark.asyncio
    async def test_refresh_from_db_keeps_last_value_on_failure(self, monkeypatch):
        mgr = CacheVersionManager()
        mgr.update(5)

        async def _boom(session):
            raise RuntimeError("db down")

        monkeypatch.setattr(
            "app.core.cache_version_manager.get_cache_version", _boom
        )

        await mgr.refresh_from_db()
        assert mgr.get_version() == 5

    @pytest.mark.asyncio
    async def test_refresh_from_db_updates_value(self, monkeypatch):
        mgr = CacheVersionManager()
        mgr.update(5)

        async def _fake_get(session):
            return 9

        monkeypatch.setattr(
            "app.core.cache_version_manager.get_cache_version", _fake_get
        )
        monkeypatch.setattr(
            "app.core.cache_version_manager.async_session_factory",
            _async_cm_factory(session=object()),
        )

        await mgr.refresh_from_db()
        assert mgr.get_version() == 9


@pytest.mark.asyncio
async def test_cache_version_sync_loop_refreshes_periodically(monkeypatch):
    refreshes = []

    async def _fake_refresh():
        refreshes.append(1)
        if len(refreshes) >= 3:
            raise asyncio.CancelledError

    async def _fake_sleep(_seconds):
        return None

    monkeypatch.setattr(
        "app.core.cache_version_manager.cache_version_manager.refresh_from_db",
        _fake_refresh,
    )
    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await cache_version_sync_loop(interval_seconds=1)

    assert refreshes == [1, 1, 1]


@pytest.mark.asyncio
async def test_cache_version_sync_loop_uses_configured_interval(monkeypatch):
    sleeps = []

    async def _fake_sleep(seconds):
        sleeps.append(seconds)
        raise asyncio.CancelledError

    async def _fake_refresh():
        return None

    monkeypatch.setattr(
        "app.core.cache_version_manager.cache_version_manager.refresh_from_db",
        _fake_refresh,
    )
    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await cache_version_sync_loop()

    assert sleeps == [settings.CACHE_VERSION_REFRESH_SECONDS]
