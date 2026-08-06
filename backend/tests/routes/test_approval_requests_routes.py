"""Route tests for the employee approval-request API (role sub_distribution_employee)."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_approval_services():
    patchers = [
        patch("app.routes.approval_requests.approval_request_service"),
        patch("app.routes.approval_requests.log_business_activity", new=AsyncMock()),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


class TestSubmit:
    URL = "/api/approval-requests/"

    def test_employee_submits_distribution_request(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distribution_employee")
        mod.approval_request_service.submit_request = AsyncMock(return_value={
            "success": True,
            "message": "Approval request submitted successfully",
            "data": {"request_id": "APR-ABC12345", "request_type": "distribution",
                     "status": "pending", "required_roles": ["sub_distributor"]},
        })

        resp = client.post(self.URL, json={
            "request_type": "distribution",
            "payload": {"to_user_id": "30", "device_ids": ["d1", "d2"]},
            "summary": "Send two devices",
        })

        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "pending"
        mod.approval_request_service.submit_request.assert_awaited_once()

    def test_non_employee_gets_403(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("manager")
        mod.approval_request_service.submit_request = AsyncMock(
            side_effect=PermissionError("Only sub distribution employees can submit approval requests")
        )

        resp = client.post(self.URL, json={
            "request_type": "distribution",
            "payload": {"to_user_id": "30", "device_ids": ["d1"]},
        })

        assert resp.status_code == 403

    def test_invalid_payload_gets_400(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distribution_employee")
        mod.approval_request_service.submit_request = AsyncMock(
            side_effect=ValueError("to_user_id is required")
        )

        resp = client.post(self.URL, json={
            "request_type": "distribution",
            "payload": {"device_ids": []},
        })

        assert resp.status_code == 400


class TestMyRequests:
    URL = "/api/approval-requests/my"

    def test_employee_lists_own(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distribution_employee")
        mod.approval_request_service.get_my_requests = AsyncMock(return_value={
            "data": [{"request_id": "APR-ABC12345", "request_type": "distribution", "status": "pending"}],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1,
                           "has_next": False, "has_prev": False},
        })

        resp = client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_non_employee_gets_403(self, client, mock_approval_services, set_role):
        set_role("super_admin")
        resp = client.get(self.URL)
        assert resp.status_code == 403


class TestPending:
    URL = "/api/approval-requests/pending"

    def test_sub_distributor_can_list(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distributor")
        mod.approval_request_service.get_requests_for_approver = AsyncMock(return_value={
            "data": [],
            "pagination": {"page": 1, "page_size": 20, "total": 0, "total_pages": 0,
                           "has_next": False, "has_prev": False},
        })

        resp = client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_sub_distribution_manager_can_list(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distribution_manager")
        mod.approval_request_service.get_requests_for_approver = AsyncMock(return_value={
            "data": [],
            "pagination": {"page": 1, "page_size": 20, "total": 0, "total_pages": 0,
                           "has_next": False, "has_prev": False},
        })

        resp = client.get(self.URL)

        assert resp.status_code == 200

    def test_employee_gets_403(self, client, mock_approval_services, set_role):
        set_role("sub_distribution_employee")
        resp = client.get(self.URL)
        assert resp.status_code == 403


class TestDetail:
    URL = "/api/approval-requests/APR-ABC12345"

    def test_viewer_gets_detail(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distribution_employee")
        mod.approval_request_service.get_request_detail = AsyncMock(return_value={
            "request_id": "APR-ABC12345", "status": "pending",
        })

        resp = client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["data"]["request_id"] == "APR-ABC12345"

    def test_not_found_gets_404(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distribution_employee")
        mod.approval_request_service.get_request_detail = AsyncMock(
            side_effect=LookupError("Approval request not found")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 404

    def test_unauthorized_gets_403(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("operator")
        mod.approval_request_service.get_request_detail = AsyncMock(
            side_effect=PermissionError("You are not authorized to view this request")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 403


class TestDecide:
    URL = "/api/approval-requests/APR-ABC12345/decide"

    def test_approve(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distributor")
        mod.approval_request_service.decide_request = AsyncMock(return_value={
            "success": True, "message": "Request approved and applied",
            "data": {"request_type": "distribution", "result_id": "DIST-2026-0001"},
        })

        resp = client.post(self.URL, json={"action": "approve"})

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_reject(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distribution_manager")
        mod.approval_request_service.decide_request = AsyncMock(return_value={
            "success": True, "message": "Request rejected",
        })

        resp = client.post(self.URL, json={"action": "reject", "review_note": "not needed"})

        assert resp.status_code == 200
        assert resp.json()["message"] == "Request rejected"

    def test_invalid_action_gets_400(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distributor")
        mod.approval_request_service.decide_request = AsyncMock(
            side_effect=ValueError("action must be 'approve' or 'reject'")
        )

        resp = client.post(self.URL, json={"action": "maybe"})

        assert resp.status_code == 400

    def test_non_approver_gets_403(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("operator")
        mod.approval_request_service.decide_request = AsyncMock(
            side_effect=PermissionError("You are not an approver for employee requests")
        )

        resp = client.post(self.URL, json={"action": "approve"})

        assert resp.status_code == 403


class TestCancel:
    URL = "/api/approval-requests/APR-ABC12345/cancel"

    def test_employee_cancels(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distribution_employee")
        mod.approval_request_service.cancel_request = AsyncMock(return_value={
            "success": True, "message": "Approval request cancelled",
        })

        resp = client.post(self.URL)

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_non_employee_gets_403(self, client, mock_approval_services, set_role):
        set_role("super_admin")
        resp = client.post(self.URL)
        assert resp.status_code == 403

    def test_cancel_non_pending_gets_400(self, client, mock_approval_services, set_role):
        import app.routes.approval_requests as mod

        set_role("sub_distribution_employee")
        mod.approval_request_service.cancel_request = AsyncMock(
            side_effect=ValueError("Only pending requests can be cancelled")
        )

        resp = client.post(self.URL)

        assert resp.status_code == 400
