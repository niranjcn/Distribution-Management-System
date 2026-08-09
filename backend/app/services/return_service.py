from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set

from sqlalchemy import text

from app.core.cache_version import bump_cache_version
from app.database_sqlalchemy import async_session_factory
from app.models.return_device import ReturnCreate, ReturnUpdate, ReturnStatus, ReturnReason
from app.models.device import DeviceStatus
from app.services import device_service, notification_service
from app.services.digital_id_search import build_identity_search_clause
from app.utils.helpers import get_pagination, generate_return_id, is_set_top_box_device


async def _get_return_branch_scope_user_ids(session, user: Dict[str, Any]) -> Optional[Set[str]]:
    """Return the set of user ids whose returns the given user may view.

    Mirrors the scope logic used by the returns list (returns are attributed to
    the reporter of the linked defect): management/PDIC roles get ``None`` (no
    scope restriction); everyone else is limited to their own branch.
    """
    role = str(user.get("role") or "")
    user_id = str(user.get("id") or user.get("_id") or "")
    parent_id = str(user.get("parent_id") or "")

    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        return None

    scope_root = parent_id if role in ("sub_distribution_manager", "sub_distribution_employee") and parent_id.isdigit() else user_id
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


async def user_can_view_return(user: Dict[str, Any], return_req: Dict[str, Any]) -> bool:
    """Whether ``user`` may view the given return request by ID.

    Mirrors the scoped returns list: management/PDIC roles see all returns;
    everyone else may only view returns requested by themselves or by users
    within their sub-distribution scope.
    """
    role = str(user.get("role") or "")
    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        return True

    async with async_session_factory() as session:
        scope_ids = await _get_return_branch_scope_user_ids(session, user)
    if scope_ids is None:
        return True

    return str(return_req.get("requested_by")) in scope_ids


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

        scope_root = parent_id if role in ("sub_distribution_manager", "sub_distribution_employee") and parent_id.isdigit() else user_id
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
            conditions.append(f"def.reported_by IN ({ph})")
            for i, sid in enumerate(scope_list):
                params[f"sr_{i}"] = sid
        elif requested_by:
            conditions.append("def.reported_by = :requested_by")
            params["requested_by"] = requested_by
        if search:
            like = f"%{search}%"
            search_field_map = {
                "return_id": "r.return_id",
                "device_serial": "r.device_serial",
                "device_nuid": "r.device_nuid",
                "requested_by_name": "def.reported_by_name",
                "reason": "r.reason",
                "status": "r.status",
            }
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by in {"digital_id", "broadband_id"}:
                clause, iparams = build_identity_search_clause(
                    ["def.reported_by"], like, fields=[normalized_search_by]
                )
                conditions.append(clause)
                params.update(iparams)
            elif normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE :search_like")
                params["search_like"] = like
            else:
                id_clause, iparams = build_identity_search_clause(["def.reported_by"], like)
                conditions.append("(r.return_id LIKE :sl1 OR r.device_serial LIKE :sl2 OR r.device_nuid LIKE :sl6 OR def.reported_by_name LIKE :sl3 OR r.reason LIKE :sl4 OR r.status LIKE :sl5 OR " + id_clause + ")")
                for i in range(6):
                    params[f"sl{i+1}"] = like
                params.update(iparams)

        where = " AND ".join(conditions)

        total = (await session.execute(
            text(f"SELECT COUNT(*) FROM returns r LEFT JOIN defects def ON def.id = r.defect_id WHERE {where}"), params
        )).scalar() or 0

        offset = (page - 1) * page_size
        params["_limit"] = page_size
        params["_offset"] = offset
        rows = (await session.execute(
            text(f"""
                SELECT
                    r.*,
                    dv.model AS device_model,
                    dv.manufacturer AS manufacturer,
                    dv.device_id AS source_device_id,
                    def.report_id AS defect_report_id,
                    def.reported_by AS requested_by,
                    def.reported_by_name AS requested_by_name,
                    def.description AS description,
                    def.return_approved_by AS return_approved_by,
                    def.return_approved_by_name AS return_approved_by_name,
                    def.return_approved_at AS return_approved_at,
                    def.defect_approved_at AS defect_approved_at
                FROM returns r
                LEFT JOIN defects def ON def.id = r.defect_id
                LEFT JOIN devices dv ON dv.id = r.device_id
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
                    dv.model AS device_model,
                    dv.manufacturer AS manufacturer,
                    dv.device_id AS source_device_id,
                    def.report_id AS defect_report_id,
                    def.reported_by AS requested_by,
                    def.reported_by_name AS requested_by_name,
                    def.description AS description,
                    def.return_approved_by AS return_approved_by,
                    def.return_approved_by_name AS return_approved_by_name,
                    def.return_approved_at AS return_approved_at,
                    def.defect_approved_at AS defect_approved_at
                FROM returns r
                LEFT JOIN defects def ON def.id = r.defect_id
                LEFT JOIN devices dv ON dv.id = r.device_id
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

        now = datetime.now().replace(tzinfo=None)
        return_id_val = generate_return_id()

        is_sb = is_set_top_box_device(device)
        device_serial = None if is_sb else device.get("serial_number")
        device_nuid = device.get("nuid") if is_sb else None
        mac_address = None if is_sb else device.get("mac_address")

        result = await session.execute(
            text("""
                INSERT INTO returns (return_id, device_id, device_serial, device_nuid, device_type, mac_address,
                reason, status, request_date, received_date,
                created_at, updated_at)
                VALUES (:return_id, :device_id, :device_serial, :device_nuid, :device_type, :mac_address,
                :reason, :status, :request_date, :received_date,
                :created_at, :updated_at)
            """),
            {
                "return_id": return_id_val,
                "device_id": return_data.device_id,
                "device_serial": device_serial,
                "device_nuid": device_nuid,
                "device_type": device["device_type"],
                "mac_address": mac_address,
                "reason": return_data.reason.value,
                "status": ReturnStatus.PENDING.value,
                "request_date": now,
                "received_date": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        return_row_id = result.lastrowid

        await bump_cache_version(session)
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
            "user_id": s["id"],
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

        linked_defect: Optional[Dict[str, Any]] = None
        if return_req.get("defect_id"):
            linked_defect = (await session.execute(
                text("SELECT id, report_id, reported_by, reported_by_name FROM defects WHERE id = :id"),
                {"id": int(return_req["defect_id"])}
            )).mappings().first()
            linked_defect = dict(linked_defect) if linked_defect else None

        now = datetime.now().replace(tzinfo=None)

        if status == ReturnStatus.APPROVED.value:
            await session.execute(
                text("UPDATE returns SET status = :status, updated_at = :now2 WHERE id = :id"),
                {"status": status, "now2": now, "id": int(return_id)}
            )
            if linked_defect:
                await session.execute(
                    text("UPDATE defects SET return_approved_by = :uid, return_approved_by_name = :uname, return_approved_at = :now, updated_at = :now2 WHERE id = :did"),
                    {"uid": int(user["_id"]), "uname": user["name"], "now": now, "now2": now, "did": linked_defect["id"]}
                )

        elif status == ReturnStatus.RECEIVED.value:
            await session.execute(
                text("UPDATE returns SET status = :status, received_date = :now, updated_at = :now2 WHERE id = :id"),
                {"status": status, "now": now, "now2": now, "id": int(return_id)}
            )

            if return_req.get("defect_id"):
                if linked_defect:
                    await session.execute(
                        text("UPDATE defects SET return_approved_by = :uid, return_approved_by_name = :uname, return_approved_at = :now, updated_at = :now2 WHERE id = :did"),
                        {"uid": int(user["_id"]), "uname": user["name"], "now": now, "now2": now, "did": linked_defect["id"]}
                    )
                set_fragments = [
                    "payment_due_user_id = :due_uid",
                    "payment_due_user_name = :due_uname",
                    "updated_at = :upd_at",
                ]
                defect_params: Dict[str, Any] = {
                    "due_uid": str((linked_defect or {}).get("reported_by") or ""),
                    "due_uname": str((linked_defect or {}).get("reported_by_name") or "Unknown"),
                    "upd_at": now,
                }
                if return_amount is not None:
                    set_fragments.append("return_amount = :ret_amt")
                    defect_params["ret_amt"] = float(return_amount) if float(return_amount) > 0 else None
                    if float(return_amount) > 0:
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

        await bump_cache_version(session)
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
            from_user_id=int((linked_defect or {}).get("reported_by") or 0) or None,
            from_user_name=(linked_defect or {}).get("reported_by_name"),
            notes=f"Returned and received at PDIC via {return_req['return_id']}"
        )

    notify_user_id = (linked_defect or {}).get("reported_by")
    if notify_user_id:
        await notification_service.create_notification(
            user_id=notify_user_id,
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
                "user_id": r["id"],
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

        requester_id = None
        if return_req.get("defect_id"):
            requester_id = (await session.execute(
                text("SELECT reported_by FROM defects WHERE id = :id"),
                {"id": int(return_req["defect_id"])}
            )).scalar()

        if requester_id is None or int(requester_id) != user_id:
            raise ValueError("Only the requester can cancel this return request")
        if return_req["status"] != ReturnStatus.PENDING.value:
            raise ValueError("Only pending return requests can be cancelled")

        now = datetime.now().replace(tzinfo=None)
        await session.execute(
            text("UPDATE returns SET status = :status, updated_at = :now WHERE id = :id"),
            {"status": ReturnStatus.CANCELLED.value, "now": now, "id": int(return_id)}
        )
        await bump_cache_version(session)
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

        row = (await session.execute(
            text(f"""SELECT
                    COUNT(*) AS total,
                    SUM(status = 'pending') AS pending,
                    SUM(status = 'approved') AS approved,
                    SUM(status = 'received') AS received,
                    SUM(status = 'rejected') AS rejected,
                    SUM(reason = 'defective') AS defective,
                    SUM(reason = 'unused') AS unused,
                    SUM(reason = 'end_of_contract') AS end_of_contract
                FROM returns WHERE {date_filter}"""),
            params
        )).mappings().first()

        return {
            "total": int(row["total"] or 0),
            "by_status": {
                "pending": int(row["pending"] or 0),
                "approved": int(row["approved"] or 0),
                "received": int(row["received"] or 0),
                "rejected": int(row["rejected"] or 0),
            },
            "by_reason": {
                "defective": int(row["defective"] or 0),
                "unused": int(row["unused"] or 0),
                "end_of_contract": int(row["end_of_contract"] or 0),
            }
        }


async def auto_create_defect_return(
    device_id: str,
    defect_id: str,
    defect_report_id: str,
    requester_id: int
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

        now = datetime.now().replace(tzinfo=None)
        return_id_val = generate_return_id()

        is_sb = is_set_top_box_device(device)
        device_serial = None if is_sb else device.get("serial_number")
        device_nuid = device.get("nuid") if is_sb else None
        mac_address = None if is_sb else device.get("mac_address")

        result = await session.execute(
            text("""
                INSERT INTO returns (return_id, device_id, device_serial, device_nuid, device_type, mac_address,
                reason, status, request_date, received_date,
                defect_id, created_at, updated_at)
                VALUES (:return_id, :device_id, :device_serial, :device_nuid, :device_type, :mac_address,
                :reason, :status, :request_date, :received_date,
                :defect_id, :created_at, :updated_at)
            """),
            {
                "return_id": return_id_val,
                "device_id": device_id,
                "device_serial": device_serial,
                "device_nuid": device_nuid,
                "device_type": device["device_type"],
                "mac_address": mac_address,
                "reason": ReturnReason.DEFECTIVE.value,
                "status": ReturnStatus.PENDING.value,
                "request_date": now,
                "received_date": None,
                "defect_id": defect_id,
                "created_at": now,
                "updated_at": now,
            }
        )
        return_row_id = result.lastrowid

        await bump_cache_version(session)
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
            "user_id": a["id"],
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

