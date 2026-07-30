from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import json

from app.database_sqlalchemy import async_session_factory
from sqlalchemy import text
from app.utils.helpers import get_pagination
from app.core.activity_logger import log_business_activity


def _count_total_children(children: List[Dict[str, Any]]) -> int:
    """Recursively count all items including nested ones."""
    count = 0
    for c in children:
        count += 1
        if c.get("children"):
            count += _count_total_children(c["children"])
    return count


async def create_reassignment_request(
    deleted_user: Dict[str, Any],
    children: List[Dict[str, Any]],
    actor_name: str
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        now = datetime.now().replace(tzinfo=None)
        children_json = json.dumps(children)

        year = datetime.now().year
        result = await session.execute(
            text("SELECT COUNT(*) FROM reassignment_requests WHERE request_id LIKE :pattern"),
            {"pattern": f"REASSIGN-{year}-%"}
        )
        count = result.scalar() or 0
        request_id = f"REASSIGN-{year}-{count + 1:04d}"

        result = await session.execute(
            text("""INSERT INTO reassignment_requests
            (request_id, deleted_user_id, deleted_user_name, deleted_user_role, status,
             children_json, created_at, updated_at)
            VALUES (:request_id, :deleted_user_id, :deleted_user_name, :deleted_user_role, 'pending', :children_json, :created_at, :updated_at)"""),
            {
                "request_id": request_id,
                "deleted_user_id": int(deleted_user["id"]),
                "deleted_user_name": deleted_user.get("email", ""),
                "deleted_user_role": deleted_user.get("role", ""),
                "children_json": children_json,
                "created_at": now,
                "updated_at": now
            }
        )
        await session.commit()

        result = await session.execute(
            text("SELECT * FROM reassignment_requests WHERE id = :id"),
            {"id": result.inserted_primary_key[0]}
        )
        row = result.mappings().first()
        return dict(row) if row else {"request_id": request_id, "status": "pending"}


async def get_reassignment_requests(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        conditions = []
        params = {}
        if status:
            conditions.append("status = :status")
            params["status"] = status

        where = " AND ".join(conditions) if conditions else "1=1"

        result = await session.execute(
            text(f"SELECT COUNT(*) FROM reassignment_requests WHERE {where}"),
            params
        )
        total = result.scalar()

        offset = (page - 1) * page_size
        result = await session.execute(
            text(f"SELECT * FROM reassignment_requests WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            {**params, "limit": page_size, "offset": offset}
        )
        rows = result.mappings().all()
        data = [dict(r) for r in rows]
        for req in data:
            if req.get("children_json"):
                try:
                    req["children"] = json.loads(req["children_json"])
                except (json.JSONDecodeError, TypeError):
                    req["children"] = []
                req.pop("children_json", None)

        return {
            "data": data,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_reassignment_request(request_id: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM reassignment_requests WHERE id = :id"),
            {"id": int(request_id)}
        )
        row = result.mappings().first()
        if not row:
            return None
        req = dict(row)
        if req.get("children_json"):
            try:
                req["children"] = json.loads(req["children_json"])
            except (json.JSONDecodeError, TypeError):
                req["children"] = []
            req.pop("children_json", None)
        return req


def _get_direct_children(children: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract only top-level items from nested children for parent_id updates.
    Handles both old flat format (no 'children' key) and new nested format."""
    direct = []
    for c in children:
        direct.append({
            "id": c["id"],
            "name": c.get("name", ""),
            "email": c.get("email", ""),
            "role": c.get("role", ""),
            "parent_id": c.get("parent_id")
        })
    return direct


async def reassign_users(
    request_id: str,
    new_parent_id: int,
    new_parent_name: str,
    new_parent_role: str,
    deleted_by_user: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM reassignment_requests WHERE id = :id"),
            {"id": int(request_id)}
        )
        row = result.mappings().first()
        if not row:
            return False, "Reassignment request not found"

        req = dict(row)
        if req.get("status") != "pending":
            return False, f"Request is already {req.get('status')}"

        children_json = req.get("children_json", "[]")
        try:
            children = json.loads(children_json)
        except (json.JSONDecodeError, TypeError):
            children = []

        if not children:
            return False, "No children to reassign"

        # Only update parent_id for top-level (direct) children.
        # Nested items (operators under clusters, etc.) keep their existing parent_id.
        direct_children = _get_direct_children(children)

        deleted_user_id = int(req["deleted_user_id"])
        now = datetime.now().replace(tzinfo=None)

        if direct_children:
            child_ids = [int(child["id"]) for child in direct_children]
            placeholders = ",".join(f":id_{i}" for i in range(len(child_ids)))
            params_dict = {"parent_id": new_parent_id, "updated_at": now}
            for i, cid in enumerate(child_ids):
                params_dict[f"id_{i}"] = cid
            await session.execute(
                text(f"UPDATE users SET parent_id = :parent_id, updated_at = :updated_at WHERE id IN ({placeholders})"),
                params_dict
            )

        await session.execute(
            text("""UPDATE reassignment_requests
            SET status = 'completed', reassigned_to_id = :reassigned_to_id, reassigned_to_name = :reassigned_to_name,
                reassigned_to_role = :reassigned_to_role, updated_at = :updated_at
            WHERE id = :id"""),
            {
                "reassigned_to_id": new_parent_id,
                "reassigned_to_name": new_parent_name,
                "reassigned_to_role": new_parent_role,
                "updated_at": now,
                "id": int(request_id)
            }
        )

        result = await session.execute(
            text("SELECT name, email, role FROM users WHERE id = :id"),
            {"id": deleted_user_id}
        )
        deleted_user_row = result.mappings().first()
        deleted_user_name = dict(deleted_user_row)["name"] if deleted_user_row else str(deleted_user_id)

        await session.execute(
            text("DELETE FROM users WHERE id = :id"),
            {"id": deleted_user_id}
        )

        await session.commit()

        if deleted_by_user:
            await log_business_activity(
                user=deleted_by_user,
                path="/activity/users/delete",
                description=f"{deleted_by_user.get('name') or deleted_by_user.get('email')} deleted user {deleted_user_name} (via reassignment request #{request_id})",
            )

        return True, f"Reassigned {len(direct_children)} user(s) to {new_parent_name}"


async def reject_request(request_id: str) -> Tuple[bool, str]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM reassignment_requests WHERE id = :id"),
            {"id": int(request_id)}
        )
        row = result.mappings().first()
        if not row:
            return False, "Reassignment request not found"

        req = dict(row)
        if req.get("status") != "pending":
            return False, f"Request is already {req.get('status')}"

        now = datetime.now().replace(tzinfo=None)
        await session.execute(
            text("UPDATE reassignment_requests SET status = 'rejected', updated_at = :updated_at WHERE id = :id"),
            {"updated_at": now, "id": int(request_id)}
        )
        await session.commit()
        return True, "Request rejected"
