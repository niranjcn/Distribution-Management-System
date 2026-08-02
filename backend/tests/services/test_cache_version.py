"""Unit tests for app.core.cache_version helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.cache_version import (
    CACHE_VERSION_BUMP_FLAG,
    CACHE_VERSION_ID,
    build_etag,
    bump_cache_version,
    ensure_cache_version_row,
    etag_matches,
    get_cache_version,
)


class TestBuildEtag:
    def test_format(self):
        assert build_etag(42) == '"v42"'

    def test_zero(self):
        assert build_etag(0) == '"v0"'


class TestEtagMatches:
    def test_single_match(self):
        assert etag_matches('"v42"', '"v42"') is True

    def test_no_header(self):
        assert etag_matches(None, '"v42"') is False

    def test_empty_header(self):
        assert etag_matches("", '"v42"') is False

    def test_list_match(self):
        assert etag_matches('"v41", "v42"', '"v42"') is True

    def test_list_no_match(self):
        assert etag_matches('"v40", "v41"', '"v42"') is False

    def test_star(self):
        assert etag_matches("*", '"v42"') is True

    def test_weak_match(self):
        assert etag_matches('W/"v42"', '"v42"') is True

    def test_whitespace(self):
        assert etag_matches(' "v42" ', '"v42"') is True


class TestGetCacheVersion:
    @pytest.mark.asyncio
    async def test_returns_version(self):
        session = AsyncMock()
        result = MagicMock()
        row = MagicMock()
        row.__getitem__ = lambda self, key: 42
        result.first.return_value = row
        session.execute.return_value = result

        assert await get_cache_version(session) == 42
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_row_returns_none(self):
        session = AsyncMock()
        result = MagicMock()
        result.first.return_value = None
        session.execute.return_value = result

        assert await get_cache_version(session) is None


class TestBumpCacheVersion:
    @pytest.mark.asyncio
    async def test_executes_bump_sql_and_flags_session(self):
        session = AsyncMock()
        session.info = {}

        await bump_cache_version(session)

        session.execute.assert_awaited_once()
        params = session.execute.await_args.args[1]
        assert params == {"cid": CACHE_VERSION_ID}
        assert session.info.get(CACHE_VERSION_BUMP_FLAG) is True


class TestEnsureCacheVersionRow:
    @pytest.mark.asyncio
    async def test_executes_insert_ignore(self):
        session = AsyncMock()
        session.info = {}

        await ensure_cache_version_row(session)

        session.execute.assert_awaited_once()
        params = session.execute.await_args.args[1]
        assert params == {"cid": CACHE_VERSION_ID}
        assert session.info.get(CACHE_VERSION_BUMP_FLAG) is None

