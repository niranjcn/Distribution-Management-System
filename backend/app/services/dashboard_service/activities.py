from typing import Dict, Any, List, Optional

from sqlalchemy import text

from app.database_sqlalchemy import async_session_factory
from app.core.activity_logger import log_api_activity


async def get_recent_activities(user: Dict[str, Any], limit: int = 10) -> list:
    role = user.get("role")
    user_id = str(user.get("_id", user.get("id", "")))
    activities = []

    async with async_session_factory() as session:
        if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
            rows = (await session.execute(
                text("SELECT * FROM device_history WHERE action NOT IN ('bulk_registered', 'bulk_distributed') ORDER BY timestamp DESC LIMIT :lim"),
                {"lim": limit}
            )).mappings().all()
        else:
            rows = (await session.execute(
                text("""SELECT * FROM device_history
                WHERE (performed_by = :uid OR from_user_id = :uid2 OR to_user_id = :uid3)
                  AND action NOT IN ('bulk_registered', 'bulk_distributed')
                ORDER BY timestamp DESC LIMIT :lim"""),
                {"uid": user_id, "uid2": user_id, "uid3": user_id, "lim": limit}
            )).mappings().all()

        for hd in rows:
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
    normalized_category = (category or "all").strip().lower()
    activities: List[Dict[str, Any]] = []
    fetch_limit = (page + 1) * page_size
    table_total = 0

    async with async_session_factory() as session:
        if normalized_category in {"all", "device"}:
            conditions = ["1=1"]
            params: Dict[str, Any] = {}

            conditions.append("action != :bulk_action")
            params["bulk_action"] = "bulk_registered"

            # Bulk distribution receipts write one per-device history row for
            # tracking purposes but must surface as a single activity entry.
            conditions.append("action != :bulk_action2")
            params["bulk_action2"] = "bulk_distributed"

            conditions.append("(notes IS NULL OR notes NOT LIKE :excl1)")
            params["excl1"] = "Device replaced by % for defect %"
            conditions.append("(notes IS NULL OR notes NOT LIKE :excl2)")
            params["excl2"] = "Device serviced and reassigned for defect %"

            if actor:
                conditions.append("performed_by_name LIKE :actor")
                params["actor"] = f"%{actor}%"

            if search:
                like = f"%{search}%"
                conditions.append("(action LIKE :sl1 OR notes LIKE :sl2 OR device_id LIKE :sl3 OR performed_by_name LIKE :sl4)")
                for i, key in enumerate(["sl1", "sl2", "sl3", "sl4"]):
                    params[key] = like

            if start_date:
                conditions.append("timestamp >= :start_date")
                params["start_date"] = start_date

            if end_date:
                conditions.append("timestamp <= :end_date")
                params["end_date"] = end_date

            where = " AND ".join(conditions)
            table_total += (await session.execute(
                text(f"SELECT COUNT(*) FROM device_history WHERE {where}"), params
            )).scalar() or 0

            rows = (await session.execute(
                text(f"""SELECT id, device_id, action, notes, performed_by_name, timestamp
                    FROM device_history
                    WHERE {where}
                    ORDER BY timestamp DESC
                    LIMIT :lim"""),
                {**params, "lim": fetch_limit}
            )).mappings().all()
            for item in rows:
                actor_name = item.get("performed_by_name") or "Unknown"
                description = (
                    item.get("notes")
                    or f"{item.get('action', 'updated')} on device {item.get('device_id', '-')}."
                )
                activities.append({
                    "id": f"device-{item.get('id')}",
                    "category": "device",
                    "action": item.get("action") or "device_update",
                    "actor": actor_name,
                    "description": description,
                    "date": item.get("timestamp"),
                    "link": None,
                })

        if normalized_category in {"all", "inventory"}:
            conditions = ["1=1"]
            params: Dict[str, Any] = {}

            if actor:
                conditions.append("distributed_by_name LIKE :actor")
                params["actor"] = f"%{actor}%"

            if search:
                like = f"%{search}%"
                conditions.append("(history_id LIKE :sl1 OR item_name LIKE :sl2 OR recipient_name LIKE :sl3 OR distributed_by_name LIKE :sl4 OR notes LIKE :sl5)")
                for i, key in enumerate([f"sl{i+1}" for i in range(5)]):
                    params[key] = like

            if start_date:
                conditions.append("distributed_at >= :start_date")
                params["start_date"] = start_date

            if end_date:
                conditions.append("distributed_at <= :end_date")
                params["end_date"] = end_date

            where = " AND ".join(conditions)
            table_total += (await session.execute(
                text(f"SELECT COUNT(*) FROM external_device_history WHERE {where}"), params
            )).scalar() or 0

            rows = (await session.execute(
                text(f"""SELECT id, history_id, item_name, quantity, recipient_name, distributed_by_name, distributed_at, notes
                    FROM external_device_history
                    WHERE {where}
                    ORDER BY distributed_at DESC
                    LIMIT :lim"""),
                {**params, "lim": fetch_limit}
            )).mappings().all()
            for item in rows:
                actor_name = item.get("distributed_by_name") or "Unknown"
                description = (
                    item.get("notes")
                    or f"Distributed {item.get('item_name', '-')} to {item.get('recipient_name') or '-'}."
                )
                activities.append({
                    "id": f"inventory-{item.get('id')}",
                    "category": "inventory",
                    "action": "distribution",
                    "actor": actor_name,
                    "description": description,
                    "date": item.get("distributed_at"),
                    "link": None,
                })

        if normalized_category in {"all", "api"}:
            conditions = ["1=1"]
            params: Dict[str, Any] = {}

            conditions.append("description NOT LIKE :excl")
            params["excl"] = "% returned %"

            if actor:
                conditions.append("actor_name LIKE :actor")
                params["actor"] = f"%{actor}%"

            if search:
                like = f"%{search}%"
                conditions.append("(description LIKE :sl1 OR path LIKE :sl2 OR method LIKE :sl3 OR actor_name LIKE :sl4)")
                for i, key in enumerate([f"sl{i+1}" for i in range(4)]):
                    params[key] = like

            if start_date:
                conditions.append("created_at >= :start_date")
                params["start_date"] = start_date

            if end_date:
                conditions.append("created_at <= :end_date")
                params["end_date"] = end_date

            where = " AND ".join(conditions)
            table_total += (await session.execute(
                text(f"SELECT COUNT(*) FROM api_activity_logs WHERE {where}"), params
            )).scalar() or 0

            rows = (await session.execute(
                text(f"""SELECT id, actor_name, method, path, status_code, description, created_at
                    FROM api_activity_logs
                    WHERE {where}
                    ORDER BY created_at DESC
                    LIMIT :lim"""),
                {**params, "lim": fetch_limit}
            )).mappings().all()
            for item in rows:
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

                activities.append({
                    "id": f"api-{item.get('id')}",
                    "category": "api",
                    "action": f"{item.get('method', 'API')} {item.get('path', '')}",
                    "actor": item.get("actor_name") or "Anonymous",
                    "description": item.get("description") or "API activity",
                    "date": item.get("created_at"),
                    "link": link,
                })

    activities.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
    start_idx = max(0, (page - 1) * page_size)
    end_idx = start_idx + page_size
    paged = activities[start_idx:end_idx]

    return {
        "data": paged,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": table_total,
            "total_pages": ((table_total + page_size - 1) // page_size) if page_size > 0 else 0,
        },
    }


async def track_client_activity(
    user: Dict[str, Any],
    action: str,
    description: str,
    context: Optional[str] = None,
) -> None:
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
