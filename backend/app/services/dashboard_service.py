from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Set

from app.database import get_db, rows_to_list
from app.core.activity_logger import log_api_activity
from app.services import device_service, distribution_service, defect_service, return_service, user_service, approval_service, operator_service


ACTIVE_DEVICE_STATUSES = {"active", "available", "distributed", "in_use"}


async def _get_descendant_user_ids(db, root_user_id: str) -> Set[str]:
    descendants: Set[str] = set()
    if not root_user_id or not str(root_user_id).isdigit():
        return descendants

    pending: List[int] = [int(root_user_id)]
    visited: Set[int] = set()

    while pending:
        current_parent_id = pending.pop()
        if current_parent_id in visited:
            continue
        visited.add(current_parent_id)

        cursor = await db.execute(
            "SELECT id FROM users WHERE parent_id = ?",
            (current_parent_id,)
        )
        rows = await cursor.fetchall()
        for row in rows:
            child_id = int(row["id"])
            child_id_str = str(child_id)
            if child_id_str not in descendants:
                descendants.add(child_id_str)
                pending.append(child_id)

    return descendants


def _resolve_scope_root_for_sub_distribution_manager(user: Dict[str, Any], user_id: str) -> str:
    role = str(user.get("role") or "").lower()
    parent_id = str(user.get("parent_id") or "")
    if role == "sub_distribution_manager" and parent_id.isdigit():
        return parent_id
    return user_id


def _month_start(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, 1)


def _shift_months(dt: datetime, months: int) -> datetime:
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    return datetime(year, month, 1)


def _active_inactive_from_status_counts(status_counts: Dict[str, int]) -> Dict[str, int]:
    active = sum(int(total) for status, total in status_counts.items() if status in ACTIVE_DEVICE_STATUSES)
    total = sum(int(total) for total in status_counts.values())
    return {
        "active": int(active),
        "inactive": int(max(0, total - active)),
    }


async def _get_user_status_split_by_role(db, role: str, parent_id: Optional[str] = None) -> Dict[str, int]:
    query = """
        SELECT
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_total,
            SUM(CASE WHEN status != 'active' THEN 1 ELSE 0 END) AS inactive_total
        FROM users
        WHERE role = ?
    """
    params = [role]
    if parent_id is not None:
        query += " AND parent_id = ?"
        params.append(int(parent_id))

    cursor = await db.execute(query, tuple(params))
    row = await cursor.fetchone()
    return {
        "active": int((row[0] if row and row[0] is not None else 0)),
        "inactive": int((row[1] if row and row[1] is not None else 0)),
    }


async def _get_device_status_counts_for_holder(db, holder_id: str) -> Dict[str, int]:
    cursor = await db.execute(
        "SELECT status, COUNT(*) AS total FROM devices WHERE current_holder_id = ? GROUP BY status",
        (str(holder_id),)
    )
    rows = await cursor.fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


