from unittest.mock import patch
from contextlib import asynccontextmanager
import pytest

from app.services.notification_service import (
    _parse_notification_metadata,
    _parse_notification_list,
    get_notifications,
    get_unread_count,
    get_latest_notifications,
    create_notification,
    mark_as_read,
    mark_all_as_read,
    delete_notification,
    delete_old_notifications,
    send_bulk_notification,
)


@pytest.fixture
def mock_notif_db(mock_db):
    @asynccontextmanager
    async def _fake():
        yield mock_db
    patcher = patch("app.services.notification_service.get_db", _fake)
    patcher.start()
    yield mock_db
    patcher.stop()


class TestParseNotificationMetadata:
    def test_string_metadata_parsed(self):
        n = {"metadata": '{"key": "val"}'}
        result = _parse_notification_metadata(n)
        assert result["metadata"] == {"key": "val"}

    def test_dict_metadata_unchanged(self):
        n = {"metadata": {"key": "val"}}
        result = _parse_notification_metadata(n)
        assert result["metadata"] == {"key": "val"}

    def test_invalid_json_returns_none(self):
        n = {"metadata": "not-json"}
        result = _parse_notification_metadata(n)
        assert result["metadata"] is None

    def test_missing_metadata(self):
        n = {}
        result = _parse_notification_metadata(n)
        assert "metadata" not in result


class TestParseNotificationList:
    def test_empty_list(self):
        assert _parse_notification_list([]) == []

    def test_calls_parse_on_each(self):
        items = [{"metadata": '{"a":1}'}, {"metadata": '{"b":2}'}]
        result = _parse_notification_list(items)
        assert result[0]["metadata"] == {"a": 1}
        assert result[1]["metadata"] == {"b": 2}


class TestGetNotifications:
    async def test_returns_paginated_data(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=(2,))
        mock_notif_db.add_result(fetchall_result=[
            {"id": 1, "user_id": "1", "title": "Test", "message": "Msg", "is_read": 0, "metadata": "{}", "created_at": "2025-01-01T00:00:00"},
            {"id": 2, "user_id": "1", "title": "Test2", "message": "Msg2", "is_read": 1},
        ])
        result = await get_notifications("1")
        assert result["pagination"]["total"] == 2
        assert len(result["data"]) == 2

    async def test_filters_by_is_read(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=(1,))
        mock_notif_db.add_result(fetchall_result=[
            {"id": 3, "user_id": "1", "title": "Unread", "message": "M", "is_read": 0},
        ])
        result = await get_notifications("1", is_read=False)
        assert "user_id" in mock_notif_db.executed_queries[0]

    async def test_empty_returns_no_data(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=(0,))
        result = await get_notifications("99")
        assert result["data"] == []


class TestGetUnreadCount:
    async def test_returns_count(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=(5,))
        count = await get_unread_count("1")
        assert count == 5

    async def test_zero_when_none(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=(0,))
        count = await get_unread_count("1")
        assert count == 0


class TestGetLatestNotifications:
    async def test_returns_list(self, mock_notif_db):
        mock_notif_db.add_result(fetchall_result=[
            {"id": 1, "user_id": "1", "title": "T", "message": "M", "is_read": 0, "metadata": "{}"},
        ])
        result = await get_latest_notifications("1", limit=5)
        assert len(result) == 1
        assert "LIMIT ?" in mock_notif_db.executed_queries[0]

    async def test_empty(self, mock_notif_db):
        mock_notif_db.add_result(fetchall_result=[])
        result = await get_latest_notifications("1")
        assert result == []


class TestCreateNotification:
    async def test_creates_and_returns(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None, rowcount=1, lastrowid=10)
        mock_notif_db.add_result(fetchone_result={"id": "10", "user_id": "1", "title": "Hi", "message": "Test", "metadata": None})
        result = await create_notification("1", "Hi", "Test")
        assert result["id"] == "10"

    async def test_with_metadata(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None, rowcount=1, lastrowid=11)
        mock_notif_db.add_result(fetchone_result={"id": "11", "user_id": "1", "title": "Hi", "message": "Test", "metadata": '{"link":"x"}'})
        result = await create_notification("1", "Hi", "Test", metadata={"link": "x"})
        assert result["id"] == "11"


class TestMarkAsRead:
    async def test_returns_true_when_updated(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None, rowcount=1)
        result = await mark_as_read("1", "1")
        assert result is True

    async def test_returns_false_when_not_found(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None, rowcount=0)
        result = await mark_as_read("999", "1")
        assert result is False


class TestMarkAllAsRead:
    async def test_returns_count(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None, rowcount=3)
        result = await mark_all_as_read("1")
        assert result == 3

    async def test_zero_when_none_unread(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None, rowcount=0)
        result = await mark_all_as_read("1")
        assert result == 0


class TestDeleteNotification:
    async def test_returns_true(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None, rowcount=1)
        result = await delete_notification("1", "1")
        assert result is True

    async def test_returns_false_when_not_found(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None, rowcount=0)
        result = await delete_notification("999", "1")
        assert result is False


class TestDeleteOldNotifications:
    async def test_returns_deleted_count(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None, rowcount=5)
        result = await delete_old_notifications(days=30)
        assert result == 5

    async def test_zero_when_none_old(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None, rowcount=0)
        result = await delete_old_notifications(days=30)
        assert result == 0


class TestSendBulkNotification:
    async def test_sends_to_all_users(self, mock_notif_db):
        mock_notif_db.add_result(fetchone_result=None)
        mock_notif_db.add_result(fetchone_result=None)
        mock_notif_db.add_result(fetchone_result=None)
        result = await send_bulk_notification(["1", "2", "3"], "Title", "Message")
        assert result == 3

    async def test_empty_list(self, mock_notif_db):
        result = await send_bulk_notification([], "Title", "Message")
        assert result == 0
