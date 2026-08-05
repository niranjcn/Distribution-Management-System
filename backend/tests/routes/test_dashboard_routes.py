from unittest.mock import AsyncMock
import pytest


class TestDashboardStats:
    STATS_URL = "/api/dashboard/stats"

    # ---------- success ----------

    def test_authenticated_returns_stats(self, client, mock_dashboard_services):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_dashboard_stats = AsyncMock(
            return_value={
                "my_devices": 42,
                "available_devices": 30,
                "defect_reports": 5,
            }
        )

        resp = client.get(self.STATS_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["my_devices"] == 42
        assert body["data"]["available_devices"] == 30

    def test_passes_date_params_to_service(self, client, mock_dashboard_services):
        from unittest.mock import ANY
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_dashboard_stats = AsyncMock(
            return_value={"my_devices": 10}
        )

        client.get(self.STATS_URL, params={"start_date": "2025-01-01", "end_date": "2025-06-30"})

        dash_mod.dashboard_service.get_dashboard_stats.assert_awaited_once_with(
            ANY, "2025-01-01", "2025-06-30"
        )

    # ---------- 4xx ----------

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.STATS_URL)
        assert resp.status_code == 401

    # ---------- 5xx ----------

    def test_service_error_returns_500(self, client, mock_dashboard_services):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_dashboard_stats = AsyncMock(
            side_effect=RuntimeError("Stats service error")
        )

        resp = client.get(self.STATS_URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestDashboardRecentActivities:
    RECENT_URL = "/api/dashboard/recent-activities"

    def test_returns_activities(self, client, mock_dashboard_services):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_recent_activities = AsyncMock(
            return_value=[
                {"action": "login", "actor": "Admin", "timestamp": "2025-01-01T00:00:00"}
            ]
        )

        resp = client.get(self.RECENT_URL)

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert len(resp.json()["data"]) == 1

    def test_passes_limit_param(self, client, mock_dashboard_services):
        from unittest.mock import ANY
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_recent_activities = AsyncMock(return_value=[])

        client.get(self.RECENT_URL, params={"limit": 5})

        dash_mod.dashboard_service.get_recent_activities.assert_awaited_once_with(
            ANY, 5
        )


class TestDashboardAdminActivities:
    ACTIVITIES_URL = "/api/dashboard/activities"

    def _fake_result(self, page=1, page_size=10, total=25):
        data = [
            {
                "id": f"device-{i}",
                "category": "device",
                "action": "registered",
                "actor": "Admin",
                "description": f"Activity {i}",
                "date": f"2025-01-{i + 1:02d}T00:00:00",
                "link": None,
            }
            for i in range(1, 6)
        ]
        return {
            "data": data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }

    def test_success_returns_activities(self, client, mock_dashboard_services):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_admin_activities = AsyncMock(
            return_value=self._fake_result()
        )

        resp = client.get(self.ACTIVITIES_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Activities retrieved successfully"
        assert len(body["data"]) == 5
        assert body["pagination"]["total"] == 25

    def test_passes_pagination_and_filters(self, client, mock_dashboard_services):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_admin_activities = AsyncMock(
            return_value=self._fake_result()
        )

        client.get(
            self.ACTIVITIES_URL,
            params={
                "page": 2,
                "page_size": 50,
                "actor": "Admin",
                "category": "device",
                "search": "registered",
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
            },
        )

        dash_mod.dashboard_service.get_admin_activities.assert_awaited_once_with(
            page=2,
            page_size=50,
            actor="Admin",
            category="device",
            search="registered",
            start_date="2025-01-01",
            end_date="2025-01-31",
        )

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.ACTIVITIES_URL)
        assert resp.status_code == 401

    def test_service_error_returns_500(self, client, mock_dashboard_services):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_admin_activities = AsyncMock(
            side_effect=RuntimeError("Activities service error")
        )

        resp = client.get(self.ACTIVITIES_URL)

        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestDashboardUserKpi:
    KPI_URL = "/api/dashboard/user-kpi/10"

    def test_returns_kpi(self, client, mock_dashboard_services):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_user_kpi = AsyncMock(
            return_value={
                "user": {"id": "10", "name": "SubDist", "role": "sub_distributor"},
                "kpis": {"devices_in_hand": 5},
                "charts": {},
            }
        )

        resp = client.get(self.KPI_URL, params={"start_date": "2025-01-01"})

        assert resp.status_code == 200
        assert resp.json()["data"]["kpis"]["devices_in_hand"] == 5

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.KPI_URL)
        assert resp.status_code == 401


class TestDashboardAdvancedMetrics:
    METRICS_URL = "/api/dashboard/advanced-metrics"

    def test_returns_metrics(self, client, mock_dashboard_services):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_advanced_dashboard_metrics = AsyncMock(
            return_value={
                "kpis": {"total_devices": 100},
                "charts": {},
                "alerts": [],
                "reliability": {"summary": {}, "trend": []},
            }
        )

        resp = client.get(self.METRICS_URL)

        assert resp.status_code == 200
        assert resp.json()["data"]["kpis"]["total_devices"] == 100

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.METRICS_URL)
        assert resp.status_code == 401


class TestDashboardDistributionDeviceAnalytics:
    ANALYTICS_URL = "/api/dashboard/distribution-device-analytics"

    def test_returns_analytics(self, client, mock_dashboard_services):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_distribution_device_analytics = AsyncMock(
            return_value={
                "sent_by_type": [{"device_type": "ONT", "total": 10}],
                "total_sent": 10,
                "remaining_available": 5,
            }
        )

        resp = client.get(self.ANALYTICS_URL)

        assert resp.status_code == 200
        assert resp.json()["data"]["total_sent"] == 10

    def test_manager_can_access(self, client, mock_dashboard_services, set_role):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_distribution_device_analytics = AsyncMock(
            return_value={"total_sent": 3}
        )
        set_role("manager")

        resp = client.get(self.ANALYTICS_URL)

        assert resp.status_code == 200
        assert resp.json()["data"]["total_sent"] == 3

    def test_operator_forbidden(self, client, mock_dashboard_services, set_role):
        import app.routes.dashboard as dash_mod

        dash_mod.dashboard_service.get_distribution_device_analytics = AsyncMock(
            return_value={"total_sent": 3}
        )
        set_role("operator")

        resp = client.get(self.ANALYTICS_URL)

        assert resp.status_code == 403
