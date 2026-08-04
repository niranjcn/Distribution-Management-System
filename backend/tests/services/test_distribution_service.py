from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services import distribution_service


class _FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


def _device(**overrides):
    base = {
        "id": 1,
        "device_id": "DEV-0001",
        "mac_address": "AA:BB:CC:DD:EE:01",
        "serial_number": "SN-0001",
        "nuid": "NUID-0001",
        "status": "available",
        "current_holder_id": 100,
    }
    base.update(overrides)
    return base


def _build_session(devices, open_lock_ids=None, pending_blocked_ids=None):
    open_lock_ids = {str(i) for i in (open_lock_ids or [])}
    pending_blocked_ids = {str(i) for i in (pending_blocked_ids or [])}

    def execute(statement, params=None):
        sql = str(statement)
        if ":mac_" in sql:
            return _FakeResult([d for d in devices if d.get("mac_address")])
        if ":ser_" in sql:
            return _FakeResult([d for d in devices if d.get("serial_number")])
        if ":nuid_" in sql:
            return _FakeResult([d for d in devices if d.get("nuid")])
        if "current_distribution_id" in sql and "status IN" in sql:
            return _FakeResult([
                {"device_id": str(d["id"])} for d in devices if str(d["id"]) in open_lock_ids
            ])
        if "to_user_id" in sql:
            return _FakeResult([
                {"device_id": str(d["id"])} for d in devices if str(d["id"]) in pending_blocked_ids
            ])
        return _FakeResult([])

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute)
    session.close = AsyncMock()
    return session


async def _run(identifier_rows, from_user, devices, open_lock_ids=None,
               pending_blocked_ids=None, expected_distribution=None):
    """Run create_distribution_from_identifiers against a mocked session.

    Returns (result, create_distribution_mock).
    """
    session = _build_session(
        devices, open_lock_ids=open_lock_ids, pending_blocked_ids=pending_blocked_ids
    )

    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = None
    session_factory = MagicMock(return_value=cm)

    create_distribution_mock = AsyncMock(return_value=expected_distribution)

    with patch.object(distribution_service, "async_session_factory", session_factory), \
         patch.object(distribution_service, "create_distribution", create_distribution_mock):
        result = await distribution_service.create_distribution_from_identifiers(
            to_user_id="200",
            identifier_rows=identifier_rows,
            from_user=from_user,
        )

    return result, create_distribution_mock


class TestManagementUploaderAvailabilityErrors:
    async def test_unavailable_devices_become_row_errors(self):
        available = _device(id=1, device_id="DEV-OK", mac_address="AA:AA:AA:AA:00:01")
        locked = _device(id=2, device_id="DEV-LOCKED", mac_address="AA:AA:AA:AA:00:02")
        taken = _device(id=3, device_id="DEV-TAKEN", mac_address="AA:AA:AA:AA:00:03",
                        status="distributed")

        rows = [
            {"row": 2, "mac_address": "AA:AA:AA:AA:00:01", "serial_number": "", "nuid": ""},
            {"row": 3, "mac_address": "AA:AA:AA:AA:00:02", "serial_number": "", "nuid": ""},
            {"row": 4, "mac_address": "AA:AA:AA:AA:00:03", "serial_number": "", "nuid": ""},
        ]
        manager = {"id": 100, "role": "manager"}
        fake_dist = {"distribution_id": "DIST-2026-0001", "to_user_name": "Operator A"}

        result, create_mock = await _run(
            rows, manager, [available, locked, taken],
            open_lock_ids=[2], expected_distribution=fake_dist,
        )

        assert result["created"] is True
        assert result["created_count"] == 1
        assert result["error_count"] == 2

        error_msgs = [e["error"] for e in result["errors"]]
        assert any("already in an unconfirmed or disputed" in m for m in error_msgs)
        assert any("Device DEV-TAKEN is not available" in m for m in error_msgs)

        create_mock.assert_awaited_once()
        device_ids = create_mock.await_args.kwargs["dist_data"].device_ids
        assert device_ids == [str(available["id"])]

    async def test_defective_device_becomes_row_error(self):
        defective = _device(id=7, device_id="DEV-BROKEN", serial_number="SN-BROKEN",
                            status="defective")
        rows = [{"row": 2, "serial_number": "SN-BROKEN"}]
        result, create_mock = await _run(rows, {"id": 100, "role": "manager"}, [defective])

        assert result["created"] is False
        assert result["distribution"] is None
        assert result["error_count"] == 1
        assert "marked defective" in result["errors"][0]["error"]
        create_mock.assert_not_awaited()

    async def test_all_rows_invalid_no_distribution_created(self):
        taken = _device(id=3, device_id="DEV-TAKEN", serial_number="SN-TAKEN",
                        status="distributed")
        rows = [{"row": 2, "serial_number": "SN-TAKEN"}]
        result, create_mock = await _run(rows, {"id": 100, "role": "manager"}, [taken])

        assert result["created"] is False
        assert result["distribution"] is None
        assert result["error_count"] == 1
        create_mock.assert_not_awaited()

    async def test_valid_rows_still_create_distribution_with_unavailable_excluded(self):
        available = _device(id=1, device_id="DEV-OK", serial_number="SN-OK")
        taken = _device(id=3, device_id="DEV-TAKEN", serial_number="SN-TAKEN",
                        status="distributed")
        rows = [
            {"row": 2, "serial_number": "SN-OK"},
            {"row": 3, "serial_number": "SN-TAKEN"},
        ]
        fake_dist = {"distribution_id": "DIST-2026-0002", "to_user_name": "Operator A"}

        result, create_mock = await _run(
            rows, {"id": 100, "role": "manager"}, [available, taken],
            expected_distribution=fake_dist,
        )

        assert result["created"] is True
        assert result["created_count"] == 1
        assert result["error_count"] == 1
        create_mock.assert_awaited_once()
        device_ids = create_mock.await_args.kwargs["dist_data"].device_ids
        assert device_ids == [str(available["id"])]


