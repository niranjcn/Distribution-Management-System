from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
import pytest


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
    """Patches get_db inside dashboard_service (where the local import lives)."""
    @asynccontextmanager
    async def _fake_get_db():
        yield mock_db

    patcher = patch("app.services.dashboard_service.get_db", _fake_get_db)
    patcher.start()
    yield mock_db
    patcher.stop()


@pytest.fixture
def mock_services():
    """Patches all service dependencies used by dashboard_service."""
    patchers = [
        patch("app.services.dashboard_service.device_service", spec=True),
        patch("app.services.dashboard_service.distribution_service", spec=True),
        patch("app.services.dashboard_service.defect_service", spec=True),
        patch("app.services.dashboard_service.return_service", spec=True),
        patch("app.services.dashboard_service.user_service", spec=True),
        patch("app.services.dashboard_service.approval_service", spec=True),
        patch("app.services.dashboard_service.operator_service", spec=True),
        patch("app.services.dashboard_service.log_api_activity", new=AsyncMock()),
    ]
    mocks = [p.start() for p in patchers]
    yield {m._extract_mock_name() if hasattr(m, '_extract_mock_name') else str(i): m
           for i, m in enumerate(mocks)}
    for p in patchers:
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
