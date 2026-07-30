from datetime import datetime

import pytest

from app.core.cache import invalidate_cache
from app.services.dashboard_service import (
    _build_date_filter,
    _active_inactive_from_status_counts,
    _month_start,
    _shift_months,
    _resolve_scope_root_for_sub_distribution_manager,
    get_advanced_dashboard_metrics,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_cache()


class TestBuildDateFilter:
    def test_no_dates(self):
        cond, params = _build_date_filter("1=1", {}, None, None)
        assert cond == "1=1"
        assert params == {}

    def test_start_date_only(self):
        cond, params = _build_date_filter("status = :s", {"s": "active"}, "2025-01-01", None)
        assert "created_at >= :start_date" in cond
        assert params["start_date"] == "2025-01-01"
        assert params["s"] == "active"

    def test_end_date_only(self):
        cond, params = _build_date_filter("status = :s", {"s": "active"}, None, "2025-12-31")
        assert "created_at <= :end_date" in cond
        assert params["end_date"] == "2025-12-31"
        assert params["s"] == "active"

    def test_both_dates(self):
        cond, params = _build_date_filter("1=1", {}, "2025-01-01", "2025-12-31")
        assert "created_at >= :start_date" in cond
        assert "created_at <= :end_date" in cond
        assert params["start_date"] == "2025-01-01"
        assert params["end_date"] == "2025-12-31"

    def test_base_params_preserved(self):
        cond, params = _build_date_filter("holder_id = :hid", {"hid": "42"}, "2025-06-01", None)
        assert "holder_id = :hid" in cond
        assert params["hid"] == "42"
        assert params["start_date"] == "2025-06-01"


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


class TestGetAdvancedDashboardMetrics:
    async def test_unknown_role(self):
        user = {"_id": "99", "role": "unknown_role"}
        result = await get_advanced_dashboard_metrics(user)
        assert result == {"kpis": {}, "charts": {}, "alerts": [], "reliability": {"summary": {}, "trend": []}}
