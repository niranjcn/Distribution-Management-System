from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from contextlib import asynccontextmanager
import pytest
from jose import JWTError

from app.services.auth_service import (
    _parse_datetime,
    authenticate_user,
    create_user_token,
    refresh_access_token,
    blacklist_token,
    is_token_blacklisted,
    get_current_user_from_token,
    complete_forced_credential_update,
    change_user_password,
)


@pytest.fixture
def mock_auth_db(mock_db):
    @asynccontextmanager
    async def _fake():
        yield mock_db
    patcher = patch("app.services.auth_service.get_db", _fake)
    patcher.start()
    yield mock_db
    patcher.stop()


@pytest.fixture
def sample_user():
    return {
        "id": "1",
        "email": "admin@test.com",
        "name": "Admin",
        "role": "super_admin",
        "password_hash": "hashed_pass",
        "force_email_change": 0,
        "force_password_change": 0,
        "failed_login_attempts": 0,
        "locked_until": None,
        "permissions": "{}",
        "status": "active",
    }


class TestParseDatetime:
    def test_valid_iso(self):
        dt = _parse_datetime("2025-06-01T10:00:00")
        assert dt is not None
        assert dt.year == 2025

    def test_valid_iso_zulu(self):
        dt = _parse_datetime("2025-06-01T10:00:00Z")
        assert dt is not None

    def test_none_value(self):
        assert _parse_datetime("not-a-date") is None

    def test_empty_string(self):
        assert _parse_datetime("") is None


