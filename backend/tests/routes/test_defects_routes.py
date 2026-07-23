from unittest.mock import AsyncMock
import pytest


class TestGetReplacementDefects:
    URL = "/api/defects/replacements"

    def _fake_paginated(self):
        return {
            "data": [{"id": "1", "status": "replacement_pending_confirmation"}],
            "pagination": {"page": 1, "page_size": 100, "total": 1, "total_pages": 1},
        }

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_replacement_defects = AsyncMock(return_value=self._fake_paginated())
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert "pagination" in body

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_replacement_defects = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.get(self.URL)
        assert resp.status_code == 500


class TestGetPendingReplacementDefects:
    URL = "/api/defects/replacements/pending"

    def _fake_paginated(self):
        return {
            "data": [{"id": "1", "status": "defective"}],
            "pagination": {"page": 1, "page_size": 100, "total": 1, "total_pages": 1},
        }

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_pending_replacement_defects = AsyncMock(
            return_value=self._fake_paginated()
        )
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert "pagination" in body

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_pending_replacement_defects = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.get(self.URL)
        assert resp.status_code == 500


class TestListDefects:
    URL = "/api/defects"

    def _fake_paginated(self):
        return {
            "data": [{"id": "1", "report_id": "DF001", "status": "defective"}],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        }

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_defects = AsyncMock(return_value=self._fake_paginated())
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Defect reports retrieved successfully"
        assert "data" in body
        assert "pagination" in body

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_defects = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.get(self.URL)
        assert resp.status_code == 500


