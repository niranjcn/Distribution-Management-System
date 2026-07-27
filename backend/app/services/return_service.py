from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set

from app.database import get_db, row_to_dict, rows_to_list
from app.models.return_device import ReturnCreate, ReturnUpdate, ReturnStatus, ReturnReason
from app.models.device import DeviceStatus
from app.services import approval_service, device_service, notification_service
from app.utils.helpers import get_pagination, generate_return_id
from app.utils.hierarchy import get_descendant_user_ids


async def get_returns(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    reason: Optional[str] = None,
    requested_by: Optional[str] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    current_user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get all return requests with pagination and filters"""

    async def _get_return_scope_user_ids(db, user: Dict[str, Any]) -> Optional[Set[str]]:
        role = str(user.get("role") or "")
        user_id = str(user.get("id") or user.get("_id") or "")
        parent_id = str(user.get("parent_id") or "")

        if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
            return None

        scope_root = parent_id if role == "sub_distribution_manager" and parent_id.isdigit() else user_id
        scoped_ids: Set[str] = {scope_root}
        scoped_ids.update(await get_descendant_user_ids(db, scope_root))
        return scoped_ids

    async with get_db() as db:
        conditions = ["1=1"]
        params = []

        if status:
            conditions.append("r.status = ?")
            params.append(status)
        if reason:
            conditions.append("r.reason = ?")
            params.append(reason)

        scope_ids = await _get_return_scope_user_ids(db, current_user) if current_user else None
        if scope_ids is not None:
            if not scope_ids:
                return {"data": [], "pagination": get_pagination(page, page_size, 0)}
            scope_list = sorted(scope_ids)
            placeholders = ",".join(["?"] * len(scope_list))
            conditions.append(f"r.requested_by IN ({placeholders})")
            params.extend(scope_list)
        elif requested_by:
            conditions.append("r.requested_by = ?")
            params.append(requested_by)
        if search:
            like = f"%{search}%"
            search_field_map = {
                "return_id": "r.return_id",
                "device_serial": "r.device_serial",
                "requested_by_name": "r.requested_by_name",
                "reason": "r.reason",
                "status": "r.status",
            }
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE ?")
                params.append(like)
            else:
                conditions.append("(r.return_id LIKE ? OR r.device_serial LIKE ? OR r.requested_by_name LIKE ? OR r.reason LIKE ? OR r.status LIKE ?)")
                params.extend([like, like, like, like, like])

        where = " AND ".join(conditions)

        cursor = await db.execute(f"SELECT COUNT(*) FROM returns r WHERE {where}", params)
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"""
            SELECT
                r.*,
                d.model AS device_model,
                d.manufacturer AS manufacturer,
                d.device_id AS source_device_id,
                d.nuid AS device_nuid
            FROM returns r
            LEFT JOIN devices d ON d.id = r.device_id
            WHERE {where}
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset]
        )
        rows = await cursor.fetchall()

        return {
            "data": rows_to_list(rows),
            "pagination": get_pagination(page, page_size, total)
        }


