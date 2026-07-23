from unittest.mock import AsyncMock, patch, PropertyMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.core.rate_limiter import limiter


# Mutable container so per-test overrides work cleanly.
CURRENT_TEST_USER: dict | None = {
    "_id": "1",
    "id": "1",
    "role": "super_admin",
    "name": "Admin",
    "email": "admin@test.com",
    "status": "active",
}


_GET_CURRENT_USER_OVERRIDE_CLEANUP = None


@pytest.fixture
def test_app():
    app = FastAPI(lifespan=None, title="DMS Test App")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    with patch.object(limiter, "limit", return_value=lambda f: f):
        from app.routes.auth import router as auth_router
    from app.routes.dashboard import router as dashboard_router
    from app.routes.reports import router as reports_router

    app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(reports_router, prefix="/api/reports", tags=["Reports"])

    from app.middleware.auth_middleware import get_current_user

    app.dependency_overrides[get_current_user] = lambda: CURRENT_TEST_USER

    return app


@pytest.fixture
def client(test_app):
    with TestClient(test_app) as c:
        yield c


@pytest.fixture(autouse=True)
def _route_test_cleanup(test_app):
    from app.middleware.auth_middleware import get_current_user

    yield

    CURRENT_TEST_USER.clear()
    CURRENT_TEST_USER.update({
        "_id": "1",
        "id": "1",
        "role": "super_admin",
        "name": "Admin",
        "email": "admin@test.com",
        "status": "active",
    })
    test_app.dependency_overrides[get_current_user] = lambda: CURRENT_TEST_USER


@pytest.fixture
def set_role():
    def _set_role(role: str, status: str = "active"):
        CURRENT_TEST_USER["role"] = role
        CURRENT_TEST_USER["status"] = status
    return _set_role


@pytest.fixture
def mock_auth_services():
    patchers = [
        patch("app.routes.auth.auth_service", spec=True),
        patch("app.routes.auth.log_api_activity", new=AsyncMock()),
        patch("app.routes.auth.audit_logger"),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_dashboard_services():
    patchers = [
        patch("app.routes.dashboard.dashboard_service", spec=True),
        patch("app.routes.dashboard.log_business_activity", new=AsyncMock()),
        patch("app.routes.dashboard.user_service", spec=True),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_report_services():
    patchers = [
        patch("app.routes.reports.report_service", spec=True),
        patch("app.routes.reports.dashboard_service", spec=True),
        patch("app.routes.reports.log_business_activity", new=AsyncMock()),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()
