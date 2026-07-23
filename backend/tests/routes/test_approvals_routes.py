from unittest.mock import AsyncMock
import pytest


class TestGetApprovals:
    URL = "/api/approvals"

    def _fake_approval_list(self):
        return {
            "data": [
                {"id": "A1", "status": "pending", "approval_type": "distribution"},
            ],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        }

    def test_success_returns_approvals(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.get_approvals = AsyncMock(
            return_value=self._fake_approval_list()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Approvals retrieved successfully"
        assert "data" in body
        assert "pagination" in body

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_forbidden_non_management_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_internal_error_returns_500(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.get_approvals = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetRoleRoutingConfig:
    URL = "/api/approvals/role-routing/config"

    def _fake_config(self):
        return {"routing": {"admin": ["manager"], "manager": ["admin"]}}

    def test_success_returns_config(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.get_role_routing_config = AsyncMock(
            return_value=self._fake_config()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Approval role routing config retrieved successfully"
        assert body["data"] == self._fake_config()

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_forbidden_non_management_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_internal_error_returns_500(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.get_role_routing_config = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestUpdateRoleRoutingConfig:
    URL = "/api/approvals/role-routing/config"

    def _fake_updated_config(self):
        return {
            "distribution": {"super_admin": True, "manager": True, "pdic_staff": False},
            "return": {"super_admin": True, "manager": True, "pdic_staff": False},
            "defect": {"super_admin": True, "manager": False, "pdic_staff": True},
        }

    def _valid_payload(self):
        return {
            "distribution": {"admin": True, "manager": True, "staff": False},
            "return": {"admin": True, "manager": True, "staff": False},
            "defect": {"admin": True, "manager": False, "staff": True},
        }

    def test_success_updates_config(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.update_role_routing_config = AsyncMock(
            return_value=self._fake_updated_config()
        )

        resp = client.put(
            self.URL,
            json=self._valid_payload(),
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Approval role routing config updated successfully"
        assert body["data"] == self._fake_updated_config()

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.put(self.URL, json=self._valid_payload())
        assert resp.status_code == 401

    def test_forbidden_non_admin_returns_403(self, client, set_role):
        set_role("manager")
        resp = client.put(self.URL, json=self._valid_payload())
        assert resp.status_code == 403

    def test_internal_error_returns_500(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.update_role_routing_config = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.put(
            self.URL,
            json=self._valid_payload(),
        )

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetApproval:
    URL = "/api/approvals/A1"

    def _fake_approval(self):
        return {"id": "A1", "status": "pending", "approval_type": "distribution"}

    def test_success_returns_approval(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.get_approval_by_id = AsyncMock(
            return_value=self._fake_approval()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Approval retrieved successfully"
        assert body["data"]["id"] == "A1"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_forbidden_non_management_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_not_found_returns_404(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.get_approval_by_id = AsyncMock(return_value=None)

        resp = client.get("/api/approvals/UNKNOWN")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Approval not found"

    def test_internal_error_returns_500(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.get_approval_by_id = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestApproveRequest:
    URL = "/api/approvals/A1/approve"

    def _fake_approved(self):
        return {"id": "A1", "status": "approved"}

    def test_success_approves_request(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.approve_request = AsyncMock(
            return_value=self._fake_approved()
        )

        resp = client.post(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Request approved successfully"
        assert body["data"]["status"] == "approved"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL)
        assert resp.status_code == 401

    def test_forbidden_non_management_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.post(self.URL)
        assert resp.status_code == 403

    def test_not_found_returns_404(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.approve_request = AsyncMock(return_value=None)

        resp = client.post("/api/approvals/UNKNOWN/approve")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Approval not found"

    def test_internal_error_returns_500(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.approve_request = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.post(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestRejectRequest:
    URL = "/api/approvals/A1/reject"

    def _fake_rejected(self):
        return {"id": "A1", "status": "rejected"}

    def test_success_rejects_request(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.reject_request = AsyncMock(
            return_value=self._fake_rejected()
        )

        resp = client.post(
            self.URL,
            json={"rejection_reason": "Insufficient inventory", "notes": "Rejected"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Request rejected successfully"
        assert body["data"]["status"] == "rejected"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(
            self.URL, json={"rejection_reason": "reason", "notes": "notes"}
        )
        assert resp.status_code == 401

    def test_forbidden_non_management_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.post(
            self.URL, json={"rejection_reason": "reason", "notes": "notes"}
        )
        assert resp.status_code == 403

    def test_not_found_returns_404(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.reject_request = AsyncMock(return_value=None)

        resp = client.post(
            "/api/approvals/UNKNOWN/reject",
            json={"rejection_reason": "reason", "notes": "notes"},
        )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Approval not found"

    def test_internal_error_returns_500(self, client, mock_approval_services):
        import app.routes.approvals as mod

        mod.approval_service.reject_request = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.post(
            self.URL,
            json={"rejection_reason": "reason", "notes": "notes"},
        )

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()