async def get_dashboard_stats(user: Dict[str, Any]) -> Dict[str, Any]:
    """Get dashboard statistics based on user role"""
    role = user.get("role")
    user_id = str(user.get("_id", user.get("id", "")))
    scope_root_id = _resolve_scope_root_for_sub_distribution_manager(user, user_id)

    stats = {}

    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        device_stats = await device_service.get_device_stats()
        dist_stats = await distribution_service.get_distribution_stats()
        defect_stats = await defect_service.get_defect_stats()
        return_stats = await return_service.get_return_stats()
        user_stats = await user_service.get_user_stats()
        approval_stats = await approval_service.get_approval_stats()

        # This month's distributions
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        month_start = datetime(now.year, now.month, 1).isoformat()
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM distributions WHERE created_at >= ?", (month_start,)
            )
            distributions_this_month = (await cursor.fetchone())[0]

        stats = {
            "total_devices": device_stats.get("total", 0),
            "available_devices": device_stats.get("available", 0),
            "distributed_devices": device_stats.get("distributed", 0),
            "in_use_devices": device_stats.get("in_use", 0),
            "defective_devices": device_stats.get("defective", 0),
            "returned_devices": device_stats.get("returned", 0),
            "active_devices": (
                device_stats.get("available", 0) +
                device_stats.get("distributed", 0) +
                device_stats.get("in_use", 0)
            ),
            "total_distributions": dist_stats.get("total", 0),
            "pending_distributions": dist_stats.get("pending", 0),
            "approved_distributions": dist_stats.get("approved", 0),
            "delivered_distributions": dist_stats.get("delivered", 0),
            "rejected_distributions": dist_stats.get("rejected", 0),
            "distribution_this_month": distributions_this_month,
            "total_defects": defect_stats.get("total", 0),
            "defect_reports": defect_stats.get("total", 0),
            "reported_defects": defect_stats.get("by_status", {}).get("reported", 0),
            "under_review_defects": defect_stats.get("by_status", {}).get("under_review", 0),
            "resolved_defects": defect_stats.get("by_status", {}).get("resolved", 0),
            "total_returns": return_stats.get("total", 0),
            "return_requests": return_stats.get("total", 0),
            "pending_returns": return_stats.get("by_status", {}).get("pending", 0),
            "approved_returns": return_stats.get("by_status", {}).get("approved", 0),
            "received_returns": return_stats.get("by_status", {}).get("received", 0),
            "rejected_returns": return_stats.get("by_status", {}).get("rejected", 0),
            "total_users": user_stats.get("total", 0),
            "active_users": user_stats.get("active", 0),
            "pending_approvals": approval_stats.get("total_pending", 0),
            "pending_receipts": dist_stats.get("pending_receipt", 0),
            "total_approved": approval_stats.get("approved", 0),
            "total_rejected": approval_stats.get("rejected", 0),
            "devices": device_stats,
            "distributions": dist_stats,
            "defects": defect_stats,
            "returns": return_stats,
            "users": user_stats,
            "approvals": approval_stats
        }

    elif role == "sub_distributor":
        async with get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM devices WHERE current_holder_id = ?", (user_id,))
            my_devices = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM devices WHERE current_holder_id = ? AND status = 'available'", (user_id,))
            available_devices = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM distributions WHERE from_user_id = ?", (user_id,))
            sent = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM distributions WHERE to_user_id = ?", (user_id,))
            received = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM distributions WHERE from_user_id = ? AND status = 'pending'", (user_id,))
            pending = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT id FROM users WHERE role = 'sub_distribution_manager' AND parent_id = ?", (int(user_id),))
            sub_dist_manager_ids = [row[0] for row in await cursor.fetchall()]
            candidate_cluster_parent_ids = [int(user_id)] + sub_dist_manager_ids
            if candidate_cluster_parent_ids:
                placeholders = ",".join("?" * len(candidate_cluster_parent_ids))
                cursor = await db.execute(
                    f"SELECT id FROM users WHERE role = 'cluster' AND parent_id IN ({placeholders})",
                    tuple(candidate_cluster_parent_ids)
                )
                cluster_ids = [row[0] for row in await cursor.fetchall()]
            else:
                cluster_ids = []

            if cluster_ids:
                placeholders = ",".join("?" * len(cluster_ids))
                cursor = await db.execute(
                    f"SELECT COUNT(*) FROM users WHERE role = 'operator' AND parent_id IN ({placeholders})",
                    tuple(cluster_ids)
                )
                operator_count = (await cursor.fetchone())[0]
            else:
                operator_count = 0

        stats = {
            "my_devices": my_devices,
            "received_devices": my_devices,
            "available_devices": available_devices,
            "distributions_sent": sent,
            "distributions_received": received,
            "pending_distributions": pending,
            "operator_count": operator_count,
        }

    elif role == "sub_distribution_manager":
        async with get_db() as db:
            scope_ids = sorted({scope_root_id} | await _get_descendant_user_ids(db, scope_root_id))
            placeholders = ",".join(["?"] * len(scope_ids)) if scope_ids else "?"

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM devices WHERE current_holder_id IN ({placeholders})",
                tuple(scope_ids)
            )
            branch_devices = (await cursor.fetchone())[0]

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM devices WHERE current_holder_id IN ({placeholders}) AND status = 'available'",
                tuple(scope_ids)
            )
            available_devices = (await cursor.fetchone())[0]

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM distributions WHERE from_user_id IN ({placeholders})",
                tuple(scope_ids)
            )
            sent = (await cursor.fetchone())[0]

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM distributions WHERE to_user_id IN ({placeholders})",
                tuple(scope_ids)
            )
            received = (await cursor.fetchone())[0]

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM distributions WHERE to_user_id = ? AND status = 'pending_receipt'",
                (user_id,)
            )
            pending = (await cursor.fetchone())[0]

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM users WHERE role = 'operator' AND id IN ({placeholders})",
                tuple(scope_ids)
            )
            operator_count = (await cursor.fetchone())[0]

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM defects WHERE CAST(reported_by AS TEXT) IN ({placeholders})",
                tuple(scope_ids)
            )
            defect_reports = (await cursor.fetchone())[0]

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM returns WHERE CAST(requested_by AS TEXT) IN ({placeholders})",
                tuple(scope_ids)
            )
            return_requests = (await cursor.fetchone())[0]

        stats = {
            "my_devices": branch_devices,
            "received_devices": branch_devices,
            "available_devices": available_devices,
            "distributions_sent": sent,
            "distributions_received": received,
            "pending_distributions": pending,
            "operator_count": operator_count,
            "defect_reports": defect_reports,
            "return_requests": return_requests,
            "assigned_to_operators": sent,
        }

    elif role == "cluster":
        async with get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM devices WHERE current_holder_id = ?", (user_id,))
            my_devices = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM distributions WHERE from_user_id = ?", (user_id,))
            sent = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM distributions WHERE to_user_id = ?", (user_id,))
            received = (await cursor.fetchone())[0]
        operator_stats_data = await operator_service.get_operator_stats(user_id)
        stats = {
            "my_devices": my_devices,
            "operators": operator_stats_data,
            "distributions_sent": sent,
            "distributions_received": received
        }

    elif role == "operator":
        async with get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM devices WHERE current_holder_id = ?", (user_id,))
            my_devices = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM defects WHERE reported_by = ?", (user_id,))
            my_defects = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM returns WHERE requested_by = ?", (user_id,))
            my_returns = (await cursor.fetchone())[0]
        stats = {
            "my_devices": my_devices,
            "my_defects": my_defects,
            "my_returns": my_returns
        }

    return stats


