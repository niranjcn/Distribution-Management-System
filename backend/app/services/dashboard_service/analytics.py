from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import asyncio

from app.database_sqlalchemy import async_session_factory
from sqlalchemy import text
from app.core.cache import cached
from app.services import device_service, user_service, defect_service, return_service, distribution_service

from .helpers import (
    _build_named_date_filter,
    _month_start,
    _shift_months,
    _active_inactive_from_status_counts,
    _get_device_status_counts_for_holder,
    _resolve_scope_root_for_sub_distribution_manager,
    _get_descendant_user_ids,
    _get_user_status_split_by_role,
)
from .kpi import get_system_alerts


async def get_advanced_dashboard_metrics(user: Dict[str, Any],
                                         start_date: Optional[str] = None,
                                         end_date: Optional[str] = None) -> Dict[str, Any]:
    cache_key = f"advanced_metrics:{user.get('_id', user.get('id', ''))}:{user.get('role')}:{start_date}:{end_date}"
    return await cached(ttl_seconds=30, key=cache_key, factory=lambda: _compute_advanced_dashboard_metrics(user, start_date, end_date))


async def _compute_advanced_dashboard_metrics(user: Dict[str, Any],
                                              start_date: Optional[str] = None,
                                              end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get advanced analytics payload for management dashboards."""
    role = user.get("role")
    user_id = str(user.get("_id", user.get("id", "")))
    scope_root_id = _resolve_scope_root_for_sub_distribution_manager(user, user_id)

    if role not in ["super_admin", "md_director", "manager", "pdic_staff", "sub_distribution_manager", "sub_distributor", "cluster", "operator"]:
        return {"kpis": {}, "charts": {}, "alerts": [], "reliability": {"summary": {}, "trend": []}}

    # Role-scoped advanced payload for non-management dashboards.
    if role in ["sub_distribution_manager", "sub_distributor", "cluster", "operator"]:
        async with async_session_factory() as session:
            if role == "sub_distribution_manager":
                scope_ids = sorted({scope_root_id} | await _get_descendant_user_ids(session, scope_root_id))
                if scope_ids:
                    sid_params = {f"sid{i}": sid for i, sid in enumerate(scope_ids)}
                    sid_placeholders = ", ".join(f":sid{i}" for i in range(len(scope_ids)))
                    result = await session.execute(
                        text(f"SELECT status, COUNT(*) AS total FROM devices WHERE current_holder_id IN ({sid_placeholders}) GROUP BY status"),
                        sid_params
                    )
                    rows = result.mappings().all()
                else:
                    rows = []
                my_device_status = {str(row["status"]): int(row["total"]) for row in rows}
            else:
                my_device_status = await _get_device_status_counts_for_holder(session, user_id)
            my_device_active_split = _active_inactive_from_status_counts(my_device_status)

            charts = {
                "my_device_status": my_device_status,
                "my_device_active_split": my_device_active_split,
            }
            kpis = {
                "my_total_devices": int(sum(my_device_status.values())),
                "my_active_devices": int(my_device_active_split.get("active", 0)),
                "my_inactive_devices": int(my_device_active_split.get("inactive", 0)),
            }

            if role in ["sub_distribution_manager", "sub_distributor"]:
                if role == "sub_distribution_manager":
                    result = await session.execute(
                        text("""
                            SELECT id
                            FROM users
                            WHERE role = 'cluster'
                                AND (
                                    parent_id = :root_id
                                    OR parent_id IN (
                                        SELECT id FROM users WHERE role = 'sub_distribution_manager' AND parent_id = :root_id
                                    )
                                )
                        """),
                        {"root_id": int(scope_root_id)}
                    )
                    cluster_ids = [int(row[0]) for row in result.all()]
                    if cluster_ids:
                        cid_params = {f"cid{i}": cid for i, cid in enumerate(cluster_ids)}
                        cid_placeholders = ", ".join(f":cid{i}" for i in range(len(cluster_ids)))
                        result = await session.execute(
                            text(f"""
                                SELECT
                                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_total,
                                    SUM(CASE WHEN status != 'active' THEN 1 ELSE 0 END) AS inactive_total
                                FROM users
                                WHERE role = 'cluster' AND id IN ({cid_placeholders})
                            """),
                            cid_params
                        )
                        cs_row = result.mappings().first()
                        cluster_status_split = {
                            "active": int((cs_row["active_total"] if cs_row and cs_row["active_total"] is not None else 0)),
                            "inactive": int((cs_row["inactive_total"] if cs_row and cs_row["inactive_total"] is not None else 0)),
                        }
                    else:
                        cluster_status_split = {"active": 0, "inactive": 0}
                else:
                    cluster_status_split = await _get_user_status_split_by_role(session, "cluster", user_id)
                    result = await session.execute(
                        text("SELECT id FROM users WHERE role = 'cluster' AND parent_id = :uid"),
                        {"uid": int(user_id)}
                    )
                    cluster_ids = [int(row[0]) for row in result.all()]

                if cluster_ids:
                    op_params = {f"cid{i}": cid for i, cid in enumerate(cluster_ids)}
                    op_placeholders = ", ".join(f":cid{i}" for i in range(len(cluster_ids)))
                    result = await session.execute(
                        text(f"""
                            SELECT
                                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_total,
                                SUM(CASE WHEN status != 'active' THEN 1 ELSE 0 END) AS inactive_total
                            FROM users
                            WHERE role = 'operator' AND parent_id IN ({op_placeholders})
                        """),
                        op_params
                    )
                    op_row = result.mappings().first()
                    operator_status_split = {
                        "active": int((op_row["active_total"] if op_row and op_row["active_total"] is not None else 0)),
                        "inactive": int((op_row["inactive_total"] if op_row and op_row["inactive_total"] is not None else 0)),
                    }
                else:
                    operator_status_split = {"active": 0, "inactive": 0}

                charts["cluster_account_active_split"] = cluster_status_split
                charts["operator_account_active_split"] = operator_status_split
                kpis["my_total_clusters"] = int(cluster_status_split["active"] + cluster_status_split["inactive"])
                kpis["my_total_operators"] = int(operator_status_split["active"] + operator_status_split["inactive"])

            elif role == "cluster":
                operator_status_split = await _get_user_status_split_by_role(session, "operator", user_id)
                charts["operator_account_active_split"] = operator_status_split
                kpis["my_total_operators"] = int(operator_status_split["active"] + operator_status_split["inactive"])

            elif role == "operator":
                is_active = int(user.get("status", "active") == "active")
                charts["operator_account_active_split"] = {
                    "active": is_active,
                    "inactive": 0 if is_active else 1,
                }

        return {
            "kpis": kpis,
            "charts": charts,
            "alerts": [],
            "reliability": {"summary": {}, "trend": []},
        }

    now = datetime.now().replace(tzinfo=None)
    month_start = _month_start(now)
    year_start = datetime(now.year, 1, 1)

    effective_start = start_date or month_start.isoformat()
    effective_year_start = start_date or year_start.isoformat()

    device_stats, user_stats, defect_stats, return_stats, dist_stats, alerts = await asyncio.gather(
        device_service.get_device_stats(start_date, end_date),
        user_service.get_user_stats(),
        defect_service.get_defect_stats(start_date, end_date),
        return_service.get_return_stats(start_date, end_date),
        distribution_service.get_distribution_stats(start_date, end_date),
        get_system_alerts(user),
    )
    approval_stats = {"total_pending": 0, "approved": 0, "rejected": 0}

    async with async_session_factory() as session:
        # Defect month/year totals (respect range if provided)
        dm_params = {}
        dm_cond = _build_named_date_filter(dm_params, effective_start, end_date)
        defects_this_month = (await session.execute(text(f"SELECT COUNT(*) FROM defects WHERE {dm_cond}"), dm_params)).scalar() or 0

        dy_params = {}
        dy_cond = _build_named_date_filter(dy_params, effective_year_start, end_date)
        defects_this_year = (await session.execute(text(f"SELECT COUNT(*) FROM defects WHERE {dy_cond}"), dy_params)).scalar() or 0

        # Replacement metrics (current state - no date filter)
        replacements_total = (await session.execute(
            text("SELECT COUNT(*) FROM defects WHERE replacement_device_id IS NOT NULL")
        )).scalar() or 0

        replacements_confirmed = (await session.execute(
            text("""SELECT COUNT(*) FROM defects
               WHERE replacement_device_id IS NOT NULL
               AND replacement_confirmed_at IS NOT NULL""")
        )).scalar() or 0

        replacements_pending = (await session.execute(
            text("""SELECT COUNT(*) FROM defects
               WHERE replacement_device_id IS NOT NULL
               AND replacement_confirmed_at IS NULL""")
        )).scalar() or 0

        # Role totals (current state - no date filter)
        result = await session.execute(
            text("SELECT role, COUNT(*) AS total FROM users GROUP BY role")
        )
        role_rows = result.all()
        role_counts = {str(r[0]): int(r[1]) for r in role_rows}

        result = await session.execute(
            text("""
            SELECT
                role,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_total,
                SUM(CASE WHEN status != 'active' THEN 1 ELSE 0 END) AS inactive_total
            FROM users
            WHERE role IN ('sub_distributor', 'cluster', 'operator')
            GROUP BY role
            """)
        )
        role_status_rows = result.all()
        role_status_splits = {
            str(row[0]): {
                "active": int(row[1] or 0),
                "inactive": int(row[2] or 0),
            }
            for row in role_status_rows
        }

        # Device status distribution (current state - no date filter)
        result = await session.execute(
            text("SELECT status, COUNT(*) AS total FROM devices GROUP BY status")
        )
        device_rows = result.all()
        device_status_counts = {str(r[0]): int(r[1]) for r in device_rows}

        result = await session.execute(
            text("""
            SELECT u.role, d.status, COUNT(*) AS total
            FROM devices d
            INNER JOIN users u
                ON d.current_holder_id = u.id
            WHERE u.role IN ('sub_distributor', 'cluster', 'operator')
            GROUP BY u.role, d.status
            """)
        )
        holder_rows = result.all()
        holder_role_status_counts = {
            "sub_distributor": {},
            "cluster": {},
            "operator": {},
        }
        for row in holder_rows:
            holder_role = str(row[0])
            status_name = str(row[1])
            total = int(row[2])
            holder_role_status_counts.setdefault(holder_role, {})[status_name] = total

        # Monthly defect/distribution trend (aggregated, not N+1)
        defect_trend = []
        distribution_trend = []

        if not (start_date or end_date):
            trend_start = _shift_months(month_start, -11)
            trend_end = _shift_months(month_start, 1)

            t_params = {"t_start": trend_start.isoformat(), "t_end": trend_end.isoformat()}

            result = await session.execute(
                text("SELECT SUBSTRING(created_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE created_at >= :t_start AND created_at < :t_end GROUP BY SUBSTRING(created_at, 1, 7) ORDER BY m"),
                t_params
            )
            reported_by_month = {str(row["m"]): int(row["total"]) for row in result.mappings().all()}

            result = await session.execute(
                text("SELECT SUBSTRING(resolved_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE status = 'resolved' AND resolved_at >= :t_start AND resolved_at < :t_end GROUP BY SUBSTRING(resolved_at, 1, 7) ORDER BY m"),
                t_params
            )
            resolved_by_month = {str(row["m"]): int(row["total"]) for row in result.mappings().all()}

            result = await session.execute(
                text("SELECT SUBSTRING(return_approved_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE replacement_device_id IS NOT NULL AND return_approved_at >= :t_start AND return_approved_at < :t_end GROUP BY SUBSTRING(return_approved_at, 1, 7) ORDER BY m"),
                t_params
            )
            replaced_by_month = {str(row["m"]): int(row["total"]) for row in result.mappings().all()}

            result = await session.execute(
                text("SELECT SUBSTRING(created_at, 1, 7) AS m, COUNT(*) AS total, SUM(CASE WHEN status IN ('approved', 'delivered') THEN 1 ELSE 0 END) AS delivered FROM distributions WHERE created_at >= :t_start AND created_at < :t_end GROUP BY SUBSTRING(created_at, 1, 7) ORDER BY m"),
                t_params
            )
            dist_by_month = {str(row["m"]): {"total": int(row["total"]), "delivered": int(row["delivered"])} for row in result.mappings().all()}

            for i in range(11, -1, -1):
                start = _shift_months(month_start, -i)
                month_key = start.strftime("%Y-%m")
                defect_trend.append({
                    "month": start.strftime("%b"),
                    "reported": reported_by_month.get(month_key, 0),
                    "resolved": resolved_by_month.get(month_key, 0),
                    "replaced": replaced_by_month.get(month_key, 0),
                })
                dist_data = dist_by_month.get(month_key, {"total": 0, "delivered": 0})
                distribution_trend.append({
                    "month": start.strftime("%b"),
                    "total": dist_data["total"],
                    "delivered": dist_data["delivered"],
                })

        # If date range provided, add a single aggregated entry
        if start_date or end_date:
            df_params = {}
            df_cond = _build_named_date_filter(df_params, start_date, end_date)
            reported_total = (await session.execute(text(f"SELECT COUNT(*) FROM defects WHERE {df_cond}"), df_params)).scalar() or 0

            rs_params = {}
            rs_conds = ["status = 'resolved'"]
            if start_date:
                rs_conds.append("resolved_at >= :rs_start")
                rs_params["rs_start"] = start_date
            if end_date:
                rs_conds.append("resolved_at <= :rs_end")
                rs_params["rs_end"] = end_date
            resolved_total = (await session.execute(text(f"SELECT COUNT(*) FROM defects WHERE {' AND '.join(rs_conds)}"), rs_params)).scalar() or 0

            rp_params = {}
            rp_conds = ["replacement_device_id IS NOT NULL"]
            if start_date:
                rp_conds.append("return_approved_at >= :rp_start")
                rp_params["rp_start"] = start_date
            if end_date:
                rp_conds.append("return_approved_at <= :rp_end")
                rp_params["rp_end"] = end_date
            replaced_total = (await session.execute(text(f"SELECT COUNT(*) FROM defects WHERE {' AND '.join(rp_conds)}"), rp_params)).scalar() or 0

            defect_trend.append({
                "month": "Filtered",
                "reported": reported_total,
                "resolved": resolved_total,
                "replaced": replaced_total,
            })

            total_dist = (await session.execute(text(f"SELECT COUNT(*) FROM distributions WHERE {df_cond}"), df_params)).scalar() or 0

            dd_params = {}
            dd_conds = ["status IN ('approved', 'delivered')"]
            if start_date:
                dd_conds.append("created_at >= :dd_start")
                dd_params["dd_start"] = start_date
            if end_date:
                dd_conds.append("created_at <= :dd_end")
                dd_params["dd_end"] = end_date
            delivered_total = (await session.execute(text(f"SELECT COUNT(*) FROM distributions WHERE {' AND '.join(dd_conds)}"), dd_params)).scalar() or 0

            distribution_trend.append({
                "month": "Filtered",
                "total": total_dist,
                "delivered": delivered_total,
            })

        # Reliability analytics used by Defect Incidence cards
        reliability_start = start_date or (now - timedelta(days=60)).isoformat()
        if not start_date:
            reliability_start = (now - timedelta(days=60)).isoformat()

        rl_params = {}
        rl_cond = _build_named_date_filter(rl_params, reliability_start, end_date)
        defects_last_60_days = int((await session.execute(text(f"SELECT COUNT(*) FROM defects WHERE {rl_cond}"), rl_params)).scalar() or 0)

        # Build resolved_at-based date filter for repair rate queries
        rr_params = {}
        rr_conds = ["1=1"]
        if start_date:
            rr_conds.append("resolved_at >= :rr_start")
            rr_params["rr_start"] = start_date
        if end_date:
            rr_conds.append("resolved_at <= :rr_end")
            rr_params["rr_end"] = end_date
        rr_cond = " AND ".join(rr_conds)

        repaired_within_sla_devices = int((await session.execute(
            text(f"""SELECT COUNT(*) FROM defects
               WHERE resolved_at IS NOT NULL
               AND TIMESTAMPDIFF(
                   DAY,
                   STR_TO_DATE(SUBSTRING(REPLACE(created_at, 'T', ' '), 1, 19), '%%Y-%%m-%%d %%H:%%i:%%s'),
                   STR_TO_DATE(SUBSTRING(REPLACE(resolved_at, 'T', ' '), 1, 19), '%%Y-%%m-%%d %%H:%%i:%%s')
               ) <= 60
               AND {rr_cond}"""), rr_params
        )).scalar() or 0)

        total_resolved_defects = int((await session.execute(
            text(f"SELECT COUNT(*) FROM defects WHERE resolved_at IS NOT NULL AND {rr_cond}"), rr_params
        )).scalar() or 0)

        total_devices_for_reliability = int(device_stats.get("total", 0))
        defect_incidence_percentage = (
            round((defects_last_60_days / total_devices_for_reliability) * 100, 2)
            if total_devices_for_reliability > 0 else 0.0
        )
        repaired_within_sla_percentage = (
            round((repaired_within_sla_devices / total_resolved_defects) * 100, 2)
            if total_resolved_defects > 0 else 0.0
        )

    active_devices = (
        device_stats.get("available", 0) +
        device_stats.get("distributed", 0) +
        device_stats.get("in_use", 0)
    )
    total_devices = int(device_stats.get("total", 0))
    inactive_devices = max(0, total_devices - active_devices)

    replacement_success_rate = (
        round((replacements_confirmed / replacements_total) * 100, 2)
        if replacements_total > 0 else 0
    )

    management_kpis = {
        "total_devices": total_devices,
        "active_devices": active_devices,
        "inactive_devices": inactive_devices,
        "total_users": int(user_stats.get("total", 0)),
        "total_staff": int(role_counts.get("pdic_staff", 0)),
        "total_operators": int(role_counts.get("operator", 0)),
        "total_sub_distributors": int(role_counts.get("sub_distributor", 0)),
        "total_clusters": int(role_counts.get("cluster", 0)),
        "defects_this_month": int(defects_this_month),
        "defects_this_year": int(defects_this_year),
        "replacements_total": int(replacements_total),
        "replacements_confirmed": int(replacements_confirmed),
        "replacements_pending": int(replacements_pending),
        "replacement_success_rate": replacement_success_rate,
        "pending_approvals": int(approval_stats.get("total_pending", 0)),
        "pending_receipts": int(dist_stats.get("pending_receipt", 0)),
    }

    charts = {
        "device_status": {
            "available": int(device_status_counts.get("available", 0)),
            "distributed": int(device_status_counts.get("distributed", 0)),
            "in_use": int(device_status_counts.get("in_use", 0)),
            "defective": int(device_status_counts.get("defective", 0)),
            "returned": int(device_status_counts.get("returned", 0)),
        },
        "device_active_split": {
            "active": active_devices,
            "inactive": inactive_devices,
        },
        "user_roles": {
            "pdic_staff": int(role_counts.get("pdic_staff", 0)),
            "sub_distributor": int(role_counts.get("sub_distributor", 0)),
            "cluster": int(role_counts.get("cluster", 0)),
            "operator": int(role_counts.get("operator", 0)),
            "manager": int(role_counts.get("manager", 0)),
            "super_admin": int(role_counts.get("super_admin", 0)),
        },
        "defect_severity": {
            "critical": int(defect_stats.get("by_severity", {}).get("critical", 0)),
            "high": int(defect_stats.get("by_severity", {}).get("high", 0)),
            "medium": int(defect_stats.get("by_severity", {}).get("medium", 0)),
            "low": int(defect_stats.get("by_severity", {}).get("low", 0)),
        },
        "defect_trend_12m": defect_trend,
        "distribution_trend_12m": distribution_trend,
        "replacement_pipeline": {
            "replaced": int(replacements_total),
            "confirmed": int(replacements_confirmed),
            "pending_confirmation": int(replacements_pending),
        },
        "returns_by_status": {
            "pending": int(return_stats.get("by_status", {}).get("pending", 0)),
            "approved": int(return_stats.get("by_status", {}).get("approved", 0)),
            "received": int(return_stats.get("by_status", {}).get("received", 0)),
            "rejected": int(return_stats.get("by_status", {}).get("rejected", 0)),
        },
        "sub_distributor_account_active_split": role_status_splits.get("sub_distributor", {"active": 0, "inactive": 0}),
        "cluster_account_active_split": role_status_splits.get("cluster", {"active": 0, "inactive": 0}),
        "operator_account_active_split": role_status_splits.get("operator", {"active": 0, "inactive": 0}),
        "sub_distributor_device_active_split": _active_inactive_from_status_counts(
            holder_role_status_counts.get("sub_distributor", {})
        ),
        "cluster_device_active_split": _active_inactive_from_status_counts(
            holder_role_status_counts.get("cluster", {})
        ),
        "operator_device_active_split": _active_inactive_from_status_counts(
            holder_role_status_counts.get("operator", {})
        ),
        "pending_action_queue": {
            "approvals": int(approval_stats.get("total_pending", 0)),
            "receipts": int(dist_stats.get("pending_receipt", 0)),
            "returns": int(return_stats.get("by_status", {}).get("pending", 0)),
        },
    }

    # Staff should not get governance-only user-role visibility for admin/manager counts.
    if role == "pdic_staff":
        charts["user_roles"].pop("super_admin", None)
        charts["user_roles"].pop("manager", None)

    return {
        "kpis": management_kpis,
        "charts": charts,
        "alerts": alerts,
        "reliability": {
            "summary": {
                "defect_incidence_percentage": defect_incidence_percentage,
                "repaired_within_sla_devices": repaired_within_sla_devices,
                "repaired_within_sla_percentage": repaired_within_sla_percentage,
                "defects_last_60_days": defects_last_60_days,
                "total_resolved_defects": total_resolved_defects,
            },
            "trend": defect_trend,
        },
    }


async def get_distribution_device_analytics(start_date: Optional[str] = None,
                                            end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get distribution device analytics: sent, remaining, by type and manufacturer (cached)."""
    cache_key = f"distribution_device_analytics:{start_date}:{end_date}"
    return await cached(ttl_seconds=30, key=cache_key, factory=lambda: _compute_distribution_device_analytics(start_date, end_date))


async def _compute_distribution_device_analytics(start_date: Optional[str] = None,
                                                 end_date: Optional[str] = None) -> Dict[str, Any]:
    async with async_session_factory() as session:
        base_cond = "status IN ('distributed', 'in_use')"
        dd_params = {}
        date_filter = _build_named_date_filter(dd_params, start_date, end_date)
        date_cond = f"{base_cond} AND {date_filter}" if date_filter != "1=1" else base_cond

        result = await session.execute(
            text(f"""SELECT
                   COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown') AS device_type,
                   COUNT(*) AS total
               FROM devices
               WHERE {date_cond}
               GROUP BY COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown')
               ORDER BY total DESC"""),
            dd_params
        )
        sent_by_type_rows = result.mappings().all()

        total_sent = (await session.execute(
            text(f"SELECT COUNT(*) FROM devices WHERE {date_cond}"), dd_params
        )).scalar() or 0

        remaining_available = (await session.execute(
            text("SELECT COUNT(*) FROM devices WHERE status = 'available'")
        )).scalar() or 0

        result = await session.execute(
            text("""SELECT
                   COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown') AS device_type,
                   COUNT(*) AS total
               FROM devices
               WHERE status = 'available'
               GROUP BY COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown')
               ORDER BY total DESC""")
        )
        remaining_by_type_rows = result.mappings().all()

        result = await session.execute(
            text(f"""SELECT
                   COALESCE(NULLIF(TRIM(manufacturer), ''), 'Unknown') AS manufacturer,
                   COUNT(*) AS total
               FROM devices
               WHERE {date_cond}
               GROUP BY COALESCE(NULLIF(TRIM(manufacturer), ''), 'Unknown')
               ORDER BY total DESC"""),
            dd_params
        )
        by_manufacturer_rows = result.mappings().all()

        per_holder_cond = date_cond.replace("status IN ('distributed', 'in_use')", "d.status IN ('distributed', 'in_use')")
        per_holder_cond = per_holder_cond.replace("created_at", "d.created_at")
        result = await session.execute(
            text(f"""SELECT
                   d.current_holder_id AS holder_id,
                   COALESCE(NULLIF(TRIM(d.current_holder_name), ''), 'Unknown') AS holder_name,
                   COALESCE(NULLIF(TRIM(d.device_type), ''), 'Unknown') AS device_type,
                   COUNT(*) AS total
               FROM devices d
                INNER JOIN users u ON d.current_holder_id = u.id AND u.role = 'sub_distributor'
                WHERE {per_holder_cond}
                AND d.current_holder_id IS NOT NULL
                GROUP BY
                    d.current_holder_id,
                    COALESCE(NULLIF(TRIM(d.current_holder_name), ''), 'Unknown'),
                    COALESCE(NULLIF(TRIM(d.device_type), ''), 'Unknown')
                ORDER BY holder_name, device_type"""),
            dd_params
        )
        per_holder_rows = result.mappings().all()

        result = await session.execute(
            text("""SELECT
                   d.current_holder_id AS holder_id,
                   COALESCE(NULLIF(TRIM(d.current_holder_name), ''), 'Unknown') AS holder_name,
                   COUNT(*) AS total
               FROM devices d
                INNER JOIN users u ON d.current_holder_id = u.id AND u.role = 'sub_distributor'
                WHERE d.status = 'available'
               AND d.current_holder_id IS NOT NULL
               GROUP BY
                   d.current_holder_id,
                   COALESCE(NULLIF(TRIM(d.current_holder_name), ''), 'Unknown')
               ORDER BY total DESC""")
        )
        per_holder_available_rows = result.mappings().all()

    remaining_by_type: Dict[str, int] = {
        row["device_type"]: int(row["total"]) for row in remaining_by_type_rows
    }
    sent_by_type = [
        {
            "device_type": row["device_type"],
            "sent": int(row["total"]),
            "remaining": remaining_by_type.get(row["device_type"], 0),
        }
        for row in sent_by_type_rows
    ]

    by_manufacturer = [
        {"manufacturer": row["manufacturer"], "total": int(row["total"])}
        for row in by_manufacturer_rows
    ]

    holder_map: Dict[str, Dict[str, Any]] = {}
    for row in per_holder_rows:
        hid = row["holder_id"]
        if hid not in holder_map:
            holder_map[hid] = {
                "holder_id": hid,
                "holder_name": row["holder_name"],
                "total_sent": 0,
                "by_type": {},
            }
        count = int(row["total"])
        holder_map[hid]["total_sent"] += count
        holder_map[hid]["by_type"][row["device_type"]] = (
            holder_map[hid]["by_type"].get(row["device_type"], 0) + count
        )

    available_map: Dict[str, int] = {}
    for row in per_holder_available_rows:
        available_map[row["holder_id"]] = int(row["total"])

    per_holder = []
    for hid, payload in holder_map.items():
        per_holder.append({
            "holder_id": hid,
            "holder_name": payload["holder_name"],
            "total_sent": payload["total_sent"],
            "remaining_available": available_map.get(hid, 0),
            "type_breakdown": [
                {"device_type": dt, "count": c}
                for dt, c in sorted(payload["by_type"].items(), key=lambda x: x[1], reverse=True)
            ],
        })
    per_holder.sort(key=lambda x: x["total_sent"], reverse=True)

    return {
        "total_sent_to_distribution": total_sent,
        "remaining_available_devices": remaining_available,
        "sent_by_type": sent_by_type,
        "by_manufacturer": by_manufacturer,
        "per_holder_breakdown": per_holder,
    }
