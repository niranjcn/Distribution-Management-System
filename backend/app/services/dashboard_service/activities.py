from typing import Dict, Any, List, Optional

from app.database import get_db
from app.core.activity_logger import log_api_activity


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

            conditions.append("action != ?")
            params.append("bulk_registered")

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
