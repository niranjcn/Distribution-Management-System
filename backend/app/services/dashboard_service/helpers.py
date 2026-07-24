from datetime import datetime
from typing import Dict, Any, List, Optional, Set


ACTIVE_DEVICE_STATUSES = {"active", "available", "distributed", "in_use"}


def _build_date_filter(base_condition: str, base_params: tuple, start_date: Optional[str], end_date: Optional[str]) -> tuple:
    conds = [base_condition]
    params = list(base_params)
    if start_date:
        conds.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conds.append("created_at <= ?")
        params.append(end_date)
    return " AND ".join(conds), tuple(params)


from app.utils.hierarchy import get_descendant_user_ids as _get_descendant_user_ids


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
