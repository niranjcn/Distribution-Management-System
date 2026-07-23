from unittest.mock import AsyncMock
import pytest


class TestSubmitChangeRequest:
    URL = "/api/change-requests"
    VALID_PAYLOAD = {
        "request_type": "email_change",
        "new_email": "new@test.com",
    }

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_forbidden_for_cluster(self, client, set_role):
        set_role("cluster")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_forbidden_for_sub_distributor(self, client, set_role):
        set_role("sub_distributor")
        resp = client.post(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403


class TestListChangeRequests:
    URL = "/api/change-requests"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_forbidden_for_pdic_staff(self, client, set_role):
        set_role("pdic_staff")
        resp = client.get(self.URL)
        assert resp.status_code == 403


class TestReviewChangeRequest:
    URL = "/api/change-requests/CR-001/review"
    VALID_PAYLOAD = {"action": "approve"}

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user
        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_forbidden_for_operator(self, client, set_role):
        set_role("operator")
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_forbidden_for_pdic_staff(self, client, set_role):
        set_role("pdic_staff")
        resp = client.patch(self.URL, json=self.VALID_PAYLOAD)
        assert resp.status_code == 403
