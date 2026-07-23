from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.services.dashboard_service import (
    _build_date_filter,
    _active_inactive_from_status_counts,
    _month_start,
    _shift_months,
    _resolve_scope_root_for_sub_distribution_manager,
    get_dashboard_stats,
    get_recent_activities,
    get_scope_users,
    get_user_kpi,
    get_system_alerts,
    get_advanced_dashboard_metrics,
    get_distribution_device_analytics,
)


# ---------------------------------------------------------------------------
# Pure-function unit tests (no mocks needed)
# ---------------------------------------------------------------------------

class TestBuildDateFilter:
    def test_no_dates(self):
        cond, params = _build_date_filter("1=1", (), None, None)
        assert cond == "1=1"
        assert params == ()

    def test_start_date_only(self):
        cond, params = _build_date_filter("status = ?", ("active",), "2025-01-01", None)
        assert "created_at >= ?" in cond
        assert "2025-01-01" in params

    def test_end_date_only(self):
        cond, params = _build_date_filter("status = ?", ("active",), None, "2025-12-31")
        assert "created_at <= ?" in cond
        assert "2025-12-31" in params

    def test_both_dates(self):
        cond, params = _build_date_filter("1=1", (), "2025-01-01", "2025-12-31")
        assert "created_at >= ?" in cond
        assert "created_at <= ?" in cond
        assert "2025-01-01" in params
        assert "2025-12-31" in params

    def test_base_params_preserved(self):
        cond, params = _build_date_filter("holder_id = ?", ("42",), "2025-06-01", None)
        assert "holder_id = ?" in cond
        assert "42" in params
        assert "2025-06-01" in params


class TestActiveInactiveFromStatusCounts:
    def test_all_active(self):
        result = _active_inactive_from_status_counts(
            {"available": 10, "distributed": 5, "in_use": 3}
        )
        assert result == {"active": 18, "inactive": 0}

    def test_all_inactive(self):
        result = _active_inactive_from_status_counts(
            {"defective": 4, "returned": 2, "maintenance": 1}
        )
        assert result == {"active": 0, "inactive": 7}

    def test_mixed(self):
        result = _active_inactive_from_status_counts(
            {"available": 8, "defective": 3, "in_use": 2}
        )
        assert result == {"active": 10, "inactive": 3}

    def test_empty(self):
        result = _active_inactive_from_status_counts({})
        assert result == {"active": 0, "inactive": 0}


class TestMonthStart:
    def test_mid_month(self):
        result = _month_start(datetime(2025, 6, 15))
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 1

    def test_january(self):
        result = _month_start(datetime(2025, 1, 31))
        assert result.month == 1
        assert result.day == 1


class TestShiftMonths:
    def test_next_month(self):
        result = _shift_months(datetime(2025, 1, 1), 1)
        assert result.month == 2

    def test_previous_month(self):
        result = _shift_months(datetime(2025, 3, 1), -1)
        assert result.month == 2

    def test_year_wrap_forward(self):
        result = _shift_months(datetime(2025, 12, 1), 1)
        assert result.year == 2026
        assert result.month == 1

    def test_year_wrap_backward(self):
        result = _shift_months(datetime(2025, 1, 1), -1)
        assert result.year == 2024
        assert result.month == 12


class TestResolveScopeRootForSubDistributionManager:
    def test_not_sdm_returns_own_id(self):
        result = _resolve_scope_root_for_sub_distribution_manager(
            {"role": "cluster", "parent_id": "10"}, "15"
        )
        assert result == "15"

    def test_sdm_with_parent_returns_parent(self):
        result = _resolve_scope_root_for_sub_distribution_manager(
            {"role": "sub_distribution_manager", "parent_id": "10"}, "15"
        )
        assert result == "10"

    def test_sdm_no_parent_returns_own_id(self):
        result = _resolve_scope_root_for_sub_distribution_manager(
            {"role": "sub_distribution_manager", "parent_id": ""}, "15"
        )
        assert result == "15"


