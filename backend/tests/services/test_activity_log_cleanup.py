from unittest.mock import AsyncMock, patch

import pytest

from app.services.activity_log_cleanup import purge_old_activity_logs


class _FakeResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class _FakeSession:
    def __init__(self):
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params))
        return _FakeResult(1)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_purge_old_activity_logs_targets_auth_noise_in_both_tables():
    session = _FakeSession()
    with patch(
        "app.services.activity_log_cleanup.async_session_factory",
        return_value=session,
    ):
        await purge_old_activity_logs()

    assert len(session.executed) == 2
    api_stmt, api_params = session.executed[0]
    feed_stmt, feed_params = session.executed[1]

    assert "DELETE FROM api_activity_logs" in api_stmt
    assert "path LIKE" in api_stmt and "description LIKE" in api_stmt
    assert "activities" in feed_stmt
    assert feed_params["login_pattern"] == "/api/auth/login%"
    assert feed_params["refresh_pattern"] == "%refresh%"
    assert getattr(session, "committed", False) is True
