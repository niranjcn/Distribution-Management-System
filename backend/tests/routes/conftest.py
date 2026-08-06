from unittest.mock import AsyncMock, patch, PropertyMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.core.rate_limiter import limiter


CURRENT_TEST_USER: dict | None = {
    "_id": "1",
    "id": "1",
    "role": "super_admin",
    "name": "Admin",
    "email": "admin@test.com",
    "status": "active",
}


@ pytest.fixture
def test_app():
    app = FastAPI(lifespan=None, title="DMS Test App")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    with patch.object(limiter, "limit", return_value=lambda f: f):
        from app.routes.auth import router as auth_router
        from app.routes.users import router as users_router
        from app.routes.devices import router as devices_router
        from app.routes.distributions import router as distributions_router
        from app.routes.change_requests import router as change_requests_router
        from app.routes.dashboard import router as dashboard_router
        from app.routes.defects import router as defects_router
        from app.routes.external_inventory import router as external_inventory_router
        from app.routes.notifications import router as notifications_router
        from app.routes.operators import router as operators_router
        from app.routes.reassignment_requests import router as reassignment_requests_router
        from app.routes.reports import router as reports_router
        from app.routes.returns import router as returns_router
        from app.routes.approval_requests import router as approval_requests_router

    app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(users_router, prefix="/api/users", tags=["Users"])
    app.include_router(devices_router, prefix="/api/devices", tags=["Devices"])
    app.include_router(distributions_router, prefix="/api/distributions", tags=["Distributions"])
    app.include_router(change_requests_router, prefix="/api/change-requests", tags=["Change Requests"])
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(defects_router, prefix="/api/defects", tags=["Defects"])
    app.include_router(external_inventory_router, prefix="/api/external-inventory", tags=["External Inventory"])
    app.include_router(notifications_router, prefix="/api/notifications", tags=["Notifications"])
    app.include_router(operators_router, prefix="/api/operators", tags=["Operators"])
    app.include_router(reassignment_requests_router, prefix="/api/reassignment-requests", tags=["Reassignment Requests"])
    app.include_router(reports_router, prefix="/api/reports", tags=["Reports"])
    app.include_router(returns_router, prefix="/api/returns", tags=["Returns"])
    app.include_router(approval_requests_router, prefix="/api/approval-requests", tags=["Approval Requests"])

    from app.middleware.auth_middleware import get_current_user

    app.dependency_overrides[get_current_user] = lambda: CURRENT_TEST_USER

    return app


@ pytest.fixture
def client(test_app):
    with TestClient(test_app) as c:
        yield c


@ pytest.fixture(autouse=True)
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


@ pytest.fixture
def set_role():
    def _set_role(role: str, status: str = "active"):
        CURRENT_TEST_USER["role"] = role
        CURRENT_TEST_USER["status"] = status
    return _set_role


# --- Auth mocks ---
@ pytest.fixture
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


# --- Dashboard mocks ---
@ pytest.fixture
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


# --- Report mocks ---
@ pytest.fixture
def mock_report_services():
    patchers = [
        patch("app.routes.reports.report_service", spec=True),
        patch("app.routes.reports.dashboard_service", spec=True),
        patch("app.routes.reports.log_business_activity", new=AsyncMock()),
        patch("app.routes.reports.list_vault_documents", new=AsyncMock()),
        patch("app.routes.reports.upload_vault_document", new=AsyncMock()),
        patch("app.routes.reports.download_vault_document", new=AsyncMock()),
        patch("app.routes.reports.get_db_backup_schedule", new=AsyncMock()),
        patch("app.routes.reports.update_db_backup_schedule", new=AsyncMock()),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


# --- Generic mocks for routes that call services directly ---
@pytest.fixture
def mock_user_services():
    patchers = [
        patch("app.routes.users.user_service", spec=True),
        patch("app.routes.users.notification_service", spec=True),
        patch("app.routes.users.reassignment_request_service", spec=True),
        patch("app.routes.users.bulk_upload_service", spec=True),
        patch("app.routes.users.log_business_activity", new=AsyncMock()),
        patch("app.routes.users.audit_logger"),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_device_services():
    patchers = [
        patch("app.routes.devices.device_service", spec=True),
        patch("app.routes.devices.notification_service", spec=True),
        patch("app.routes.devices.defect_service", spec=True),
        patch("app.routes.devices.log_business_activity", new=AsyncMock()),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_distribution_services():
    patchers = [
        patch("app.routes.distributions.distribution_service", spec=True),
        patch("app.routes.distributions.log_business_activity", new=AsyncMock()),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_defect_services():
    patchers = [
        patch("app.routes.defects.defect_service", spec=True),
        patch("app.routes.defects.log_business_activity", new=AsyncMock()),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_notification_services():
    patchers = [
        patch("app.routes.notifications.notification_service", spec=True),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_operator_services():
    patchers = [
        patch("app.routes.operators.operator_service", spec=True),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_reassignment_services():
    patchers = [
        patch("app.routes.reassignment_requests.reassignment_request_service", spec=True),
        patch("app.routes.reassignment_requests.log_business_activity", new=AsyncMock()),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_inventory_services():
    patchers = [
        patch("app.routes.external_inventory.inventory_service", spec=True),
        patch("app.routes.external_inventory.log_business_activity", new=AsyncMock()),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_return_services():
    patchers = [
        patch("app.routes.returns.return_service", spec=True),
        patch("app.routes.returns.log_business_activity", new=AsyncMock()),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_change_request_services():
    patchers = [
        patch("app.routes.change_requests.device_service", spec=True),
        patch("app.routes.change_requests.notification_service", spec=True),
        patch("app.routes.change_requests.defect_service", spec=True),
        patch("app.routes.change_requests.audit_logger"),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()