# ---------------------------------------------------------------------------
# Integration tests (mock DB + mock service dependencies)
# ---------------------------------------------------------------------------

class TestGetDashboardStats:
    """Covers every role branch in get_dashboard_stats."""

    async def test_super_admin(self, mock_get_db, mock_services, super_admin_user):
        svc = mock_services["device_service"]
        svc.get_device_stats = AsyncMock(return_value={
            "total": 100, "available": 50, "distributed": 30, "in_use": 10,
            "defective": 5, "returned": 3,
        })

        svc = mock_services["distribution_service"]
        svc.get_distribution_stats = AsyncMock(return_value={
            "total": 20, "pending": 5, "approved": 10, "delivered": 3,
            "rejected": 2, "pending_receipt": 1,
        })

        svc = mock_services["defect_service"]
        svc.get_defect_stats = AsyncMock(return_value={
            "total": 8, "by_status": {"reported": 3, "under_review": 2, "resolved": 3},
        })

        svc = mock_services["return_service"]
        svc.get_return_stats = AsyncMock(return_value={
            "total": 6, "by_status": {"pending": 2, "approved": 2, "received": 1, "rejected": 1},
        })

        svc = mock_services["user_service"]
        svc.get_user_stats = AsyncMock(return_value={"total": 50, "active": 40})

        svc = mock_services["approval_service"]
        svc.get_approval_stats = AsyncMock(return_value={"total_pending": 3, "approved": 5, "rejected": 1})

        mock_get_db.add_result(fetchone_result=(15,))
        mock_get_db.add_result(fetchone_result=(2,))
        mock_get_db.add_result(fetchone_result=(5,))

        result = await get_dashboard_stats(super_admin_user)

        assert result["total_devices"] == 100
        assert result["total_active_devices"] == 90
        assert result["total_distributed_devices"] == 40
        assert result["total_defective_devices"] == 5
        assert result["total_replaced_devices"] == 5
        assert result["replacements_in_range"] == 2
        assert result["distribution_this_month"] == 15

    async def test_sub_distributor(self, mock_get_db, sub_distributor_user):
        mock_get_db.add_result(fetchone_result=(12,))
        mock_get_db.add_result(fetchone_result=(5,))
        mock_get_db.add_result(fetchone_result=(7,))
        mock_get_db.add_result(fetchone_result=(10,))
        mock_get_db.add_result(fetchone_result=(3,))
        mock_get_db.add_result(fetchall_result=[(100,), (101,)])
        mock_get_db.add_result(fetchall_result=[(200,), (201,)])
        mock_get_db.add_result(fetchone_result=(4,))

        result = await get_dashboard_stats(sub_distributor_user)

        assert result["my_devices"] == 12
        assert result["available_devices"] == 5
        assert result["distributions_sent"] == 7
        assert result["distributions_received"] == 10
        assert result["pending_distributions"] == 3
        assert result["operator_count"] == 4

    async def test_sub_distribution_manager(self, mock_get_db, sub_distribution_manager_user):
        mock_get_db.add_result(fetchall_result=[{"id": 21}])
        mock_get_db.add_result(fetchall_result=[])
        mock_get_db.add_result(fetchone_result=(25,))
        mock_get_db.add_result(fetchone_result=(8,))
        mock_get_db.add_result(fetchone_result=(5,))
        mock_get_db.add_result(fetchone_result=(6,))
        mock_get_db.add_result(fetchone_result=(2,))
        mock_get_db.add_result(fetchone_result=(3,))
        mock_get_db.add_result(fetchone_result=(2,))
        mock_get_db.add_result(fetchone_result=(1,))

        result = await get_dashboard_stats(sub_distribution_manager_user)
        assert result["my_devices"] == 25
        assert result["available_devices"] == 8
        assert result["defect_reports"] == 2
        assert result["return_requests"] == 1

    async def test_cluster(self, mock_get_db, mock_services, cluster_user):
        mock_get_db.add_result(fetchone_result=(5,))
        mock_get_db.add_result(fetchone_result=(3,))
        mock_get_db.add_result(fetchone_result=(4,))

        svc = mock_services["operator_service"]
        svc.get_operator_stats = AsyncMock(return_value={"total": 2, "active": 2})

        result = await get_dashboard_stats(cluster_user)
        assert result["my_devices"] == 5
        assert result["distributions_sent"] == 3
        assert result["distributions_received"] == 4
        assert result["operators"] == {"total": 2, "active": 2}

    async def test_operator(self, mock_get_db, operator_user):
        mock_get_db.add_result(fetchone_result=(3,))
        mock_get_db.add_result(fetchone_result=(1,))
        mock_get_db.add_result(fetchone_result=(2,))

        result = await get_dashboard_stats(operator_user)
        assert result["my_devices"] == 3
        assert result["my_defects"] == 1
        assert result["my_returns"] == 2


