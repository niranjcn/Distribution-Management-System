from datetime import datetime
from typing import Dict, Any, Optional, Set

from app.database import get_db

from .helpers import (
    _build_date_filter,
    _resolve_scope_root_for_sub_distribution_manager,
    _get_descendant_user_ids,
    _month_start,
    _shift_months,
    _active_inactive_from_status_counts,
    ACTIVE_DEVICE_STATUSES,
)


async def get_scope_users(user: Dict[str, Any]) -> Dict[str, list]:
    """Return sub_distributors, clusters, and operators visible to the current user."""
    role = user.get("role")
    user_id = str(user.get("_id", user.get("id", "")))
    scope_root_id = _resolve_scope_root_for_sub_distribution_manager(user, user_id)

    async with get_db() as db:
        if role == "super_admin":
            cursor = await db.execute(
                "SELECT id, email, name, role, COALESCE(parent_id, '') AS parent_id FROM users WHERE role IN ('sub_distributor', 'cluster', 'operator') ORDER BY role, name"
            )
        elif role in ("manager", "md_director", "pdic_staff"):
            scope_ids = sorted({scope_root_id} | await _get_descendant_user_ids(db, scope_root_id))
            placeholders = ",".join(["?"] * len(scope_ids)) if scope_ids else "?"
            cursor = await db.execute(
                f"SELECT id, email, name, role, COALESCE(parent_id, '') AS parent_id FROM users WHERE role IN ('sub_distributor', 'cluster', 'operator') AND id IN ({placeholders}) ORDER BY role, name",
                tuple(scope_ids)
            )
        elif role == "sub_distributor":
            cursor = await db.execute(
                "SELECT id, email, name, role, COALESCE(parent_id, '') AS parent_id FROM users WHERE (role = 'cluster' AND parent_id = ?) OR (role = 'operator' AND parent_id IN (SELECT id FROM users WHERE role = 'cluster' AND parent_id = ?)) ORDER BY role, name",
                (int(user_id), int(user_id))
            )
        elif role == "cluster":
            cursor = await db.execute(
                "SELECT id, email, name, role, COALESCE(parent_id, '') AS parent_id FROM users WHERE role = 'operator' AND parent_id = ? ORDER BY name",
                (int(user_id),)
            )
        elif role == "sub_distribution_manager":
            scope_ids = sorted({scope_root_id} | await _get_descendant_user_ids(db, scope_root_id))
            placeholders = ",".join(["?"] * len(scope_ids)) if scope_ids else "?"
            cursor = await db.execute(
                f"SELECT id, email, name, role, COALESCE(parent_id, '') AS parent_id FROM users WHERE role IN ('sub_distributor', 'cluster', 'operator') AND id IN ({placeholders}) ORDER BY role, name",
                tuple(scope_ids)
            )
        else:
            return {"sub_distributors": [], "clusters": [], "operators": []}

        rows = await cursor.fetchall()
        users_list = [dict(r) for r in rows]
        for u in users_list:
            u["id"] = str(u["id"])
            u["parent_id"] = str(u["parent_id"]) if u["parent_id"] else ""

    role_map = {
        "sub_distributor": "sub_distributors",
        "cluster": "clusters",
        "operator": "operators",
    }
    result = {"sub_distributors": [], "clusters": [], "operators": []}
    for u in users_list:
        mapped_key = role_map.get(u["role"])
        if mapped_key:
            result[mapped_key].append(u)
    return result


