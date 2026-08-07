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
            # Management feed reads the denormalised activities table (migration
            # 0021, kept in sync by AFTER INSERT triggers) so the hot path is a
            # single index-ordered scan instead of a scan over device_history.
            rows = (await session.execute(
                text("""SELECT activity_id AS id, action, actor AS performed_by_name,
                               activity_date AS timestamp
                        FROM activities
                        WHERE category = 'device'
                        ORDER BY activity_date DESC, activity_id DESC
                        LIMIT :lim"""),
                {"lim": limit}
            )).mappings().all()
        else:
            rows = (await session.execute(
                text("""SELECT id, action, performed_by_name, timestamp FROM device_history
                WHERE (performed_by = :uid OR from_user_id = :uid2 OR to_user_id = :uid3)
                  AND action NOT IN ('bulk_registered', 'bulk_distributed')
                ORDER BY timestamp DESC, id DESC LIMIT :lim"""),
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


def _build_api_activity_link(path_value: str) -> Optional[str]:
    if path_value.startswith("/activity/devices"):
        return "/devices"
    if path_value.startswith("/activity/distributions"):
        return "/distributions"
    if path_value.startswith("/activity/users"):
        return "/users"
    if path_value.startswith("/activity/defects"):
        return "/defects"
    if path_value.startswith("/activity/returns"):
        return "/returns"
    if path_value.startswith("/activity/pending-dues"):
        return "/defects"
    if path_value.startswith("/activity/reports"):
        return "/backup"
    if path_value.startswith("/activity/external-inventory"):
        return "/external-inventory"
    return None


async def get_admin_activities(
    page: int = 1,
    page_size: int = 50,
    actor: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    actor_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """SQL-paginated admin-wide activities.

    Reads from the denormalised ``activities`` table, which is maintained by
    AFTER INSERT triggers on ``device_history``, ``external_device_history``
    and ``api_activity_logs`` (migration 0021). The whole feed is therefore a
    single indexed SELECT + COUNT instead of a UNION over three audit tables.

    When ``actor_ids`` is provided the feed is scoped to those actor ids only
    (used for sub-distributor employee-activity feeds).
    """
    normalized_category = (category or "all").strip().lower()

    category_filter = {
        "all": "('device', 'inventory', 'api')",
        "device": "('device')",
        "inventory": "('inventory')",
        "api": "('api')",
    }.get(normalized_category)

    if not category_filter:
        return {
            "data": [],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": 0,
                "total_pages": 0,
            },
        }

    conditions = ["category IN " + category_filter]
    params: Dict[str, Any] = {}

    # Defense in depth: the triggers already exclude these rows, but keep the
    # filters here too so rows missed by a backfill can never surface.
    conditions.append("NOT (category = 'device' AND action IN ('bulk_registered', 'bulk_distributed'))")
    conditions.append("NOT (category = 'api' AND description LIKE '% returned %')")

    if actor:
        conditions.append("actor LIKE :actor")
        params["actor"] = f"%{actor}%"

    if search:
        conditions.append("search_text LIKE :search")
        params["search"] = f"%{search}%"

    if start_date:
        conditions.append("activity_date >= :start_date")
        params["start_date"] = start_date

    if end_date:
        conditions.append("activity_date <= :end_date")
        params["end_date"] = end_date

    if actor_ids is not None:
        if not actor_ids:
            conditions.append("1 = 0")
        else:
            placeholders = ", ".join(f":actor_id_{i}" for i in range(len(actor_ids)))
            conditions.append(f"actor_id IN ({placeholders})")
            for i, actor_id in enumerate(actor_ids):
                params[f"actor_id_{i}"] = int(actor_id)

    where = " AND ".join(conditions)

    async with async_session_factory() as session:
        total = (await session.execute(
            text(f"SELECT COUNT(*) FROM activities WHERE {where}"),
            params,
        )).scalar() or 0

        offset = max((page - 1) * page_size, 0)
        rows = (await session.execute(
            text(
                "SELECT activity_id, category, action, actor, description, "
                "activity_date AS date, method, path "
                f"FROM activities WHERE {where} "
                "ORDER BY activity_date DESC, "
                "FIELD(category, 'device', 'inventory', 'api'), activity_id DESC "
                "LIMIT :offset, :page_size"
            ),
            {**params, "offset": offset, "page_size": page_size},
        )).mappings().all()

    activities: List[Dict[str, Any]] = []
    for item in rows:
        category_name = item.get("category")
        entry = {
            "id": item.get("activity_id"),
            "category": category_name,
            "action": item.get("action"),
            "actor": item.get("actor") or "Unknown",
            "description": item.get("description"),
            "date": item.get("date"),
        }
        if category_name == "api":
            entry["link"] = _build_api_activity_link(str(item.get("path") or ""))
        else:
            entry["link"] = None
        activities.append(entry)

    return {
        "data": activities,
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