class TestGetRecentActivities:
    async def test_super_admin(self, mock_get_db, super_admin_user):
        mock_get_db.add_result(fetchall_result=[
            {"id": 1, "action": "distributed", "performed_by_name": "Admin",
             "timestamp": "2025-06-01T10:00:00", "performed_by": "1",
             "from_user_id": "1", "to_user_id": "2"},
        ])

        result = await get_recent_activities(super_admin_user)
        assert len(result) == 1
        assert result[0]["action"] == "distributed"
        assert result[0]["user_name"] == "Admin"

    async def test_operator_scoped(self, mock_get_db, operator_user):
        mock_get_db.add_result(fetchall_result=[
            {"id": 2, "action": "received", "performed_by_name": "Operator",
             "timestamp": "2025-06-02T12:00:00", "performed_by": "40",
             "from_user_id": "40", "to_user_id": "41"},
        ])

        result = await get_recent_activities(operator_user)
        assert len(result) == 1
        assert result[0]["action"] == "received"


class TestGetScopeUsers:
    async def test_super_admin(self, mock_get_db, super_admin_user):
        mock_get_db.add_result(fetchall_result=[
            {"id": 10, "email": "sd@t.com", "name": "SD1", "role": "sub_distributor", "parent_id": "1"},
            {"id": 20, "email": "cl@t.com", "name": "CL1", "role": "cluster", "parent_id": "10"},
            {"id": 30, "email": "op@t.com", "name": "OP1", "role": "operator", "parent_id": "20"},
        ])
        result = await get_scope_users(super_admin_user)
        assert len(result["sub_distributors"]) == 1
        assert len(result["clusters"]) == 1
        assert len(result["operators"]) == 1

    async def test_cluster(self, mock_get_db, cluster_user):
        mock_get_db.add_result(fetchall_result=[
            {"id": 40, "email": "op1@t.com", "name": "OP1", "role": "operator", "parent_id": "30"},
        ])
        result = await get_scope_users(cluster_user)
        assert len(result["sub_distributors"]) == 0
        assert len(result["operators"]) == 1

    async def test_operator_returns_empty(self, mock_get_db, operator_user):
        result = await get_scope_users(operator_user)
        assert result == {"sub_distributors": [], "clusters": [], "operators": []}


class TestGetUserKpi:
    async def test_valid_user(self, mock_get_db, super_admin_user):
        target_user_id = "10"
        mock_get_db.add_result(fetchone_result={"id": 10, "email": "sd@t.com", "name": "SD1", "role": "sub_distributor"})
        mock_get_db.add_result(fetchone_result=(5,))
        mock_get_db.add_result(fetchall_result=[{"id": 20}])
        mock_get_db.add_result(fetchall_result=[])
        mock_get_db.add_result(fetchone_result=(15,))
        mock_get_db.add_result(fetchall_result=[
            ("available", 8), ("distributed", 5), ("defective", 2),
        ])
        mock_get_db.add_result(fetchone_result=(7,))
        mock_get_db.add_result(fetchone_result=(3,))

        for _ in range(24):
            mock_get_db.add_result(fetchone_result=(0,))

        result = await get_user_kpi(super_admin_user, target_user_id)
        assert result["user"]["id"] == "10"
        assert result["kpis"]["devices_in_hand"] == 5
        assert result["kpis"]["devices_in_hierarchy"] == 15
        assert result["kpis"]["hierarchy_active_devices"] == 13
        assert result["kpis"]["distributed_count"] == 7
        assert result["kpis"]["total_defects"] == 3

    async def test_nonexistent_user_returns_empty(self, mock_get_db, super_admin_user):
        mock_get_db.add_result(fetchone_result=None)
        result = await get_user_kpi(super_admin_user, "999")
        assert result == {"user": {}, "kpis": {}, "charts": {}}


