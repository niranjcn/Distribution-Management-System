from unittest.mock import AsyncMock
import pytest


class TestGetDistributions:
    URL = "/api/distributions"

    def _fake_distribution_list(self):
        return {
            "data": [
                {"distribution_id": "D1", "status": "pending", "device_count": 3},
                {"distribution_id": "D2", "status": "approved", "device_count": 5},
            ],
            "pagination": {"page": 1, "page_size": 20, "total": 2, "total_pages": 1},
        }

    def test_success_returns_distributions(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.get_distributions = AsyncMock(
            return_value=self._fake_distribution_list()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Distributions retrieved successfully"
        assert "data" in body
        assert "pagination" in body
        assert len(body["data"]) == 2

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.get_distributions = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetPendingDistributions:
    URL = "/api/distributions/pending"

    def _fake_pending_list(self):
        return [
            {"distribution_id": "D3", "status": "pending", "device_count": 2}
        ]

    def test_success_returns_pending(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.get_pending_distributions = AsyncMock(
            return_value=self._fake_pending_list()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Pending distributions retrieved successfully"
        assert body["data"] == self._fake_pending_list()

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_forbidden_non_management_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_internal_error_returns_500(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.get_pending_distributions = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetDistribution:
    URL = "/api/distributions/D1"

    def _fake_distribution(self):
        return {
            "distribution_id": "D1",
            "status": "pending",
            "device_count": 3,
            "to_user_name": "User A",
        }

    def test_success_returns_distribution(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.get_distribution_by_id = AsyncMock(
            return_value=self._fake_distribution()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Distribution retrieved successfully"
        assert body["data"]["distribution_id"] == "D1"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_not_found_returns_404(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.get_distribution_by_id = AsyncMock(return_value=None)

        resp = client.get("/api/distributions/UNKNOWN")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Distribution not found"

    def test_internal_error_returns_500(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.get_distribution_by_id = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestCreateDistribution:
    URL = "/api/distributions"

    def _fake_created(self):
        return {
            "distribution_id": "D4",
            "status": "pending",
            "device_count": 1,
            "to_user_id": "user2",
        }

    def test_success_creates_distribution(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.create_distribution = AsyncMock(
            return_value=self._fake_created()
        )

        resp = client.post(
            self.URL,
            json={
                "to_user_id": "user2",
                "device_ids": ["dev1"],
                "notes": "test distribution",
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Distribution created successfully"
        assert body["data"]["distribution_id"] == "D4"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(
            self.URL,
            json={"to_user_id": "user2", "device_ids": ["dev1"]},
        )
        assert resp.status_code == 401

    def test_forbidden_md_director_returns_403(self, client, set_role):
        set_role("md_director")
        resp = client.post(
            self.URL,
            json={"to_user_id": "user2", "device_ids": ["dev1"]},
        )
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"].lower()

    def test_forbidden_sub_distribution_manager_returns_403(self, client, set_role):
        set_role("sub_distribution_manager")
        resp = client.post(
            self.URL,
            json={"to_user_id": "user2", "device_ids": ["dev1"]},
        )
        assert resp.status_code == 403
        assert "cannot create" in resp.json()["detail"].lower()

    def test_internal_error_returns_500(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.create_distribution = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.post(
            self.URL,
            json={"to_user_id": "user2", "device_ids": ["dev1"]},
        )

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestUpdateDistributionStatus:
    URL = "/api/distributions/D1/status"

    def _fake_updated(self):
        return {"distribution_id": "D1", "status": "delivered"}

    def test_success_updates_status(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.get_distribution_by_id = AsyncMock(
            return_value=self._fake_updated()
        )
        mod.distribution_service.update_distribution_status = AsyncMock(
            return_value=self._fake_updated()
        )

        resp = client.patch(
            self.URL,
            json={"status": "delivered"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Distribution status updated successfully"
        assert body["data"]["status"] == "delivered"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.patch(
            self.URL,
            json={"status": "delivered"},
        )
        assert resp.status_code == 401

    def test_forbidden_md_director_returns_403(self, client, set_role):
        set_role("md_director")
        resp = client.patch(
            self.URL,
            json={"status": "delivered"},
        )
        assert resp.status_code == 403

    def test_not_found_returns_404(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.get_distribution_by_id = AsyncMock(return_value=None)
        mod.distribution_service.update_distribution_status = AsyncMock(return_value=None)

        resp = client.patch(
            "/api/distributions/UNKNOWN/status",
            json={"status": "delivered"},
        )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Distribution not found"

    def test_internal_error_returns_500(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.get_distribution_by_id = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.patch(
            self.URL,
            json={"status": "delivered"},
        )

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestDeleteDistribution:
    URL = "/api/distributions/D1"

    def test_success_cancels_distribution(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.cancel_distribution = AsyncMock(return_value=True)

        resp = client.delete(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Distribution cancelled successfully"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.delete(self.URL)
        assert resp.status_code == 401

    def test_forbidden_md_director_returns_403(self, client, set_role):
        set_role("md_director")
        resp = client.delete(self.URL)
        assert resp.status_code == 403

    def test_not_found_returns_404(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.cancel_distribution = AsyncMock(return_value=False)

        resp = client.delete("/api/distributions/UNKNOWN")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Distribution not found"

    def test_internal_error_returns_500(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.cancel_distribution = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.delete(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestConfirmDistributionReceipt:
    URL = "/api/distributions/D1/receipt"

    def _fake_receipt_confirmed(self):
        return {"distribution_id": "D1", "status": "approved"}

    def test_success_confirms_receipt(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.confirm_receipt = AsyncMock(
            return_value=self._fake_receipt_confirmed()
        )

        resp = client.post(
            self.URL,
            json={"received": True},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Receipt confirmed successfully"
        assert body["data"]["status"] == "approved"

    def test_success_disputes_receipt(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.confirm_receipt = AsyncMock(
            return_value={"distribution_id": "D1", "status": "disputed"}
        )

        resp = client.post(
            self.URL,
            json={"received": False, "notes": "Missing devices"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Receipt disputed successfully"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json={"received": True})
        assert resp.status_code == 401

    def test_forbidden_md_director_returns_403(self, client, set_role):
        set_role("md_director")
        resp = client.post(self.URL, json={"received": True})
        assert resp.status_code == 403

    def test_internal_error_returns_500(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.confirm_receipt = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.post(self.URL, json={"received": True})

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestConfirmDisputedReturn:
    URL = "/api/distributions/D1/confirm-return"

    def _fake_return_confirmed(self):
        return {"distribution_id": "D1", "status": "returned"}

    def test_success_confirms_disputed_return(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.confirm_disputed_return = AsyncMock(
            return_value=self._fake_return_confirmed()
        )

        resp = client.post(self.URL, json={})

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Disputed return confirmed successfully"
        assert body["data"]["status"] == "returned"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json={})
        assert resp.status_code == 401

    def test_forbidden_non_management_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.post(self.URL, json={})
        assert resp.status_code == 403

    def test_forbidden_md_director_returns_403(self, client, set_role):
        set_role("md_director")
        resp = client.post(self.URL, json={})
        assert resp.status_code == 403

    def test_internal_error_returns_500(self, client, mock_distribution_services):
        import app.routes.distributions as mod

        mod.distribution_service.confirm_disputed_return = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.post(self.URL, json={})

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()