class TestAuthenticateUser:
    async def test_success(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        with patch("app.services.auth_service.verify_password", return_value=True):
            result = await authenticate_user("admin@test.com", "pass")
        assert result is not None
        assert result["email"] == "admin@test.com"

    async def test_user_not_found(self, mock_auth_db):
        mock_auth_db.add_result(fetchone_result=None)
        result = await authenticate_user("nonexist@test.com", "pass")
        assert result is None

    async def test_wrong_password(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        with patch("app.services.auth_service.verify_password", return_value=False):
            result = await authenticate_user("admin@test.com", "wrong")
        assert result is None

    async def test_locked_account(self, mock_auth_db, sample_user):
        locked_user = dict(sample_user)
        locked_user["locked_until"] = (datetime.now() + timedelta(hours=1)).isoformat()
        mock_auth_db.add_result(fetchone_result=locked_user)
        from fastapi import HTTPException
        with patch("app.services.auth_service.verify_password", return_value=True):
            with pytest.raises(HTTPException) as exc:
                await authenticate_user("admin@test.com", "pass")
        assert exc.value.status_code == 423

    async def test_max_attempts_locks(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        with patch("app.services.auth_service.verify_password", return_value=False):
            result = await authenticate_user("admin@test.com", "wrong")
        assert result is None
        assert "failed_login_attempts" in mock_auth_db.executed_queries[1]

    async def test_expired_lock_clears(self, mock_auth_db, sample_user):
        locked_user = dict(sample_user)
        locked_user["locked_until"] = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_auth_db.add_result(fetchone_result=locked_user)
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        with patch("app.services.auth_service.verify_password", return_value=True):
            mock_auth_db.add_result(fetchone_result=None, rowcount=1)
            mock_auth_db.add_result(fetchone_result=None, rowcount=1)
            result = await authenticate_user("admin@test.com", "pass")
        assert result is not None


class TestCreateUserToken:
    async def test_returns_token_payload(self, sample_user):
        with (
            patch("app.services.auth_service.create_access_token", return_value="access123"),
            patch("app.services.auth_service.create_refresh_token", return_value="refresh123"),
        ):
            result = await create_user_token(sample_user)
        assert result["access_token"] == "access123"
        assert result["refresh_token"] == "refresh123"
        assert result["token_type"] == "bearer"
        assert result["user"]["id"] == "1"

    async def test_force_flags(self, sample_user):
        forced_user = dict(sample_user, force_email_change=1, force_password_change=1)
        with (
            patch("app.services.auth_service.create_access_token", return_value="tok"),
            patch("app.services.auth_service.create_refresh_token", return_value="rtok"),
        ):
            result = await create_user_token(forced_user)
        assert result["user"]["force_email_change"] is True
        assert result["user"]["force_password_change"] is True


class TestRefreshAccessToken:
    async def test_success(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        with (
            patch("app.services.auth_service.verify_token_type", return_value=True),
            patch("app.services.auth_service.is_token_blacklisted", return_value=False),
            patch("app.services.auth_service.jwt.decode", return_value={"sub": "1"}),
            patch("app.services.auth_service.create_access_token", return_value="new_access"),
        ):
            result = await refresh_access_token("valid_refresh")
        assert result["access_token"] == "new_access"

    async def test_wrong_token_type(self, mock_auth_db):
        with patch("app.services.auth_service.verify_token_type", return_value=False):
            result = await refresh_access_token("bad_token")
        assert result is None

    async def test_blacklisted(self, mock_auth_db):
        with (
            patch("app.services.auth_service.verify_token_type", return_value=True),
            patch("app.services.auth_service.is_token_blacklisted", return_value=True),
        ):
            result = await refresh_access_token("blacklisted")
        assert result is None

    async def test_invalid_jwt(self, mock_auth_db):
        with (
            patch("app.services.auth_service.verify_token_type", return_value=True),
            patch("app.services.auth_service.is_token_blacklisted", return_value=False),
            patch("app.services.auth_service.jwt.decode", side_effect=JWTError),
        ):
            result = await refresh_access_token("bad_jwt")
        assert result is None

    async def test_user_not_found(self, mock_auth_db):
        mock_auth_db.add_result(fetchone_result=None)
        with (
            patch("app.services.auth_service.verify_token_type", return_value=True),
            patch("app.services.auth_service.is_token_blacklisted", return_value=False),
            patch("app.services.auth_service.jwt.decode", return_value={"sub": "999"}),
        ):
            result = await refresh_access_token("tok")
        assert result is None

    async def test_inactive_user(self, mock_auth_db, sample_user):
        inactive_user = dict(sample_user, status="inactive")
        mock_auth_db.add_result(fetchone_result=inactive_user)
        with (
            patch("app.services.auth_service.verify_token_type", return_value=True),
            patch("app.services.auth_service.is_token_blacklisted", return_value=False),
            patch("app.services.auth_service.jwt.decode", return_value={"sub": "1"}),
        ):
            result = await refresh_access_token("tok")
        assert result is None


class TestBlacklistToken:
    async def test_blacklists_and_cleans(self, mock_auth_db):
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        with patch("app.services.auth_service.jwt.decode", return_value={"exp": datetime.now().timestamp() + 3600}):
            await blacklist_token("some_token")
        assert "INSERT OR IGNORE INTO token_blacklist" in mock_auth_db.executed_queries[0]

    async def test_fallback_expiry_on_decode_failure(self, mock_auth_db):
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        with patch("app.services.auth_service.jwt.decode", side_effect=JWTError):
            await blacklist_token("bad_token")
        assert "INSERT OR IGNORE INTO token_blacklist" in mock_auth_db.executed_queries[0]


class TestIsTokenBlacklisted:
    async def test_returns_true_when_found(self, mock_auth_db):
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        mock_auth_db.add_result(fetchone_result=(1,))
        result = await is_token_blacklisted("token")
        assert result is True

    async def test_returns_false_when_not_found(self, mock_auth_db):
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        mock_auth_db.add_result(fetchone_result=None)
        result = await is_token_blacklisted("clean_token")
        assert result is False


class TestGetCurrentUserFromToken:
    async def test_success(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        token_data = type("TokenData", (), {"user_id": "1", "role": "super_admin"})()
        with (
            patch("app.services.auth_service.is_token_blacklisted", return_value=False),
            patch("app.services.auth_service.decode_token", return_value=token_data),
        ):
            result = await get_current_user_from_token("valid_token")
        assert result is not None
        assert "password_hash" not in result

    async def test_blacklisted(self, mock_auth_db):
        with patch("app.services.auth_service.is_token_blacklisted", return_value=True):
            result = await get_current_user_from_token("blacklisted")
        assert result is None

    async def test_decode_failure(self, mock_auth_db):
        with (
            patch("app.services.auth_service.is_token_blacklisted", return_value=False),
            patch("app.services.auth_service.decode_token", return_value=None),
        ):
            result = await get_current_user_from_token("bad")
        assert result is None

    async def test_role_mismatch(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        token_data = type("TokenData", (), {"user_id": "1", "role": "manager"})()
        with (
            patch("app.services.auth_service.is_token_blacklisted", return_value=False),
            patch("app.services.auth_service.decode_token", return_value=token_data),
        ):
            result = await get_current_user_from_token("mismatch")
        assert result is None


class TestCompleteForcedCredentialUpdate:
    async def test_success(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        mock_auth_db.add_result(fetchone_result=None)
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        mock_auth_db.add_result(fetchone_result=sample_user)
        with (
            patch("app.services.auth_service.verify_password", side_effect=[True, False]),
            patch("app.services.auth_service.get_password_hash", return_value="new_hash"),
        ):
            result = await complete_forced_credential_update("1", "curr_pass", "new@email.com", "new_pass")
        assert result is not None

    async def test_user_not_found(self, mock_auth_db):
        mock_auth_db.add_result(fetchone_result=None)
        result = await complete_forced_credential_update("999", "pass", "e@t.com", "new")
        assert result is None

    async def test_wrong_current_password(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        with patch("app.services.auth_service.verify_password", return_value=False):
            result = await complete_forced_credential_update("1", "wrong", "e@t.com", "new")
        assert result is None

    async def test_same_email_raises(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        from fastapi import HTTPException
        with (
            patch("app.services.auth_service.verify_password", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            await complete_forced_credential_update("1", "pass", "admin@test.com", "new")
        assert exc.value.status_code == 400

    async def test_duplicate_email_raises(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        mock_auth_db.add_result(fetchone_result=(2,))
        from fastapi import HTTPException
        with (
            patch("app.services.auth_service.verify_password", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            await complete_forced_credential_update("1", "pass", "other@test.com", "new")
        assert exc.value.status_code == 400

    async def test_same_password_raises(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        mock_auth_db.add_result(fetchone_result=None)
        from fastapi import HTTPException
        with (
            patch("app.services.auth_service.verify_password", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            await complete_forced_credential_update("1", "pass", "other@test.com", "hashed_pass")
        assert exc.value.status_code == 400


class TestChangeUserPassword:
    async def test_success(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        mock_auth_db.add_result(fetchone_result=None, rowcount=1)
        with (
            patch("app.services.auth_service.verify_password", return_value=True),
            patch("app.services.auth_service.get_password_hash", return_value="new_hash"),
        ):
            result = await change_user_password("1", "old_pass", "new_pass")
        assert result is True

    async def test_user_not_found(self, mock_auth_db):
        mock_auth_db.add_result(fetchone_result=None)
        result = await change_user_password("999", "pass", "new")
        assert result is False

    async def test_wrong_current_password(self, mock_auth_db, sample_user):
        mock_auth_db.add_result(fetchone_result=sample_user)
        with patch("app.services.auth_service.verify_password", return_value=False):
            result = await change_user_password("1", "wrong", "new")
        assert result is False