class TestGetSystemAlerts:
    async def test_no_alerts(self, mock_get_db, super_admin_user):
        mock_get_db.add_result(fetchone_result=(0,))
        mock_get_db.add_result(fetchone_result=(0,))
        mock_get_db.add_result(fetchone_result=(100,))

        result = await get_system_alerts(super_admin_user)
        assert result == []

    async def test_critical_defects_alert(self, mock_get_db, super_admin_user):
        mock_get_db.add_result(fetchone_result=(3,))
        mock_get_db.add_result(fetchone_result=(0,))
        mock_get_db.add_result(fetchone_result=(100,))

        result = await get_system_alerts(super_admin_user)
        assert any(a["type"] == "error" and "Critical" in a["title"] for a in result)

    async def test_pending_approvals_alert(self, mock_get_db, super_admin_user):
        mock_get_db.add_result(fetchone_result=(0,))
        mock_get_db.add_result(fetchone_result=(5,))
        mock_get_db.add_result(fetchone_result=(100,))

        result = await get_system_alerts(super_admin_user)
        assert any(a["type"] == "warning" and "Pending" in a["title"] for a in result)

    async def test_low_stock_alert(self, mock_get_db, super_admin_user):
        mock_get_db.add_result(fetchone_result=(0,))
        mock_get_db.add_result(fetchone_result=(0,))
        mock_get_db.add_result(fetchone_result=(3,))

        result = await get_system_alerts(super_admin_user)
        assert any(a["type"] == "warning" and "Low" in a["title"] for a in result)

    async def test_non_management_returns_empty(self, mock_get_db, operator_user):
        result = await get_system_alerts(operator_user)
        assert result == []


