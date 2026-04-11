import logging
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from typing import Optional

from app.database import get_db
from app.models.user import UserCreate, UserUpdate
from app.services import user_service
from app.middleware.auth_middleware import get_current_user
from app.core.audit import audit_logger
from app.core.activity_logger import build_field_change_summary, log_business_activity
from app.utils.roles import (
    SUPER_ADMIN,
    MD_DIRECTOR,
    MANAGER,
    PDIC_STAFF,
    SUB_DISTRIBUTION_MANAGER,
    SUB_DISTRIBUTOR,
    CLUSTER,
    OPERATOR,
    normalize_role,
    can_manage_user,
    can_mutate_super_admin,
)

router = APIRouter()

logger = logging.getLogger(__name__)


ALLOWED_CREATE_BY_ROLE = {
    SUPER_ADMIN: [SUPER_ADMIN, MD_DIRECTOR, MANAGER, PDIC_STAFF, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER, OPERATOR],
    MANAGER: [PDIC_STAFF, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER, OPERATOR],
    SUB_DISTRIBUTION_MANAGER: [CLUSTER, OPERATOR],
}


async def _branch_contains_user(root_user_id: str, target_user_id: str) -> bool:
    if str(root_user_id) == str(target_user_id):
        return True

    pending = [int(root_user_id)]
    visited = set()

    async with get_db() as db:
        while pending:
            parent_id = pending.pop()
            if parent_id in visited:
                continue
            visited.add(parent_id)

            cursor = await db.execute("SELECT id FROM users WHERE parent_id = ?", (parent_id,))
            children = await cursor.fetchall()
            for child in children:
                child_id = int(child["id"])
                if str(child_id) == str(target_user_id):
                    return True
                pending.append(child_id)

    return False


async def _can_access_user(current_user: dict, target_user: dict, *, write: bool) -> bool:
    actor_role = normalize_role(current_user.get("role"))
    target_role = normalize_role(target_user.get("role"))

    if actor_role == MD_DIRECTOR and target_role == SUPER_ADMIN:
        return False

    if str(current_user.get("id")) == str(target_user.get("id")):
        return True

    if actor_role == SUPER_ADMIN:
        if write:
            return can_mutate_super_admin(current_user.get("id"), actor_role, target_user.get("id"), target_role)
        return True

    if actor_role == MD_DIRECTOR:
        return not write

    if actor_role == PDIC_STAFF:
        return False

    if actor_role == MANAGER:
        if not write and target_role == MANAGER:
            if current_user.get("parent_id"):
                return await _branch_contains_user(current_user["parent_id"], target_user.get("id"))
            return True
        if not can_manage_user(actor_role, target_role):
            return False
        if current_user.get("parent_id"):
            return await _branch_contains_user(current_user["parent_id"], target_user.get("id"))
        return True

    if actor_role == SUB_DISTRIBUTION_MANAGER:
        if write and target_role in {SUB_DISTRIBUTOR, SUB_DISTRIBUTION_MANAGER}:
            return False
        if target_role not in {SUB_DISTRIBUTOR, SUB_DISTRIBUTION_MANAGER, CLUSTER, OPERATOR}:
            return False
        root_id = str(current_user.get("parent_id") or current_user.get("id"))
        if str(target_user.get("id")) == root_id:
            return True
        return await _branch_contains_user(root_id, target_user.get("id"))

    if actor_role == SUB_DISTRIBUTOR:
        if write:
            return False
        if target_role not in {CLUSTER, OPERATOR}:
            return False
        return await _branch_contains_user(current_user.get("id"), target_user.get("id"))

    if actor_role == CLUSTER:
        if write:
            return False
        return target_role == OPERATOR and str(target_user.get("parent_id")) == str(current_user.get("id"))

    return False


