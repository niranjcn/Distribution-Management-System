from unittest.mock import AsyncMock
import pytest


class TestGetReturns:
    URL = "/api/returns"

    def _fake_return_list(self):
        return {
            "data": [
                {"return_id": "R1", "status": "pending", "device_count": 2},
            ],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        }

    def test_success_returns_returns(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.get_returns = AsyncMock(
            return_value=self._fake_return_list()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Return requests retrieved successfully"
        assert "data" in body
        assert "pagination" in body

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.get_returns = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetReturn:
    URL = "/api/returns/R1"

    def _fake_return(self):
        return {"return_id": "R1", "status": "pending", "reason": "defective"}

    def test_success_returns_return(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.get_return_by_id = AsyncMock(
            return_value=self._fake_return()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Return request retrieved successfully"
        assert body["data"]["return_id"] == "R1"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_not_found_returns_404(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.get_return_by_id = AsyncMock(return_value=None)

        resp = client.get("/api/returns/UNKNOWN")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Return request not found"

    def test_internal_error_returns_500(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.get_return_by_id = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestCreateReturn:
    URL = "/api/returns"

    def _fake_created(self):
        return {"return_id": "R2", "status": "pending", "reason": "defective"}

    def test_success_creates_return(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.create_return = AsyncMock(
            return_value=self._fake_created()
        )

        resp = client.post(
            self.URL,
            json={"device_id": "dev1", "reason": "defective", "description": "Broken screen"},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Return request created successfully"
        assert body["data"]["return_id"] == "R2"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(
            self.URL,
            json={"device_id": "dev1", "reason": "defective"},
        )
        assert resp.status_code == 401

    def test_forbidden_md_director_returns_403(self, client, set_role):
        set_role("md_director")
        resp = client.post(
            self.URL,
            json={"device_id": "dev1", "reason": "defective"},
        )
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"].lower()

    def test_internal_error_returns_500(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.create_return = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.post(
            self.URL,
            json={"device_id": "dev1", "reason": "defective"},
        )

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestUpdateReturnStatus:
    URL = "/api/returns/R1/status"

    def _fake_updated(self):
        return {"return_id": "R1", "status": "approved"}

    def test_success_updates_status(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.get_return_by_id = AsyncMock(
            return_value=self._fake_updated()
        )
        mod.return_service.update_return_status = AsyncMock(
            return_value=self._fake_updated()
        )

        resp = client.patch(
            self.URL,
            json={"status": "approved"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Return status updated successfully"
        assert body["data"]["status"] == "approved"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.patch(self.URL, json={"status": "approved"})
        assert resp.status_code == 401

    def test_forbidden_md_director_returns_403(self, client, set_role):
        set_role("md_director")
        resp = client.patch(self.URL, json={"status": "approved"})
        assert resp.status_code == 403

    def test_not_found_returns_404(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.get_return_by_id = AsyncMock(return_value=None)
        mod.return_service.update_return_status = AsyncMock(return_value=None)

        resp = client.patch(
            "/api/returns/UNKNOWN/status",
            json={"status": "approved"},
        )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Return request not found"

    def test_internal_error_returns_500(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.get_return_by_id = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.patch(self.URL, json={"status": "approved"})

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestDeleteReturn:
    URL = "/api/returns/R1"

    def test_success_cancels_return(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.cancel_return = AsyncMock(return_value=True)

        resp = client.delete(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Return request cancelled successfully"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.delete(self.URL)
        assert resp.status_code == 401

    def test_forbidden_md_director_returns_403(self, client, set_role):
        set_role("md_director")
        resp = client.delete(self.URL)
        assert resp.status_code == 403

    def test_not_found_returns_404(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.cancel_return = AsyncMock(return_value=False)

        resp = client.delete("/api/returns/UNKNOWN")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Return request not found"

    def test_internal_error_returns_500(self, client, mock_return_services):
        import app.routes.returns as mod

        mod.return_service.cancel_return = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.delete(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()
