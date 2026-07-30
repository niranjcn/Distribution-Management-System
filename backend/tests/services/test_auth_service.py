from datetime import datetime, timedelta
from unittest.mock import patch
import pytest
from jose import JWTError

from app.services.auth_service import (
    _parse_datetime,
    create_user_token,
)


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