@router.get("")
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    role: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    parent_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    actor_role = normalize_role(current_user.get("role"))
    normalized_role_filter = normalize_role(role) if role else None

    parent_id_filter = None
    parent_ids_in_filter = None

    if actor_role in {SUPER_ADMIN, MD_DIRECTOR, MANAGER}:
        parent_id_filter = parent_id
    elif actor_role == PDIC_STAFF:
        # Staff needs role-filtered lookup for distribution recipient selectors.
        # Keep legacy self-only response for generic, non-role-filtered listing.
        if normalized_role_filter in {SUB_DISTRIBUTOR, CLUSTER, OPERATOR}:
            parent_id_filter = parent_id
        else:
            user = await user_service.get_user_by_id(str(current_user["id"]))
            return {
                "success": True,
                "message": "Users retrieved successfully",
                "data": [user] if user else [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": 1 if user else 0,
                    "total_pages": 1,
                    "has_next": False,
                    "has_prev": False,
                },
            }
    elif actor_role == SUB_DISTRIBUTION_MANAGER:
        scope_root = str(current_user.get("parent_id") or current_user["id"])
        parent_id_filter = scope_root
        if normalized_role_filter in {CLUSTER, OPERATOR}:
            manager_result = await user_service.get_users(role=SUB_DISTRIBUTION_MANAGER, parent_id=scope_root, page_size=1_000_000)
            manager_ids = [int(m["id"]) for m in manager_result["data"]]
            candidate_parent_ids = [int(scope_root)] + manager_ids if str(scope_root).isdigit() else manager_ids

            if normalized_role_filter == CLUSTER:
                parent_ids_in_filter = candidate_parent_ids
                parent_id_filter = None
            else:
                if not candidate_parent_ids:
                    parent_ids_in_filter = []
                    parent_id_filter = None
                else:
                    clusters_result = await user_service.get_users(role=CLUSTER, parent_ids_in=candidate_parent_ids, page_size=1_000_000)
                    cluster_ids = [int(c["id"]) for c in clusters_result["data"]]
                    parent_ids_in_filter = cluster_ids + candidate_parent_ids
                    parent_id_filter = None
    elif actor_role == SUB_DISTRIBUTOR:
        parent_id_filter = str(current_user["id"])
        if normalized_role_filter == OPERATOR:
            sub_dist_manager_result = await user_service.get_users(role=SUB_DISTRIBUTION_MANAGER, parent_id=str(current_user["id"]), page_size=1_000_000)
            sub_dist_manager_ids = [int(m["id"]) for m in sub_dist_manager_result["data"]]
            candidate_cluster_parent_ids = [int(current_user["id"])] + sub_dist_manager_ids
            clusters_result = await user_service.get_users(role=CLUSTER, parent_ids_in=candidate_cluster_parent_ids, page_size=1_000_000)
            parent_ids_in_filter = [int(c["id"]) for c in clusters_result["data"]]
            parent_id_filter = None
    elif actor_role == CLUSTER:
        parent_id_filter = str(current_user["id"])
    elif actor_role == OPERATOR:
        if normalized_role_filter == OPERATOR:
            parent_id_filter = str(current_user.get("parent_id", ""))
        else:
            raise HTTPException(status_code=403, detail="Operators can only list operators")

    try:
        result = await user_service.get_users(
            page=page,
            page_size=page_size,
            role=normalized_role_filter,
            status=status_filter,
            search=search,
            parent_id=parent_id_filter,
            parent_ids_in=parent_ids_in_filter,
        )

        if actor_role in {MANAGER, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER}:
            filtered = []
            for row in result["data"]:
                if await _can_access_user(current_user, row, write=False):
                    filtered.append(row)
            result["data"] = filtered

        if actor_role == MD_DIRECTOR:
            result["data"] = [row for row in result["data"] if normalize_role(row.get("role")) != SUPER_ADMIN]

        return {
            "success": True,
            "message": "Users retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.get("/{user_id}")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    try:
        user = await user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if not await _can_access_user(current_user, user, write=False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        return {"success": True, "message": "User retrieved successfully", "data": user}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate, current_user: dict = Depends(get_current_user)):
    actor_role = normalize_role(current_user.get("role"))
    target_role = normalize_role(user_data.role.value)

    if target_role != SUB_DISTRIBUTOR:
        user_data = user_data.model_copy(update={"digital_id": None, "broadband_id": None})

    if actor_role not in ALLOWED_CREATE_BY_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to create users")

    if target_role not in ALLOWED_CREATE_BY_ROLE[actor_role]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"You cannot create role '{target_role}'")

    if target_role == SUB_DISTRIBUTION_MANAGER:
        if actor_role == SUB_DISTRIBUTOR and not user_data.parent_id:
            user_data = user_data.model_copy(update={"parent_id": str(current_user["id"])})

        if not user_data.parent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must select a sub distributor parent for sub distribution manager",
            )

        parent_user = await user_service.get_user_by_id(user_data.parent_id)
        if not parent_user or normalize_role(parent_user.get("role")) != SUB_DISTRIBUTOR:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sub distributor selected")

        if actor_role == SUB_DISTRIBUTOR and str(user_data.parent_id) != str(current_user.get("id")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only assign sub distribution managers under your own account",
            )

    if target_role == CLUSTER:
        if actor_role == SUB_DISTRIBUTION_MANAGER and not user_data.parent_id:
            user_data = user_data.model_copy(update={"parent_id": str(current_user.get("parent_id"))})

        if not user_data.parent_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must select a sub distributor parent for cluster")

        parent_user = await user_service.get_user_by_id(user_data.parent_id)
        if not parent_user or normalize_role(parent_user.get("role")) != SUB_DISTRIBUTOR:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sub distributor selected")

        if actor_role == SUB_DISTRIBUTION_MANAGER and str(user_data.parent_id) != str(current_user.get("parent_id")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only assign clusters under your own sub distribution")

        if actor_role == SUB_DISTRIBUTOR and not await _branch_contains_user(current_user.get("id"), user_data.parent_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected sub distributor is outside your branch")

    if actor_role == CLUSTER and target_role == OPERATOR and not user_data.parent_id:
        user_data = user_data.model_copy(update={"parent_id": str(current_user["id"])})

    if target_role == OPERATOR:
        if not user_data.parent_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must select a cluster parent for operator")
        cluster = await user_service.get_user_by_id(user_data.parent_id)
        if not cluster or normalize_role(cluster.get("role")) != CLUSTER:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cluster selected")

    if actor_role == SUB_DISTRIBUTOR:
        if target_role == OPERATOR:
            cluster = await user_service.get_user_by_id(user_data.parent_id)
            if not cluster or not await _branch_contains_user(current_user.get("id"), cluster.get("id")):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected cluster is outside your branch")

    if actor_role == SUB_DISTRIBUTION_MANAGER and target_role == OPERATOR:
        cluster = await user_service.get_user_by_id(user_data.parent_id)
        if not cluster or not await _branch_contains_user(current_user.get("id"), cluster.get("id")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected cluster is outside your branch")

    try:
        user = await user_service.create_user(user_data, creator_role=actor_role)
        actor_name = current_user.get("name") or current_user.get("email") or "User"
        await log_business_activity(
            user=current_user,
            path="/activity/users/create",
            description=(
                f"{actor_name} created user {user.get('name') or user.get('email') or user.get('id')} "
                f"({user.get('role') or 'unknown role'})"
            ),
        )
        return {"success": True, "message": "User created successfully", "data": user}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.put("/{user_id}")
async def update_user(user_id: str, user_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    try:
        actor_role = normalize_role(current_user.get("role"))
        if actor_role == MD_DIRECTOR:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MD/Director has read-only access to users")

        target_user = await user_service.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if not await _can_access_user(current_user, target_user, write=True):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        if actor_role in {MD_DIRECTOR, PDIC_STAFF} and str(current_user.get("id")) != str(user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        if actor_role in {MD_DIRECTOR, PDIC_STAFF} and user_data.status is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot change account status")

        user = await user_service.update_user(user_id, user_data)
        actor_name = current_user.get("name") or current_user.get("email") or "User"
        edited_fields = list(user_data.model_dump(exclude_unset=True).keys())
        change_summary = build_field_change_summary(
            before=target_user or {},
            after=user or {},
            fields=edited_fields,
            exclude_fields={"updated_at", "password_hash"},
        )
        await log_business_activity(
            user=current_user,
            path="/activity/users/update",
            description=(
                f"{actor_name} updated user "
                f"{user.get('name') or user.get('email') or user_id}; "
                f"changes: {change_summary}"
            ),
        )
        return {"success": True, "message": "User updated successfully", "data": user}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.delete("/{user_id}")
async def delete_user(request: Request, user_id: str, current_user: dict = Depends(get_current_user)):
    actor_role = normalize_role(current_user.get("role"))

    if actor_role not in {SUPER_ADMIN, SUB_DISTRIBUTION_MANAGER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if str(current_user.get("id")) == str(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")

    target_user = await user_service.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if actor_role == SUPER_ADMIN:
        if not can_mutate_super_admin(current_user.get("id"), actor_role, target_user.get("id"), target_user.get("role")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another super admin")
    else:
        if not await _can_access_user(current_user, target_user, write=True):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    try:
        success = await user_service.delete_user(user_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        actor_name = current_user.get("name") or current_user.get("email") or "User"
        target_name = target_user.get("name") or target_user.get("email") or user_id
        await log_business_activity(
            user=current_user,
            path="/activity/users/delete",
            description=f"{actor_name} deleted user {target_name}",
        )

        audit_logger.warning(
            "USER_DELETE | actor_id=%s | actor_email=%s | target_user_id=%s | ip=%s",
            current_user.get("id"),
            current_user.get("email"),
            user_id,
            request.client.host if request.client else "unknown",
        )

        return {"success": True, "message": "User deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.patch("/{user_id}/status")
async def update_user_status(
    request: Request,
    user_id: str,
    status_update: dict,
    current_user: dict = Depends(get_current_user),
):
    actor_role = normalize_role(current_user.get("role"))
    if actor_role not in {SUPER_ADMIN, MANAGER, SUB_DISTRIBUTION_MANAGER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    status_value = status_update.get("status")
    if status_value not in ["active", "inactive", "suspended"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status value")

    target_user = await user_service.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not await _can_access_user(current_user, target_user, write=True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if actor_role in {MANAGER, SUB_DISTRIBUTION_MANAGER} and normalize_role(target_user.get("role")) == SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update super admin status")

    try:
        user = await user_service.update_user_status(user_id, status_value)
        actor_name = current_user.get("name") or current_user.get("email") or "User"
        change_summary = build_field_change_summary(
            before=target_user or {},
            after=user or {},
            fields=["status"],
            exclude_fields={"updated_at"},
        )
        await log_business_activity(
            user=current_user,
            path="/activity/users/status-update",
            description=(
                f"{actor_name} updated user status for "
                f"{user.get('name') or user.get('email') or user_id}; "
                f"changes: {change_summary}"
            ),
        )
        audit_logger.info(
            "USER_STATUS_UPDATE | actor_id=%s | actor_email=%s | target_user_id=%s | status=%s | ip=%s",
            current_user.get("id"),
            current_user.get("email"),
            user_id,
            status_value,
            request.client.host if request.client else "unknown",
        )
        return {"success": True, "message": "User status updated successfully", "data": user}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.patch("/{user_id}/credentials")
async def admin_update_credentials(
    request: Request,
    user_id: str,
    data: dict,
    current_user: dict = Depends(get_current_user),
):
    from app.utils.security import get_password_hash as _hash
    from datetime import datetime as _dt, timezone as _timezone

    actor_role = normalize_role(current_user.get("role"))
    if actor_role != SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    target_user = await user_service.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not can_mutate_super_admin(current_user.get("id"), actor_role, target_user.get("id"), target_user.get("role")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update another super admin credentials")

    try:
        async with get_db() as db:
            update_fields = []
            params = []

            if "email" in data and data["email"]:
                normalized_email = str(data["email"]).lower().strip()
                cursor = await db.execute("SELECT id FROM users WHERE email = ? AND id != ?", (normalized_email, int(user_id)))
                if await cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Email already in use")
                update_fields.append("email = ?")
                params.append(normalized_email)

            if "password" in data and data["password"]:
                if len(data["password"]) < 8:
                    raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
                update_fields.append("password_hash = ?")
                params.append(_hash(data["password"]))

            if not update_fields:
                raise HTTPException(status_code=400, detail="No data to update")

            update_fields.append("updated_at = ?")
            params.append(_dt.now(_timezone.utc).replace(tzinfo=None).isoformat())
            params.append(int(user_id))

            cursor = await db.execute(f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?", params)
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found")
            await db.commit()

        updated = await user_service.get_user_by_id(user_id)

        audit_logger.info(
            "USER_CREDENTIALS_UPDATE | actor_id=%s | actor_email=%s | target_user_id=%s | ip=%s",
            current_user.get("id"),
            current_user.get("email"),
            user_id,
            request.client.host if request.client else "unknown",
        )

        return {"success": True, "message": "Credentials updated", "data": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.get("/role/{role}")
async def get_users_by_role(role: str, current_user: dict = Depends(get_current_user)):
    actor_role = normalize_role(current_user.get("role"))
    normalized = normalize_role(role)

    if actor_role not in {SUPER_ADMIN, MD_DIRECTOR, MANAGER, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    try:
        users = await user_service.get_users_by_role(normalized)
        filtered = []
        for row in users:
            if await _can_access_user(current_user, row, write=False):
                filtered.append(row)
        return {"success": True, "message": "Users retrieved successfully", "data": filtered}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")




