from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set

from sqlalchemy import text

from app.database_sqlalchemy import async_session_factory
from app.models.return_device import ReturnCreate, ReturnUpdate, ReturnStatus, ReturnReason
from app.models.device import DeviceStatus
from app.services import device_service, notification_service
from app.utils.helpers import get_pagination, generate_return_id


async def get_returns(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    reason: Optional[str] = None,
    requested_by: Optional[int] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    current_user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    async def _get_return_scope_user_ids(session, user: Dict[str, Any]) -> Optional[Set[str]]:
        role = str(user.get("role") or "")
        user_id = str(user.get("id") or user.get("_id") or "")
        parent_id = str(user.get("parent_id") or "")

        if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
            return None

        scope_root = parent_id if role == "sub_distribution_manager" and parent_id.isdigit() else user_id
        scoped_ids: Set[str] = {scope_root}
        if str(scope_root).isdigit():
            desc_rows = (await session.execute(
                text("""
                    WITH RECURSIVE descendants AS (
                        SELECT id FROM users WHERE parent_id = :root
                        UNION ALL
                        SELECT u.id FROM users u
                        INNER JOIN descendants d ON u.parent_id = d.id
                    )
                    SELECT id FROM descendants
                """),
                {"root": int(scope_root)}
            )).scalars().all()
            scoped_ids.update(str(did) for did in desc_rows if did)
        return scoped_ids

    async with async_session_factory() as session:
        conditions = ["1=1"]
        params: Dict[str, Any] = {}

        if status:
            conditions.append("r.status = :status")
            params["status"] = status
        if reason:
            conditions.append("r.reason = :reason")
            params["reason"] = reason

        scope_ids = await _get_return_scope_user_ids(session, current_user) if current_user else None
        if scope_ids is not None:
            if not scope_ids:
                return {"data": [], "pagination": get_pagination(page, page_size, 0)}
            scope_list = sorted(scope_ids)
            ph = ",".join([f":sr_{i}" for i in range(len(scope_list))])
            conditions.append(f"r.requested_by IN ({ph})")
            for i, sid in enumerate(scope_list):
                params[f"sr_{i}"] = sid
        elif requested_by:
            conditions.append("r.requested_by = :requested_by")
            params["requested_by"] = requested_by
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
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE :search_like")
                params["search_like"] = like
            else:
                conditions.append("(r.return_id LIKE :sl1 OR r.device_serial LIKE :sl2 OR r.requested_by_name LIKE :sl3 OR r.reason LIKE :sl4 OR r.status LIKE :sl5)")
                for i in range(5):
                    params[f"sl{i+1}"] = like

        where = " AND ".join(conditions)

        total = (await session.execute(
            text(f"SELECT COUNT(*) FROM returns r WHERE {where}"), params
        )).scalar() or 0

        offset = (page - 1) * page_size
        params["_limit"] = page_size
        params["_offset"] = offset
        rows = (await session.execute(
            text(f"""
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
                LIMIT :_limit OFFSET :_offset
            """),
            params
        )).mappings().all()

        return {
            "data": [dict(r) for r in rows],
            "pagination": get_pagination(page, page_size, total)
        }


async def get_return_by_id(return_id: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        row = (await session.execute(
            text("""
                SELECT
                    r.*,
                    d.model AS device_model,
                    d.manufacturer AS manufacturer,
                    d.device_id AS source_device_id,
                    d.nuid AS device_nuid
                FROM returns r
                LEFT JOIN devices d ON d.id = r.device_id
                WHERE r.id = :id
            """),
            {"id": int(return_id)}
        )).mappings().first()
        return dict(row) if row else None


async def create_return(return_data: ReturnCreate, requester: Dict[str, Any]) -> Dict[str, Any]:
    async with async_session_factory() as session:
        device = (await session.execute(
            text("SELECT * FROM devices WHERE id = :id"), {"id": int(return_data.device_id)}
        )).mappings().first()
        if not device:
            raise ValueError("Device not found")
        device = dict(device)

        return_to_user = (await session.execute(
            text("SELECT * FROM users WHERE role IN ('super_admin', 'manager') LIMIT 1")
        )).mappings().first()
        if not return_to_user:
            raise ValueError("No admin/manager found to process return")
        return_to_user = dict(return_to_user)

        now = datetime.now().replace(tzinfo=None)
        return_id_val = generate_return_id()

        result = await session.execute(
            text("""
                INSERT INTO returns (return_id, device_id, device_serial, device_type, mac_address,
                requested_by, requested_by_name, return_to, return_to_name, reason, description,
                status, request_date, approval_date, received_date, approved_by, approved_by_name,
                created_at, updated_at)
                VALUES (:return_id, :device_id, :device_serial, :device_type, :mac_address,
                :requested_by, :requested_by_name, :return_to, :return_to_name, :reason, :description,
                :status, :request_date, :approval_date, :received_date, :approved_by, :approved_by_name,
                :created_at, :updated_at)
            """),
            {
                "return_id": return_id_val,
                "device_id": return_data.device_id,
                "device_serial": device["serial_number"],
                "device_type": device["device_type"],
                "mac_address": device.get("mac_address"),
                "requested_by": int(requester["_id"]),
                "requested_by_name": requester["name"],
                "return_to": str(return_to_user["id"]),
                "return_to_name": return_to_user["name"],
                "reason": return_data.reason.value,
                "description": return_data.description,
                "status": ReturnStatus.PENDING.value,
                "request_date": now,
                "approval_date": None,
                "received_date": None,
                "approved_by": None,
                "approved_by_name": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        return_row_id = result.lastrowid

        await session.commit()

    enabled_roles = ["super_admin", "manager", "pdic_staff"]
    if not enabled_roles:
        enabled_roles = ["super_admin"]
    roles_ph = ",".join([f":r_{i}" for i in range(len(enabled_roles))])
    roles_params = {f"r_{i}": r for i, r in enumerate(enabled_roles)}
    async with async_session_factory() as session:
        staff_rows = (await session.execute(
            text(f"SELECT id, name FROM users WHERE role IN ({roles_ph})"),
            roles_params
        )).mappings().all()
    await notification_service.bulk_create_notifications([
        {
            "user_id": str(s["id"]),
            "title": "New Return Request — Awaiting Approval",
            "message": (
                f"{requester['name']} has submitted a return request for device "
                f"{device['device_id']} ({return_data.reason.value}). Please review and approve."
            ),
            "notification_type": "info",
            "category": "return",
            "link": f"/returns?returnId={return_row_id}"
        }
        for s in staff_rows
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
    user_role = str(user.get("role", "")).lower()
    
    async with async_session_factory() as session:
        return_req = (await session.execute(
            text("SELECT * FROM returns WHERE id = :id"), {"id": int(return_id)}
        )).mappings().first()
        if not return_req:
            return None
        return_req = dict(return_req)

        now = datetime.now().replace(tzinfo=None)

        if status == ReturnStatus.APPROVED.value:
            await session.execute(
                text("UPDATE returns SET status = :status, approval_date = :now, approved_by = :uid, approved_by_name = :uname, updated_at = :now2 WHERE id = :id"),
                {"status": status, "now": now, "uid": int(user["_id"]), "uname": user["name"], "now2": now, "id": int(return_id)}
            )

        elif status == ReturnStatus.RECEIVED.value:
            await session.execute(
                text("UPDATE returns SET status = :status, received_date = :now, updated_at = :now2 WHERE id = :id"),
                {"status": status, "now": now, "now2": now, "id": int(return_id)}
            )

            if return_req.get("defect_id"):
                set_fragments = [
                    "payment_due_user_id = :due_uid",
                    "payment_due_user_name = :due_uname",
                    "updated_at = :upd_at",
                ]
                defect_params: Dict[str, Any] = {
                    "due_uid": str(return_req.get("requested_by") or ""),
                    "due_uname": str(return_req.get("requested_by_name") or "Unknown"),
                    "upd_at": now,
                }
                if return_amount is not None:
                    set_fragments.append("return_amount = :ret_amt")
                    defect_params["ret_amt"] = float(return_amount)
                    set_fragments.append("payment_confirmed = 0")
                if payment_bill_url:
                    set_fragments.append("payment_bill_url = :bill_url")
                    defect_params["bill_url"] = str(payment_bill_url)
                defect_params["did"] = int(return_req["defect_id"])
                await session.execute(
                    text(f"UPDATE defects SET {', '.join(set_fragments)} WHERE id = :did AND COALESCE(payment_confirmed, 0) = 0"),
                    defect_params
                )

        elif status == ReturnStatus.REJECTED.value:
            await session.execute(
                text("UPDATE returns SET status = :status, updated_at = :now WHERE id = :id"),
                {"status": status, "now": now, "id": int(return_id)}
            )
        else:
            await session.execute(
                text("UPDATE returns SET status = :status, updated_at = :now WHERE id = :id"),
                {"status": status, "now": now, "id": int(return_id)}
            )

        await session.commit()

    if status == ReturnStatus.RECEIVED.value:
        await device_service.update_device_status(
            device_id=return_req["device_id"],
            status=DeviceStatus.RETURNED.value,
            performed_by=int(user["_id"]),
            performed_by_name=user["name"],
            notes=f"Device returned and received at PDIC via {return_req['return_id']}"
        )
        await device_service.update_device_holder(
            device_id=return_req["device_id"],
            holder_id=None,
            holder_name="PDIC (Distribution)",
            holder_type="noc",
            location="PDIC",
            status=DeviceStatus.RETURNED.value,
            performed_by=int(user["_id"]),
            performed_by_name=user["name"],
            from_user_id=int(return_req["requested_by"]),
            from_user_name=return_req["requested_by_name"],
            notes=f"Returned and received at PDIC via {return_req['return_id']}"
        )

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

    if status == ReturnStatus.APPROVED.value:
        enabled_roles = ["super_admin", "manager", "pdic_staff"]
        acting_user_id = int(user.get("_id") or user.get("id"))
        roles_ph = ",".join([f":r_{i}" for i in range(len(enabled_roles))])
        roles_params = {f"r_{i}": r for i, r in enumerate(enabled_roles)}
        roles_params["acting_uid"] = acting_user_id
        async with async_session_factory() as session:
            staff_rows = (await session.execute(
                text(f"SELECT id FROM users WHERE role IN ({roles_ph}) AND CAST(id AS CHAR) != :acting_uid"),
                roles_params
            )).mappings().all()
        await notification_service.bulk_create_notifications([
            {
                "user_id": str(r["id"]),
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
            for r in staff_rows
        ])

    return await get_return_by_id(return_id)


async def cancel_return(return_id: str, user_id: int) -> bool:
    async with async_session_factory() as session:
        return_req = (await session.execute(
            text("SELECT * FROM returns WHERE id = :id"), {"id": int(return_id)}
        )).mappings().first()
        if not return_req:
            return False
        return_req = dict(return_req)

        if return_req["requested_by"] != user_id:
            raise ValueError("Only the requester can cancel this return request")
        if return_req["status"] != ReturnStatus.PENDING.value:
            raise ValueError("Only pending return requests can be cancelled")

        now = datetime.now().replace(tzinfo=None)
        await session.execute(
            text("UPDATE returns SET status = :status, updated_at = :now WHERE id = :id"),
            {"status": ReturnStatus.CANCELLED.value, "now": now, "id": int(return_id)}
        )
        await session.commit()
        return True


async def get_return_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    async with async_session_factory() as session:
        params: Dict[str, Any] = {}
        conditions = []
        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date
        date_filter = " AND ".join(conditions) if conditions else "1=1"

        total = 0
        by_status: Dict[str, int] = {}
        rows = (await session.execute(
            text(f"SELECT status, COUNT(*) AS cnt FROM returns WHERE {date_filter} GROUP BY status"),
            params
        )).mappings().all()
        for row in rows:
            status = str(row["status"])
            count = int(row["cnt"])
            total += count
            by_status[status] = count

        by_reason: Dict[str, int] = {}
        rows = (await session.execute(
            text(f"SELECT reason, COUNT(*) AS cnt FROM returns WHERE {date_filter} GROUP BY reason"),
            params
        )).mappings().all()
        for row in rows:
            by_reason[str(row["reason"])] = int(row["cnt"])

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
    requester_id: int,
    requester_name: str
) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        device = (await session.execute(
            text("SELECT * FROM devices WHERE id = :id"), {"id": int(device_id)}
        )).mappings().first()
        if not device:
            raise ValueError("Device not found")
        device = dict(device)

        existing = (await session.execute(
            text("SELECT id FROM returns WHERE device_id = :did AND status = 'pending'"),
            {"did": device_id}
        )).mappings().first()
        if existing:
            return await get_return_by_id(str(existing["id"]))

        return_to_user = (await session.execute(
            text("SELECT * FROM users WHERE role IN ('super_admin', 'manager') LIMIT 1")
        )).mappings().first()
        if not return_to_user:
            raise ValueError("No admin/manager found to process return")
        return_to_user = dict(return_to_user)

        now = datetime.now().replace(tzinfo=None)
        return_id_val = generate_return_id()

        result = await session.execute(
            text("""
                INSERT INTO returns (return_id, device_id, device_serial, device_type, mac_address,
                requested_by, requested_by_name, return_to, return_to_name, reason, description,
                status, request_date, approval_date, received_date, approved_by, approved_by_name,
                defect_id, created_at, updated_at)
                VALUES (:return_id, :device_id, :device_serial, :device_type, :mac_address,
                :requested_by, :requested_by_name, :return_to, :return_to_name, :reason, :description,
                :status, :request_date, :approval_date, :received_date, :approved_by, :approved_by_name,
                :defect_id, :created_at, :updated_at)
            """),
            {
                "return_id": return_id_val,
                "device_id": device_id,
                "device_serial": device["serial_number"],
                "device_type": device["device_type"],
                "mac_address": device.get("mac_address"),
                "requested_by": requester_id,
                "requested_by_name": requester_name,
                "return_to": str(return_to_user["id"]),
                "return_to_name": return_to_user["name"],
                "reason": ReturnReason.DEFECTIVE.value,
                "description": f"Auto-generated return for approved defect report {defect_report_id}",
                "status": ReturnStatus.PENDING.value,
                "request_date": now,
                "approval_date": None,
                "received_date": None,
                "approved_by": None,
                "approved_by_name": None,
                "defect_id": defect_id,
                "created_at": now,
                "updated_at": now,
            }
        )
        return_row_id = result.lastrowid

        await session.commit()

    enabled_roles = ["super_admin", "manager", "pdic_staff"]
    roles_ph = ",".join([f":r_{i}" for i in range(len(enabled_roles))])
    roles_params = {f"r_{i}": r for i, r in enumerate(enabled_roles)}
    async with async_session_factory() as session:
        approver_rows = (await session.execute(
            text(f"SELECT id FROM users WHERE role IN ({roles_ph})"),
            roles_params
        )).mappings().all()

    await notification_service.bulk_create_notifications([
        {
            "user_id": str(a["id"]),
            "title": "Return Request Created — Defective Device",
            "message": (
                f"A return request has been auto-created for defective device "
                f"{device['device_id']} (Defect: {defect_report_id}). Please approve receipt."
            ),
            "notification_type": "warning",
            "category": "return",
            "link": f"/returns?returnId={return_row_id}"
        }
        for a in approver_rows
    ])

    async with async_session_factory() as session:
        row = (await session.execute(
            text("SELECT return_id FROM returns WHERE id = :id"), {"id": return_row_id}
        )).mappings().first()
        created_return_id = row["return_id"] if row else str(return_row_id)

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

