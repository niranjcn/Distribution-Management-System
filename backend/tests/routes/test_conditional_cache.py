"""Tests for the ConditionalCacheMiddleware (ETag / 304 / Cache-Control).

The middleware reads the cache version from the in-memory CacheVersionManager,
so these tests patch `cache_version_manager.get_version` instead of the DB.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.conditional_cache import ConditionalCacheMiddleware

_VERSION_PATCH = "app.middleware.conditional_cache.cache_version_manager.get_version"


@pytest.fixture(autouse=True)
def _fixed_cache_version():
    """Serve ETags for a fixed version in every test."""
    with patch(_VERSION_PATCH, return_value=42) as get_version:
        yield get_version


def _build_app():
    calls = {"count": 0}

    app = FastAPI(title="ConditionalCacheTest")
    app.add_middleware(ConditionalCacheMiddleware)

    @app.get("/api/items")
    async def get_items():
        calls["count"] += 1
        return {"success": True, "data": [1, 2, 3]}

    @app.get("/api/items/{item_id}")
    async def get_item(item_id: int):
        calls["count"] += 1
        return {"success": True, "data": {"id": item_id}}

    @app.get("/api/missing")
    async def get_missing():
        calls["count"] += 1
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")

    @app.post("/api/items")
    async def create_item():
        return {"success": True}

    @app.get("/api/auth/me")
    async def me():
        calls["count"] += 1
        return {"success": True, "data": {"user": "me"}}

    @app.get("/api/uploads/file.png")
    async def upload():
        calls["count"] += 1
        return {"success": True}

    return app, calls


class TestConditionalCacheMiddleware:
    def test_200_sets_etag_and_cache_control(self):
        app, _ = _build_app()
        with TestClient(app) as client:
            resp = client.get("/api/items")
        assert resp.status_code == 200
        assert resp.headers["etag"] == '"v42"'
        assert resp.headers["cache-control"] == "private, no-cache"

    def test_matching_etag_returns_304_without_hitting_endpoint(self):
        app, calls = _build_app()
        with TestClient(app) as client:
            resp = client.get("/api/items", headers={"If-None-Match": '"v42"'})
        assert resp.status_code == 304
        assert resp.headers["etag"] == '"v42"'
        assert resp.headers["cache-control"] == "private, no-cache"
        assert calls["count"] == 0

    def test_matching_etag_weak_returns_304(self):
        app, calls = _build_app()
        with TestClient(app) as client:
            resp = client.get("/api/items", headers={"If-None-Match": 'W/"v42"'})
        assert resp.status_code == 304
        assert calls["count"] == 0

    def test_stale_etag_runs_endpoint(self):
        app, calls = _build_app()
        with TestClient(app) as client:
            resp = client.get("/api/items", headers={"If-None-Match": '"v41"'})
        assert resp.status_code == 200
        assert resp.headers["etag"] == '"v42"'
        assert calls["count"] == 1

    def test_head_request_cached(self):
        app, calls = _build_app()
        with TestClient(app) as client:
            resp = client.head("/api/items", headers={"If-None-Match": '"v42"'})
        assert resp.status_code == 304
        assert calls["count"] == 0

    def test_unsafe_method_not_cached(self):
        app, calls = _build_app()
        with TestClient(app) as client:
            resp = client.post("/api/items", json={"name": "x"})
        assert resp.status_code == 200
        assert "etag" not in resp.headers
        assert "cache-control" not in resp.headers

    def test_excluded_auth_me_not_cached(self):
        app, calls = _build_app()
        with TestClient(app) as client:
            resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert "etag" not in resp.headers
        assert "cache-control" not in resp.headers

    def test_excluded_uploads_not_cached(self):
        app, calls = _build_app()
        with TestClient(app) as client:
            resp = client.get("/api/uploads/file.png")
        assert resp.status_code == 200
        assert "etag" not in resp.headers
        assert "cache-control" not in resp.headers

    def test_non_2xx_not_cached(self):
        app, _ = _build_app()
        with TestClient(app) as client:
            resp = client.get("/api/missing")
        assert resp.status_code == 404
        assert "etag" not in resp.headers
        assert "cache-control" not in resp.headers

    def test_version_read_from_manager(self, _fixed_cache_version):
        """Cacheable GET reads the version from the in-memory manager."""
        app, _ = _build_app()
        with TestClient(app) as client:
            resp = client.get("/api/items", headers={"If-None-Match": '"v42"'})
        assert resp.status_code == 304
        _fixed_cache_version.assert_called()
