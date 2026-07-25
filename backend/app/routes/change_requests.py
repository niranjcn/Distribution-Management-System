import logging
import json
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from typing import Optional
from pydantic import BaseModel
from app.database import get_db, row_to_dict, rows_to_list
from app.models.device import DeviceUpdate
from app.middleware.auth_middleware import get_current_user, require_admin, require_admin_or_manager
from app.utils.security import get_password_hash
from app.utils.helpers import get_pagination
from app.services import device_service, notification_service, defect_service
from app.core.audit import audit_logger
from datetime import datetime, timezone
import uuid

router = APIRouter()

logger = logging.getLogger(__name__)


def _looks_like_bcrypt_hash(value: Optional[str]) -> bool:
    if not value:
        return False
    return value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")


class ChangeRequestCreate(BaseModel):
    request_type: str  # 'email_change', 'password_reset', 'both', 'device_status_change', 'device_edit_change', 'replacement_transfer_fix'
    new_email: Optional[str] = None
    new_password: Optional[str] = None
    device_id: Optional[str] = None
    requested_status: Optional[str] = None
    reason: Optional[str] = None


ALLOWED_TRANSFER_FIX_DEFECT_STATUSES = {
    "replacement_pending_confirmation",
    "replacement_waiting_for_device",
}


async def _validate_operator_transfer_fix_request(db, operator_user: dict, defect_id: str) -> dict:
    """Validate that operator is involved in the defect and transfer-fix is applicable."""
    if not str(defect_id).isdigit():
        raise HTTPException(status_code=400, detail="defect_id must be numeric")

    cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
    defect = await cursor.fetchone()
    if not defect:
        raise HTTPException(status_code=404, detail="Defect not found")
    defect = dict(defect)

    if defect.get("status") not in ALLOWED_TRANSFER_FIX_DEFECT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Transfer fix can only be requested for pending/waiting replacement defects",
        )

    if not defect.get("replacement_device_id"):
        raise HTTPException(status_code=400, detail="Defect has no replacement device mapping yet")

    cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(defect["device_id"]),))
    defective_device = await cursor.fetchone()
    defective_device = dict(defective_device) if defective_device else {}

    operator_id = str(operator_user["id"])
    reported_by = str(defect.get("reported_by")) if defect.get("reported_by") is not None else None
    holder_id = (
        str(defective_device.get("current_holder_id"))
        if defective_device.get("current_holder_id") is not None
        else None
    )
    if operator_id not in {reported_by, holder_id}:
        raise HTTPException(status_code=403, detail="You are not involved in this defect")

    return defect


class ReviewRequest(BaseModel):
    action: str  # 'approve' or 'reject'
    review_note: Optional[str] = None
    # Admin can override the values on approval
    new_email: Optional[str] = None
    new_password: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED, summary="Submit a change request")