async def get_recent_activities(user: Dict[str, Any], limit: int = 10) -> list:
    """Get recent activities based on user role"""
    role = user.get("role")
    user_id = str(user.get("_id", user.get("id", "")))

    activities = []

    async with get_db() as db:
        if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
            cursor = await db.execute(
                "SELECT * FROM device_history ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        else:
            cursor = await db.execute(
                """SELECT * FROM device_history
                WHERE performed_by = ? OR from_user_id = ? OR to_user_id = ?
                ORDER BY timestamp DESC LIMIT ?""",
                (user_id, user_id, user_id, limit)
            )
        rows = await cursor.fetchall()

        for h in rows:
            hd = dict(h)
            activities.append({
                "id": str(hd["id"]),
                "action": hd["action"],
                "description": f"{hd.get('performed_by_name', 'Unknown')} {hd['action']} device",
                "user_name": hd.get("performed_by_name", "Unknown"),
                "timestamp": hd["timestamp"],
                "category": "device",
                "link": None
            })

    return activities


async def get_admin_activities(
    page: int = 1,
    page_size: int = 50,
    actor: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Get unified activity stream for admin users with filtering."""
    normalized_category = (category or "all").strip().lower()
    activities: List[Dict[str, Any]] = []

    async with get_db() as db:
        if normalized_category in {"all", "device"}:
            conditions = ["1=1"]
            params: List[Any] = []

            # Keep bulk device uploads as one summary entry in API activity logs.
            conditions.append("action != ?")
            params.append("bulk_registered")

            # Replacement workflow already writes a curated API business activity.
            # Hide matching device-history rows so replacement appears as a single activity.
            conditions.append("(notes IS NULL OR notes NOT LIKE ?)")
            params.append("Device replaced by % for defect %")
            conditions.append("(notes IS NULL OR notes NOT LIKE ?)")
            params.append("Device serviced and reassigned for defect %")

            if actor:
                conditions.append("performed_by_name LIKE ?")
                params.append(f"%{actor}%")

            if search:
                like = f"%{search}%"
                conditions.append("(action LIKE ? OR notes LIKE ? OR device_id LIKE ? OR performed_by_name LIKE ?)")
                params.extend([like, like, like, like])

            if start_date:
                conditions.append("timestamp >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("timestamp <= ?")
                params.append(end_date)

            where_clause = " AND ".join(conditions)
            cursor = await db.execute(
                f"""SELECT id, device_id, action, notes, performed_by_name, timestamp
                    FROM device_history
                    WHERE {where_clause}
                    ORDER BY timestamp DESC""",
                params,
            )
            rows = await cursor.fetchall()
            for row in rows:
                item = dict(row)
                actor_name = item.get("performed_by_name") or "Unknown"
                description = (
                    item.get("notes")
                    or f"{item.get('action', 'updated')} on device {item.get('device_id', '-')}."
                )
                activities.append(
                    {
                        "id": f"device-{item.get('id')}",
                        "category": "device",
                        "action": item.get("action") or "device_update",
                        "actor": actor_name,
                        "description": description,
                        "date": item.get("timestamp"),
                        "link": None,
                    }
                )

        if normalized_category in {"all", "inventory"}:
            conditions = ["1=1"]
            params = []

            if actor:
                conditions.append("performed_by_name LIKE ?")
                params.append(f"%{actor}%")

            if search:
                like = f"%{search}%"
                conditions.append("(movement_type LIKE ? OR notes LIKE ? OR item_sku LIKE ? OR item_name LIKE ? OR performed_by_name LIKE ?)")
                params.extend([like, like, like, like, like])

            if start_date:
                conditions.append("created_at >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("created_at <= ?")
                params.append(end_date)

            where_clause = " AND ".join(conditions)
            cursor = await db.execute(
                f"""SELECT id, item_sku, item_name, movement_type, notes, performed_by_name, created_at
                    FROM inventory_stock_movements
                    WHERE {where_clause}
                    ORDER BY created_at DESC""",
                params,
            )
            rows = await cursor.fetchall()
            for row in rows:
                item = dict(row)
                actor_name = item.get("performed_by_name") or "Unknown"
                description = (
                    item.get("notes")
                    or f"{item.get('movement_type', 'movement')} for {item.get('item_sku') or item.get('item_name') or '-'}."
                )
                activities.append(
                    {
                        "id": f"inventory-{item.get('id')}",
                        "category": "inventory",
                        "action": item.get("movement_type") or "movement",
                        "actor": actor_name,
                        "description": description,
                        "date": item.get("created_at"),
                        "link": None,
                    }
                )

        if normalized_category in {"all", "api"}:
            conditions = ["1=1"]
            params = []

            # Hide legacy generic middleware rows and surface only curated business-action API logs.
            conditions.append("description NOT LIKE ?")
            params.append("% returned %")

            if actor:
                conditions.append("actor_name LIKE ?")
                params.append(f"%{actor}%")

            if search:
                like = f"%{search}%"
                conditions.append("(description LIKE ? OR path LIKE ? OR method LIKE ? OR actor_name LIKE ?)")
                params.extend([like, like, like, like])

            if start_date:
                conditions.append("created_at >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("created_at <= ?")
                params.append(end_date)

            where_clause = " AND ".join(conditions)
            cursor = await db.execute(
                f"""SELECT id, actor_name, method, path, status_code, description, created_at
                    FROM api_activity_logs
                    WHERE {where_clause}
                    ORDER BY created_at DESC""",
                params,
            )
            rows = await cursor.fetchall()
            for row in rows:
                item = dict(row)
                path_value = str(item.get("path") or "")

                link = None
                if path_value.startswith("/activity/devices"):
                    link = "/devices"
                elif path_value.startswith("/activity/distributions"):
                    link = "/distributions"
                elif path_value.startswith("/activity/users"):
                    link = "/users"
                elif path_value.startswith("/activity/defects"):
                    link = "/defects"
                elif path_value.startswith("/activity/returns"):
                    link = "/returns"
                elif path_value.startswith("/activity/pending-dues"):
                    link = "/defects"
                elif path_value.startswith("/activity/reports"):
                    link = "/backup"
                elif path_value.startswith("/activity/external-inventory"):
                    link = "/external-inventory"

                activities.append(
                    {
                        "id": f"api-{item.get('id')}",
                        "category": "api",
                        "action": f"{item.get('method', 'API')} {item.get('path', '')}",
                        "actor": item.get("actor_name") or "Anonymous",
                        "description": item.get("description") or "API activity",
                        "date": item.get("created_at"),
                        "link": link,
                    }
                )

    activities.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
    total = len(activities)
    start_idx = max(0, (page - 1) * page_size)
    end_idx = start_idx + page_size
    paged = activities[start_idx:end_idx]

    return {
        "data": paged,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ((total + page_size - 1) // page_size) if page_size > 0 else 0,
        },
    }


async def track_client_activity(
    user: Dict[str, Any],
    action: str,
    description: str,
    context: Optional[str] = None,
) -> None:
    """Persist explicit client-side activity events (for UI-only actions)."""
    user_id = str(user.get("id") or user.get("_id") or user.get("user_id") or user.get("sub") or "")
    actor_name = str(user.get("name") or user.get("email") or "Unknown")
    actor_role = str(user.get("role") or "")
    normalized_action = str(action or "ui_action").strip() or "ui_action"
    final_description = str(description or "User action").strip() or "User action"
    path = f"/ui/{normalized_action}"
    if context:
        path = f"{path}/{str(context).strip()[:128]}"

    await log_api_activity(
        method="UI",
        path=path,
        status_code=200,
        actor_id=user_id,
        actor_name=actor_name,
        actor_role=actor_role,
        description=final_description,
    )


async def get_distribution_chart_data() -> list:
    """Get distribution data for charts"""
    data = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with get_db() as db:
        for i in range(11, -1, -1):
            month_start = datetime(now.year, now.month, 1) - timedelta(days=i * 30)
            month_end = month_start + timedelta(days=30)

            cursor = await db.execute(
                "SELECT COUNT(*) FROM distributions WHERE status = 'delivered' AND created_at >= ? AND created_at < ?",
                (month_start.isoformat(), month_end.isoformat())
            )
            count = (await cursor.fetchone())[0]

            data.append({
                "month": month_start.strftime("%b"),
                "distributions": count
            })

    return data


async def get_defect_chart_data() -> list:
    """Get defect data for charts"""
    data = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with get_db() as db:
        for i in range(11, -1, -1):
            month_start = datetime(now.year, now.month, 1) - timedelta(days=i * 30)
            month_end = month_start + timedelta(days=30)

            cursor = await db.execute(
                "SELECT COUNT(*) FROM defects WHERE created_at >= ? AND created_at < ?",
                (month_start.isoformat(), month_end.isoformat())
            )
            reported = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM defects WHERE status = 'resolved' AND resolved_at >= ? AND resolved_at < ?",
                (month_start.isoformat(), month_end.isoformat())
            )
            resolved = (await cursor.fetchone())[0]

            data.append({
                "month": month_start.strftime("%b"),
                "reported": reported,
                "resolved": resolved
            })

    return data


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


async def get_user_kpi(current_user: Dict[str, Any], target_user_id: str) -> Dict[str, Any]:
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
        cursor = await db.execute(
            "SELECT COUNT(*) FROM devices WHERE current_holder_id = ?",
            (target_user["id"],)
        )
        devices_in_hand = (await cursor.fetchone())[0]

        # Devices in hierarchy (descendants)
        descendant_ids = sorted({target_user["id"]} | await _get_descendant_user_ids(db, target_user["id"]))
        placeholders = ",".join(["?"] * len(descendant_ids)) if descendant_ids else "?"
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM devices WHERE current_holder_id IN ({placeholders})",
            tuple(descendant_ids)
        )
        devices_in_hierarchy = (await cursor.fetchone())[0]

        # Active/inactive in hierarchy
        cursor = await db.execute(
            f"""SELECT status, COUNT(*) AS total FROM devices
                WHERE current_holder_id IN ({placeholders})
                GROUP BY status""",
            tuple(descendant_ids)
        )
        device_status_rows = await cursor.fetchall()
        device_status = {str(r[0]): int(r[1]) for r in device_status_rows}
        hierarchy_active = sum(
            v for k, v in device_status.items() if k in ACTIVE_DEVICE_STATUSES
        )
        hierarchy_inactive = max(0, devices_in_hierarchy - hierarchy_active)

        # Distributions where this user is the sender
        cursor = await db.execute(
            "SELECT COUNT(*) FROM distributions WHERE from_user_id = ?",
            (target_user["id"],)
        )
        distributed_count = (await cursor.fetchone())[0]

        # Defects reported by this user
        cursor = await db.execute(
            "SELECT COUNT(*) FROM defects WHERE CAST(reported_by AS CHAR) = ?",
            (target_user["id"],)
        )
        total_defects = (await cursor.fetchone())[0]

        # Defect trend (12 months)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        month_start = _month_start(now)
        defect_trend = []
        for i in range(11, -1, -1):
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
        for i in range(11, -1, -1):
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
                    "title": "Pending Approvals",
                    "message": f"{pending_approvals} request(s) waiting for approval",
                    "link": "/approvals"
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


async def get_advanced_dashboard_metrics(user: Dict[str, Any]) -> Dict[str, Any]:
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

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    month_start = _month_start(now)
    year_start = datetime(now.year, 1, 1)

    device_stats = await device_service.get_device_stats()
    user_stats = await user_service.get_user_stats()
    defect_stats = await defect_service.get_defect_stats()
    return_stats = await return_service.get_return_stats()
    dist_stats = await distribution_service.get_distribution_stats()
    approval_stats = await approval_service.get_approval_stats()
    alerts = await get_system_alerts(user)

    async with get_db() as db:
        # Defect month/year totals
        cursor = await db.execute(
            "SELECT COUNT(*) FROM defects WHERE created_at >= ?",
            (month_start.isoformat(),)
        )
        defects_this_month = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM defects WHERE created_at >= ?",
            (year_start.isoformat(),)
        )
        defects_this_year = (await cursor.fetchone())[0]

        # Replacement metrics
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

        # Role totals
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

        # Device status distribution
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

        # Monthly defect trend (last 12 months)
        defect_trend = []
        distribution_trend = []
        for i in range(11, -1, -1):
            start = _shift_months(month_start, -i)
            end = _shift_months(start, 1)

            cursor = await db.execute(
                "SELECT COUNT(*) FROM defects WHERE created_at >= ? AND created_at < ?",
                (start.isoformat(), end.isoformat())
            )
            reported = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM defects WHERE status = 'resolved' AND resolved_at >= ? AND resolved_at < ?",
                (start.isoformat(), end.isoformat())
            )
            resolved = (await cursor.fetchone())[0]

            cursor = await db.execute(
                """SELECT COUNT(*) FROM defects
                   WHERE replacement_device_id IS NOT NULL
                   AND replacement_requested_at >= ? AND replacement_requested_at < ?""",
                (start.isoformat(), end.isoformat())
            )
            replaced = (await cursor.fetchone())[0]

            defect_trend.append({
                "month": start.strftime("%b"),
                "reported": reported,
                "resolved": resolved,
                "replaced": replaced
            })

            cursor = await db.execute(
                "SELECT COUNT(*) FROM distributions WHERE created_at >= ? AND created_at < ?",
                (start.isoformat(), end.isoformat())
            )
            total_dist = (await cursor.fetchone())[0]

            cursor = await db.execute(
                """SELECT COUNT(*) FROM distributions
                   WHERE status IN ('approved', 'delivered')
                   AND created_at >= ? AND created_at < ?""",
                (start.isoformat(), end.isoformat())
            )
            delivered = (await cursor.fetchone())[0]

            distribution_trend.append({
                "month": start.strftime("%b"),
                "total": total_dist,
                "delivered": delivered
            })

        # Reliability analytics used by Defect Incidence cards
        sixty_days_ago = (now - timedelta(days=60)).isoformat()

        cursor = await db.execute("SELECT COUNT(*) FROM defects WHERE created_at >= ?", (sixty_days_ago,))
        defects_last_60_days = int((await cursor.fetchone())[0])

        cursor = await db.execute(
            """SELECT COUNT(*) FROM defects
               WHERE resolved_at IS NOT NULL
               AND TIMESTAMPDIFF(
                   DAY,
                   STR_TO_DATE(SUBSTRING(REPLACE(created_at, 'T', ' '), 1, 19), '%%Y-%%m-%%d %%H:%%i:%%s'),
                   STR_TO_DATE(SUBSTRING(REPLACE(resolved_at, 'T', ' '), 1, 19), '%%Y-%%m-%%d %%H:%%i:%%s')
               ) <= 60"""
        )
        repaired_within_sla_devices = int((await cursor.fetchone())[0])

        cursor = await db.execute("SELECT COUNT(*) FROM defects WHERE resolved_at IS NOT NULL")
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