async def get_user_kpi(current_user: Dict[str, Any], target_user_id: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get KPI data for a specific user (devices, distributions, defects)."""
    empty = {"user": {}, "kpis": {}, "charts": {}}

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, email, name, role FROM users WHERE id = ?",
            (int(target_user_id),)
        )
        target_user = await cursor.fetchone()
        if not target_user:
            return empty

        target_user = dict(target_user)
        target_user["id"] = str(target_user["id"])

        # Devices held by this user
        dc, dp = _build_date_filter("current_holder_id = ?", (target_user["id"],), start_date, end_date)
        cursor = await db.execute(f"SELECT COUNT(*) FROM devices WHERE {dc}", dp)
        devices_in_hand = (await cursor.fetchone())[0]

        # Devices in hierarchy (descendants)
        descendant_ids = sorted({target_user["id"]} | await _get_descendant_user_ids(db, target_user["id"]))
        placeholders = ",".join(["?"] * len(descendant_ids)) if descendant_ids else "?"
        hc, hp = _build_date_filter(f"current_holder_id IN ({placeholders})", tuple(descendant_ids), start_date, end_date)
        cursor = await db.execute(f"SELECT COUNT(*) FROM devices WHERE {hc}", hp)
        devices_in_hierarchy = (await cursor.fetchone())[0]

        # Active/inactive in hierarchy
        cursor = await db.execute(
            f"""SELECT status, COUNT(*) AS total FROM devices
                WHERE {hc}
                GROUP BY status""",
            hp
        )
        device_status_rows = await cursor.fetchall()
        device_status = {str(r[0]): int(r[1]) for r in device_status_rows}
        hierarchy_active = sum(
            v for k, v in device_status.items() if k in ACTIVE_DEVICE_STATUSES
        )
        hierarchy_inactive = max(0, devices_in_hierarchy - hierarchy_active)

        # Distributions where this user is the sender
        dc2, dp2 = _build_date_filter("from_user_id = ?", (target_user["id"],), start_date, end_date)
        cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {dc2}", dp2)
        distributed_count = (await cursor.fetchone())[0]

        # Defects reported by this user
        dfc, dfp = _build_date_filter("CAST(reported_by AS CHAR) = ?", (target_user["id"],), start_date, end_date)
        cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {dfc}", dfp)
        total_defects = (await cursor.fetchone())[0]

        # Defect trend (12 months)
        now = datetime.now().replace(tzinfo=None)
        month_start = _month_start(now)
        defect_trend = []
        trend_range = range(11, -1, -1) if not (start_date or end_date) else range(0, 0)
        for i in trend_range:
            start = _shift_months(month_start, -i)
            end = _shift_months(start, 1)
            cursor = await db.execute(
                "SELECT COUNT(*) FROM defects WHERE CAST(reported_by AS CHAR) = ? AND created_at >= ? AND created_at < ?",
                (target_user["id"], start.isoformat(), end.isoformat())
            )
            reported = (await cursor.fetchone())[0]
            cursor = await db.execute(
                "SELECT COUNT(*) FROM defects WHERE CAST(reported_by AS CHAR) = ? AND status = 'resolved' AND resolved_at >= ? AND resolved_at < ?",
                (target_user["id"], start.isoformat(), end.isoformat())
            )
            resolved = (await cursor.fetchone())[0]
            defect_trend.append({
                "month": start.strftime("%b"),
                "reported": reported,
                "resolved": resolved,
            })

        # Distribution trend (12 months)
        distribution_trend = []
        for i in trend_range:
            start = _shift_months(month_start, -i)
            end = _shift_months(start, 1)
            cursor = await db.execute(
                "SELECT COUNT(*) FROM distributions WHERE from_user_id = ? AND created_at >= ? AND created_at < ?",
                (target_user["id"], start.isoformat(), end.isoformat())
            )
            total = (await cursor.fetchone())[0]
            cursor = await db.execute(
                "SELECT COUNT(*) FROM distributions WHERE from_user_id = ? AND status = 'delivered' AND created_at >= ? AND created_at < ?",
                (target_user["id"], start.isoformat(), end.isoformat())
            )
            delivered = (await cursor.fetchone())[0]
            distribution_trend.append({
                "month": start.strftime("%b"),
                "total": total,
                "delivered": delivered,
            })

    return {
        "user": {
            "id": target_user["id"],
            "name": target_user["name"],
            "role": target_user["role"],
            "email": target_user["email"],
        },
        "kpis": {
            "devices_in_hand": devices_in_hand,
            "devices_in_hierarchy": devices_in_hierarchy,
            "hierarchy_active_devices": hierarchy_active,
            "hierarchy_inactive_devices": hierarchy_inactive,
            "distributed_count": distributed_count,
            "total_defects": total_defects,
        },
        "charts": {
            "device_status": device_status,
            "defect_trend_12m": defect_trend,
            "distribution_trend_12m": distribution_trend,
        },
    }


async def get_system_alerts(user: Dict[str, Any]) -> list:
    """Get system alerts for dashboard"""
    role = user.get("role")
    alerts = []

    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM defects WHERE severity = 'critical' AND status != 'resolved'"
            )
            critical_defects = (await cursor.fetchone())[0]
            if critical_defects > 0:
                alerts.append({
                    "type": "error",
                    "title": "Critical Defects",
                    "message": f"{critical_defects} critical defect(s) require attention",
                    "link": "/defects?severity=critical"
                })

            cursor = await db.execute("SELECT COUNT(*) FROM approvals WHERE status = 'pending'")
            pending_approvals = (await cursor.fetchone())[0]
            if pending_approvals > 0:
                alerts.append({
                    "type": "warning",
                    "title": "Pending",
                    "message": f"{pending_approvals} request(s) waiting for approval with Pending payments",
                    "link": "/payments"
                })

            cursor = await db.execute("SELECT COUNT(*) FROM devices WHERE status = 'available'")
            available_devices = (await cursor.fetchone())[0]
            if available_devices < 10:
                alerts.append({
                    "type": "warning",
                    "title": "Low Device Stock",
                    "message": f"Only {available_devices} devices available in stock",
                    "link": "/devices"
                })

    return alerts