async def get_return_by_id(return_id: str) -> Optional[Dict[str, Any]]:
    """Get return request by ID"""
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT
                r.*,
                d.model AS device_model,
                d.manufacturer AS manufacturer,
                d.device_id AS source_device_id,
                d.nuid AS device_nuid
            FROM returns r
            LEFT JOIN devices d ON d.id = r.device_id
            WHERE r.id = ?
            """,
            (int(return_id),)
        )
        row = await cursor.fetchone()
        return row_to_dict(row) if row else None


async def create_return(return_data: ReturnCreate, requester: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new return request"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(return_data.device_id),))
        device = await cursor.fetchone()
        if not device:
            raise ValueError("Device not found")
        device = dict(device)

        cursor = await db.execute("SELECT * FROM users WHERE role IN ('super_admin', 'manager') LIMIT 1")
        return_to_user = await cursor.fetchone()
        if not return_to_user:
            raise ValueError("No admin/manager found to process return")
        return_to_user = dict(return_to_user)

        now = datetime.now().replace(tzinfo=None).isoformat()

        cursor = await db.execute(
            """INSERT INTO returns (return_id, device_id, device_serial, device_type, mac_address,
            requested_by, requested_by_name, return_to, return_to_name, reason, description,
            status, request_date, approval_date, received_date, approved_by, approved_by_name,
            created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                generate_return_id(),
                return_data.device_id,
                device["serial_number"],
                device["device_type"],
                device.get("mac_address"),
                str(requester["_id"]),
                requester["name"],
                str(return_to_user["id"]),
                return_to_user["name"],
                return_data.reason.value,
                return_data.description,
                ReturnStatus.PENDING.value,
                now, None, None, None, None,
                now, now
            )
        )
        return_row_id = cursor.lastrowid

        # Create approval entry
        await db.execute(
            """INSERT INTO approvals (approval_type, entity_id, entity_type, requested_by,
            requested_by_name, status, priority, request_date, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "return", str(return_row_id), "return",
                str(requester["_id"]), requester["name"],
                "pending", "medium", now,
                return_data.description, now, now
            )
        )
        await db.commit()

    # Notify only enabled approval roles for return requests.
    enabled_roles = await approval_service.get_routing_enabled_roles_for_approval_type("return")
    if not enabled_roles:
        enabled_roles = ["super_admin"]
    role_placeholders = ", ".join(["?"] * len(enabled_roles))
    async with get_db() as db:
        cursor = await db.execute(
            f"SELECT id, name FROM users WHERE role IN ({role_placeholders})",
            enabled_roles,
        )
        staff_rows = await cursor.fetchall()
    await notification_service.bulk_create_notifications([
        {
            "user_id": str(dict(staff)["id"]),
            "title": "New Return Request — Awaiting Approval",
            "message": (
                f"{requester['name']} has submitted a return request for device "
                f"{device['device_id']} ({return_data.reason.value}). Please review and approve."
            ),
            "notification_type": "info",
            "category": "return",
            "link": f"/returns?returnId={return_row_id}"
        }
        for staff in staff_rows
    ])

    return await get_return_by_id(str(return_row_id))


async def update_return_status(
    return_id: str,
    status: str,
    user: Dict[str, Any],
    notes: Optional[str] = None,
    return_amount: Optional[float] = None,
    payment_bill_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update return request status"""
    user_role = str(user.get("role", "")).lower()
    if status in {ReturnStatus.APPROVED.value, ReturnStatus.REJECTED.value} and user_role in {"super_admin", "manager", "pdic_staff"}:
        allowed = await approval_service.is_role_allowed_for_approval_type(user_role, "return")
        if not allowed:
            raise PermissionError(f"{user_role.capitalize()} role is not allowed to process return approvals")

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM returns WHERE id = ?", (int(return_id),))
        return_req = await cursor.fetchone()
        if not return_req:
            return None
        return_req = dict(return_req)

        now = datetime.now().replace(tzinfo=None).isoformat()

        if status == ReturnStatus.APPROVED.value:
            await db.execute(
                "UPDATE returns SET status = ?, approval_date = ?, approved_by = ?, approved_by_name = ?, updated_at = ? WHERE id = ?",
                (status, now, str(user["_id"]), user["name"], now, int(return_id))
            )
            await db.execute(
                """UPDATE approvals SET status = 'approved', approved_by = ?, approved_by_name = ?,
                approval_date = ?, updated_at = ? WHERE entity_id = ? AND approval_type = 'return'""",
                (str(user["_id"]), user["name"], now, now, return_id)
            )

        elif status == ReturnStatus.RECEIVED.value:
            await db.execute(
                "UPDATE returns SET status = ?, received_date = ?, updated_at = ? WHERE id = ?",
                (status, now, now, int(return_id))
            )

            if return_req.get("defect_id"):
                set_fragments = [
                    "payment_due_user_id = ?",
                    "payment_due_user_name = ?",
                    "updated_at = ?",
                ]
                defect_params = [
                    str(return_req.get("requested_by") or ""),
                    str(return_req.get("requested_by_name") or "Unknown"),
                    now,
                ]

                if return_amount is not None:
                    set_fragments.append("return_amount = ?")
                    defect_params.append(float(return_amount))
                    set_fragments.append("payment_confirmed = 0")
                if payment_bill_url:
                    set_fragments.append("payment_bill_url = ?")
                    defect_params.append(str(payment_bill_url))

                defect_params.append(int(return_req["defect_id"]))
                await db.execute(
                    f"UPDATE defects SET {', '.join(set_fragments)} WHERE id = ? AND COALESCE(payment_confirmed, 0) = 0",
                    defect_params
                )

        elif status == ReturnStatus.REJECTED.value:
            await db.execute(
                "UPDATE returns SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, int(return_id))
            )
            await db.execute(
                """UPDATE approvals SET status = 'rejected', approved_by = ?, approved_by_name = ?,
                approval_date = ?, rejection_reason = ?, updated_at = ?
                WHERE entity_id = ? AND approval_type = 'return'""",
                (str(user["_id"]), user["name"], now, notes, now, return_id)
            )
        else:
            await db.execute(
                "UPDATE returns SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, int(return_id))
            )

        await db.commit()

    if status == ReturnStatus.RECEIVED.value:
        await device_service.update_device_holder(
            device_id=return_req["device_id"],
            holder_id=None,
            holder_name="PDIC (Distribution)",
            holder_type="noc",
            location="PDIC",
            status=DeviceStatus.RETURNED.value,
            performed_by=str(user["_id"]),
            performed_by_name=user["name"],
            from_user_id=return_req["requested_by"],
            from_user_name=return_req["requested_by_name"],
            notes=f"Returned and received at PDIC via {return_req['return_id']}"
        )

    # Notify the operator (requester)
    await notification_service.create_notification(
        user_id=return_req["requested_by"],
        title=(
            "Device Received at PDIC" if status == ReturnStatus.RECEIVED.value
            else f"Return Request {status.capitalize()}"
        ),
        message=(
            f"Your return request {return_req['return_id']} has been confirmed received at PDIC. "
            f"Device ownership has been transferred back to distribution."
        ) if status == ReturnStatus.RECEIVED.value else (
            f"Your return request {return_req['return_id']} has been {status}. "
            + ("Please bring the device to PDIC as soon as possible." if status == ReturnStatus.APPROVED.value else "")
        ),
        notification_type="success" if status in ["approved", "received"] else "warning",
        category="return",
        link=f"/returns?returnId={return_id}"
    )

    # When approved, remind all other staff to watch for the incoming device
    if status == ReturnStatus.APPROVED.value:
        enabled_roles = await approval_service.get_routing_enabled_roles_for_approval_type("return")
        if not enabled_roles:
            enabled_roles = ["super_admin"]
        role_placeholders = ", ".join(["?"] * len(enabled_roles))
        acting_user_id = str(user.get("_id") or user.get("id"))
        async with get_db() as db:
            cursor = await db.execute(
                f"SELECT id FROM users WHERE role IN ({role_placeholders}) AND CAST(id AS TEXT) != ?",
                enabled_roles + [acting_user_id],
            )
            staff_rows = await cursor.fetchall()
        await notification_service.bulk_create_notifications([
            {
                "user_id": str(dict(row)["id"]),
                "title": "Return Approved — Confirm Device Receipt",
                "message": (
                    f"Return request {return_req['return_id']} approved. "
                    f"Device {return_req['device_serial']} ({return_req['device_type']}) is on its way to PDIC. "
                    f"Please confirm receipt when it arrives."
                ),
                "notification_type": "info",
                "category": "return",
                "link": f"/returns?returnId={return_id}"
            }
            for row in staff_rows
        ])

    return await get_return_by_id(return_id)


async def cancel_return(return_id: str, user_id: str) -> bool:
    """Cancel a return request (only by creator)"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM returns WHERE id = ?", (int(return_id),))
        return_req = await cursor.fetchone()
        if not return_req:
            return False
        return_req = dict(return_req)

        if return_req["requested_by"] != user_id:
            raise ValueError("Only the requester can cancel this return request")
        if return_req["status"] != ReturnStatus.PENDING.value:
            raise ValueError("Only pending return requests can be cancelled")

        await db.execute(
            "UPDATE returns SET status = ?, updated_at = ? WHERE id = ?",
            (ReturnStatus.CANCELLED.value, datetime.now().replace(tzinfo=None).isoformat(), int(return_id))
        )
        await db.execute(
            "DELETE FROM approvals WHERE entity_id = ? AND approval_type = 'return'",
            (return_id,)
        )
        await db.commit()
        return True


async def get_return_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get return statistics"""
    async with get_db() as db:
        params: List[Any] = []
        date_filter = "1=1"
        if start_date:
            date_filter = "created_at >= ?"
            params.append(start_date)
        if end_date:
            date_filter += " AND created_at <= ?" if date_filter != "1=1" else "created_at <= ?"
            params.append(end_date)

        total = 0
        by_status: Dict[str, int] = {}
        cursor = await db.execute(
            f"SELECT status, COUNT(*) AS total FROM returns WHERE {date_filter} GROUP BY status",
            params
        )
        for row in await cursor.fetchall():
            status = str(row[0])
            count = int(row[1])
            total += count
            by_status[status] = count

        by_reason: Dict[str, int] = {}
        cursor = await db.execute(
            f"SELECT reason, COUNT(*) AS total FROM returns WHERE {date_filter} GROUP BY reason",
            params
        )
        for row in await cursor.fetchall():
            by_reason[str(row[0])] = int(row[1])

        return {
            "total": total,
            "by_status": {
                "pending": by_status.get("pending", 0),
                "approved": by_status.get("approved", 0),
                "received": by_status.get("received", 0),
                "rejected": by_status.get("rejected", 0),
            },
            "by_reason": {
                "defective": by_reason.get("defective", 0),
                "unused": by_reason.get("unused", 0),
                "end_of_contract": by_reason.get("end_of_contract", 0),
            }
        }


async def auto_create_defect_return(
    device_id: str,
    defect_id: str,
    defect_report_id: str,
    requester_id: str,
    requester_name: str
) -> Optional[Dict[str, Any]]:
    """Auto-create a return request when a defect report is approved by manager/staff."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(device_id),))
        device = await cursor.fetchone()
        if not device:
            raise ValueError("Device not found")
        device = dict(device)

        # Avoid duplicate pending returns for the same device
        cursor = await db.execute(
            "SELECT id FROM returns WHERE device_id = ? AND status = 'pending'",
            (device_id,)
        )
        existing = await cursor.fetchone()
        if existing:
            return await get_return_by_id(str(dict(existing)["id"]))

        cursor = await db.execute("SELECT * FROM users WHERE role IN ('super_admin', 'manager') LIMIT 1")
        return_to_user = await cursor.fetchone()
        if not return_to_user:
            raise ValueError("No admin/manager found to process return")
        return_to_user = dict(return_to_user)

        now = datetime.now().replace(tzinfo=None).isoformat()

        cursor = await db.execute(
            """INSERT INTO returns (return_id, device_id, device_serial, device_type, mac_address,
            requested_by, requested_by_name, return_to, return_to_name, reason, description,
            status, request_date, approval_date, received_date, approved_by, approved_by_name,
            defect_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                generate_return_id(),
                device_id,
                device["serial_number"],
                device["device_type"],
                device.get("mac_address"),
                requester_id,
                requester_name,
                str(return_to_user["id"]),
                return_to_user["name"],
                ReturnReason.DEFECTIVE.value,
                f"Auto-generated return for approved defect report {defect_report_id}",
                ReturnStatus.PENDING.value,
                now, None, None, None, None,
                defect_id,
                now, now
            )
        )
        return_row_id = cursor.lastrowid

        await db.execute(
            """INSERT INTO approvals (approval_type, entity_id, entity_type, requested_by,
            requested_by_name, status, priority, request_date, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "return", str(return_row_id), "return",
                requester_id, requester_name,
                "pending", "high", now,
                f"Auto-generated from defect {defect_report_id}", now, now
            )
        )
        await db.commit()

    # Notify only enabled approval roles for return requests.
    enabled_roles = await approval_service.get_routing_enabled_roles_for_approval_type("return")
    if not enabled_roles:
        enabled_roles = ["super_admin"]
    role_placeholders = ", ".join(["?"] * len(enabled_roles))
    async with get_db() as db:
        cursor = await db.execute(
            f"SELECT id FROM users WHERE role IN ({role_placeholders})",
            enabled_roles,
        )
        approver_rows = await cursor.fetchall()

    await notification_service.bulk_create_notifications([
        {
            "user_id": str(dict(approver)["id"]),
            "title": "Return Request Created — Defective Device",
            "message": (
                f"A return request has been auto-created for defective device "
                f"{device['device_id']} (Defect: {defect_report_id}). Please approve receipt."
            ),
            "notification_type": "warning",
            "category": "return",
            "link": f"/returns?returnId={return_row_id}"
        }
        for approver in approver_rows
    ])

    # Alert the operator (requester) to physically return the device
    async with get_db() as db:
        cursor = await db.execute("SELECT return_id FROM returns WHERE id = ?", (return_row_id,))
        row = await cursor.fetchone()
        created_return_id = dict(row)["return_id"] if row else str(return_row_id)

    await notification_service.create_notification(
        user_id=requester_id,
        title="Action Required: Return Defective Device",
        message=(
            f"Your defect report {defect_report_id} has been approved. "
            f"Please return device {device['device_id']} to PDIC immediately. "
            f"Return request {created_return_id} has been created — awaiting PDIC receipt confirmation."
        ),
        notification_type="warning",
        category="return",
        link=f"/returns?returnId={return_row_id}"
    )

    return await get_return_by_id(str(return_row_id))

