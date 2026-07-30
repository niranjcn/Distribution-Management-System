from datetime import datetime
from typing import Dict, Any, List, Optional, Set

from sqlalchemy import text


ACTIVE_DEVICE_STATUSES = {"active", "available", "distributed", "in_use"}


def _build_date_filter(base_condition: str, base_params: dict, start_date: Optional[str], end_date: Optional[str]) -> tuple:
    conds = [base_condition]
    params = dict(base_params)
    if start_date:
        conds.append("created_at >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conds.append("created_at <= :end_date")
        params["end_date"] = end_date
    return " AND ".join(conds), params


def _build_named_date_filter(
    base_params: Dict[str, Any],
    start_date: Optional[str],
    end_date: Optional[str],
    prefix: str = ""
) -> str:
    """Build date filter clause with named params, returns WHERE fragment."""
    conds = []
    if start_date:
        conds.append(f"created_at >= :{prefix}start_date")
        base_params[f"{prefix}start_date"] = start_date
    if end_date:
        conds.append(f"created_at <= :{prefix}end_date")
        base_params[f"{prefix}end_date"] = end_date
    return " AND ".join(conds) if conds else "1=1"


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


async def _get_user_status_split_by_role(session, role: str, parent_id: Optional[str] = None) -> Dict[str, int]:
    params: Dict[str, Any] = {"role": role}
    query = """
        SELECT
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_total,
            SUM(CASE WHEN status != 'active' THEN 1 ELSE 0 END) AS inactive_total
        FROM users
        WHERE role = :role
    """
    if parent_id is not None:
        query += " AND parent_id = :parent_id"
        params["parent_id"] = int(parent_id)

    row = (await session.execute(text(query), params)).mappings().first()
    return {
        "active": int(row["active_total"] if row and row["active_total"] is not None else 0),
        "inactive": int(row["inactive_total"] if row and row["inactive_total"] is not None else 0),
    }


async def _get_device_status_counts_for_holder(session, holder_id: str) -> Dict[str, int]:
    rows = (await session.execute(
        text("SELECT status, COUNT(*) AS total FROM devices WHERE current_holder_id = :hid GROUP BY status"),
        {"hid": str(holder_id)}
    )).mappings().all()
    return {str(r["status"]): int(r["total"]) for r in rows}


async def _get_descendant_user_ids(session, root_user_id: str) -> Set[str]:
    if not root_user_id or not str(root_user_id).isdigit():
        return set()
    rows = (await session.execute(
        text("""
            WITH RECURSIVE descendants AS (
                SELECT id FROM users WHERE parent_id = :root
                UNION ALL
                SELECT u.id FROM users u
                INNER JOIN descendants d ON u.parent_id = d.id
            )
            SELECT id FROM descendants
        """),
        {"root": int(root_user_id)}
    )).scalars().all()
    return {str(did) for did in rows if did}
