from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.database import get_db, row_to_dict, rows_to_list
from app.models.approval import ApprovalStatus, ApprovalType
from app.core.activity_logger import log_business_activity
from app.services import notification_service
from app.utils.helpers import get_pagination


APPROVAL_TYPES = ("distribution", "return", "defect")
ENTITY_TABLE_MAP = {
    "distribution": "distributions",
    "return": "returns",
    "defect": "defects",
}
ALLOWED_ENTITY_TABLES = set(ENTITY_TABLE_MAP.values())


def _normalize_role(role: Optional[str]) -> str:
    return str(role or "").strip().lower()


async def _ensure_default_routing_rows(db) -> None:
    for approval_type in APPROVAL_TYPES:
        await db.execute(
            """INSERT OR IGNORE INTO approval_role_routing
               (approval_type, admin_enabled, manager_enabled, staff_enabled, updated_by, updated_at)
               VALUES (?, 1, 1, 1, 'system', ?)""",
            (approval_type, datetime.now(timezone.utc).replace(tzinfo=None).isoformat()),
        )


def _routing_rows_to_payload(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    payload = {
        "distribution": {"super_admin": True, "manager": True, "pdic_staff": True},
        "return": {"super_admin": True, "manager": True, "pdic_staff": True},
        "defect": {"super_admin": True, "manager": True, "pdic_staff": True},
        "updated_at": None,
    }
    last_updated = None
    for row in rows:
        approval_type = row.get("approval_type")
        if approval_type not in APPROVAL_TYPES:
            continue
        payload[approval_type] = {
            "super_admin": bool(row.get("admin_enabled", 1)),
            "manager": bool(row.get("manager_enabled", 1)),
            "pdic_staff": bool(row.get("staff_enabled", 1)),
        }
        updated_at = row.get("updated_at")
        if updated_at and (last_updated is None or updated_at > last_updated):
            last_updated = updated_at
    payload["updated_at"] = last_updated
    return payload


async def get_role_routing_config() -> Dict[str, Any]:
    async with get_db() as db:
        await _ensure_default_routing_rows(db)
        await db.commit()
        cursor = await db.execute(
            "SELECT id, approval_type, admin_enabled, manager_enabled, staff_enabled, updated_at FROM approval_role_routing"
        )
        rows = [dict(r) for r in await cursor.fetchall()]
    return _routing_rows_to_payload(rows)


async def update_role_routing_config(config: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    actor_id = actor.get("id") or actor.get("_id")
    actor_name = actor.get("name") or "super_admin"
    updated_by = f"{actor_name} ({actor_id})" if actor_id else str(actor_name)
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    async with get_db() as db:
        await _ensure_default_routing_rows(db)

        for approval_type in APPROVAL_TYPES:
            role_config = config.get(approval_type) or {}
            admin_enabled = 1 if bool(role_config.get("super_admin", True)) else 0
            manager_enabled = 1 if bool(role_config.get("manager", True)) else 0
            staff_enabled = 1 if bool(role_config.get("pdic_staff", True)) else 0
            await db.execute(
                """UPDATE approval_role_routing
                   SET admin_enabled = ?, manager_enabled = ?, staff_enabled = ?, updated_by = ?, updated_at = ?
                   WHERE approval_type = ?""",
                (admin_enabled, manager_enabled, staff_enabled, updated_by, now, approval_type),
            )

        await db.commit()

    return await get_role_routing_config()


async def is_role_allowed_for_approval_type(role: str, approval_type: str) -> bool:
    normalized_role = _normalize_role(role)
    if normalized_role not in {"super_admin", "manager", "pdic_staff"}:
        return True

    if approval_type not in APPROVAL_TYPES:
        return True

    async with get_db() as db:
        await _ensure_default_routing_rows(db)
        cursor = await db.execute(
            """SELECT admin_enabled, manager_enabled, staff_enabled
               FROM approval_role_routing
               WHERE approval_type = ?""",
            (approval_type,),
        )
        row = await cursor.fetchone()
        await db.commit()

    if not row:
        return True

    row_dict = dict(row)
    if normalized_role == "super_admin":
        return bool(row_dict.get("admin_enabled", 1))
    if normalized_role == "manager":
        return bool(row_dict.get("manager_enabled", 1))
    if normalized_role == "pdic_staff":
        return bool(row_dict.get("staff_enabled", 1))
    return True


async def get_enabled_approval_types_for_role(role: str) -> List[str]:
    normalized_role = _normalize_role(role)
    if normalized_role not in {"super_admin", "manager", "pdic_staff"}:
        return list(APPROVAL_TYPES)

    async with get_db() as db:
        await _ensure_default_routing_rows(db)
        cursor = await db.execute(
            "SELECT id, approval_type, admin_enabled, manager_enabled, staff_enabled FROM approval_role_routing"
        )
        rows = [dict(r) for r in await cursor.fetchall()]
        await db.commit()

    enabled_types: List[str] = []
    for row in rows:
        approval_type = row.get("approval_type")
        if approval_type not in APPROVAL_TYPES:
            continue
        if normalized_role == "super_admin" and bool(row.get("admin_enabled", 1)):
            enabled_types.append(approval_type)
        if normalized_role == "manager" and bool(row.get("manager_enabled", 1)):
            enabled_types.append(approval_type)
        if normalized_role == "pdic_staff" and bool(row.get("staff_enabled", 1)):
            enabled_types.append(approval_type)
    return enabled_types


async def get_routing_enabled_roles_for_approval_type(approval_type: str) -> List[str]:
    if approval_type not in APPROVAL_TYPES:
        return ["super_admin", "manager", "pdic_staff"]
    async with get_db() as db:
        await _ensure_default_routing_rows(db)
        cursor = await db.execute(
            """SELECT admin_enabled, manager_enabled, staff_enabled
               FROM approval_role_routing
               WHERE approval_type = ?""",
            (approval_type,),
        )
        row = await cursor.fetchone()
        await db.commit()
    if not row:
        return ["super_admin", "manager", "pdic_staff"]
    row_dict = dict(row)
    roles: List[str] = []
    if bool(row_dict.get("admin_enabled", 1)):
        roles.append("super_admin")
    if bool(row_dict.get("manager_enabled", 1)):
        roles.append("manager")
    if bool(row_dict.get("staff_enabled", 1)):
        roles.append("pdic_staff")
    return roles


async def _get_entity_details(db, approval_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
    """Get entity details for an approval"""
    table = ENTITY_TABLE_MAP.get(approval_type)
    if table and table not in ALLOWED_ENTITY_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    if not table:
        return None
    cursor = await db.execute(f"SELECT * FROM {table} WHERE id = ?", (int(entity_id),))
    row = await cursor.fetchone()
    if not row:
        return None
    entity = row_to_dict(row)

    if approval_type == "distribution":
        return {
            "distribution_id": entity.get("distribution_id"),
            "device_count": entity.get("device_count"),
            "from_user_name": entity.get("from_user_name"),
            "to_user_name": entity.get("to_user_name")
        }
    elif approval_type == "return":
        return {
            "return_id": entity.get("return_id"),
            "device_serial": entity.get("device_serial"),
            "reason": entity.get("reason"),
            "requested_by_name": entity.get("requested_by_name")
        }
    elif approval_type == "defect":
        return {
            "report_id": entity.get("report_id"),
            "device_serial": entity.get("device_serial"),
            "defect_type": entity.get("defect_type"),
            "severity": entity.get("severity")
        }
    return None


async def get_approvals(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    approval_type: Optional[str] = None,
    search: Optional[str] = None,
    viewer_role: Optional[str] = None,
) -> Dict[str, Any]:
    """Get all pending approvals with pagination"""
    async with get_db() as db:
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        else:
            conditions.append("status = ?")
            params.append(ApprovalStatus.PENDING.value)
        if approval_type:
            conditions.append("approval_type = ?")
            params.append(approval_type)
        if search:
            conditions.append("requested_by_name LIKE ?")
            params.append(f"%{search}%")

        enabled_types = await get_enabled_approval_types_for_role(viewer_role or "")
        if enabled_types:
            placeholders = ", ".join(["?"] * len(enabled_types))
            conditions.append(f"approval_type IN ({placeholders})")
            params.extend(enabled_types)
        else:
            conditions.append("1 = 0")

        where = " AND ".join(conditions) if conditions else "1=1"

        cursor = await db.execute(f"SELECT COUNT(*) FROM approvals WHERE {where}", params)
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"SELECT * FROM approvals WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = await cursor.fetchall()

        enriched = []
        for row in rows:
            approval_data = row_to_dict(row)
            details = await _get_entity_details(db, approval_data.get("approval_type", ""), approval_data.get("entity_id", ""))
            if details:
                approval_data["entity_details"] = details
            enriched.append(approval_data)

        return {
            "data": enriched,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_approval_by_id(approval_id: str) -> Optional[Dict[str, Any]]:
    """Get approval by ID with entity details"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM approvals WHERE id = ?", (int(approval_id),))
        row = await cursor.fetchone()
        if not row:
            return None

        approval_data = row_to_dict(row)

        # Get full entity details
        table = ENTITY_TABLE_MAP.get(approval_data.get("approval_type"))
        if table and table not in ALLOWED_ENTITY_TABLES:
            raise ValueError(f"Invalid table name: {table}")
        if table and approval_data.get("entity_id"):
            cursor = await db.execute(f"SELECT * FROM {table} WHERE id = ?", (int(approval_data["entity_id"]),))
            entity_row = await cursor.fetchone()
            if entity_row:
                approval_data["entity_details"] = row_to_dict(entity_row)

        return approval_data


async def approve_request(
    approval_id: str,
    approver: Dict[str, Any],
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Approve a pending request"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM approvals WHERE id = ?", (int(approval_id),))
        approval = await cursor.fetchone()
        if not approval:
            return None
        approval = dict(approval)

        if approval["status"] != ApprovalStatus.PENDING.value:
            raise ValueError("This request has already been processed")

        approver_role = _normalize_role(approver.get("role"))
        if approver_role in {"super_admin", "manager", "pdic_staff"}:
            allowed = await is_role_allowed_for_approval_type(approver_role, approval.get("approval_type"))
            if not allowed:
                raise PermissionError(
                    f"{approver_role.capitalize()} role is not allowed to process {approval.get('approval_type')} requests"
                )

        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        await db.execute(
            """UPDATE approvals SET status = ?, approved_by = ?, approved_by_name = ?,
            approval_date = ?, notes = ?, updated_at = ? WHERE id = ?""",
            (ApprovalStatus.APPROVED.value, str(approver["_id"]), approver["name"],
             now, notes, now, int(approval_id))
        )

        # Update related entity
        entity_id = approval["entity_id"]
        if approval["approval_type"] == "distribution":
            await db.execute(
                """UPDATE distributions SET status = 'approved', approval_date = ?,
                approved_by = ?, approved_by_name = ?, updated_at = ? WHERE id = ?""",
                (now, str(approver["_id"]), approver["name"], now, int(entity_id))
            )
        elif approval["approval_type"] == "return":
            await db.execute(
                """UPDATE returns SET status = 'approved', approval_date = ?,
                approved_by = ?, approved_by_name = ?, updated_at = ? WHERE id = ?""",
                (now, str(approver["_id"]), approver["name"], now, int(entity_id))
            )
        elif approval["approval_type"] == "defect":
            await db.execute(
                "UPDATE defects SET status = 'approved', updated_at = ? WHERE id = ?",
                (now, int(entity_id))
            )

        await db.commit()

    await notification_service.create_notification(
        user_id=approval["requested_by"],
        title="Request Approved",
        message=f"Your {approval['approval_type']} request has been approved by {approver['name']}",
        notification_type="success",
        category="approval"
    )

    try:
        approval_record = await get_approval_by_id(approval_id)
        entity_details = (approval_record or {}).get("entity_details") or {}
        approver_name = approver.get("name") or approver.get("email") or "User"

        if approval.get("approval_type") == "defect":
            report_ref = entity_details.get("report_id") or approval.get("entity_id")
            await log_business_activity(
                user=approver,
                path="/activity/defects/approve",
                description=f"{approver_name} approved defect {report_ref}",
            )
        elif approval.get("approval_type") == "return":
            return_ref = entity_details.get("return_id") or approval.get("entity_id")
            requester = entity_details.get("requested_by_name") or approval.get("requested_by_name") or "unknown user"
            await log_business_activity(
                user=approver,
                path="/activity/returns/approve",
                description=f"{approver_name} approved return request {return_ref} from {requester}",
            )
    except Exception:
        # Approval should still succeed even if activity logging fails.
        pass

    return await get_approval_by_id(approval_id)


async def reject_request(
    approval_id: str,
    approver: Dict[str, Any],
    rejection_reason: Optional[str] = None,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Reject a pending request"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM approvals WHERE id = ?", (int(approval_id),))
        approval = await cursor.fetchone()
        if not approval:
            return None
        approval = dict(approval)

        if approval["status"] != ApprovalStatus.PENDING.value:
            raise ValueError("This request has already been processed")

        approver_role = _normalize_role(approver.get("role"))
        if approver_role in {"super_admin", "manager", "pdic_staff"}:
            allowed = await is_role_allowed_for_approval_type(approver_role, approval.get("approval_type"))
            if not allowed:
                raise PermissionError(
                    f"{approver_role.capitalize()} role is not allowed to process {approval.get('approval_type')} requests"
                )

        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        await db.execute(
            """UPDATE approvals SET status = ?, approved_by = ?, approved_by_name = ?,
            approval_date = ?, rejection_reason = ?, notes = ?, updated_at = ? WHERE id = ?""",
            (ApprovalStatus.REJECTED.value, str(approver["_id"]), approver["name"],
             now, rejection_reason, notes, now, int(approval_id))
        )

        entity_id = approval["entity_id"]
        if approval["approval_type"] == "distribution":
            await db.execute(
                "UPDATE distributions SET status = 'rejected', notes = ?, updated_at = ? WHERE id = ?",
                (rejection_reason, now, int(entity_id))
            )
        elif approval["approval_type"] == "return":
            await db.execute(
                "UPDATE returns SET status = 'rejected', updated_at = ? WHERE id = ?",
                (now, int(entity_id))
            )
        elif approval["approval_type"] == "defect":
            await db.execute(
                "UPDATE defects SET status = 'rejected', updated_at = ? WHERE id = ?",
                (now, int(entity_id))
            )

        await db.commit()

    await notification_service.create_notification(
        user_id=approval["requested_by"],
        title="Request Rejected",
        message=f"Your {approval['approval_type']} request has been rejected by {approver['name']}. Reason: {rejection_reason or 'No reason provided'}",
        notification_type="error",
        category="approval"
    )

    return await get_approval_by_id(approval_id)


async def get_approval_stats() -> Dict[str, int]:
    """Get approval statistics"""
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM approvals WHERE status = 'pending'")
        pending = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM approvals WHERE status = 'approved'")
        approved = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM approvals WHERE status = 'rejected'")
        rejected = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM approvals WHERE approval_type = 'distribution' AND status = 'pending'")
        dist_pending = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM approvals WHERE approval_type = 'return' AND status = 'pending'")
        ret_pending = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM approvals WHERE approval_type = 'defect' AND status = 'pending'")
        def_pending = (await cursor.fetchone())[0]

        return {
            "total_pending": pending,
            "approved": approved,
            "rejected": rejected,
            "by_type": {
                "distributions": dist_pending,
                "returns": ret_pending,
                "defects": def_pending
            }
        }

