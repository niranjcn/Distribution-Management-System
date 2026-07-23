from unittest.mock import AsyncMock
import pytest


class TestGetOperators:
    URL = "/api/operators"

    def _fake_operator_list(self):
        return {
            "data": [
                {"id": "OP1", "name": "John Doe", "status": "active"},
            ],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        }

    def test_success_returns_operators(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.get_operators = AsyncMock(
            return_value=self._fake_operator_list()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Operators retrieved successfully"
        assert "data" in body
        assert "pagination" in body

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.get_operators = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetOperator:
    URL = "/api/operators/OP1"

    def _fake_operator(self):
        return {"id": "OP1", "name": "John Doe", "status": "active"}

    def test_success_returns_operator(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.get_operator_by_id = AsyncMock(
            return_value=self._fake_operator()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Operator retrieved successfully"
        assert body["data"]["id"] == "OP1"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_not_found_returns_404(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.get_operator_by_id = AsyncMock(return_value=None)

        resp = client.get("/api/operators/UNKNOWN")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Operator not found"

    def test_internal_error_returns_500(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.get_operator_by_id = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetOperatorDevices:
    URL = "/api/operators/OP1/devices"

    def _fake_operator_devices(self):
        return [
            {"device_id": "D1", "serial_number": "SN001", "status": "assigned"},
        ]

    def test_success_returns_devices(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.get_operator_by_id = AsyncMock(
            return_value={"id": "OP1", "name": "John Doe"}
        )
        mod.operator_service.get_operator_devices = AsyncMock(
            return_value=self._fake_operator_devices()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Operator devices retrieved successfully"
        assert len(body["data"]) == 1

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_not_found_returns_404(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.get_operator_by_id = AsyncMock(return_value=None)

        resp = client.get("/api/operators/UNKNOWN/devices")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Operator not found"

    def test_internal_error_returns_500(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.get_operator_by_id = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestCreateOperator:
    URL = "/api/operators"

    def _fake_created(self):
        return {"id": "OP2", "name": "Jane Doe", "status": "active"}

    def test_success_creates_operator(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.create_operator = AsyncMock(
            return_value=self._fake_created()
        )

        resp = client.post(
            self.URL,
            json={"name": "Jane Doe", "phone": "1234567890", "email": "jane@test.com", "cluster": "ClusterA"},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Operator created successfully"
        assert body["data"]["id"] == "OP2"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(
            self.URL,
            json={"name": "Jane Doe", "phone": "1234567890", "email": "jane@test.com", "cluster": "ClusterA"},
        )
        assert resp.status_code == 401

    def test_forbidden_operator_role_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.post(
            self.URL,
            json={"name": "Jane Doe", "phone": "1234567890", "email": "jane@test.com", "cluster": "ClusterA"},
        )
        assert resp.status_code == 403
        assert "permission" in resp.json()["detail"].lower()

    def test_internal_error_returns_500(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.create_operator = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.post(
            self.URL,
            json={"name": "Jane Doe", "phone": "1234567890", "email": "jane@test.com", "cluster": "ClusterA"},
        )

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestUpdateOperator:
    URL = "/api/operators/OP1"

    def _fake_updated(self):
        return {"id": "OP1", "name": "John Updated", "status": "active"}

    def test_success_updates_operator(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.get_operator_by_id = AsyncMock(
            return_value={"id": "OP1", "name": "John Doe", "assigned_to": "1"}
        )
        mod.operator_service.update_operator = AsyncMock(
            return_value=self._fake_updated()
        )

        resp = client.put(
            self.URL,
            json={"name": "John Updated"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Operator updated successfully"
        assert body["data"]["name"] == "John Updated"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.put(self.URL, json={"name": "John Updated"})
        assert resp.status_code == 401

    def test_not_found_returns_404(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.update_operator = AsyncMock(return_value=None)

        resp = client.put(
            "/api/operators/UNKNOWN",
            json={"name": "John Updated"},
        )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Operator not found"

    def test_internal_error_returns_500(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.update_operator = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.put(self.URL, json={"name": "John Updated"})

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestDeleteOperator:
    URL = "/api/operators/OP1"

    def test_success_deletes_operator(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.delete_operator = AsyncMock(return_value=True)

        resp = client.delete(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Operator deleted successfully"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.delete(self.URL)
        assert resp.status_code == 401

    def test_forbidden_operator_role_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.delete(self.URL)
        assert resp.status_code == 403
        assert "permission" in resp.json()["detail"].lower()

    def test_not_found_returns_404(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.delete_operator = AsyncMock(return_value=False)

        resp = client.delete("/api/operators/UNKNOWN")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Operator not found"

    def test_internal_error_returns_500(self, client, mock_operator_services):
        import app.routes.operators as mod

        mod.operator_service.delete_operator = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.delete(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()
