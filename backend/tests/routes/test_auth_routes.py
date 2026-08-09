from unittest.mock import AsyncMock, patch
import pytest


class TestLogin:
    LOGIN_URL = "/api/auth/login"

    def _fake_user(self, **overrides):
        return {
            "id": "1",
            "_id": "1",
            "email": "admin@test.com",
            "name": "Admin",
            "role": "super_admin",
            "status": "active",
            **overrides,
        }

    def _fake_token(self):
        return {
            "access_token": "eyJfake.access.token",
            "refresh_token": "eyJfake.refresh.token",
            "token_type": "bearer",
            "expires_in": 3600,
            "refresh_expires_in": 604800,
            "user": {
                "id": "1",
                "email": "admin@test.com",
                "name": "Admin",
                "role": "super_admin",
                "force_email_change": False,
                "force_password_change": False,
            },
        }

    # ---------- success ----------

    def test_successful_login_returns_200(self, client, mock_auth_services):
        import app.routes.auth as auth_mod

        auth_mod.auth_service.authenticate_user = AsyncMock(
            return_value=self._fake_user()
        )
        auth_mod.auth_service.create_user_token = AsyncMock(
            return_value=self._fake_token()
        )

        resp = client.post(
            self.LOGIN_URL,
            json={"email": "admin@test.com", "password": "correct_password"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Login successful"
        assert body["data"]["access_token"] == "eyJfake.access.token"
        assert body["data"]["token_type"] == "bearer"
        assert body["data"]["user"]["email"] == "admin@test.com"
        assert body["data"]["user"]["role"] == "super_admin"

    def test_successful_login_calls_authenticate_user(self, client, mock_auth_services):
        import app.routes.auth as auth_mod

        auth_mod.auth_service.authenticate_user = AsyncMock(
            return_value=self._fake_user()
        )
        auth_mod.auth_service.create_user_token = AsyncMock(
            return_value=self._fake_token()
        )

        client.post(
            self.LOGIN_URL,
            json={"email": "admin@test.com", "password": "correct_password"},
        )

        auth_mod.auth_service.authenticate_user.assert_awaited_once_with(
            "admin@test.com", "correct_password"
        )

    # ---------- 4xx errors ----------

    def test_invalid_credentials_returns_401(self, client, mock_auth_services):
        import app.routes.auth as auth_mod

        auth_mod.auth_service.authenticate_user = AsyncMock(return_value=None)

        resp = client.post(
            self.LOGIN_URL,
            json={"email": "wrong@test.com", "password": "wrong_password"},
        )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    def test_inactive_user_returns_403(self, client, mock_auth_services):
        import app.routes.auth as auth_mod

        auth_mod.auth_service.authenticate_user = AsyncMock(
            return_value=self._fake_user(status="inactive")
        )

        resp = client.post(
            self.LOGIN_URL,
            json={"email": "inactive@test.com", "password": "any_password"},
        )

        assert resp.status_code == 403
        assert resp.json()["detail"] == "Account is not active"

    def test_invalid_email_format_returns_422(self, client, mock_auth_services):
        resp = client.post(
            self.LOGIN_URL,
            json={"email": "not-an-email", "password": "test"},
        )

        assert resp.status_code == 422

    def test_missing_password_field_returns_422(self, client, mock_auth_services):
        resp = client.post(
            self.LOGIN_URL,
            json={"email": "admin@test.com"},
        )

        assert resp.status_code == 422

    def test_empty_request_body_returns_422(self, client, mock_auth_services):
        resp = client.post(self.LOGIN_URL, json={})

        assert resp.status_code == 422

    # ---------- cookies ----------

    def test_sets_http_only_cookies(self, client, mock_auth_services):
        import app.routes.auth as auth_mod

        auth_mod.auth_service.authenticate_user = AsyncMock(
            return_value=self._fake_user()
        )
        auth_mod.auth_service.create_user_token = AsyncMock(
            return_value=self._fake_token()
        )

        resp = client.post(
            self.LOGIN_URL,
            json={"email": "admin@test.com", "password": "correct_password"},
        )

        set_cookie = resp.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "refresh_token=" in set_cookie
        assert "HttpOnly" in set_cookie

    # ---------- 5xx ----------

    def test_internal_error_returns_500(self, client, mock_auth_services):
        import app.routes.auth as auth_mod

        auth_mod.auth_service.authenticate_user = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        resp = client.post(
            self.LOGIN_URL,
            json={"email": "admin@test.com", "password": "password"},
        )

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestMe:
    ME_URL = "/api/auth/me"

    def test_authenticated_returns_user(self, client):
        resp = client.get(self.ME_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["email"] == "admin@test.com"
        assert body["data"]["role"] == "super_admin"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.ME_URL)
        assert resp.status_code == 401

    def test_refresh_token_cookie_returns_401(self, client, test_app):
        # A refresh token placed in the access_token cookie must NOT authenticate.
        from app.middleware.auth_middleware import get_current_user
        from app.utils.security import create_refresh_token

        test_app.dependency_overrides.pop(get_current_user, None)
        refresh = create_refresh_token({
            "sub": "1",
            "email": "admin@test.com",
            "role": "super_admin",
            "name": "Admin",
        })
        with patch("app.services.auth_service.is_token_blacklisted", new=AsyncMock(return_value=False)):
            resp = client.get(self.ME_URL, cookies={"access_token": refresh})
        assert resp.status_code == 401

    def test_refresh_token_bearer_header_returns_401(self, client, test_app):
        # The same protection applies when the refresh token is presented as
        # an Authorization: Bearer credential.
        from app.middleware.auth_middleware import get_current_user
        from app.utils.security import create_refresh_token

        test_app.dependency_overrides.pop(get_current_user, None)
        refresh = create_refresh_token({
            "sub": "1",
            "email": "admin@test.com",
            "role": "super_admin",
            "name": "Admin",
        })
        with patch("app.services.auth_service.is_token_blacklisted", new=AsyncMock(return_value=False)):
            resp = client.get(self.ME_URL, headers={"Authorization": f"Bearer {refresh}"})
        assert resp.status_code == 401


class TestRefresh:
    REFRESH_URL = "/api/auth/refresh"

    def test_missing_refresh_token_returns_401(self, client, mock_auth_services):
        import app.routes.auth as auth_mod

        auth_mod.auth_service.refresh_access_token = AsyncMock(return_value=None)

        resp = client.post(
            self.REFRESH_URL, json={"refresh_token": "invalid_or_expired"}
        )

        assert resp.status_code == 401
        assert "Invalid or expired" in resp.json()["detail"]

    def test_valid_refresh_returns_tokens(self, client, mock_auth_services):
        import app.routes.auth as auth_mod

        auth_mod.auth_service.refresh_access_token = AsyncMock(
            return_value={
                "access_token": "new.access.token",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        )

        resp = client.post(
            self.REFRESH_URL, json={"refresh_token": "valid.refresh.token"}
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_internal_error_on_refresh_returns_500(self, client, mock_auth_services):
        import app.routes.auth as auth_mod

        auth_mod.auth_service.refresh_access_token = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.post(
            self.REFRESH_URL, json={"refresh_token": "any.token"}
        )

        assert resp.status_code == 500
