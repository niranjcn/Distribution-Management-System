from unittest.mock import AsyncMock
import pytest


class TestGetNotifications:
    URL = "/api/notifications"

    def _fake_notification_list(self):
        return {
            "data": [
                {"id": "N1", "title": "New distribution", "is_read": False},
            ],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        }

    def test_success_returns_notifications(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.get_notifications = AsyncMock(
            return_value=self._fake_notification_list()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Notifications retrieved successfully"
        assert "data" in body
        assert "pagination" in body

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.get_notifications = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetUnreadCount:
    URL = "/api/notifications/unread"

    def test_success_returns_unread_count(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.get_unread_count = AsyncMock(return_value=5)

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Unread count retrieved"
        assert body["data"]["count"] == 5

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.get_unread_count = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestGetLatestNotifications:
    URL = "/api/notifications/latest"

    def _fake_latest(self):
        return [
            {"id": "N1", "title": "New distribution", "is_read": False},
            {"id": "N2", "title": "Device assigned", "is_read": True},
        ]

    def test_success_returns_latest(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.get_latest_notifications = AsyncMock(
            return_value=self._fake_latest()
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Latest notifications retrieved"
        assert len(body["data"]) == 2

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.get_latest_notifications = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.get(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestMarkAsRead:
    URL = "/api/notifications/N1/read"

    def test_success_marks_as_read(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.mark_as_read = AsyncMock(return_value=True)

        resp = client.patch(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Notification marked as read"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.patch(self.URL)
        assert resp.status_code == 401

    def test_not_found_returns_404(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.mark_as_read = AsyncMock(return_value=False)

        resp = client.patch("/api/notifications/UNKNOWN/read")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Notification not found"

    def test_internal_error_returns_500(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.mark_as_read = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.patch(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestMarkAllAsRead:
    URL = "/api/notifications/read-all"

    def test_success_marks_all_as_read(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.mark_all_as_read = AsyncMock(return_value=3)

        resp = client.patch(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "3 notifications marked as read"
        assert body["data"]["count"] == 3

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.patch(self.URL)
        assert resp.status_code == 401

    def test_internal_error_returns_500(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.mark_all_as_read = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.patch(self.URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestDeleteNotification:
    URL = "/api/notifications/N1"

    def test_success_deletes_notification(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.delete_notification = AsyncMock(return_value=True)

        resp = client.delete(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Notification deleted successfully"

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.delete(self.URL)
        assert resp.status_code == 401

    def test_not_found_returns_404(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.delete_notification = AsyncMock(return_value=False)

        resp = client.delete("/api/notifications/UNKNOWN")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Notification not found"

    def test_internal_error_returns_500(self, client, mock_notification_services):
        import app.routes.notifications as mod

        mod.notification_service.delete_notification = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        resp = client.delete(self.URL)
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()