async def submit_change_request(
    data: ChangeRequestCreate,
    current_user: dict = Depends(get_current_user)
):
    """Submit a change request"""
    VALID_TYPES = ["email_change", "password_reset", "both", "device_status_change", "device_edit_change", "replacement_transfer_fix"]
    if data.request_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="Invalid request_type")

    if data.request_type == "replacement_transfer_fix":
        if current_user["role"] != "operator":
            raise HTTPException(status_code=403, detail="Only operators can submit replacement transfer fix requests")
        if not data.device_id:
            raise HTTPException(status_code=400, detail="defect_id is required in device_id for replacement_transfer_fix")
    elif data.request_type == "device_status_change":
        if current_user["role"] not in ["pdic_staff", "manager"]:
            raise HTTPException(status_code=403, detail="Only staff and managers can submit device status change requests")
        if not data.device_id:
            raise HTTPException(status_code=400, detail="device_id required for device_status_change")
        if not data.requested_status:
            raise HTTPException(status_code=400, detail="requested_status required for device_status_change")
        if not data.reason:
            raise HTTPException(status_code=400, detail="reason required for device_status_change")
    else:
        if current_user["role"] not in ["pdic_staff", "manager", "md_director"]:
            raise HTTPException(status_code=403, detail="Only staff, managers, and MD/Director can submit change requests")
        if data.request_type in ["email_change", "both"] and not data.new_email:
            raise HTTPException(status_code=400, detail="new_email required for email_change")
        if data.request_type in ["password_reset", "both"] and not data.new_password:
            raise HTTPException(status_code=400, detail="new_password required for password_reset")
        if data.new_password and len(data.new_password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    try:
        now = datetime.now().replace(tzinfo=None).isoformat()
        request_id = f"CR-{uuid.uuid4().hex[:8].upper()}"
        hashed_new_password = get_password_hash(data.new_password) if data.new_password else None
        manager_notification_payloads = []
        super_admin_notification_payloads = []

        async with get_db() as db:
            defect = None
            if data.request_type == "replacement_transfer_fix":
                defect = await _validate_operator_transfer_fix_request(db, current_user, data.device_id)

                cursor = await db.execute(
                    """SELECT id FROM change_requests
                       WHERE request_type = 'replacement_transfer_fix'
                       AND requested_by = ? AND device_id = ? AND status = 'pending'
                       LIMIT 1""",
                    (int(current_user["id"]), str(data.device_id)),
                )
                existing = await cursor.fetchone()
                if existing:
                    raise HTTPException(
                        status_code=400,
                        detail="A transfer-fix request is already pending for this defect",
                    )

            await db.execute(
                """INSERT INTO change_requests
                   (request_id, requested_by, requested_by_name, requested_by_role,
                    request_type, new_email, new_password, device_id, requested_status,
                    reason, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (
                    request_id,
                    int(current_user["id"]),
                    current_user["name"],
                    current_user["role"],
                    data.request_type,
                    data.new_email,
                    hashed_new_password,
                    data.device_id,
                    data.requested_status if data.request_type != "replacement_transfer_fix" else "transfer_fix",
                    data.reason,
                    now, now
                )
            )

            if data.request_type in {"email_change", "password_reset", "both"}:
                cursor = await db.execute("SELECT id FROM users WHERE role = 'super_admin' AND status = 'active'")
                super_admin_rows = await cursor.fetchall()
                for row in super_admin_rows:
                    super_admin_notification_payloads.append(
                        {
                            "user_id": str(row[0]),
                            "title": "Credential Change Request Pending",
                            "message": (
                                f"{current_user['name']} ({current_user['role']}) submitted a "
                                f"{data.request_type.replace('_', ' ')} request (ID: {request_id})."
                            ),
                            "notification_type": "warning",
                            "category": "approval",
                            "link": "/change-requests",
                            "metadata": {
                                "action": "credential_change_request",
                                "request_id": request_id,
                                "request_type": data.request_type,
                                "requested_by": str(current_user.get("id") or ""),
                                "requested_by_role": str(current_user.get("role") or ""),
                            },
                        }
                    )

            if data.request_type == "replacement_transfer_fix":
                cursor = await db.execute("SELECT id FROM users WHERE role IN ('super_admin', 'manager', 'pdic_staff')")
                managers = await cursor.fetchall()
                defect_report_id = defect.get("report_id") if defect else None
                for row in managers:
                    manager_id = str(row[0])
                    manager_notification_payloads.append(
                        {
                            "user_id": manager_id,
                            "title": "Replacement Transfer Fix Requested",
                            "message": (
                                f"Operator {current_user['name']} requested transfer fix for "
                                f"defect {defect_report_id or data.device_id}."
                            ),
                            "notification_type": "warning",
                            "category": "approval",
                            "link": "/change-requests",
                            "metadata": {
                                "action": "replacement_transfer_fix",
                                "request_id": request_id,
                                "defect_id": str(data.device_id),
                                "defect_report_id": defect_report_id,
                                "operator_id": str(current_user["id"]),
                                "operator_name": current_user["name"],
                                "notes": data.reason,
                            },
                        }
                    )
            await db.commit()

        if manager_notification_payloads:
            await notification_service.bulk_create_notifications(manager_notification_payloads)
        if super_admin_notification_payloads:
            await notification_service.bulk_create_notifications(super_admin_notification_payloads)

        return {"success": True, "message": "Change request submitted successfully", "data": {"request_id": request_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("", summary="Get change requests - admin sees all, manager sees staff requests only")
async def get_change_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user)
):
    """Get change requests - admin sees all, manager sees staff requests only"""
    role = current_user["role"]
    if role not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        async with get_db() as db:
            conditions = []
            params = []

            if role == "manager":
                # Managers can review:
                # - all PDIC staff requests (including credential requests)
                # - operator replacement transfer-fix requests
                # They cannot review manager/MD-director credential requests.
                conditions.append("(requested_by_role = 'pdic_staff' OR request_type = 'replacement_transfer_fix')")

            if status_filter:
                if status_filter == "rejected":
                    # Backward compatibility: older rows may have been saved as `rejectd`.
                    conditions.append("(status = ? OR status = ?)")
                    params.extend(["rejected", "rejectd"])
                else:
                    conditions.append("status = ?")
                    params.append(status_filter)

            where = " AND ".join(conditions) if conditions else "1=1"

            cursor = await db.execute(f"SELECT COUNT(*) FROM change_requests WHERE {where}", params)
            total = (await cursor.fetchone())[0]

            offset = (page - 1) * page_size
            cursor = await db.execute(
                f"SELECT * FROM change_requests WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [page_size, offset]
            )
            rows = await cursor.fetchall()
            items = rows_to_list(rows)

            # Never expose stored password material in API responses.
            for item in items:
                item.pop("new_password", None)
                if item.get("status") == "rejectd":
                    item["status"] = "rejected"

        return {
            "success": True,
            "data": items,
            "pagination": get_pagination(page, page_size, total)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.patch("/{request_id}/review", summary="Approve or reject a change request")
async def review_change_request(
    request: Request,
    request_id: str,
    review: ReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """Approve or reject a change request"""
    role = current_user["role"]
    if role not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if review.action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    try:
        operator_notification_payload = None
        requester_rejection_notification_payload = None
        transfer_plan = None
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM change_requests WHERE request_id = ?", (request_id,)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Request not found")

            req = row_to_dict(row)

            credential_request = req.get("request_type") in {"email_change", "password_reset", "both"}
            if credential_request and role == "manager" and req.get("requested_by_role") != "pdic_staff":
                raise HTTPException(
                    status_code=403,
                    detail="Managers can only review credential change requests submitted by PDIC staff"
                )
            if credential_request and role not in {"manager", "super_admin"}:
                raise HTTPException(status_code=403, detail="Only manager or super admin can review this request")

            # Managers can only review staff requests
            if role == "manager" and req["requested_by_role"] != "pdic_staff" and req["request_type"] != "replacement_transfer_fix":
                raise HTTPException(status_code=403, detail="Managers can only review staff requests")

            if req["status"] != "pending":
                raise HTTPException(status_code=400, detail="Request already reviewed")

            now = datetime.now().replace(tzinfo=None).isoformat()

            if review.action == "approve":
                if req["request_type"] == "device_status_change":
                    # Apply device status change
                    dev_id = req.get("device_id")
                    new_dev_status = req.get("requested_status")
                    if dev_id and new_dev_status:
                        await device_service.update_device_status(
                            device_id=dev_id,
                            status=new_dev_status,
                            performed_by=current_user["id"],
                            performed_by_name=current_user["name"],
                            notes=f"Approved via change request {request_id}"
                        )
                        if str(new_dev_status).lower() == "defective":
                            defect_reporter = {
                                "id": str(req.get("requested_by") or current_user["id"]),
                                "name": req.get("requested_by_name") or current_user["name"],
                            }
                            defect_notes_parts = [
                                f"Defect created from approved status change request {request_id}."
                            ]
                            if req.get("reason"):
                                defect_notes_parts.append(f"Requester reason: {req['reason']}")
                            if review.review_note:
                                defect_notes_parts.append(f"Reviewer note: {review.review_note}")

                            await defect_service.create_or_get_active_defect_for_device(
                                device_id=dev_id,
                                reporter=defect_reporter,
                                notes=" ".join(defect_notes_parts)
                            )
                elif req["request_type"] == "device_edit_change":
                    dev_id = req.get("device_id")
                    if not dev_id:
                        raise HTTPException(status_code=400, detail="device_id is required for device edit change requests")

                    raw_reason = req.get("reason")
                    changes_payload = {}
                    if raw_reason:
                        try:
                            parsed = json.loads(raw_reason)
                            if isinstance(parsed, dict) and isinstance(parsed.get("changes"), dict):
                                changes_payload = parsed.get("changes") or {}
                            elif isinstance(parsed, dict):
                                changes_payload = parsed
                        except Exception:
                            raise HTTPException(status_code=400, detail="Invalid device edit payload stored in request")

                    if not changes_payload:
                        raise HTTPException(status_code=400, detail="No device edit changes found in request")

                    updated_device = await device_service.update_device(
                        device_id=str(dev_id),
                        device_data=DeviceUpdate(**changes_payload)
                    )
                    if not updated_device:
                        raise HTTPException(status_code=404, detail="Device not found for edit approval")
                elif req["request_type"] in ["email_change", "password_reset", "both"]:
                    # Use override values if provided, else use original request values
                    email_to_set = review.new_email or req.get("new_email")
                    password_to_set = review.new_password
                    stored_password_value = req.get("new_password")

                    update_fields = []
                    update_params = []

                    if req["request_type"] in ["email_change", "both"] and email_to_set:
                        # Check email uniqueness
                        cursor = await db.execute(
                            "SELECT id FROM users WHERE email = ? AND id != ?",
                            (email_to_set.lower(), req["requested_by"])
                        )
                        if await cursor.fetchone():
                            raise HTTPException(status_code=400, detail="Email already in use by another user")
                        update_fields.append("email = ?")
                        update_params.append(email_to_set.lower())

                    if req["request_type"] in ["password_reset", "both"]:
                        if password_to_set:
                            if len(password_to_set) < 6:
                                raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
                            update_fields.append("password_hash = ?")
                            update_params.append(get_password_hash(password_to_set))
                        elif stored_password_value:
                            if not _looks_like_bcrypt_hash(stored_password_value):
                                raise HTTPException(
                                    status_code=500,
                                    detail="Insecure stored password material detected; recreate this request",
                                )
                            update_fields.append("password_hash = ?")
                            update_params.append(stored_password_value)

                    if update_fields:
                        update_fields.append("updated_at = ?")
                        update_params.append(now)
                        update_params.append(req["requested_by"])
                        await db.execute(
                            f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?",
                            update_params
                        )
                        if req["request_type"] in ["password_reset", "both"]:
                            audit_logger.warning(
                                "PASSWORD_CHANGE_APPROVED | reviewer_id=%s | reviewer_role=%s | target_user_id=%s | request_id=%s | ip=%s",
                                current_user.get("id"),
                                current_user.get("role"),
                                req.get("requested_by"),
                                request_id,
                                request.client.host if request.client else "unknown",
                            )
                elif req["request_type"] == "replacement_transfer_fix":
                    defect_id = req.get("device_id")
                    if not defect_id or not str(defect_id).isdigit():
                        raise HTTPException(status_code=400, detail="Invalid defect id in transfer-fix request")

                    cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
                    defect = await cursor.fetchone()
                    if not defect:
                        raise HTTPException(status_code=404, detail="Defect not found for transfer-fix request")
                    defect = dict(defect)

                    replacement_device_id = defect.get("replacement_device_id")
                    if not replacement_device_id:
                        raise HTTPException(status_code=400, detail="No replacement device mapped for this defect")

                    cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(defect["device_id"]),))
                    old_device_row = await cursor.fetchone()
                    old_device = dict(old_device_row) if old_device_row else {}

                    # Always transfer to the operator who requested the fix.
                    # This prevents misrouting to stale defect/device holder metadata.
                    target_holder_id = req.get("requested_by")
                    target_holder_name = req.get("requested_by_name") or old_device.get("current_holder_name") or defect.get("reported_by_name")
                    target_location = old_device.get("current_location") or "Field"

                    if not target_holder_id:
                        raise HTTPException(
                            status_code=400,
                            detail="Unable to determine operator holder for replacement transfer"
                        )

                    cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(replacement_device_id),))
                    replacement_row = await cursor.fetchone()
                    if not replacement_row:
                        raise HTTPException(status_code=404, detail="Replacement device not found")
                    replacement_device = dict(replacement_row)

                    already_assigned = (
                        str(replacement_device.get("current_holder_id")) == str(target_holder_id)
                        and replacement_device.get("current_holder_type") == "operator"
                    )

                    transfer_plan = {
                        "already_assigned": already_assigned,
                        "replacement_device_id": str(replacement_device_id),
                        "replacement_device_code": replacement_device.get("device_id"),
                        "replacement_serial": replacement_device.get("serial_number"),
                        "from_user_id": replacement_device.get("current_holder_id"),
                        "from_user_name": replacement_device.get("current_holder_name"),
                        "target_holder_id": str(target_holder_id),
                        "target_holder_name": target_holder_name,
                        "target_location": target_location,
                        "defect_id": str(defect_id),
                        "defect_report_id": defect.get("report_id"),
                    }

                    # If it was marked waiting and this transfer fix is approved, return it to pending confirmation.
                    if defect.get("status") == "replacement_waiting_for_device":
                        await db.execute(
                            "UPDATE defects SET status = ?, updated_at = ? WHERE id = ?",
                            ("replacement_pending_confirmation", now, int(defect_id))
                        )

            if req["request_type"] == "replacement_transfer_fix":
                operator_notification_payload = {
                    "user_id": str(req["requested_by"]),
                    "title": (
                        "Replacement Transfer Fix Approved"
                        if review.action == "approve"
                        else "Replacement Transfer Fix Rejected"
                    ),
                    "message": (
                        "Your replacement transfer-fix request is approved. Your replacement device has been transferred."
                        if review.action == "approve"
                        else "Your replacement transfer-fix request was rejected."
                    ),
                    "notification_type": "success" if review.action == "approve" else "warning",
                    "category": "approval",
                    "link": "/replacement-confirmation",
                    "metadata": {
                        "action": "replacement_transfer_fix_reviewed",
                        "request_id": request_id,
                        "decision": review.action,
                        "defect_id": str(req.get("device_id") or ""),
                    },
                }
            elif review.action == "reject":
                rejection_link = "/devices/edit-requests" if req.get("request_type") == "device_edit_change" else "/change-requests"
                requester_rejection_notification_payload = {
                    "user_id": str(req["requested_by"]),
                    "title": "Update Request Rejected",
                    "message": (
                        f"Your {str(req.get('request_type') or 'update').replace('_', ' ')} request "
                        f"({request_id}) was rejected by {current_user.get('name')}."
                        + (f" Note: {review.review_note}" if review.review_note else "")
                    ),
                    "notification_type": "warning",
                    "category": "approval",
                    "link": rejection_link,
                    "metadata": {
                        "action": "change_request_rejected",
                        "request_id": request_id,
                        "request_type": req.get("request_type"),
                        "reviewed_by": str(current_user.get("id") or ""),
                        "reviewed_by_role": str(current_user.get("role") or ""),
                    },
                }

            # Update the request status
            await db.execute(
                """UPDATE change_requests SET status = ?, reviewed_by = ?, reviewed_by_name = ?,
                   review_note = ?, updated_at = ? WHERE request_id = ?""",
                ("approved" if review.action == "approve" else "rejected", int(current_user["id"]), current_user["name"],
                 review.review_note, now, request_id)
            )
            await db.commit()

        if review.action == "approve" and req["request_type"] == "replacement_transfer_fix" and transfer_plan:
            if not transfer_plan["already_assigned"]:
                await device_service.update_device_holder(
                    device_id=transfer_plan["replacement_device_id"],
                    holder_id=transfer_plan["target_holder_id"],
                    holder_name=transfer_plan["target_holder_name"],
                    holder_type="operator",
                    location=transfer_plan["target_location"],
                    status="distributed",
                    performed_by=str(current_user["id"]),
                    performed_by_name=current_user["name"],
                    from_user_id=(str(transfer_plan["from_user_id"]) if transfer_plan["from_user_id"] is not None else None),
                    from_user_name=transfer_plan["from_user_name"],
                    notes=(
                        f"Replacement transfer-fix approved via {request_id} for "
                        f"defect {transfer_plan['defect_report_id']}"
                    )
                )

            # Additional explicit transfer confirmation for the operator.
            await notification_service.create_notification(
                user_id=str(req["requested_by"]),
                title="Replacement Device Transferred",
                message=(
                    f"Replacement device {transfer_plan.get('replacement_device_code') or transfer_plan.get('replacement_serial') or ''} "
                    "has been transferred to your possession."
                ),
                notification_type="success",
                category="defect",
                link="/replacement-confirmation",
                metadata={
                    "action": "replacement_transfer_completed",
                    "request_id": request_id,
                    "defect_id": transfer_plan.get("defect_id"),
                    "defect_report_id": transfer_plan.get("defect_report_id"),
                    "replacement_device_id": transfer_plan.get("replacement_device_id"),
                    "assigned_holder_id": transfer_plan.get("target_holder_id"),
                    "assigned_holder_name": transfer_plan.get("target_holder_name"),
                },
            )

        if operator_notification_payload:
            await notification_service.create_notification(**operator_notification_payload)
        if requester_rejection_notification_payload:
            await notification_service.create_notification(**requester_rejection_notification_payload)

        if credential_request:
            audit_logger.info(
                "CREDENTIAL_CHANGE_REQUEST_REVIEW | reviewer_id=%s | reviewer_role=%s | requester_id=%s | requester_role=%s | request_id=%s | decision=%s | ip=%s",
                current_user.get("id"),
                current_user.get("role"),
                req.get("requested_by"),
                req.get("requested_by_role"),
                request_id,
                review.action,
                request.client.host if request.client else "unknown",
            )

        return {"success": True, "message": f"Request {review.action}d successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )




