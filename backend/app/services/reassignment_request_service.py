from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import json

from app.core.cache_version import bump_cache_version
from app.database_sqlalchemy import async_session_factory
from app.services.bulk_upload_service import chunks
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


def _flatten_child_ids(children: List[Dict[str, Any]]) -> List[int]:
    """Collect every child user id (including nested ones) referenced by a request."""
    ids = []
    for c in children:
        cid = c.get("id")
        if cid is not None:
            try:
                ids.append(int(cid))
            except (TypeError, ValueError):
                pass
        if c.get("children"):
            ids.extend(_flatten_child_ids(c["children"]))
    return ids


def _prune_children(children: List[Dict[str, Any]], existing_ids: set) -> List[Dict[str, Any]]:
    """Keep only children that still exist, recursing into nested children."""
    pruned = []
    for c in children:
        cid = c.get("id")
        if cid is None:
            continue
        try:
            keep = int(cid) in existing_ids
        except (TypeError, ValueError):
            keep = False
        if keep:
            item = dict(c)
            if c.get("children"):
                item["children"] = _prune_children(c["children"], existing_ids)
            pruned.append(item)
    return pruned


async def cleanup_stale_reassignment_requests() -> int:
    """Take down pending reassignment requests whose users for reassignment no longer exist.

    A request whose children were all deleted cannot be reassigned, so it is removed.
    If the user scheduled for deletion still exists and currently has no children, the
    deferred deletion is completed. Requests that lost only some children are pruned to
    reference surviving users only. Returns the number of requests removed.
    """
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM reassignment_requests WHERE status = 'pending'")
        )
        rows = result.mappings().all()
        if not rows:
            return 0

        removed = 0
        now = datetime.now().replace(tzinfo=None)

        for row in rows:
            req = dict(row)
            try:
                children = json.loads(req.get("children_json") or "[]")
            except (json.JSONDecodeError, TypeError):
                children = []

            child_ids = _flatten_child_ids(children)
            if not child_ids:
                continue

            placeholders = ",".join(f":id_{i}" for i in range(len(child_ids)))
            params = {f"id_{i}": cid for i, cid in enumerate(child_ids)}
            existing_res = await session.execute(
                text(f"SELECT id FROM users WHERE id IN ({placeholders})"),
                params,
            )
            existing_ids = {int(r[0]) for r in existing_res.all()}

            if not existing_ids:
                await session.execute(
                    text("DELETE FROM reassignment_requests WHERE id = :id"),
                    {"id": int(req["id"])},
                )
                removed += 1

                deleted_user_id = req.get("deleted_user_id")
                if deleted_user_id is not None:
                    user_res = await session.execute(
                        text("SELECT id FROM users WHERE id = :id"),
                        {"id": int(deleted_user_id)},
                    )
                    if user_res.first():
                        child_count = await session.execute(
                            text("SELECT COUNT(*) FROM users WHERE parent_id = :pid"),
                            {"pid": int(deleted_user_id)},
                        )
                        if (child_count.scalar() or 0) == 0:
                            await session.execute(
                                text("DELETE FROM users WHERE id = :id"),
                                {"id": int(deleted_user_id)},
                            )
                            await session.execute(
                                text("DELETE FROM digital_identities WHERE user_id = :uid"),
                                {"uid": int(deleted_user_id)},
                            )
            elif len(existing_ids) < len(child_ids):
                surviving = _prune_children(children, existing_ids)
                await session.execute(
                    text("UPDATE reassignment_requests SET children_json = :cj, updated_at = :updated_at WHERE id = :id"),
                    {"cj": json.dumps(surviving), "updated_at": now, "id": int(req["id"])},
                )

        await bump_cache_version(session)
        await session.commit()
        return removed


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
        await bump_cache_version(session)
        await session.commit()

        result = await session.execute(
            text("SELECT * FROM reassignment_requests WHERE request_id = :request_id"),
            {"request_id": request_id}
        )
        row = result.mappings().first()
        return dict(row) if row else {"request_id": request_id, "status": "pending"}


async def get_reassignment_requests(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None
) -> Dict[str, Any]:
    cleaned_up = await cleanup_stale_reassignment_requests()
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
            "pagination": get_pagination(page, page_size, total),
            "cleaned_up": cleaned_up
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
            for batch in chunks(child_ids, 1000):
                placeholders = ",".join(f":id_{i}" for i in range(len(batch)))
                params_dict = {"parent_id": new_parent_id, "updated_at": now}
                for i, cid in enumerate(batch):
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

        await bump_cache_version(session)
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
        await bump_cache_version(session)
        await session.commit()
        return True, "Request rejected"