class TestGetAdvancedDashboardMetrics:
    async def test_management_full_payload(self, mock_get_db, mock_services, super_admin_user):
        svc = mock_services["device_service"]
        svc.get_device_stats = AsyncMock(return_value={
            "total": 100, "available": 50, "distributed": 30, "in_use": 10,
            "defective": 5, "returned": 3,
        })

        svc = mock_services["user_service"]
        svc.get_user_stats = AsyncMock(return_value={"total": 50, "active": 40})

        svc = mock_services["defect_service"]
        svc.get_defect_stats = AsyncMock(return_value={
            "total": 8, "by_status": {"reported": 3, "under_review": 2, "resolved": 3},
        })

        svc = mock_services["return_service"]
        svc.get_return_stats = AsyncMock(return_value={
            "total": 6, "by_status": {"pending": 2, "approved": 2, "received": 1, "rejected": 1},
        })

        svc = mock_services["distribution_service"]
        svc.get_distribution_stats = AsyncMock(return_value={
            "total": 20, "pending": 5, "approved": 10, "delivered": 3,
            "rejected": 2, "pending_receipt": 1,
        })

        svc = mock_services["approval_service"]
        svc.get_approval_stats = AsyncMock(return_value={
            "total_pending": 3, "approved": 5, "rejected": 1, "total": 9,
        })

        with (
            patch("app.services.dashboard_service.get_system_alerts", new=AsyncMock(return_value=[])),
        ):
            mock_get_db.add_result(fetchone_result=(3,))
            mock_get_db.add_result(fetchone_result=(8,))
            mock_get_db.add_result(fetchone_result=(3,))
            mock_get_db.add_result(fetchone_result=(0,))
            mock_get_db.add_result(fetchone_result=(5,))
            mock_get_db.add_result(fetchall_result=[("super_admin", 1), ("sub_distributor", 3)])
            mock_get_db.add_result(fetchall_result=[
                ("sub_distributor", 2, 1), ("cluster", 3, 0),
            ])
            mock_get_db.add_result(fetchall_result=[
                ("available", 50), ("distributed", 30),
            ])
            mock_get_db.add_result(fetchall_result=[
                ("sub_distributor", "available", 10),
                ("cluster", "distributed", 15),
            ])

            for _ in range(60):
                mock_get_db.add_result(fetchone_result=(0,))

            mock_get_db.add_result(fetchone_result=(0,))

            for _ in range(20):
                mock_get_db.add_result(fetchone_result=(0,))

            mock_get_db.add_result(fetchone_result=(5,))
            mock_get_db.add_result(fetchone_result=(3,))
            mock_get_db.add_result(fetchone_result=(2,))

            result = await get_advanced_dashboard_metrics(super_admin_user)

        assert result["kpis"]["total_devices"] == 100
        assert result["kpis"]["total_users"] == 50
        assert "reliability" in result
        assert result["charts"]["user_roles"]["super_admin"] == 1

    async def test_operator_scoped(self, mock_get_db, operator_user):
        mock_get_db.add_result(fetchall_result=[
            ("available", 2), ("in_use", 1),
        ])

        result = await get_advanced_dashboard_metrics(operator_user)
        assert result["kpis"]["my_total_devices"] == 3
        assert result["kpis"]["my_active_devices"] == 3
        assert result["kpis"]["my_inactive_devices"] == 0

    async def test_unknown_role(self):
        user = {"_id": "99", "role": "unknown_role"}
        result = await get_advanced_dashboard_metrics(user)
        assert result == {"kpis": {}, "charts": {}, "alerts": [], "reliability": {"summary": {}, "trend": []}}


class TestGetDistributionDeviceAnalytics:
    async def test_returns_structured_payload(self, mock_get_db):
        mock_get_db.add_result(fetchall_result=[
            {"device_type": "ONT", "total": 20},
            {"device_type": "Router", "total": 10},
        ])
        mock_get_db.add_result(fetchone_result=(30,))
        mock_get_db.add_result(fetchone_result=(50,))
        mock_get_db.add_result(fetchall_result=[
            {"device_type": "ONT", "total": 30},
            {"device_type": "Router", "total": 20},
        ])
        mock_get_db.add_result(fetchall_result=[
            {"manufacturer": "Huawei", "total": 15},
            {"manufacturer": "ZTE", "total": 15},
        ])
        mock_get_db.add_result(fetchall_result=[
            {"holder_id": "10", "holder_name": "SD1", "device_type": "ONT", "total": 8},
            {"holder_id": "10", "holder_name": "SD1", "device_type": "Router", "total": 2},
        ])
        mock_get_db.add_result(fetchall_result=[
            {"holder_id": "10", "holder_name": "SD1", "total": 15},
        ])

        result = await get_distribution_device_analytics()

        assert result["total_sent_to_distribution"] == 30
        assert result["remaining_available_devices"] == 50
        assert len(result["sent_by_type"]) == 2
        assert len(result["by_manufacturer"]) == 2
        assert len(result["per_holder_breakdown"]) == 1
        assert result["per_holder_breakdown"][0]["total_sent"] == 10

    async def test_with_date_filter(self, mock_get_db):
        mock_get_db.add_result(fetchall_result=[{"device_type": "ONT", "total": 5}])
        mock_get_db.add_result(fetchone_result=(5,))
        mock_get_db.add_result(fetchone_result=(50,))
        mock_get_db.add_result(fetchall_result=[{"device_type": "ONT", "total": 30}])
        mock_get_db.add_result(fetchall_result=[{"manufacturer": "Huawei", "total": 5}])
        mock_get_db.add_result(fetchall_result=[])
        mock_get_db.add_result(fetchall_result=[])

        result = await get_distribution_device_analytics("2025-01-01", "2025-06-30")
        assert result["total_sent_to_distribution"] == 5
