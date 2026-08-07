from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services import defect_service


class _FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


def _defect(**overrides):
    base = {
        "id": 1,
        "report_id": "DEF-0001",
        "status": "replacement_pending_confirmation",
        "device_id": 900,
        "reported_by": 215,
        "replacement_device_id": 901,
    }
    base.update(overrides)
    return base


def _device(**overrides):
    base = {
        "id": 901,
        "status": "available",
        "current_holder_id": 5,
    }
    base.update(overrides)
    return base


class _FakeSessionFactory:
    def __init__(self, sessions):
        self._sessions = iter(sessions)

    def __call__(self):
        session = next(self._sessions)
        cm = AsyncMock()
        cm.__aenter__.return_value = session
        cm.__aexit__.return_value = None
        return cm


def _build_session(defect, old_device, new_device, employee=None, branch=None, recipients=None):
    def execute(statement, params=None):
        sql = str(statement)
        if "FROM defects WHERE id" in sql:
            return _FakeResult([defect])
        if "FROM devices WHERE id" in sql:
            return _FakeResult([new_device if int(params["id"]) == new_device["id"] else old_device])
        if "parent_id FROM users" in sql:
            return _FakeResult([employee] if employee else [])
        if "name FROM users" in sql:
            return _FakeResult([branch] if branch else [])
        if "role IN ('super_admin'" in sql:
            return _FakeResult(recipients or [])
        return _FakeResult([])

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute)
    session.commit = AsyncMock()
    session.close = AsyncMock()
    return session


async def _run_confirm(defect, old_device, new_device, confirmer, employee=None,
                       branch=None, recipients=None, update_holder=None):
    defect_session = _build_session(defect, old_device, new_device, employee, branch, recipients)
    notify_session = _build_session(defect, old_device, new_device, employee, branch, recipients)
    factory = _FakeSessionFactory([defect_session, notify_session])

    updated = update_holder if update_holder is not None else {"id": new_device["id"]}
    resolved = {"id": defect["id"], "status": "resolved"}

    with patch.object(defect_service, "async_session_factory", factory), \
         patch.object(defect_service, "bump_cache_version", AsyncMock()), \
         patch.object(defect_service.device_service, "update_device_holder",
                      AsyncMock(return_value=updated)) as holder_mock, \
         patch.object(defect_service.notification_service, "bulk_create_notifications",
                      AsyncMock()), \
         patch.object(defect_service, "get_defect_by_id", AsyncMock(return_value=resolved)):
        result = await defect_service.confirm_replacement_receipt(
            defect_id=str(defect["id"]),
            confirmer=confirmer,
            notes="Replacement received",
        )
    holder_call = holder_mock.await_args.kwargs
    return result, holder_call


def _employee_confirmer():
    return {"_id": 215, "id": 215, "name": "test", "role": "sub_distribution_employee"}


class TestConfirmReplacementReceiptEmployeeAttribution:
    async def test_employee_confirmation_attributes_device_to_branch(self):
        defect = _defect()
        old_device = _device(id=900, status="defective")
        new_device = _device(id=901, status="available")
        branch = {"id": 5, "name": "sub1"}
        employee = {"id": 215, "parent_id": 5}

        _, holder_call = await _run_confirm(
            defect, old_device, new_device,
            confirmer=_employee_confirmer(),
            employee=employee,
            branch=branch,
            recipients=[{"id": 1}],
        )

        assert holder_call["holder_id"] == 5
        assert holder_call["holder_name"] == "sub1"
        assert holder_call["holder_type"] == "sub_distributor"
        assert holder_call["status"] == "distributed"
        assert holder_call["performed_by"] == 215
        assert holder_call["performed_by_name"] == "test"

    async def test_employee_without_branch_falls_back_to_employee(self):
        defect = _defect()
        old_device = _device(id=900, status="defective")
        new_device = _device(id=901, status="available")

        _, holder_call = await _run_confirm(
            defect, old_device, new_device,
            confirmer=_employee_confirmer(),
            employee=None,
            recipients=[{"id": 1}],
        )

        assert holder_call["holder_id"] == 215
        assert holder_call["holder_name"] == "test"
        assert holder_call["holder_type"] == "sub_distribution_employee"

    async def test_non_employee_keeps_confirmer_as_holder(self):
        defect = _defect()
        old_device = _device(id=900, status="defective", current_holder_id=7)
        new_device = _device(id=901, status="available")

        _, holder_call = await _run_confirm(
            defect, old_device, new_device,
            confirmer={"_id": 7, "id": 7, "name": "Alice", "role": "operator"},
            recipients=[{"id": 1}],
        )

        assert holder_call["holder_id"] == 7
        assert holder_call["holder_name"] == "Alice"
        assert holder_call["holder_type"] == "operator"
        assert holder_call["status"] == "in_use"

    async def test_holder_transfer_failure_raises(self):
        defect = _defect()
        old_device = _device(id=900, status="defective")
        new_device = _device(id=901, status="available")
        branch = {"id": 5, "name": "sub1"}
        employee = {"id": 215, "parent_id": 5}

        with pytest.raises(ValueError, match="holder transfer failed"):
            await _run_confirm(
                defect, old_device, new_device,
                confirmer=_employee_confirmer(),
                employee=employee,
                branch=branch,
                recipients=[{"id": 1}],
                update_holder={},
            )
