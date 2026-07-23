from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.database import get_db
from app.services import device_service, user_service, defect_service, return_service, distribution_service, approval_service

from .helpers import (
    _build_date_filter,
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
    """Get advanced analytics payload for management dashboards."""
    role = user.get("role")
    user_id = str(user.get("_id", user.get("id", "")))
    scope_root_id = _resolve_scope_root_for_sub_distribution_manager(user, user_id)

    if role not in ["super_admin", "md_director", "manager", "pdic_staff", "sub_distribution_manager", "sub_distributor", "cluster", "operator"]:
        return {"kpis": {}, "charts": {}, "alerts": [], "reliability": {"summary": {}, "trend": []}}

    # Role-scoped advanced payload for non-management dashboards.
    if role in ["sub_distribution_manager", "sub_distributor", "cluster", "operator"]:
        async with get_db() as db:
            if role == "sub_distribution_manager":
                scope_ids = sorted({scope_root_id} | await _get_descendant_user_ids(db, scope_root_id))
                placeholders = ",".join(["?"] * len(scope_ids)) if scope_ids else "?"
                cursor = await db.execute(
                    f"SELECT status, COUNT(*) AS total FROM devices WHERE current_holder_id IN ({placeholders}) GROUP BY status",
                    tuple(scope_ids)
                )
                rows = await cursor.fetchall()
                my_device_status = {str(row[0]): int(row[1]) for row in rows}
            else:
                my_device_status = await _get_device_status_counts_for_holder(db, user_id)
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
                    cursor = await db.execute(
                                                """
                                                SELECT id
                                                FROM users
                                                WHERE role = 'cluster'
                                                    AND (
                                                        parent_id = ?
                                                        OR parent_id IN (
                                                            SELECT id FROM users WHERE role = 'sub_distribution_manager' AND parent_id = ?
                                                        )
                                                    )
                                                """,
                        (int(scope_root_id), int(scope_root_id))
                    )
                    cluster_rows = await cursor.fetchall()
                    cluster_ids = [int(row[0]) for row in cluster_rows]
                    if cluster_ids:
                        placeholders = ",".join("?" * len(cluster_ids))
                        cursor = await db.execute(
                            f"""
                            SELECT
                                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_total,
                                SUM(CASE WHEN status != 'active' THEN 1 ELSE 0 END) AS inactive_total
                            FROM users
                            WHERE role = 'cluster' AND id IN ({placeholders})
                            """,
                            tuple(cluster_ids)
                        )
                        cs_row = await cursor.fetchone()
                        cluster_status_split = {
                            "active": int((cs_row[0] if cs_row and cs_row[0] is not None else 0)),
                            "inactive": int((cs_row[1] if cs_row and cs_row[1] is not None else 0)),
                        }
                    else:
                        cluster_status_split = {"active": 0, "inactive": 0}
                else:
                    cluster_status_split = await _get_user_status_split_by_role(db, "cluster", user_id)
                    cursor = await db.execute(
                        "SELECT id FROM users WHERE role = 'cluster' AND parent_id = ?",
                        (int(user_id),)
                    )
                    cluster_rows = await cursor.fetchall()
                    cluster_ids = [int(row[0]) for row in cluster_rows]

                if cluster_ids:
                    placeholders = ",".join("?" * len(cluster_ids))
                    cursor = await db.execute(
                        f"""
                        SELECT
                            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_total,
                            SUM(CASE WHEN status != 'active' THEN 1 ELSE 0 END) AS inactive_total
                        FROM users
                        WHERE role = 'operator' AND parent_id IN ({placeholders})
                        """,
                        tuple(cluster_ids)
                    )
                    op_row = await cursor.fetchone()
                    operator_status_split = {
                        "active": int((op_row[0] if op_row and op_row[0] is not None else 0)),
                        "inactive": int((op_row[1] if op_row and op_row[1] is not None else 0)),
                    }
                else:
                    operator_status_split = {"active": 0, "inactive": 0}

                charts["cluster_account_active_split"] = cluster_status_split
                charts["operator_account_active_split"] = operator_status_split
                kpis["my_total_clusters"] = int(cluster_status_split["active"] + cluster_status_split["inactive"])
                kpis["my_total_operators"] = int(operator_status_split["active"] + operator_status_split["inactive"])

            elif role == "cluster":
                operator_status_split = await _get_user_status_split_by_role(db, "operator", user_id)
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

    device_stats = await device_service.get_device_stats(start_date, end_date)
    user_stats = await user_service.get_user_stats()
    defect_stats = await defect_service.get_defect_stats(start_date, end_date)
    return_stats = await return_service.get_return_stats(start_date, end_date)
    dist_stats = await distribution_service.get_distribution_stats(start_date, end_date)
    approval_stats = await approval_service.get_approval_stats()
    alerts = await get_system_alerts(user)

    async with get_db() as db:
        # Defect month/year totals (respect range if provided)
        dc_m, dp_m = _build_date_filter("1=1", (), effective_start, end_date)
        cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {dc_m}", dp_m)
        defects_this_month = (await cursor.fetchone())[0]

        dc_y, dp_y = _build_date_filter("1=1", (), effective_year_start, end_date)
        cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {dc_y}", dp_y)
        defects_this_year = (await cursor.fetchone())[0]

        # Replacement metrics (current state - no date filter)
        cursor = await db.execute(
            "SELECT COUNT(*) FROM defects WHERE replacement_device_id IS NOT NULL"
        )
        replacements_total = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT COUNT(*) FROM defects
               WHERE replacement_device_id IS NOT NULL
               AND replacement_confirmed_at IS NOT NULL"""
        )
        replacements_confirmed = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT COUNT(*) FROM defects
               WHERE replacement_device_id IS NOT NULL
               AND replacement_confirmed_at IS NULL"""
        )
        replacements_pending = (await cursor.fetchone())[0]

        # Role totals (current state - no date filter)
        cursor = await db.execute(
            "SELECT role, COUNT(*) AS total FROM users GROUP BY role"
        )
        role_rows = await cursor.fetchall()
        role_counts = {str(r[0]): int(r[1]) for r in role_rows}

        cursor = await db.execute(
            """
            SELECT
                role,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_total,
                SUM(CASE WHEN status != 'active' THEN 1 ELSE 0 END) AS inactive_total
            FROM users
            WHERE role IN ('sub_distributor', 'cluster', 'operator')
            GROUP BY role
            """
        )
        role_status_rows = await cursor.fetchall()
        role_status_splits = {
            str(row[0]): {
                "active": int(row[1] or 0),
                "inactive": int(row[2] or 0),
            }
            for row in role_status_rows
        }

        # Device status distribution (current state - no date filter)
        cursor = await db.execute(
            "SELECT status, COUNT(*) AS total FROM devices GROUP BY status"
        )
        device_rows = await cursor.fetchall()
        device_status_counts = {str(r[0]): int(r[1]) for r in device_rows}

        cursor = await db.execute(
            """
            SELECT u.role, d.status, COUNT(*) AS total
            FROM devices d
            INNER JOIN users u
                ON d.current_holder_id REGEXP '^[0-9]+$'
               AND CAST(d.current_holder_id AS UNSIGNED) = u.id
            WHERE u.role IN ('sub_distributor', 'cluster', 'operator')
            GROUP BY u.role, d.status
            """
        )
        holder_rows = await cursor.fetchall()
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

            cursor = await db.execute(
                "SELECT SUBSTRING(created_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE created_at >= ? AND created_at < ? GROUP BY SUBSTRING(created_at, 1, 7) ORDER BY m",
                (trend_start.isoformat(), trend_end.isoformat())
            )
            reported_by_month = {str(row["m"]): int(row["total"]) for row in await cursor.fetchall()}

            cursor = await db.execute(
                "SELECT SUBSTRING(resolved_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE status = 'resolved' AND resolved_at >= ? AND resolved_at < ? GROUP BY SUBSTRING(resolved_at, 1, 7) ORDER BY m",
                (trend_start.isoformat(), trend_end.isoformat())
            )
            resolved_by_month = {str(row["m"]): int(row["total"]) for row in await cursor.fetchall()}

            cursor = await db.execute(
                "SELECT SUBSTRING(replacement_requested_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE replacement_device_id IS NOT NULL AND replacement_requested_at >= ? AND replacement_requested_at < ? GROUP BY SUBSTRING(replacement_requested_at, 1, 7) ORDER BY m",
                (trend_start.isoformat(), trend_end.isoformat())
            )
            replaced_by_month = {str(row["m"]): int(row["total"]) for row in await cursor.fetchall()}

            cursor = await db.execute(
                "SELECT SUBSTRING(created_at, 1, 7) AS m, COUNT(*) AS total, SUM(CASE WHEN status IN ('approved', 'delivered') THEN 1 ELSE 0 END) AS delivered FROM distributions WHERE created_at >= ? AND created_at < ? GROUP BY SUBSTRING(created_at, 1, 7) ORDER BY m",
                (trend_start.isoformat(), trend_end.isoformat())
            )
            dist_by_month = {str(row["m"]): {"total": int(row["total"]), "delivered": int(row["delivered"])} for row in await cursor.fetchall()}

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
            dc, dp = _build_date_filter("1=1", (), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {dc}", dp)
            reported_total = (await cursor.fetchone())[0]

            resolved_conds = ["status = 'resolved'"]
            resolved_params = []
            if start_date:
                resolved_conds.append("resolved_at >= ?")
                resolved_params.append(start_date)
            if end_date:
                resolved_conds.append("resolved_at <= ?")
                resolved_params.append(end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {' AND '.join(resolved_conds)}", tuple(resolved_params))
            resolved_total = (await cursor.fetchone())[0]

            replaced_conds = ["replacement_device_id IS NOT NULL"]
            replaced_params = []
            if start_date:
                replaced_conds.append("replacement_requested_at >= ?")
                replaced_params.append(start_date)
            if end_date:
                replaced_conds.append("replacement_requested_at <= ?")
                replaced_params.append(end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {' AND '.join(replaced_conds)}", tuple(replaced_params))
            replaced_total = (await cursor.fetchone())[0]

            defect_trend.append({
                "month": "Filtered",
                "reported": reported_total,
                "resolved": resolved_total,
                "replaced": replaced_total,
            })

            cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {dc}", dp)
            total_dist = (await cursor.fetchone())[0]

            dist_delivered_conds = ["status IN ('approved', 'delivered')"]
            if start_date:
                dist_delivered_conds.append("created_at >= ?")
            if end_date:
                dist_delivered_conds.append("created_at <= ?")
            dist_params = tuple(p for p in ([start_date] if start_date else []) + ([end_date] if end_date else []) if p)
            cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {' AND '.join(dist_delivered_conds)}", dist_params)
            delivered_total = (await cursor.fetchone())[0]

            distribution_trend.append({
                "month": "Filtered",
                "total": total_dist,
                "delivered": delivered_total,
            })

        # Reliability analytics used by Defect Incidence cards
        reliability_start = start_date or (now - timedelta(days=60)).isoformat()
        if not start_date:
            reliability_start = (now - timedelta(days=60)).isoformat()

        rc, rp = _build_date_filter("1=1", (), reliability_start, end_date)
        cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {rc}", rp)
        defects_last_60_days = int((await cursor.fetchone())[0])

        # Build resolved_at-based date filter for repair rate queries
        r_conds, r_params = ["1=1"], []
        if start_date:
            r_conds.append("resolved_at >= ?")
            r_params.append(start_date)
        if end_date:
            r_conds.append("resolved_at <= ?")
            r_params.append(end_date)
        r_cond = " AND ".join(r_conds)
        r_params = tuple(r_params)

        cursor = await db.execute(
            f"""SELECT COUNT(*) FROM defects
               WHERE resolved_at IS NOT NULL
               AND TIMESTAMPDIFF(
                   DAY,
                   STR_TO_DATE(SUBSTRING(REPLACE(created_at, 'T', ' '), 1, 19), '%%Y-%%m-%%d %%H:%%i:%%s'),
                   STR_TO_DATE(SUBSTRING(REPLACE(resolved_at, 'T', ' '), 1, 19), '%%Y-%%m-%%d %%H:%%i:%%s')
               ) <= 60
               AND {r_cond}""", r_params
        )
        repaired_within_sla_devices = int((await cursor.fetchone())[0])

        cursor = await db.execute(
            f"SELECT COUNT(*) FROM defects WHERE resolved_at IS NOT NULL AND {r_cond}", r_params
        )
        total_resolved_defects = int((await cursor.fetchone())[0])

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
    """Get distribution device analytics: sent, remaining, by type and manufacturer."""
    async with get_db() as db:
        date_cond, date_params = _build_date_filter("status IN ('distributed', 'in_use')", (), start_date, end_date)
        cursor = await db.execute(
            f"""SELECT
                   COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown') AS device_type,
                   COUNT(*) AS total
               FROM devices
               WHERE {date_cond}
               GROUP BY COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown')
               ORDER BY total DESC""",
            date_params
        )
        sent_by_type_rows = await cursor.fetchall()

        cursor = await db.execute(
            f"SELECT COUNT(*) FROM devices WHERE {date_cond}", date_params
        )
        total_sent = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM devices WHERE status = 'available'"
        )
        remaining_available = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT
                   COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown') AS device_type,
                   COUNT(*) AS total
               FROM devices
               WHERE status = 'available'
               GROUP BY COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown')
               ORDER BY total DESC"""
        )
        remaining_by_type_rows = await cursor.fetchall()

        cursor = await db.execute(
            f"""SELECT
                   COALESCE(NULLIF(TRIM(manufacturer), ''), 'Unknown') AS manufacturer,
                   COUNT(*) AS total
               FROM devices
               WHERE {date_cond}
               GROUP BY COALESCE(NULLIF(TRIM(manufacturer), ''), 'Unknown')
               ORDER BY total DESC""",
            date_params
        )
        by_manufacturer_rows = await cursor.fetchall()

        per_holder_cond = date_cond.replace("status IN ('distributed', 'in_use')", "d.status IN ('distributed', 'in_use')")
        per_holder_cond = per_holder_cond.replace("created_at", "d.created_at")
        cursor = await db.execute(
            f"""SELECT
                   CAST(d.current_holder_id AS TEXT) AS holder_id,
                   COALESCE(NULLIF(TRIM(d.current_holder_name), ''), 'Unknown') AS holder_name,
                   COALESCE(NULLIF(TRIM(d.device_type), ''), 'Unknown') AS device_type,
                   COUNT(*) AS total
               FROM devices d
               INNER JOIN users u ON CAST(d.current_holder_id AS UNSIGNED) = u.id AND u.role = 'sub_distributor'
               WHERE {per_holder_cond}
               AND d.current_holder_id IS NOT NULL
               GROUP BY
                   CAST(d.current_holder_id AS TEXT),
                   COALESCE(NULLIF(TRIM(d.current_holder_name), ''), 'Unknown'),
                   COALESCE(NULLIF(TRIM(d.device_type), ''), 'Unknown')
               ORDER BY holder_name, device_type""",
            date_params
        )
        per_holder_rows = await cursor.fetchall()

        cursor = await db.execute(
            """SELECT
                   CAST(d.current_holder_id AS TEXT) AS holder_id,
                   COALESCE(NULLIF(TRIM(d.current_holder_name), ''), 'Unknown') AS holder_name,
                   COUNT(*) AS total
               FROM devices d
               INNER JOIN users u ON CAST(d.current_holder_id AS UNSIGNED) = u.id AND u.role = 'sub_distributor'
               WHERE d.status = 'available'
               AND d.current_holder_id IS NOT NULL
               GROUP BY
                   CAST(d.current_holder_id AS TEXT),
                   COALESCE(NULLIF(TRIM(d.current_holder_name), ''), 'Unknown')
               ORDER BY total DESC"""
        )
        per_holder_available_rows = await cursor.fetchall()

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
