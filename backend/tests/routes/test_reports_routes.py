from unittest.mock import AsyncMock
import pytest


class TestInventoryReport:
    URL = "/api/reports/inventory"

    def test_super_admin_gets_report(self, client, mock_report_services):
        import app.routes.reports as rep_mod

        rep_mod.report_service.get_inventory_report = AsyncMock(
            return_value={"total_devices": 200, "by_status": {"available": 150}}
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total_devices"] == 200

    def test_passes_date_params(self, client, mock_report_services):
        import app.routes.reports as rep_mod

        rep_mod.report_service.get_inventory_report = AsyncMock(
            return_value={"total_devices": 0}
        )

        client.get(self.URL, params={"start_date": "2025-01-01", "end_date": "2025-03-31"})

        rep_mod.report_service.get_inventory_report.assert_awaited_once_with(
            "2025-01-01", "2025-03-31"
        )

    def test_operator_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403
        assert "Insufficient permissions" in resp.json()["detail"]

    def test_cluster_returns_403(self, client, set_role):
        set_role("cluster")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, client, test_app):
        from app.middleware.auth_middleware import get_current_user

        test_app.dependency_overrides.pop(get_current_user, None)
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_service_error_returns_500(self, client, mock_report_services):
        import app.routes.reports as rep_mod

        rep_mod.report_service.get_inventory_report = AsyncMock(
            side_effect=RuntimeError("Report service error")
        )

        resp = client.get(self.URL)
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


class TestDistributionSummaryReport:
    URL = "/api/reports/distribution-summary"

    def test_super_admin_gets_report(self, client, mock_report_services):
        import app.routes.reports as rep_mod

        rep_mod.report_service.get_distribution_summary = AsyncMock(
            return_value={"total_distributions": 50, "pending": 5}
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["data"]["total_distributions"] == 50

    def test_operator_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403


class TestDefectSummaryReport:
    URL = "/api/reports/defect-summary"

    def test_super_admin_gets_report(self, client, mock_report_services):
        import app.routes.reports as rep_mod

        rep_mod.report_service.get_defect_summary = AsyncMock(
            return_value={"total_defects": 25, "resolved": 20}
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["data"]["total_defects"] == 25

    def test_pdic_staff_gets_report(self, client, set_role, mock_report_services):
        set_role("pdic_staff")

        import app.routes.reports as rep_mod

        rep_mod.report_service.get_defect_summary = AsyncMock(
            return_value={"total_defects": 10}
        )

        resp = client.get(self.URL)
        assert resp.status_code == 200

    def test_operator_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_cluster_returns_403(self, client, set_role):
        set_role("cluster")
        resp = client.get(self.URL)
        assert resp.status_code == 403
        assert "Insufficient permissions" in resp.json()["detail"]


class TestReturnSummaryReport:
    URL = "/api/reports/return-summary"

    def test_super_admin_gets_report(self, client, mock_report_services):
        import app.routes.reports as rep_mod

        rep_mod.report_service.get_return_summary = AsyncMock(
            return_value={"total_returns": 15}
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["data"]["total_returns"] == 15

    def test_operator_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403


class TestUserActivityReport:
    URL = "/api/reports/user-activity"

    def test_super_admin_gets_report(self, client, mock_report_services):
        import app.routes.reports as rep_mod

        rep_mod.report_service.get_user_activity_report = AsyncMock(
            return_value={"total_activities": 100}
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["data"]["total_activities"] == 100

    def test_operator_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403


class TestDeviceUtilizationReport:
    URL = "/api/reports/device-utilization"

    def test_super_admin_gets_report(self, client, mock_report_services):
        import app.routes.reports as rep_mod

        rep_mod.report_service.get_device_utilization_report = AsyncMock(
            return_value={"utilization_rate": 75.5}
        )

        resp = client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["data"]["utilization_rate"] == 75.5

    def test_operator_returns_403(self, client, set_role):
        set_role("operator")
        resp = client.get(self.URL)
        assert resp.status_code == 403
