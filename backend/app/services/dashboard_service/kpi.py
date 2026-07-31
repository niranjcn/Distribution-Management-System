from datetime import datetime
from typing import Dict, Any, Optional, Set

from app.database_sqlalchemy import async_session_factory
from sqlalchemy import text

from .helpers import (
    _build_named_date_filter,
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

    async with async_session_factory() as session:
        if role == "super_admin":
            rows = (await session.execute(
                text("SELECT id, email, name, role, COALESCE(parent_id, '') AS parent_id FROM users WHERE role IN ('sub_distributor', 'cluster', 'operator') ORDER BY role, name")
            )).mappings().all()
        elif role in ("manager", "md_director", "pdic_staff"):
            scope_ids = sorted({scope_root_id} | await _get_descendant_user_ids(session, scope_root_id))
            if scope_ids:
                params = {f"id{i}": sid for i, sid in enumerate(scope_ids)}
                placeholders = ",".join([f":id{i}" for i in range(len(scope_ids))])
            else:
                params = {"id0": ""}
                placeholders = ":id0"
            rows = (await session.execute(
                text(f"SELECT id, email, name, role, COALESCE(parent_id, '') AS parent_id FROM users WHERE role IN ('sub_distributor', 'cluster', 'operator') AND id IN ({placeholders}) ORDER BY role, name"),
                params
            )).mappings().all()
        elif role == "sub_distributor":
            rows = (await session.execute(
                text("SELECT id, email, name, role, COALESCE(parent_id, '') AS parent_id FROM users WHERE (role = 'cluster' AND parent_id = :pid1) OR (role = 'operator' AND parent_id IN (SELECT id FROM users WHERE role = 'cluster' AND parent_id = :pid2)) ORDER BY role, name"),
                {"pid1": int(user_id), "pid2": int(user_id)}
            )).mappings().all()
        elif role == "cluster":
            rows = (await session.execute(
                text("SELECT id, email, name, role, COALESCE(parent_id, '') AS parent_id FROM users WHERE role = 'operator' AND parent_id = :parent_id ORDER BY name"),
                {"parent_id": int(user_id)}
            )).mappings().all()
        elif role == "sub_distribution_manager":
            scope_ids = sorted({scope_root_id} | await _get_descendant_user_ids(session, scope_root_id))
            if scope_ids:
                params = {f"id{i}": sid for i, sid in enumerate(scope_ids)}
                placeholders = ",".join([f":id{i}" for i in range(len(scope_ids))])
            else:
                params = {"id0": ""}
                placeholders = ":id0"
            rows = (await session.execute(
                text(f"SELECT id, email, name, role, COALESCE(parent_id, '') AS parent_id FROM users WHERE role IN ('sub_distributor', 'cluster', 'operator') AND id IN ({placeholders}) ORDER BY role, name"),
                params
            )).mappings().all()
        else:
            return {"sub_distributors": [], "clusters": [], "operators": []}

        users_list = [dict(r) for r in rows]
        for u in users_list:
            u["id"] = str(u["id"])
            u["parent_id"] = str(u["parent_id"]) if u["parent_id"] else ""
            u["digital_ids"] = []

        if users_list:
            user_ids = [int(u["id"]) for u in users_list]
            ph = ",".join([f":di_{i}" for i in range(len(user_ids))])
            id_rows = (await session.execute(
                text(f"SELECT user_id, digital_id, broadband_id FROM digital_identities WHERE user_id IN ({ph})"),
                {f"di_{i}": v for i, v in enumerate(user_ids)},
            )).mappings().all()
            digital_map: Dict[int, list] = {}
            for r in id_rows:
                digital_map.setdefault(int(r["user_id"]), []).append({
                    "digital_id": r["digital_id"],
                    "broadband_id": r["broadband_id"],
                })
            for u in users_list:
                u["digital_ids"] = digital_map.get(int(u["id"]), [])

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

    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT id, email, name, role FROM users WHERE id = :uid"),
            {"uid": int(target_user_id)}
        )
        target_user = result.mappings().first()
        if not target_user:
            return empty

        target_user = dict(target_user)
        target_user["id"] = str(target_user["id"])

        # Devices held by this user
        params = {"hid": target_user["id"]}
        date_clause = _build_named_date_filter(params, start_date, end_date)
        dc = f"current_holder_id = :hid AND {date_clause}"
        devices_in_hand = (await session.execute(text(f"SELECT COUNT(*) FROM devices WHERE {dc}"), params)).scalar()

        # Devices in hierarchy (descendants)
        descendant_ids = sorted({target_user["id"]} | await _get_descendant_user_ids(session, target_user["id"]))
        if descendant_ids:
            params2 = {f"hid{i}": did for i, did in enumerate(descendant_ids)}
            placeholders = ",".join([f":hid{i}" for i in range(len(descendant_ids))])
        else:
            params2 = {"hid0": ""}
            placeholders = ":hid0"
        date_clause2 = _build_named_date_filter(params2, start_date, end_date)
        hc = f"current_holder_id IN ({placeholders}) AND {date_clause2}"
        devices_in_hierarchy = (await session.execute(text(f"SELECT COUNT(*) FROM devices WHERE {hc}"), params2)).scalar()

        # Active/inactive in hierarchy
        device_status_rows = (await session.execute(
            text(f"""SELECT status, COUNT(*) AS total FROM devices
                WHERE {hc}
                GROUP BY status"""),
            params2
        )).mappings().all()
        device_status = {str(r["status"]): int(r["total"]) for r in device_status_rows}
        hierarchy_active = sum(
            v for k, v in device_status.items() if k in ACTIVE_DEVICE_STATUSES
        )
        hierarchy_inactive = max(0, devices_in_hierarchy - hierarchy_active)

        # Distributions where this user is the sender
        params3 = {"fuid": target_user["id"]}
        date_clause3 = _build_named_date_filter(params3, start_date, end_date)
        dc2 = f"from_user_id = :fuid AND {date_clause3}"
        distributed_count = (await session.execute(text(f"SELECT COUNT(*) FROM distributions WHERE {dc2}"), params3)).scalar()

        # Defects reported by this user
        params4 = {"ruid": target_user["id"]}
        date_clause4 = _build_named_date_filter(params4, start_date, end_date)
        dfc = f"CAST(reported_by AS CHAR) = :ruid AND {date_clause4}"
        total_defects = (await session.execute(text(f"SELECT COUNT(*) FROM defects WHERE {dfc}"), params4)).scalar()

        # Defect/distribution trend (aggregated, not N+1)
        now = datetime.now().replace(tzinfo=None)
        month_start = _month_start(now)
        defect_trend = []
        distribution_trend = []

        if not (start_date or end_date):
            trend_start = _shift_months(month_start, -11)
            trend_end = _shift_months(month_start, 1)

            reported_by_month = {
                str(row["m"]): int(row["total"])
                for row in (await session.execute(
                    text("SELECT SUBSTRING(created_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE CAST(reported_by AS CHAR) = :ruid AND created_at >= :ts AND created_at < :te GROUP BY SUBSTRING(created_at, 1, 7) ORDER BY m"),
                    {"ruid": target_user["id"], "ts": trend_start.isoformat(), "te": trend_end.isoformat()}
                )).mappings().all()
            }

            resolved_by_month = {
                str(row["m"]): int(row["total"])
                for row in (await session.execute(
                    text("SELECT SUBSTRING(resolved_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE CAST(reported_by AS CHAR) = :ruid AND status = 'resolved' AND resolved_at >= :ts AND resolved_at < :te GROUP BY SUBSTRING(resolved_at, 1, 7) ORDER BY m"),
                    {"ruid": target_user["id"], "ts": trend_start.isoformat(), "te": trend_end.isoformat()}
                )).mappings().all()
            }

            dist_rows = (await session.execute(
                text("SELECT SUBSTRING(created_at, 1, 7) AS m, COUNT(*) AS total, SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) AS delivered FROM distributions WHERE from_user_id = :fuid AND created_at >= :ts AND created_at < :te GROUP BY SUBSTRING(created_at, 1, 7) ORDER BY m"),
                {"fuid": target_user["id"], "ts": trend_start.isoformat(), "te": trend_end.isoformat()}
            )).mappings().all()
            dist_by_month = {str(row["m"]): {"total": int(row["total"]), "delivered": int(row["delivered"])} for row in dist_rows}

            for i in range(11, -1, -1):
                start = _shift_months(month_start, -i)
                month_key = start.strftime("%Y-%m")
                defect_trend.append({
                    "month": start.strftime("%b"),
                    "reported": reported_by_month.get(month_key, 0),
                    "resolved": resolved_by_month.get(month_key, 0),
                })
                dist_data = dist_by_month.get(month_key, {"total": 0, "delivered": 0})
                distribution_trend.append({
                    "month": start.strftime("%b"),
                    "total": dist_data["total"],
                    "delivered": dist_data["delivered"],
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
        async with async_session_factory() as session:
            critical_defects = (await session.execute(
                text("SELECT COUNT(*) FROM defects WHERE severity = 'critical' AND status != 'resolved'")
            )).scalar()
            if critical_defects > 0:
                alerts.append({
                    "type": "error",
                    "title": "Critical Defects",
                    "message": f"{critical_defects} critical defect(s) require attention",
                    "link": "/defects?severity=critical"
                })

            available_devices = (await session.execute(
                text("SELECT COUNT(*) FROM devices WHERE status = 'available'")
            )).scalar()
            if available_devices < 10:
                alerts.append({
                    "type": "warning",
                    "title": "Low Device Stock",
                    "message": f"Only {available_devices} devices available in stock",
                    "link": "/devices"
                })

    return alerts