class TestOperatorUploaderPossessionAndReceipt:
    async def test_not_in_possession_and_awaiting_receipt_become_row_errors(self):
        other_holder = _device(id=5, device_id="DEV-OTHER", serial_number="SN-OTHER",
                               current_holder_id=999)
        awaiting = _device(id=6, device_id="DEV-AWAIT", serial_number="SN-AWAIT",
                           current_holder_id=100)
        rows = [
            {"row": 2, "serial_number": "SN-OTHER"},
            {"row": 3, "serial_number": "SN-AWAIT"},
        ]
        operator = {"id": 100, "role": "operator"}

        result, create_mock = await _run(
            rows, operator, [other_holder, awaiting], pending_blocked_ids=[6]
        )

        assert result["created"] is False
        assert result["error_count"] == 2

        error_msgs = [e["error"] for e in result["errors"]]
        assert any("not in your possession" in m for m in error_msgs)
        assert any("awaiting your receipt confirmation" in m for m in error_msgs)
        create_mock.assert_not_awaited()


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


def _build_list_session(dist_rows, total):
    def execute(statement, params=None):
        sql = str(statement)
        if "COUNT" in sql:
            return _ScalarResult(total)
        if "ORDER BY created_at" in sql:
            return _FakeResult([dict(r) for r in dist_rows])
        return _FakeResult([])

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute)
    session.close = AsyncMock()
    return session


async def _run_list(dist_rows, total, include_device_ids=False, load_result=None):
    session = _build_list_session(dist_rows, total)

    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = None
    session_factory = MagicMock(return_value=cm)

    load_mock = AsyncMock(return_value=load_result or {})
    with patch.object(distribution_service, "async_session_factory", session_factory), \
         patch.object(distribution_service, "_load_distribution_device_ids", load_mock):
        result = await distribution_service.get_distributions(
            current_user={"id": 1, "role": "manager"},
            include_device_ids=include_device_ids,
        )

    return result, load_mock


class TestGetDistributionsLightweight:
    def _rows(self):
        return [
            {"id": 1, "distribution_id": "DIST-2026-0001", "device_count": 3,
             "to_user_name": "Operator A"},
            {"id": 2, "distribution_id": "DIST-2026-0002", "device_count": 1,
             "to_user_name": "Operator B"},
        ]

    async def test_default_list_skips_device_ids_loading(self):
        result, load_mock = await _run_list(self._rows(), 5)

        assert result["data"][0]["device_count"] == 3
        assert all(row["device_ids"] == [] for row in result["data"])
        load_mock.assert_not_awaited()

    async def test_include_device_ids_triggers_loading(self):
        load_result = {"DIST-2026-0001": ["10", "11"], "DIST-2026-0002": ["12"]}
        result, load_mock = await _run_list(self._rows(), 5, include_device_ids=True,
                                            load_result=load_result)

        load_mock.assert_awaited_once()
        assert result["data"][0]["device_ids"] == ["10", "11"]
        assert result["data"][1]["device_ids"] == ["12"]

    async def test_pagination_shape_preserved(self):
        result, _ = await _run_list(self._rows(), 5)

        assert result["pagination"]["total"] == 5