from unittest.mock import AsyncMock
import pytest


class TestGetReassignmentRequests:
    URL = "/api/reassignment-requests"

    def _fake_paginated(self):
        return {
            "data": [{"id": "1", "status": "pending"}],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        }

    def test_success(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.get_reassignment_requests = AsyncMock(
            return_value=self._fake_paginated()
        )
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Reassignment requests retrieved successfully"
        assert "data" in body
        assert "pagination" in body

    def test_forbidden_for_manager(self, client, set_role):
        set_role("manager")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.get_reassignment_requests = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.get(self.URL)
        assert resp.status_code == 500


class TestGetReassignmentRequest:
    URL = "/api/reassignment-requests/1"

    def _fake_request(self, **overrides):
        return {"id": "1", "status": "pending", "requested_by_name": "User", **overrides}

    def test_success(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.get_reassignment_request = AsyncMock(
            return_value=self._fake_request()
        )
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Reassignment request retrieved"
        assert body["data"]["id"] == "1"

    def test_not_found_returns_404(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.get_reassignment_request = AsyncMock(return_value=None)
        resp = client.get("/api/reassignment-requests/999")
        assert resp.status_code == 404

    def test_forbidden_for_manager(self, client, set_role):
        set_role("manager")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.get_reassignment_request = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.get(self.URL)
        assert resp.status_code == 500


class TestReassignUsers:
    URL = "/api/reassignment-requests/1/reassign"
    VALID_PAYLOAD = {
        "reassign_to_id": "2",
        "reassign_to_name": "New Parent",
        "reassign_to_role": "cluster",
    }

    def test_success(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.reassign_users = AsyncMock(
            return_value=(True, "Users reassigned successfully")
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Users reassigned successfully"

    def test_missing_reassign_to_id_returns_400(self, client, mock_reassignment_services):
        resp = client.post(self.URL, json={})
        assert resp.status_code == 400

    def test_reassign_failure_returns_400(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.reassign_users = AsyncMock(
            return_value=(False, "Cannot reassign")
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 400

    def test_forbidden_for_manager(self, client, set_role):
        set_role("manager")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.reassign_users = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestRejectReassignmentRequest:
    URL = "/api/reassignment-requests/1/reject"

    def test_success(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.reject_request = AsyncMock(
            return_value=(True, "Request rejected")
        )
        resp = client.post(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_reject_failure_returns_400(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.reject_request = AsyncMock(
            return_value=(False, "Cannot reject")
        )
        resp = client.post(self.URL)
        assert resp.status_code == 400

    def test_forbidden_for_manager(self, client, set_role):
        set_role("manager")
        resp = client.post(self.URL)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_reassignment_services):
        import app.routes.reassignment_requests as mod
        mod.reassignment_request_service.reject_request = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.post(self.URL)
        assert resp.status_code == 500
