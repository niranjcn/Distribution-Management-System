from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.database import get_db, row_to_dict, rows_to_list
from app.models.operator import OperatorCreate, OperatorUpdate, OperatorStatus
from app.utils.helpers import get_pagination, generate_operator_id


async def get_operators(
    page: int = 1,
    page_size: int = 20,
    assigned_to: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Get all operators with pagination and filters"""
    async with get_db() as db:
        conditions = ["1=1"]
        params = []

        if assigned_to:
            conditions.append("assigned_to = ?")
            params.append(assigned_to)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if search:
            conditions.append("(name LIKE ? OR phone LIKE ? OR email LIKE ? OR area LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like, like])

        where = " AND ".join(conditions)

        cursor = await db.execute(f"SELECT COUNT(*) FROM operators WHERE {where}", params)
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"SELECT * FROM operators WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = await cursor.fetchall()

        return {
            "data": rows_to_list(rows),
            "pagination": get_pagination(page, page_size, total)
        }


async def get_operator_by_id(operator_id: str) -> Optional[Dict[str, Any]]:
    """Get operator by ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM operators WHERE id = ?", (int(operator_id),))
        row = await cursor.fetchone()
        return row_to_dict(row) if row else None


async def create_operator(operator_data: OperatorCreate, created_by: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new operator"""
    async with get_db() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        cursor = await db.execute(
            """INSERT INTO operators (operator_id, name, phone, email, address, area, city,
            assigned_to, assigned_to_name, status, device_count, connection_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                generate_operator_id(),
                operator_data.name,
                operator_data.phone,
                operator_data.email,
                operator_data.address,
                operator_data.area,
                operator_data.city,
                str(created_by["_id"]),
                created_by["name"],
                OperatorStatus.ACTIVE.value,
                0,
                operator_data.connection_type.value if operator_data.connection_type else None,
                now, now
            )
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM operators WHERE id = ?", (cursor.lastrowid,))
        row = await cursor.fetchone()
        return row_to_dict(row)


async def update_operator(operator_id: str, operator_data: OperatorUpdate) -> Optional[Dict[str, Any]]:
    """Update operator"""
    update_dict = {k: v for k, v in operator_data.model_dump().items() if v is not None}

    if not update_dict:
        return await get_operator_by_id(operator_id)

    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value
    if "connection_type" in update_dict:
        update_dict["connection_type"] = update_dict["connection_type"].value

    update_dict["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    async with get_db() as db:
        set_clause = ", ".join(f"{k} = ?" for k in update_dict)
        values = list(update_dict.values()) + [int(operator_id)]

        cursor = await db.execute(
            f"UPDATE operators SET {set_clause} WHERE id = ?", values
        )
        await db.commit()

        if cursor.rowcount > 0:
            return await get_operator_by_id(operator_id)
        return None


async def delete_operator(operator_id: str) -> bool:
    """Delete operator"""
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM operators WHERE id = ?", (int(operator_id),))
        await db.commit()
        return cursor.rowcount > 0


async def get_operator_devices(operator_id: str) -> List[Dict[str, Any]]:
    """Get devices assigned to an operator"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM devices WHERE current_holder_id = ?", (operator_id,)
        )
        rows = await cursor.fetchall()
        return rows_to_list(rows)


async def update_operator_device_count(operator_id: str) -> None:
    """Update operator's device count"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM devices WHERE current_holder_id = ?", (operator_id,)
        )
        count = (await cursor.fetchone())[0]

        await db.execute(
            "UPDATE operators SET device_count = ?, updated_at = ? WHERE id = ?",
            (count, datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), int(operator_id))
        )
        await db.commit()


async def get_operator_stats(assigned_to: Optional[str] = None) -> Dict[str, int]:
    """Get operator statistics"""
    async with get_db() as db:
        base_condition = "1=1"
        params = []
        if assigned_to:
            base_condition = "assigned_to = ?"
            params = [assigned_to]

        cursor = await db.execute(f"SELECT COUNT(*) FROM operators WHERE {base_condition}", params)
        total = (await cursor.fetchone())[0]

        cursor = await db.execute(f"SELECT COUNT(*) FROM operators WHERE {base_condition} AND status = 'active'", params)
        active = (await cursor.fetchone())[0]

        cursor = await db.execute(f"SELECT COUNT(*) FROM operators WHERE {base_condition} AND status = 'inactive'", params)
        inactive = (await cursor.fetchone())[0]

        return {
            "total": total,
            "active": active,
            "inactive": inactive
        }
