from unittest.mock import patch

import pytest

from app.services import report_service
from app.services.report_service import get_returns_defects_backup_export


def _base_datasets(returns_rows, defects_rows, devices_rows, users_rows):
    return [returns_rows, defects_rows, devices_rows, users_rows]


class _FakeRows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, datasets):
        self._datasets = iter(datasets)
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params))
        return _FakeRows(next(self._datasets))


@pytest.fixture
def small_datasets():
    return _base_datasets(
        returns_rows=[
            {
                "return_id": "R1",
                "device_id": "D1",
                "defect_id": "1",
                "created_at": "2026-01-01 00:00:00",
                "device_type": "ONT",
                "reason": "broken",
                "status": "pending",
            }
        ],
        defects_rows=[
            {
                "id": 1,
                "report_id": "DEF-1",
                "device_id": "D1",
                "created_at": "2026-01-01 00:00:00",
                "defect_type": "hardware",
                "status": "open",
                "severity": "high",
            }
        ],
        devices_rows=[
            {"id": 1, "device_id": "D1", "model": "M1", "serial_number": "SN", "mac_address": "MAC", "nuid": "NUID", "device_type": "ONT"}
        ],
        users_rows=[{"id": 1, "name": "Alice"}],
    )


@pytest.mark.asyncio
async def test_export_bounds_queries_with_limit(small_datasets):
    session = _FakeSession(small_datasets)
    with patch.object(report_service, "async_session_factory", return_value=session):
        data = await get_returns_defects_backup_export(file_format="xlsx")

    assert len(session.executed) == 4
    for stmt, params in session.executed:
        assert "LIMIT :max_export" in stmt
        assert params["max_export"] == report_service.BACKUP_EXPORT_LIMIT
    assert data["content"]
    assert data["filename"].endswith(".xlsx")
    assert data["media_type"].startswith("application/vnd")
    assert data["truncated"] is False


@pytest.mark.asyncio
async def test_export_marks_truncated_when_hit_limit(small_datasets):
    returns_rows = [
        {
            "return_id": f"R{i}",
            "device_id": "D1",
            "defect_id": "1",
            "created_at": "2026-01-01 00:00:00",
            "device_type": "ONT",
            "reason": "broken",
            "status": "pending",
        }
        for i in range(3)
    ]
    datasets = _base_datasets(
        returns_rows=returns_rows,
        defects_rows=[],
        devices_rows=[{"id": 1, "device_id": "D1", "model": "M1", "device_type": "ONT"}],
        users_rows=[],
    )
    session = _FakeSession(datasets)
    with patch.object(report_service, "async_session_factory", return_value=session), patch.object(
        report_service, "BACKUP_EXPORT_LIMIT", 3
    ):
        data = await get_returns_defects_backup_export(file_format="xlsx")

    assert data["truncated"] is True
