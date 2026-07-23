from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
import pytest


_SUBMODULES_WITH_DB = ["stats", "activities", "charts", "kpi", "analytics", "view_as"]
_SUBMODULES_WITH_DEVICE = ["stats", "analytics", "view_as"]
_SUBMODULES_WITH_DISTRIBUTION = ["stats", "analytics"]
_SUBMODULES_WITH_DEFECT = ["stats", "analytics"]
_SUBMODULES_WITH_RETURN = ["stats", "analytics"]
_SUBMODULES_WITH_USER = ["stats", "analytics"]
_SUBMODULES_WITH_APPROVAL = ["stats", "analytics"]
_SUBMODULES_WITH_OPERATOR = ["stats"]
_SUBMODULES_WITH_LOG_API = ["activities"]


def _patch_submodules_value(modules: list, attr: str, value):
    patchers = []
    for mod in modules:
        p = patch(f"app.services.dashboard_service.{mod}.{attr}", value)
        p.start()
        patchers.append(p)
    return patchers


class MockCursor:
    """Mocks CursorWrapper with controlled fetchone / fetchall results."""

    def __init__(self, fetchone_result=None, fetchall_result=None, rowcount=0, lastrowid=None):
        self._fetchone_result = fetchone_result
        self._fetchall_result = fetchall_result or []
        self.rowcount = rowcount
        self.lastrowid = lastrowid

    async def fetchone(self):
        return self._fetchone_result

    async def fetchall(self):
        return self._fetchall_result


class MockDB:
    """Mocks MySQLDB.  Register results for specific SQL patterns."""

    def __init__(self):
        self._results: List[Dict[str, Any]] = []
        self.executed_queries: List[str] = []

    def add_result(self, fetchone_result=None, fetchall_result=None, rowcount=0, lastrowid=None):
        self._results.append({
            "fetchone": fetchone_result,
            "fetchall": fetchall_result,
            "rowcount": rowcount,
            "lastrowid": lastrowid,
        })

    async def execute(self, query: str, params=None):
        self.executed_queries.append(query)
        if self._results:
            r = self._results.pop(0)
            return MockCursor(
                fetchone_result=r["fetchone"],
                fetchall_result=r["fetchall"],
                rowcount=r["rowcount"],
                lastrowid=r["lastrowid"],
            )
        return MockCursor(fetchone_result=(0,))

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def close(self):
        pass


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def mock_get_db(mock_db):
    """Patches get_db in each dashboard_service submodule that uses it."""
    @asynccontextmanager
    async def _fake_get_db():
        yield mock_db

    patchers = _patch_submodules_value(_SUBMODULES_WITH_DB, "get_db", _fake_get_db)
    yield mock_db
    for p in patchers:
        p.stop()


@pytest.fixture
def mock_services():
    """Patches all service dependencies in the dashboard_service submodules that use them."""
    _SERVICE_SPECS = [
        ("device_service", _SUBMODULES_WITH_DEVICE),
        ("distribution_service", _SUBMODULES_WITH_DISTRIBUTION),
        ("defect_service", _SUBMODULES_WITH_DEFECT),
        ("return_service", _SUBMODULES_WITH_RETURN),
        ("user_service", _SUBMODULES_WITH_USER),
        ("approval_service", _SUBMODULES_WITH_APPROVAL),
        ("operator_service", _SUBMODULES_WITH_OPERATOR),
    ]

    all_patchers = []
    mock_map = {}

    for svc_name, submodules in _SERVICE_SPECS:
        mock_obj = MagicMock(spec=True)
        mock_map[svc_name] = mock_obj
        for mod in submodules:
            p = patch(f"app.services.dashboard_service.{mod}.{svc_name}", new=mock_obj)
            p.start()
            all_patchers.append(p)

    log_api_mock = AsyncMock()
    for mod in _SUBMODULES_WITH_LOG_API:
        p = patch(f"app.services.dashboard_service.{mod}.log_api_activity", new=log_api_mock)
        p.start()
        all_patchers.append(p)
    mock_map["log_api_activity"] = log_api_mock

    yield mock_map
    for p in all_patchers:
        p.stop()


@pytest.fixture
def super_admin_user() -> Dict[str, Any]:
    return {"_id": "1", "id": "1", "role": "super_admin", "name": "Admin", "email": "admin@test.com"}


@pytest.fixture
def manager_user() -> Dict[str, Any]:
    return {"_id": "2", "id": "2", "role": "manager", "name": "Manager", "email": "manager@test.com"}


@pytest.fixture
def pdic_staff_user() -> Dict[str, Any]:
    return {"_id": "3", "id": "3", "role": "pdic_staff", "name": "Staff", "email": "staff@test.com"}


@pytest.fixture
def sub_distributor_user() -> Dict[str, Any]:
    return {"_id": "10", "id": "10", "role": "sub_distributor", "name": "SubDist", "email": "subdist@test.com", "parent_id": "1"}


@pytest.fixture
def sub_distribution_manager_user() -> Dict[str, Any]:
    return {"_id": "20", "id": "20", "role": "sub_distribution_manager", "name": "SDM", "email": "sdm@test.com", "parent_id": "10"}


@pytest.fixture
def cluster_user() -> Dict[str, Any]:
    return {"_id": "30", "id": "30", "role": "cluster", "name": "Cluster", "email": "cluster@test.com", "parent_id": "20"}


@pytest.fixture
def operator_user() -> Dict[str, Any]:
    return {"_id": "40", "id": "40", "role": "operator", "name": "Operator", "email": "op@test.com", "parent_id": "30", "status": "active"}