class TestGetDefect:
    URL = "/api/defects/1"

    def _fake_defect(self, **overrides):
        return {"id": "1", "report_id": "DF001", "status": "defective", **overrides}

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_defect_by_id = AsyncMock(return_value=self._fake_defect())
        resp = client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Defect report retrieved successfully"
        assert body["data"]["id"] == "1"

    def test_not_found_returns_404(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_defect_by_id = AsyncMock(return_value=None)
        resp = client.get("/api/defects/999")
        assert resp.status_code == 404

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_defect_by_id = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.get(self.URL)
        assert resp.status_code == 500


class TestCreateDefect:
    URL = "/api/defects"
    VALID_PAYLOAD = {
        "device_id": "1",
        "defect_type": "hardware",
        "severity": "medium",
        "description": "Device not working",
    }

    def _fake_defect(self, **overrides):
        return {"id": "2", "report_id": "DF002", "status": "defective", **overrides}

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.create_defect = AsyncMock(return_value=self._fake_defect())
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Defect report created successfully"
        assert body["data"]["report_id"] == "DF002"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_forbidden_for_md_director(self, client, set_role):
        set_role("md_director")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.create_defect = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestUpdateDefect:
    URL = "/api/defects/1"
    VALID_PAYLOAD = {"description": "Updated description"}

    def _fake_defect(self, **overrides):
        return {"id": "1", "report_id": "DF001", "description": "Updated description", **overrides}

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.update_defect = AsyncMock(return_value=self._fake_defect())
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Defect report updated successfully"
        assert body["data"]["description"] == "Updated description"

    def test_not_found_returns_404(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.update_defect = AsyncMock(return_value=None)
        resp = client.put("/api/defects/999", json=self.VALID_PAYLOAD)
        assert resp.status_code == 404

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_forbidden_for_md_director(self, client, set_role):
        set_role("md_director")
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.update_defect = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.put(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestDeleteDefect:
    URL = "/api/defects/1"

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.delete_defect = AsyncMock(return_value=True)
        resp = client.delete(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Defect report deleted successfully"

    def test_not_found_returns_404(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.delete_defect = AsyncMock(return_value=False)
        resp = client.delete("/api/defects/999")
        assert resp.status_code == 404

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.delete(self.URL)
        assert resp.status_code == 403

    def test_forbidden_for_md_director(self, client, set_role):
        set_role("md_director")
        resp = client.delete(self.URL)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.delete(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.delete_defect = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.delete(self.URL)
        assert resp.status_code == 500


class TestResolveDefect:
    URL = "/api/defects/1/resolve"
    VALID_PAYLOAD = {"resolution": "Device has been fixed and resolved successfully"}

    def _fake_defect(self, **overrides):
        return {"id": "1", "report_id": "DF001", "status": "resolved", **overrides}

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.resolve_defect = AsyncMock(return_value=self._fake_defect())
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Defect resolved successfully"
        assert body["data"]["status"] == "resolved"

    def test_not_found_returns_404(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.resolve_defect = AsyncMock(return_value=None)
        resp = client.patch("/api/defects/999/resolve", json=self.VALID_PAYLOAD)
        assert resp.status_code == 404

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_forbidden_for_md_director(self, client, set_role):
        set_role("md_director")
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.resolve_defect = AsyncMock(side_effect=RuntimeError("error"))
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestUpdateDefectStatus:
    URL = "/api/defects/1/status"
    VALID_PAYLOAD = {"status": "resolved"}

    def _fake_defect(self, **overrides):
        return {"id": "1", "report_id": "DF001", "status": "resolved", **overrides}

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_defect_by_id = AsyncMock(return_value=self._fake_defect(status="defective"))
        mod.defect_service.update_defect_status = AsyncMock(return_value=self._fake_defect())
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Defect status updated successfully"
        assert body["data"]["status"] == "resolved"

    def test_not_found_returns_404(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_defect_by_id = AsyncMock(return_value=None)
        mod.defect_service.update_defect_status = AsyncMock(return_value=None)
        resp = client.patch("/api/defects/999/status", json=self.VALID_PAYLOAD)
        assert resp.status_code == 404

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_forbidden_for_md_director(self, client, set_role):
        set_role("md_director")
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.get_defect_by_id = AsyncMock(return_value=self._fake_defect())
        mod.defect_service.update_defect_status = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestConfirmDefectPayment:
    URL = "/api/defects/1/confirm-payment"
    VALID_PAYLOAD = {"notes": "Payment received"}

    def _fake_defect(self, **overrides):
        return {"id": "1", "report_id": "DF001", "status": "resolved", "return_amount": 100.0, **overrides}

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.confirm_defect_payment = AsyncMock(return_value=self._fake_defect())
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Defect payment confirmed successfully"
        assert body["data"]["return_amount"] == 100.0

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.confirm_defect_payment = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestReplaceDefectDevice:
    URL = "/api/defects/1/replace"
    VALID_PAYLOAD = {"replacement_device_id": "2"}

    def _fake_defect(self, **overrides):
        return {
            "id": "1",
            "report_id": "DF001",
            "status": "replacement_pending_confirmation",
            **overrides,
        }

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.replace_defect_device = AsyncMock(return_value=self._fake_defect())
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Device replaced successfully and assigned to the original operator"

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_forbidden_for_md_director(self, client, set_role):
        set_role("md_director")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.replace_defect_device = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestConfirmReplacementReceipt:
    URL = "/api/defects/1/replacement/confirm"
    VALID_PAYLOAD = {"notes": "Replacement received"}

    def _fake_defect(self, **overrides):
        return {"id": "1", "report_id": "DF001", "status": "replacement_confirmed", **overrides}

    def test_success(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.confirm_replacement_receipt = AsyncMock(
            return_value=self._fake_defect()
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Replacement receipt confirmed successfully"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_defect_services):
        import app.routes.defects as mod
        mod.defect_service.confirm_replacement_receipt = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500


class TestEnquireReplacementStatus:
    URL = "/api/defects/1/enquire"
    VALID_PAYLOAD = {"message": "When will the replacement arrive?"}

    def _fake_defect(self, **overrides):
        return {"id": "1", "report_id": "DF001", **overrides}

    def test_success(self, client, set_role, mock_defect_services):
        set_role("operator")
        import app.routes.defects as mod
        mod.defect_service.enquire_replacement_status = AsyncMock(
            return_value=self._fake_defect()
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Replacement enquiry sent successfully"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, set_role, mock_defect_services):
        set_role("operator")
        import app.routes.defects as mod
        mod.defect_service.enquire_replacement_status = AsyncMock(
            side_effect=RuntimeError("error")
        )
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 500
