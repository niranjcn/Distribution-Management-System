from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
import pytest
from jose import JWTError

from app.services.auth_service import (
    _parse_datetime,
    blacklist_token,
    create_user_token,
    get_current_user_from_token,
    refresh_access_token,
)
from app.utils.security import create_access_token, create_refresh_token, decode_token


class _FakeInstance:
    def __init__(self, user_dict):
        self._dict = user_dict

    def to_dict(self):
        return dict(self._dict)


class _FakeSession:
    def __init__(self, user_dict):
        self._user_dict = user_dict

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, model, pk):
        return _FakeInstance(self._user_dict)


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
    async def test_success_rotates_token(self, sample_user):
        with (
            patch("app.services.auth_service.verify_token_type", return_value=True),
            patch(
                "app.services.auth_service.is_token_blacklisted",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("app.services.auth_service.jwt.decode", return_value={"sub": "1"}),
            patch(
                "app.services.auth_service.async_session_factory",
                return_value=_FakeSession(sample_user),
            ),
            patch(
                "app.services.auth_service.blacklist_token",
                new_callable=AsyncMock,
            ) as blacklist,
            patch("app.services.auth_service.create_access_token", return_value="access-new"),
            patch("app.services.auth_service.create_refresh_token", return_value="refresh-new"),
        ):
            result = await refresh_access_token("old-token")

        assert result is not None
        assert result["access_token"] == "access-new"
        assert result["refresh_token"] == "refresh-new"
        assert result["token_type"] == "bearer"
        assert result["expires_in"] > 0
        assert result["refresh_expires_in"] > 0
        blacklist.assert_awaited_once_with("old-token")

    async def test_reuse_of_rotated_token_rejected(self, sample_user):
        with (
            patch("app.services.auth_service.verify_token_type", return_value=True),
            patch(
                "app.services.auth_service.is_token_blacklisted",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.services.auth_service.blacklist_token",
                new_callable=AsyncMock,
            ) as blacklist,
        ):
            result = await refresh_access_token("already-used-token")

        assert result is None
        blacklist.assert_not_awaited()

    async def test_wrong_token_type_rejected(self, sample_user):
        with (
            patch("app.services.auth_service.verify_token_type", return_value=False),
            patch(
                "app.services.auth_service.blacklist_token",
                new_callable=AsyncMock,
            ) as blacklist,
        ):
            result = await refresh_access_token("access-token")

        assert result is None
        blacklist.assert_not_awaited()

    async def test_refresh_rejected_when_concurrent_rotation_wins(self, sample_user):
        with (
            patch("app.services.auth_service.verify_token_type", return_value=True),
            patch(
                "app.services.auth_service.is_token_blacklisted",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("app.services.auth_service.jwt.decode", return_value={"sub": "1"}),
            patch(
                "app.services.auth_service.async_session_factory",
                return_value=_FakeSession(sample_user),
            ),
            patch(
                "app.services.auth_service.blacklist_token",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            result = await refresh_access_token("contested-token")

        assert result is None


class TestBlacklistToken:
    def _token(self):
        return create_refresh_token(data=_token_claims())

    async def test_new_blacklist_returns_true(self):
        token = self._token()

        class _Session:
            def __init__(self):
                self.added = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def add(self, obj):
                self.added.append(obj)

            async def execute(self, stmt, params=None):
                return None

            async def commit(self):
                self.committed = True

        session = _Session()
        with patch("app.services.auth_service.async_session_factory", return_value=session):
            result = await blacklist_token(token)

        assert result is True
        assert session.committed
        assert len(session.added) == 1

    async def test_duplicate_blacklist_returns_false_and_rolls_back(self):
        from sqlalchemy.exc import IntegrityError

        token = self._token()

        class _Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def add(self, obj):
                pass

            async def execute(self, stmt, params=None):
                return None

            async def commit(self):
                raise IntegrityError("stmt", {}, Exception("Duplicate entry"))

            async def rollback(self):
                self.rolled_back = True

        session = _Session()
        with patch("app.services.auth_service.async_session_factory", return_value=session):
            result = await blacklist_token(token)

        assert result is False
        assert session.rolled_back


def _token_claims(**overrides):
    claims = {"sub": "1", "email": "admin@test.com", "role": "super_admin", "name": "Admin"}
    claims.update(overrides)
    return claims


class TestTokenTypeSeparation:
    """Access tokens authenticate; refresh tokens must never be accepted."""

    def test_decode_token_accepts_access_token(self):
        token = create_access_token(data=_token_claims())
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded.user_id == "1"
        assert decoded.role == "super_admin"

    def test_decode_token_rejects_refresh_token(self):
        decoded = decode_token(create_refresh_token(data=_token_claims()))
        assert decoded is None

    async def test_get_current_user_rejects_refresh_token_before_db(self):
        refresh = create_refresh_token(data=_token_claims())
        with (
            patch("app.services.auth_service.is_token_blacklisted", new=AsyncMock(return_value=False)),
            patch("app.services.auth_service.async_session_factory") as sess_factory,
        ):
            result = await get_current_user_from_token(refresh)

        assert result is None
        # Rejection happens during decode, before any DB lookup happens.
        sess_factory.assert_not_called()

    async def test_get_current_user_accepts_access_token(self, sample_user):
        access = create_access_token(data=_token_claims())
        with (
            patch("app.services.auth_service.is_token_blacklisted", new=AsyncMock(return_value=False)),
            patch(
                "app.services.auth_service.async_session_factory",
                return_value=_FakeSession(sample_user),
            ),
        ):
            result = await get_current_user_from_token(access)

        assert result is not None
        assert result["id"] == "1"
        assert result["role"] == "super_admin"
