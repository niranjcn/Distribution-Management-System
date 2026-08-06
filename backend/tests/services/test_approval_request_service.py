"""Service tests for the sub_distribution_employee approval-request workflow.

These tests exercise the employee role's core behavior without a live MySQL
database: only employees may submit/cancel/list their own requests, approvers
are scoped to the employee's sub distribution, and a request only executes
after all required roles have approved (with revalidation at approval time).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import approval_request_service as svc
from app.utils.roles import (
    SUB_DISTRIBUTOR,
    SUB_DISTRIBUTION_MANAGER,
    SUB_DISTRIBUTION_EMPLOYEE,
)


class _FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows=None, rowcount=1):
        self._rows = rows if rows is not None else []
        self._rowcount = rowcount

    def mappings(self):
        return _FakeMappings(self._rows)

    def scalar(self):
        return self._rows[0] if self._rows else None

    @property
    def rowcount(self):
        return self._rowcount


_SENTINEL = object()


def _make_session(recipient=_SENTINEL, approvers=_SENTINEL, duplicates=_SENTINEL,
                  request_row=_SENTINEL, descendants=True, cancel_rowcount=1,
                  update_rowcount=1, status_row=_SENTINEL):
    """Return a MagicMock session whose execute() routes by SQL fragment."""
    if recipient is _SENTINEL:
        recipient = {"id": "30", "role": "cluster", "status": "active"}
    if approvers is _SENTINEL:
        approvers = [
            {"id": 10, "name": "SD", "role": SUB_DISTRIBUTOR, "parent_id": None},
            {"id": 20, "name": "SDM", "role": SUB_DISTRIBUTION_MANAGER, "parent_id": 10},
        ]
    if duplicates is _SENTINEL:
        duplicates = []
    if request_row is _SENTINEL:
        request_row = _request_row()
    if status_row is _SENTINEL:
        status_row = []

    def execute(statement, params=None):
        sql = str(statement)
        if "SELECT id, role, status FROM users WHERE id" in sql:
            return _FakeResult(rows=[recipient])
        if "WITH RECURSIVE descendants" in sql:
            return _FakeResult(rows=[{"1": 1}] if descendants else [])
        if "SELECT id, payload FROM approval_requests" in sql:
            return _FakeResult(rows=duplicates)
        if "SELECT id, name, role, parent_id FROM users" in sql:
            return _FakeResult(rows=approvers)
        if "SELECT status FROM approval_requests" in sql:
            return _FakeResult(rows=status_row)
        if "SELECT COUNT(*) FROM approval_requests" in sql:
            return _FakeResult(rows=[1])
        if "SELECT * FROM approval_requests" in sql:
            return _FakeResult(rows=[request_row] if request_row else [])
        if "SET status = 'cancelled'" in sql:
            return _FakeResult(rowcount=cancel_rowcount)
        if "UPDATE approval_requests" in sql:
            return _FakeResult(rowcount=update_rowcount)
        if "INSERT INTO approval_requests" in sql:
            return _FakeResult(rowcount=1)
        return _FakeResult(rowcount=1)

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute)
    session.commit = AsyncMock()
    session.close = AsyncMock()
    return session


def _enter_session(session):
    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = None
    return MagicMock(return_value=cm)


def _request_row(**overrides):
    row = {
        "id": 1,
        "request_id": "APR-ABCDEF12",
        "request_type": "distribution",
        "requested_by": 100,
        "requested_by_name": "Emp",
        "sub_distribution_id": 10,
        "summary": "test",
        "payload": json.dumps(_distribution_payload()),
        "status": "pending",
        "required_roles": json.dumps([SUB_DISTRIBUTOR, SUB_DISTRIBUTION_MANAGER]),
        "approvals": "[]",
        "rejection_reason": None,
        "execution_result": None,
        "executed_at": None,
        "created_at": None,
        "updated_at": None,
    }
    row.update(overrides)
    return row


def _employee(emp_id="100", parent_id="10"):
    return {
        "_id": emp_id,
        "id": emp_id,
        "role": SUB_DISTRIBUTION_EMPLOYEE,
        "name": "Emp",
        "email": "emp@test.com",
        "parent_id": parent_id,
    }


def _distribution_payload(to_user_id="30", device_ids=None):
    return {"to_user_id": to_user_id, "device_ids": device_ids or ["d1", "d2"]}


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------

class TestBuildRequiredRoles:
    def test_no_approvers(self):
        assert svc._build_required_roles([]) == []

    def test_only_sub_distributor(self):
        assert svc._build_required_roles([{"role": SUB_DISTRIBUTOR}]) == [SUB_DISTRIBUTOR]

    def test_sub_distributor_and_manager_order(self):
        approvers = [
            {"role": SUB_DISTRIBUTION_MANAGER},
            {"role": SUB_DISTRIBUTOR},
            {"role": SUB_DISTRIBUTOR},
        ]
        assert svc._build_required_roles(approvers) == [SUB_DISTRIBUTOR, SUB_DISTRIBUTION_MANAGER]


class TestValidateDistributionPayload:
    def test_missing_to_user_id(self):
        with pytest.raises(ValueError):
            svc._validate_distribution_payload({"device_ids": ["d1"]})

    def test_empty_device_ids(self):
        with pytest.raises(ValueError):
            svc._validate_distribution_payload({"to_user_id": "30", "device_ids": []})

    def test_valid_payload(self):
        svc._validate_distribution_payload(_distribution_payload())


class TestValidateDefectPayload:
    def test_valid_payload(self):
        svc._validate_defect_payload({
            "device_id": "1",
            "defect_type": "hardware",
            "severity": "high",
            "description": "screen is cracked on device",
        })

    def test_short_description_rejected(self):
        with pytest.raises(ValueError):
            svc._validate_defect_payload({
                "device_id": "1",
                "defect_type": "hardware",
                "severity": "high",
                "description": "short",
            })


class TestValidateUserPayload:
    def test_operator_valid(self):
        svc._validate_user_payload(
            {"email": "op@test.com", "name": "Op", "password": "password123", "phone": "1234567890"},
            "operator",
        )

    def test_cluster_requires_sub_distribution_id(self):
        with pytest.raises(ValueError):
            svc._validate_user_payload(
                {"email": "cl@test.com", "name": "Cl", "password": "password123", "phone": "1234567890"},
                "cluster",
            )

    def test_bad_email(self):
        with pytest.raises(ValueError):
            svc._validate_user_payload(
                {"email": "nope", "name": "X", "password": "password123", "phone": "1234567890"},
                "operator",
            )


class TestSerializeRequest:
    def test_parses_payload_and_required_roles(self):
        item = svc._serialize_request({
            "id": 1,
            "payload": '{"to_user_id": "30"}',
            "required_roles": '["sub_distributor"]',
        })
        assert item["_id"] == "1"
        assert item["payload"] == {"to_user_id": "30"}
        assert item["required_roles"] == ["sub_distributor"]

    def test_hides_payload_when_not_included(self):
        item = svc._serialize_request({"id": 1, "payload": "{}"}, include_approvals=False)
        assert "payload" not in item


# ---------------------------------------------------------------------------
# submit_request
# ---------------------------------------------------------------------------

class TestSubmitRequest:
    async def test_non_employee_rejected(self):
        requester = {"id": "5", "role": "manager"}
        with pytest.raises(PermissionError):
            await svc.submit_request(requester, "distribution", _distribution_payload())

    async def test_employee_without_parent_rejected(self):
        requester = _employee(parent_id=None)
        with pytest.raises(ValueError):
            await svc.submit_request(requester, "distribution", _distribution_payload())

    async def test_employee_with_invalid_parent_rejected(self):
        requester = _employee()
        session = _make_session()
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc.user_service, "get_user_by_id",
                          new=AsyncMock(return_value={"id": "10", "role": "cluster"})):
            with pytest.raises(ValueError):
                await svc.submit_request(requester, "distribution", _distribution_payload())

    async def test_successful_submission_creates_pending_request(self):
        requester = _employee()
        session = _make_session()
        bulk_mock = AsyncMock()
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc.user_service, "get_user_by_id",
                          new=AsyncMock(return_value={"id": "10", "role": SUB_DISTRIBUTOR})), \
             patch.object(svc.notification_service, "bulk_create_notifications", new=bulk_mock):
            result = await svc.submit_request(requester, "distribution", _distribution_payload())

        assert result["success"] is True
        data = result["data"]
        assert data["status"] == "pending"
        assert data["request_id"].startswith("APR-")
        assert data["required_roles"] == [SUB_DISTRIBUTOR, SUB_DISTRIBUTION_MANAGER]
        assert bulk_mock.await_count == 1
        sent = bulk_mock.await_args.args[0]
        assert len(sent) == 2

    async def test_duplicate_pending_request_rejected(self):
        requester = _employee()
        duplicates = [{"id": 5, "payload": json.dumps(_distribution_payload())}]
        session = _make_session(duplicates=duplicates)
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc.user_service, "get_user_by_id",
                          new=AsyncMock(return_value={"id": "10", "role": SUB_DISTRIBUTOR})), \
             patch.object(svc.notification_service, "bulk_create_notifications", new=AsyncMock()):
            with pytest.raises(ValueError):
                await svc.submit_request(requester, "distribution", _distribution_payload())

    async def test_recipient_outside_sub_distribution_rejected(self):
        requester = _employee()
        session = _make_session(descendants=False)
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc.user_service, "get_user_by_id",
                          new=AsyncMock(return_value={"id": "10", "role": SUB_DISTRIBUTOR})):
            with pytest.raises(ValueError):
                await svc.submit_request(requester, "distribution", _distribution_payload())


# ---------------------------------------------------------------------------
# Listing / detail / cancel
# ---------------------------------------------------------------------------

class TestGetMyRequests:
    async def test_non_employee_rejected(self):
        with pytest.raises(PermissionError):
            await svc.get_my_requests({"id": "5", "role": "manager"})

    async def test_employee_lists_own_requests(self):
        row = _request_row()
        session = _make_session(request_row=row)
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            result = await svc.get_my_requests(_employee())

        assert len(result["data"]) == 1
        assert result["data"][0]["request_id"] == row["request_id"]


class TestGetRequestsForApprover:
    async def test_non_approver_rejected(self):
        with pytest.raises(PermissionError):
            await svc.get_requests_for_approver({"id": "40", "role": "cluster"})

    async def test_sub_distributor_only_sees_own_branch(self):
        row = _request_row(sub_distribution_id=10)
        session = _make_session(request_row=row)
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            result = await svc.get_requests_for_approver(
                {"id": "10", "role": SUB_DISTRIBUTOR, "parent_id": "1"}
            )

        assert len(result["data"]) == 1

    async def test_sub_distributor_does_not_see_other_branch(self):
        row = _request_row(sub_distribution_id=99)
        session = _make_session(request_row=row)
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            result = await svc.get_requests_for_approver(
                {"id": "10", "role": SUB_DISTRIBUTOR, "parent_id": "1"}
            )

        assert result["data"] == []


class TestGetRequestDetail:
    async def test_not_found(self):
        session = _make_session(request_row=None)
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            with pytest.raises(LookupError):
                await svc.get_request_detail("APR-NOPE", _employee())

    async def test_requester_can_view_own(self):
        row = _request_row(requested_by=100)
        session = _make_session(request_row=row)
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            item = await svc.get_request_detail(row["request_id"], _employee())

        assert item["request_id"] == row["request_id"]
        assert "approver_can_approve" not in item

    async def test_unauthorized_viewer_rejected(self):
        row = _request_row(requested_by=999)
        session = _make_session(request_row=row)
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            with pytest.raises(PermissionError):
                await svc.get_request_detail(row["request_id"], _employee())


class TestCancelRequest:
    async def test_non_employee_rejected(self):
        with pytest.raises(PermissionError):
            await svc.cancel_request("APR-ABC", {"id": "5", "role": "manager"})

    async def test_cancel_pending_succeeds(self):
        session = _make_session()
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            result = await svc.cancel_request("APR-ABCDEF12", _employee())

        assert result["success"] is True

    async def test_cancel_non_pending_rejected(self):
        session = _make_session(cancel_rowcount=0, status_row=[{"status": "approved"}])
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            with pytest.raises(ValueError):
                await svc.cancel_request("APR-ABCDEF12", _employee())

    async def test_cancel_missing_rejected(self):
        session = _make_session(cancel_rowcount=0, status_row=[])
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            with pytest.raises(LookupError):
                await svc.cancel_request("APR-ABCDEF12", _employee())


# ---------------------------------------------------------------------------
# decide_request
# ---------------------------------------------------------------------------

class TestDecideRequest:
    async def test_invalid_action(self):
        with pytest.raises(ValueError):
            await svc.decide_request(
                {"id": "10", "role": SUB_DISTRIBUTOR, "name": "SD"},
                "APR-ABCDEF12", "maybe",
            )

    async def test_non_approver_rejected(self):
        with pytest.raises(PermissionError):
            await svc.decide_request(
                {"id": "40", "role": "cluster"},
                "APR-ABCDEF12", "approve",
            )

    async def test_reject_marks_rejected_and_notifies(self):
        approver = {"id": "10", "role": SUB_DISTRIBUTOR, "name": "SD"}
        row = _request_row(required_roles=json.dumps([SUB_DISTRIBUTOR]))
        session = _make_session(request_row=row)
        notif_mock = AsyncMock()
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc.notification_service, "create_notification", new=notif_mock):
            result = await svc.decide_request(approver, "APR-ABCDEF12", "reject", review_note="bad")

        assert result["success"] is True
        assert result["message"] == "Request rejected"
        assert notif_mock.await_count == 1

    async def test_partial_approval_waits_for_remaining_approver(self):
        approver = {"id": "10", "role": SUB_DISTRIBUTOR, "name": "SD"}
        row = _request_row(
            required_roles=json.dumps([SUB_DISTRIBUTOR, SUB_DISTRIBUTION_MANAGER]),
            approvals=json.dumps([]),
        )
        session = _make_session(request_row=row)
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            result = await svc.decide_request(approver, "APR-ABCDEF12", "approve")

        assert result["success"] is True
        assert "remaining approver" in result["message"]

    async def test_final_approval_executes_distribution(self):
        approver = {"id": "10", "role": SUB_DISTRIBUTOR, "name": "SD"}
        row = _request_row(required_roles=json.dumps([SUB_DISTRIBUTOR]))
        session = _make_session(request_row=row)
        dist_mock = AsyncMock(return_value={"distribution_id": "DIST-2026-0001"})
        notif_mock = AsyncMock()
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc.distribution_service, "create_distribution", dist_mock), \
             patch.object(svc.notification_service, "create_notification", new=notif_mock):
            result = await svc.decide_request(approver, "APR-ABCDEF12", "approve")

        assert result["success"] is True
        assert result["message"] == "Request approved and applied"
        assert dist_mock.await_count == 1
        assert notif_mock.await_count == 1

    async def test_execution_failure_marks_rejected(self):
        approver = {"id": "10", "role": SUB_DISTRIBUTOR, "name": "SD"}
        row = _request_row(required_roles=json.dumps([SUB_DISTRIBUTOR]))
        session = _make_session(request_row=row)
        dist_mock = AsyncMock(side_effect=ValueError("device no longer available"))
        notif_mock = AsyncMock()
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc.distribution_service, "create_distribution", dist_mock), \
             patch.object(svc.notification_service, "create_notification", new=notif_mock):
            result = await svc.decide_request(approver, "APR-ABCDEF12", "approve")

        assert result["success"] is False
        assert "could not be applied" in result["message"]
        assert "device no longer available" in result["data"]["error"]
        assert notif_mock.await_count == 1

    async def test_already_reviewed_rejected(self):
        approver = {"id": "10", "role": SUB_DISTRIBUTOR, "name": "SD"}
        row = _request_row(
            required_roles=json.dumps([SUB_DISTRIBUTOR]),
            approvals=json.dumps([{
                "role": SUB_DISTRIBUTOR, "user_id": "10", "decision": "approve",
            }]),
        )
        session = _make_session(request_row=row)
        with patch.object(svc, "async_session_factory", _enter_session(session)):
            with pytest.raises(ValueError):
                await svc.decide_request(approver, "APR-ABCDEF12", "approve")


# ---------------------------------------------------------------------------
# stage_bulk_payload
# ---------------------------------------------------------------------------

class TestStageBulkPayload:
    async def test_non_employee_rejected(self):
        with pytest.raises(PermissionError):
            await svc.stage_bulk_payload({"id": "5", "role": "manager"}, "users", b"x", "a.csv")

    async def test_bad_extension_rejected(self):
        with pytest.raises(ValueError):
            await svc.stage_bulk_payload(_employee(), "users", b"x", "a.txt")

    async def test_unsupported_kind_rejected(self):
        with pytest.raises(ValueError):
            await svc.stage_bulk_payload(_employee(), "catalog", b"a,b\n1,2", "a.csv")

    async def test_users_kind_parses_csv_rows(self):
        csv_bytes = b"name,email\nOp1,op1@t.com\nOp2,op2@t.com"
        with patch.object(svc.bulk_upload_service, "check_bulk_upload_file"), \
             patch.object(svc.bulk_upload_service, "check_bulk_upload_row_count"), \
             patch.object(svc.bulk_upload_service, "parse_file",
                          return_value=[{"name": "Op1"}, {"name": "Op2"}]):
            payload = await svc.stage_bulk_payload(
                _employee(), "users", csv_bytes, "ops.csv", role="operator", parent_id="10"
            )
        assert payload["kind"] == "users"
        assert payload["parent_id"] == "10"
        assert payload["role"] == "operator"
        assert len(payload["rows"]) == 2

    async def test_users_kind_requires_parent(self):
        with pytest.raises(ValueError):
            await svc.stage_bulk_payload(_employee(), "users", b"a\nb", "a.csv")

    async def test_distribution_csv_parses_identifiers_and_date(self):
        csv_bytes = "mac_address,date_of_distribution\nAA:BB:CC:DD:EE:FF,2026-01-01\n".encode()
        with patch.object(svc.bulk_upload_service, "check_bulk_upload_file"), \
             patch.object(svc.bulk_upload_service, "MAX_BULK_ROWS", 1000):
            payload = await svc.stage_bulk_payload(
                _employee(), "distribution", csv_bytes, "d.csv", to_user_id="30"
            )
        assert payload["kind"] == "distribution"
        assert payload["to_user_id"] == "30"
        assert payload["date_of_distribution"] == "2026-01-01"
        assert payload["rows"][0]["mac_address"] == "AA:BB:CC:DD:EE:FF"

    async def test_distribution_kind_rejects_missing_columns(self):
        with pytest.raises(ValueError):
            await svc.stage_bulk_payload(
                _employee(), "distribution", b"foo\nbar\n", "d.csv"
            )


# ---------------------------------------------------------------------------
# New branch-scoped request types
# ---------------------------------------------------------------------------

class TestNewBranchRequestTypes:
    async def test_bulk_distribution_validation_outside_branch_rejected(self):
        requester = _employee()
        payload = {"to_user_id": "30", "rows": [{"mac_address": "AA:BB:CC:DD:EE:FF"}]}
        session = _make_session(descendants=False)
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc.user_service, "get_user_by_id",
                          new=AsyncMock(return_value={"id": "10", "role": SUB_DISTRIBUTOR})):
            with pytest.raises(ValueError):
                await svc.submit_request(requester, "bulk_distribution", payload)

    async def test_user_update_executes_through_update_user(self):
        actor = {"id": 10, "name": "SD", "role": SUB_DISTRIBUTOR}
        row = _request_row(
            request_type="user_update",
            payload=json.dumps({"user_id": "55", "name": "Renamed"}),
        )
        session = _make_session(request_row=row)
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc, "_branch_sub_distributor_actor",
                          new=AsyncMock(return_value=actor)), \
             patch.object(svc.user_service, "update_user",
                          new=AsyncMock(return_value={"id": 55})):
            result = await svc._execute_request(row, _employee())

            assert result["result_id"] == "55"
            svc.user_service.update_user.assert_awaited_once()
            args, kwargs = svc.user_service.update_user.call_args
            assert args[0] == "55"
            assert args[1].name == "Renamed"

    async def test_bulk_users_executes_through_process_bulk_user_upload(self):
        row = _row_to(
            request_type="bulk_users",
            payload=json.dumps({
                "rows": [{"name": "Op1", "email": "op1@t.com"}],
                "role": "operator",
                "parent_id": "10",
            }),
        )
        session = _make_session()
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc, "_branch_sub_distributor_actor",
                          new=AsyncMock(return_value={"id": 10, "role": SUB_DISTRIBUTOR})), \
             patch.object(svc.bulk_upload_service, "process_bulk_user_upload",
                          new=AsyncMock(return_value={"created": 2, "errors": []})):
            result = await svc._execute_request(row, _employee())

        assert result["created_count"] == 2
        assert "2" in result["result_id"]

    async def test_bulk_distribution_executes_from_identifiers(self):
        row = _row_to(
            request_type="bulk_distribution",
            payload=json.dumps({
                "rows": [{"mac_address": "AA:BB:CC:DD:EE:FF"}],
                "to_user_id": "30",
                "notes": "bulk",
                "date_of_distribution": "2026-01-01",
            }),
        )
        session = _make_session()
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc, "_branch_sub_distributor_actor",
                          new=AsyncMock(return_value={"id": 10, "name": "SD"})), \
             patch.object(svc.distribution_service, "create_distribution_from_identifiers",
                          new=AsyncMock(return_value={"distribution_id": "DIST-BULK", "errors": []})):
            result = await svc._execute_request(row, _employee())

        assert result["result_id"] == "DIST-BULK"

    async def test_delivery_receipt_executes_confirm_receipt(self):
        row = _row_to(
            request_type="delivery_receipt",
            payload=json.dumps({"distribution_id": "DIST-1", "received": True, "notes": "ok"}),
        )
        session = _make_session()
        with patch.object(svc, "async_session_factory", _enter_session(session)), \
             patch.object(svc, "_branch_sub_distributor_actor",
                          new=AsyncMock(return_value={"id": 10, "name": "SD"})), \
             patch.object(svc.distribution_service, "confirm_receipt",
                          new=AsyncMock(return_value={"success": True})):
            result = await svc._execute_request(row, _employee())

            assert result["result_id"] == "DIST-1"
            svc.distribution_service.confirm_receipt.assert_awaited_once()


def _row_to(request_type, payload=None, sub_distribution_id=10):
    base = _request_row(request_type=request_type, sub_distribution_id=sub_distribution_id)
    if payload is not None:
        base["payload"] = payload
    return base
