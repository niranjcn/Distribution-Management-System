from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
import json

from sqlalchemy import text, select

from app.core.cache_version import bump_cache_version
from app.database_sqlalchemy import async_session_factory
from app.models.defect import (
    DefectCreate,
    DefectUpdate,
    DefectStatus,
    DefectSeverity,
    DefectType,
    DefectReportTarget,
)
from app.models.device import DeviceStatus, DeviceCreate
from app.services import device_service, notification_service, return_service
from app.services.digital_id_search import build_identity_search_clause
from app.utils.helpers import get_pagination, generate_defect_id, is_set_top_box_device


def _parse_json_metadata(raw_metadata: Any) -> Dict[str, Any]:
    if isinstance(raw_metadata, dict):
        return raw_metadata
    if isinstance(raw_metadata, str) and raw_metadata.strip():
        try:
            parsed = json.loads(raw_metadata)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


async def _get_user_role_and_parent(session, user_id: int) -> Optional[Dict[str, Any]]:
    row = (await session.execute(
        text("SELECT id, role, parent_id FROM users WHERE id = :uid"),
        {"uid": user_id}
    )).mappings().first()
    return dict(row) if row else None


async def _resolve_defect_lineage_ids(
    session,
    reporter_id: int,
    reporter_role: str
) -> Dict[str, Optional[int]]:
    operator_id: Optional[int] = None
    sub_distributor_id: Optional[int] = None

    normalized_role = (reporter_role or "").strip().lower()
    if not normalized_role:
        user_row = await _get_user_role_and_parent(session, reporter_id)
        normalized_role = (user_row.get("role") if user_row else "") or ""

    if normalized_role == "operator":
        operator_id = reporter_id

        op_row = (await session.execute(
            text("SELECT id, role, parent_id FROM users WHERE CAST(id AS CHAR) = CAST(:uid AS CHAR)"),
            {"uid": str(reporter_id)}
        )).mappings().first()
        if op_row and op_row["parent_id"] is not None:
            parent_id = int(op_row["parent_id"])
            parent_row = (await session.execute(
                text("SELECT id, role, parent_id FROM users WHERE id = :pid"),
                {"pid": parent_id}
            )).mappings().first()
            if parent_row:
                if parent_row["role"] == "sub_distributor":
                    sub_distributor_id = int(parent_row["id"])
                elif parent_row["role"] == "cluster" and parent_row["parent_id"] is not None:
                    sub_row = (await session.execute(
                        text("SELECT id FROM users WHERE id = :pid AND role = 'sub_distributor'"),
                        {"pid": int(parent_row["parent_id"])}
                    )).mappings().first()
                    if sub_row:
                        sub_distributor_id = int(sub_row["id"])

    elif normalized_role == "sub_distributor":
        sub_distributor_id = reporter_id

    elif normalized_role == "cluster":
        row = (await session.execute(
            text("SELECT parent_id FROM users WHERE CAST(id AS CHAR) = CAST(:uid AS CHAR) AND role = 'cluster'"),
            {"uid": str(reporter_id)}
        )).mappings().first()
        if row and row["parent_id"] is not None:
            sub_row = (await session.execute(
                text("SELECT id FROM users WHERE id = :pid AND role = 'sub_distributor'"),
                {"pid": int(row["parent_id"])}
            )).mappings().first()
            if sub_row:
                sub_distributor_id = int(sub_row["id"])

    return {
        "operator_id": operator_id,
        "sub_distributor_id": sub_distributor_id,
    }


async def _get_sub_distributor_operator_ids(session, sub_distributor_id: str) -> Set[str]:
    operator_ids: Set[str] = set()
    rows = (await session.execute(
        text("""
            SELECT CAST(id AS CHAR) AS id FROM users
            WHERE role = 'operator' AND (
                CAST(parent_id AS CHAR) = CAST(:sid AS CHAR)
                OR parent_id IN (
                    SELECT id FROM users WHERE role = 'cluster' AND CAST(parent_id AS CHAR) = CAST(:sid2 AS CHAR)
                )
            )
        """),
        {"sid": str(sub_distributor_id), "sid2": str(sub_distributor_id)}
    )).mappings().all()
    for row in rows:
        operator_ids.add(str(row["id"]))
    return operator_ids


async def _resolve_sub_distributor_targets_for_operator(session, operator_id: str) -> List[str]:
    recipients: Set[str] = set()
    operator_row = (await session.execute(
        text("SELECT id, parent_id FROM users WHERE CAST(id AS CHAR) = CAST(:uid AS CHAR)"),
        {"uid": str(operator_id)}
    )).mappings().first()
    if not operator_row:
        return []

    parent_id = operator_row["parent_id"]
    if parent_id is None:
        return []

    parent_row = (await session.execute(
        text("SELECT id, role, parent_id FROM users WHERE id = :pid"),
        {"pid": int(parent_id)}
    )).mappings().first()
    if not parent_row:
        return []

    parent_role = parent_row["role"]
    if parent_role == "sub_distributor":
        recipients.add(str(parent_row["id"]))
    elif parent_role == "cluster" and parent_row["parent_id"] is not None:
        sub_row = (await session.execute(
            text("SELECT id FROM users WHERE id = :pid AND role = 'sub_distributor'"),
            {"pid": int(parent_row["parent_id"])}
        )).mappings().first()
        if sub_row:
            recipients.add(str(sub_row["id"]))

    return sorted(recipients)


async def _get_report_scope_user_ids(session, user: Dict[str, Any]) -> Optional[Set[str]]:
    role = str(user.get("role") or "").lower()
    user_id = str(user.get("id") or user.get("_id"))
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


async def _enrich_defect_rows(session, defects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not defects:
        return defects

    device_ids = set()
    for defect in defects:
        if defect.get("device_id"):
            device_ids.add(str(defect["device_id"]))
        if defect.get("replacement_device_id"):
            device_ids.add(str(defect["replacement_device_id"]))

    devices_map: Dict[str, Dict[str, Any]] = {}
    numeric_device_ids = [device_id for device_id in device_ids if str(device_id).isdigit()]
    if numeric_device_ids:
        ph = ",".join([f":d_{i}" for i in range(len(numeric_device_ids))])
        params = {f"d_{i}": device_id for i, device_id in enumerate(numeric_device_ids)}
        rows = (await session.execute(
            text(f"SELECT * FROM devices WHERE id IN ({ph})"),
            params
        )).mappings().all()
        for row in rows:
            devices_map[str(row["id"])] = dict(row)

    for defect in defects:
        defective_device = devices_map.get(str(defect.get("device_id")))
        replacement_device = devices_map.get(str(defect.get("replacement_device_id"))) if defect.get("replacement_device_id") else None

        defect["defective_device"] = defective_device
        defect["replacement_device"] = replacement_device
        defect["replacement_mapped"] = bool(replacement_device)

        if defective_device:
            if not defect.get("device_serial") and not is_set_top_box_device(defective_device):
                defect["device_serial"] = defective_device.get("serial_number")
            if not defect.get("mac_address") and not is_set_top_box_device(defective_device):
                defect["mac_address"] = defective_device.get("mac_address")
            if not defect.get("device_type"):
                defect["device_type"] = defective_device.get("device_type")
            if not defect.get("device_name"):
                defect["device_name"] = defective_device.get("model") or defective_device.get("device_type")
            if not defect.get("nuid"):
                defect["nuid"] = defective_device.get("nuid")
            if not defect.get("device_nuid"):
                defect["device_nuid"] = defective_device.get("nuid")

        if replacement_device:
            if not defect.get("replacement_device_serial"):
                defect["replacement_device_serial"] = replacement_device.get("serial_number")
            if not defect.get("replacement_device_nuid"):
                defect["replacement_device_nuid"] = replacement_device.get("nuid")
            if not defect.get("replacement_device_code"):
                defect["replacement_device_code"] = replacement_device.get("device_id")

    auto_return_ids = [d.get("auto_return_id") for d in defects if d.get("auto_return_id")]
    if auto_return_ids:
        ph = ",".join([f":r_{i}" for i in range(len(auto_return_ids))])
        params = {f"r_{i}": rid for i, rid in enumerate(auto_return_ids)}
        rows = (await session.execute(
            text(f"SELECT return_id, status FROM returns WHERE return_id IN ({ph})"),
            params
        )).mappings().all()
        return_status_map = {r["return_id"]: r["status"] for r in rows}
        for defect in defects:
            rid = defect.get("auto_return_id")
            defect["auto_return_status"] = return_status_map.get(rid) if rid else None

    return defects


async def get_defects(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    defect_type: Optional[str] = None,
    reported_by: Optional[int] = None,
    holder_user_id: Optional[int] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    visibility_user: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        conditions = ["1=1"]
        params: Dict[str, Any] = {}

        if status:
            conditions.append("status = :status")
            params["status"] = status
        if severity:
            conditions.append("severity = :severity")
            params["severity"] = severity
        if defect_type:
            conditions.append("defect_type = :defect_type")
            params["defect_type"] = defect_type
        if reported_by:
            conditions.append("reported_by = :reported_by")
            params["reported_by"] = reported_by
        if holder_user_id:
            conditions.append(
                "(reported_by = :holder_uid OR CAST(device_id AS UNSIGNED) IN (SELECT id FROM devices WHERE current_holder_id = :holder_uid2))"
            )
            params["holder_uid"] = holder_user_id
            params["holder_uid2"] = holder_user_id
        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date
        if search:
            like = f"%{search}%"
            search_field_map = {
                "report_id": "report_id",
                "device_serial": "device_serial",
                "device_nuid": "device_nuid",
                "description": "description",
                "defect_type": "defect_type",
                "severity": "severity",
                "status": "status",
                "reported_by_name": "reported_by_name",
                "device_type": "device_type",
            }
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by in {"digital_id", "broadband_id"}:
                clause, iparams = build_identity_search_clause(
                    ["defects.reported_by"], like, fields=[normalized_search_by]
                )
                conditions.append(clause)
                params.update(iparams)
            elif normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE :search_like")
                params["search_like"] = like
            else:
                id_clause, iparams = build_identity_search_clause(["defects.reported_by"], like)
                conditions.append("(report_id LIKE :sl1 OR device_serial LIKE :sl2 OR device_nuid LIKE :sl9 OR description LIKE :sl3 OR defect_type LIKE :sl4 OR severity LIKE :sl5 OR status LIKE :sl6 OR reported_by_name LIKE :sl7 OR device_type LIKE :sl8 OR " + id_clause + ")")
                for i in range(9):
                    params[f"sl{i+1}"] = like
                params.update(iparams)

        if visibility_user:
            role = visibility_user.get("role")
            if role not in ["super_admin", "md_director", "manager", "pdic_staff"]:
                scoped_user_ids = await _get_report_scope_user_ids(session, visibility_user)
                if scoped_user_ids:
                    ph = ",".join([f":sr_{i}" for i in range(len(scoped_user_ids))])
                    conditions.append(f"CAST(reported_by AS CHAR) IN ({ph})")
                    for i, sid in enumerate(sorted(scoped_user_ids)):
                        params[f"sr_{i}"] = sid
                else:
                    conditions.append("1=0")

        where = " AND ".join(conditions)

        total = (await session.execute(
            text(f"SELECT COUNT(*) FROM defects WHERE {where}"), params
        )).scalar() or 0

        offset = (page - 1) * page_size
        params["_limit"] = page_size
        params["_offset"] = offset
        rows = (await session.execute(
            text(f"SELECT * FROM defects WHERE {where} ORDER BY created_at DESC LIMIT :_limit OFFSET :_offset"),
            params
        )).mappings().all()
        data = [dict(r) for r in rows]
        for d in data:
            if isinstance(d.get("images"), str):
                d["images"] = json.loads(d["images"])
        data = await _enrich_defect_rows(session, data)

        return {
            "data": data,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_defect_by_id(defect_id: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        row = (await session.execute(
            text("SELECT * FROM defects WHERE id = :id"), {"id": int(defect_id)}
        )).mappings().first()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("images"), str):
            d["images"] = json.loads(d["images"])
        enriched = await _enrich_defect_rows(session, [d])
        if enriched:
            return enriched[0]
        return d


async def create_defect(
    defect_data: DefectCreate,
    reporter: Dict[str, Any],
    sync_device_status: bool = True
) -> Dict[str, Any]:
    reporter_id = int(reporter.get("_id") or reporter.get("id"))
    reporter_name = reporter.get("name") or "System"
    reporter_role = reporter.get("role") or ""
    requested_target = defect_data.report_target.value if defect_data.report_target else None
    report_target = (
        DefectReportTarget.SUB_DISTRIBUTOR.value
        if requested_target == DefectReportTarget.SUB_DISTRIBUTOR.value and reporter_role == "operator"
        else DefectReportTarget.MANAGER_ADMIN.value
    )

    async with async_session_factory() as session:
        device_row = (await session.execute(
            text("SELECT * FROM devices WHERE id = :id"), {"id": int(defect_data.device_id)}
        )).mappings().first()
        if not device_row:
            raise ValueError("Device not found")
        device = dict(device_row)

        existing = (await session.execute(
            text("SELECT id, report_id, status FROM defects WHERE device_id = :did AND status NOT IN ('resolved', 'rejected') ORDER BY created_at DESC LIMIT 1"),
            {"did": defect_data.device_id}
        )).mappings().first()
        if existing:
            raise ValueError(
                f"Device already has an active defect report ({existing['report_id']}, status: {existing['status']}). "
                f"A new report can only be submitted after the existing defect is resolved."
            )

        now = datetime.now().replace(tzinfo=None)
        images_json = json.dumps(defect_data.images or [])
        lineage = await _resolve_defect_lineage_ids(session, reporter_id=reporter_id, reporter_role=reporter_role)
        report_id = generate_defect_id()

        is_sb = is_set_top_box_device(device)
        device_serial = None if is_sb else device.get("serial_number")
        device_nuid = device.get("nuid") if is_sb else None

        result = await session.execute(
            text("""
                INSERT INTO defects (report_id, device_id, device_serial, device_nuid, device_type,
                reported_by, reported_by_name, defect_type, severity, description,
                operator_id, sub_distributor_id, report_target, forwarded_to_management, status, resolution, replacement_by,
                replacement_by_name, resolved_at, images, created_at, updated_at)
                VALUES (:report_id, :device_id, :device_serial, :device_nuid, :device_type,
                :reported_by, :reported_by_name, :defect_type, :severity, :description,
                :operator_id, :sub_distributor_id, :report_target, :forwarded_to_management, :status, :resolution, :replacement_by,
                :replacement_by_name, :resolved_at, :images, :created_at, :updated_at)
            """),
            {
                "report_id": report_id,
                "device_id": defect_data.device_id,
                "device_serial": device_serial,
                "device_nuid": device_nuid,
                "device_type": device["device_type"],
                "reported_by": reporter_id,
                "reported_by_name": reporter_name,
                "defect_type": defect_data.defect_type.value,
                "severity": defect_data.severity.value,
                "description": defect_data.description,
                "operator_id": lineage.get("operator_id"),
                "sub_distributor_id": lineage.get("sub_distributor_id"),
                "report_target": report_target,
                "forwarded_to_management": 0,
                "status": DefectStatus.REPORTED.value,
                "resolution": None,
                "replacement_by": None,
                "replacement_by_name": None,
                "resolved_at": None,
                "images": images_json,
                "created_at": now,
                "updated_at": now,
            }
        )
        new_id = result.lastrowid
        await bump_cache_version(session)
        await session.commit()

    if sync_device_status:
        await device_service.update_device_status(
            device_id=defect_data.device_id,
            status=DeviceStatus.DEFECTIVE.value,
            performed_by=reporter_id,
            performed_by_name=reporter_name,
            notes=f"Defect reported: {defect_data.defect_type.value} - {defect_data.severity.value}"
        )

    async with async_session_factory() as session:
        recipient_ids: List[str] = []
        if report_target == DefectReportTarget.SUB_DISTRIBUTOR.value:
            recipient_ids = await _resolve_sub_distributor_targets_for_operator(session, reporter_id)

        if not recipient_ids:
            rows = (await session.execute(
                text("SELECT id FROM users WHERE role IN ('super_admin', 'manager', 'pdic_staff')")
            )).mappings().all()
            recipient_ids = [str(r["id"]) for r in rows]

        severity = defect_data.severity.value
        await notification_service.bulk_create_notifications([
            {
                "user_id": rid,
                "title": "New Defect Report",
                "message": f"A new {severity} severity defect has been reported for device {device['device_id']}",
                "notification_type": "warning" if severity in ["critical", "high"] else "info",
                "category": "defect",
                "link": f"/defects?defectId={new_id}",
                "metadata": {
                    "action": "new_defect_report",
                    "defect_id": str(new_id),
                    "report_target": report_target
                }
            }
            for rid in recipient_ids
        ])

    return await get_defect_by_id(str(new_id))


async def create_or_get_active_defect_for_device(
    device_id: str,
    reporter: Dict[str, Any],
    notes: Optional[str] = None
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        existing = (await session.execute(
            text("SELECT id FROM defects WHERE device_id = :did AND status NOT IN ('resolved', 'rejected') ORDER BY created_at DESC LIMIT 1"),
            {"did": str(device_id)}
        )).mappings().first()
        if existing:
            return await get_defect_by_id(str(existing["id"]))

    note_text = (notes or "").strip()
    description = note_text
    if len(description) < 10:
        description = "Device was marked as defective via status update."

    payload = DefectCreate(
        device_id=str(device_id),
        defect_type=DefectType.OTHER,
        severity=DefectSeverity.MEDIUM,
        description=description,
        images=[]
    )
    return await create_defect(payload, reporter, sync_device_status=False)


async def forward_defect_to_management(
    defect_id: str,
    forwarder: Dict[str, Any],
    notes: Optional[str] = None
) -> Dict[str, Any]:
    forwarder_role = forwarder.get("role")
    forwarder_id = int(forwarder.get("id") or forwarder.get("_id"))
    forwarder_name = forwarder.get("name") or "Sub Distributor"

    if forwarder_role != "sub_distributor":
        raise ValueError("Only sub distributors can forward defects to manager/admin")

    async with async_session_factory() as session:
        defect = (await session.execute(
            text("SELECT * FROM defects WHERE id = :id"), {"id": int(defect_id)}
        )).mappings().first()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        target = defect.get("report_target") or DefectReportTarget.MANAGER_ADMIN.value
        if target != DefectReportTarget.SUB_DISTRIBUTOR.value:
            raise ValueError("This defect is not routed through sub distributor")
        if int(defect.get("forwarded_to_management") or 0) == 1:
            raise ValueError("This defect has already been forwarded to manager/admin")

        operator_ids = await _get_sub_distributor_operator_ids(session, forwarder_id)
        if str(defect.get("reported_by")) not in operator_ids:
            raise ValueError("You can only forward defects reported by operators under your hierarchy")

        now = datetime.now().replace(tzinfo=None)
        await session.execute(
            text("""
                UPDATE defects
                SET forwarded_to_management = 1,
                    forwarded_to_management_at = :now,
                    forwarded_to_management_by = :fid,
                    forwarded_to_management_by_name = :fname,
                    updated_at = :now2
                WHERE id = :id
            """),
            {"now": now, "fid": forwarder_id, "fname": forwarder_name, "now2": now, "id": int(defect_id)}
        )
        await bump_cache_version(session)
        await session.commit()

        rows = (await session.execute(
            text("SELECT id FROM users WHERE role IN ('super_admin', 'manager', 'pdic_staff')")
        )).mappings().all()

    await notification_service.bulk_create_notifications([
        {
            "user_id": r["id"],
            "title": "Defect Forwarded by Sub Distributor",
            "message": (
                f"Defect {defect.get('report_id')} was forwarded by {forwarder_name} "
                "for manager/admin review."
            ),
            "notification_type": "info",
            "category": "defect",
            "link": f"/defects?defectId={defect_id}",
            "metadata": {
                "action": "forwarded_to_management",
                "defect_id": str(defect_id),
                "notes": notes,
                "forwarded_by": forwarder_name
            }
        }
        for r in rows
    ])

    if defect.get("reported_by"):
        await notification_service.create_notification(
            user_id=int(defect["reported_by"]),
            title="Defect Forwarded to Manager/Admin",
            message=(
                f"Your defect report {defect.get('report_id')} has been forwarded to manager/admin "
                "for further review."
            ),
            notification_type="info",
            category="defect",
            link=f"/defects?defectId={defect_id}"
        )

    return await get_defect_by_id(defect_id)


async def update_defect(defect_id: str, defect_data: DefectUpdate) -> Optional[Dict[str, Any]]:
    update_dict = {k: v for k, v in defect_data.model_dump().items() if v is not None}

    if not update_dict:
        return await get_defect_by_id(defect_id)

    if "defect_type" in update_dict:
        update_dict["defect_type"] = update_dict["defect_type"].value
    if "severity" in update_dict:
        update_dict["severity"] = update_dict["severity"].value
    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value

    update_dict["updated_at"] = datetime.now().replace(tzinfo=None)

    async with async_session_factory() as session:
        set_clause = ", ".join(f"{k} = :{k}" for k in update_dict)
        params = {**update_dict, "id": int(defect_id)}
        result = await session.execute(text(f"UPDATE defects SET {set_clause} WHERE id = :id"), params)
        await bump_cache_version(session)
        await session.commit()
        if result.rowcount > 0:
            return await get_defect_by_id(defect_id)
    return None


async def delete_defect(defect_id: str) -> bool:
    async with async_session_factory() as session:
        result = await session.execute(text("DELETE FROM defects WHERE id = :id"), {"id": int(defect_id)})
        await bump_cache_version(session)
        await session.commit()
        return result.rowcount > 0


async def update_defect_status(
    defect_id: str,
    status: str,
    user: Dict[str, Any],
    notes: Optional[str] = None,
    return_amount: Optional[float] = None,
    payment_bill_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        defect = (await session.execute(
            text("SELECT * FROM defects WHERE id = :id"), {"id": int(defect_id)}
        )).mappings().first()
        if not defect:
            return None
        defect = dict(defect)

        now = datetime.now().replace(tzinfo=None)
        update_parts = ["status = :status", "updated_at = :updated_at"]
        update_params: Dict[str, Any] = {"status": status, "updated_at": now, "id": int(defect_id)}

        if status == DefectStatus.APPROVED.value:
            amount = return_amount if return_amount is not None else (defect.get("return_amount") or None)
            stored_amount = float(amount) if amount is not None and float(amount) > 0 else None
            update_parts.append("return_amount = :return_amount")
            update_parts.append("payment_due_user_id = :payment_due_user_id")
            update_parts.append("payment_due_user_name = :payment_due_user_name")
            update_parts.append("payment_confirmed = 0")
            update_parts.append("defect_approved_by = :defect_approved_by")
            update_parts.append("defect_approved_by_name = :defect_approved_by_name")
            update_parts.append("defect_approved_at = :defect_approved_at")
            update_params["return_amount"] = stored_amount
            update_params["payment_due_user_id"] = defect.get("reported_by")
            update_params["payment_due_user_name"] = str(defect.get("reported_by_name") or "Unknown")
            update_params["defect_approved_by"] = int(user.get("_id") or user.get("id"))
            update_params["defect_approved_by_name"] = user.get("name", "Unknown")
            update_params["defect_approved_at"] = now
            if payment_bill_url:
                update_parts.append("payment_bill_url = :payment_bill_url")
                update_params["payment_bill_url"] = payment_bill_url

        set_clause = ", ".join(update_parts)
        result = await session.execute(
            text(f"UPDATE defects SET {set_clause} WHERE id = :id"),
            update_params
        )
        await bump_cache_version(session)
        await session.commit()
        affected = result.rowcount

    if affected > 0:
        extra_msg = ""
        if status == DefectStatus.APPROVED.value:
            await device_service.update_device_status(
                device_id=defect["device_id"],
                status=DeviceStatus.DEFECTIVE.value,
                performed_by=int(user.get("_id") or user.get("id")),
                performed_by_name=user.get("name", "Unknown"),
                notes=f"Defect report {defect.get('report_id', defect_id)} approved"
            )
            try:
                auto_return = await return_service.auto_create_defect_return(
                    device_id=defect["device_id"],
                    defect_id=defect_id,
                    defect_report_id=defect["report_id"],
                    requester_id=defect["reported_by"]
                )
                if auto_return:
                    async with async_session_factory() as session:
                        await session.execute(
                            text("UPDATE defects SET auto_return_id = :rid WHERE id = :id"),
                            {"rid": auto_return["return_id"], "id": int(defect_id)}
                        )
                        await bump_cache_version(session)
                        await session.commit()
                    extra_msg = f" A return request ({auto_return['return_id']}) has been automatically created."
            except Exception:
                pass

        await notification_service.create_notification(
            user_id=defect["reported_by"],
            title="Defect Report Approved — Return Required" if status == DefectStatus.APPROVED.value else "Defect Status Updated",
            message=(
                f"Your defect report {defect['report_id']} has been approved. "
                f"Please return the defective device to PDIC as soon as possible."
                + (f" Due amount: {float(return_amount):.2f}." if status == DefectStatus.APPROVED.value and return_amount is not None and float(return_amount) > 0 else "")
                + extra_msg
            ) if status == DefectStatus.APPROVED.value else (
                f"Your defect report {defect['report_id']} status has been updated to {status}."
            ),
            notification_type="warning" if status == DefectStatus.APPROVED.value else "info",
            category="defect",
            link=f"/defects?defectId={defect_id}"
        )

        if status == DefectStatus.APPROVED.value:
            enabled_roles = ["super_admin", "manager", "pdic_staff"]
            roles_ph = ",".join([f":r_{i}" for i in range(len(enabled_roles))])
            roles_params = {f"r_{i}": r for i, r in enumerate(enabled_roles)}
            async with async_session_factory() as session:
                staff_rows = (await session.execute(
                    text(f"SELECT id FROM users WHERE role IN ({roles_ph})"),
                    roles_params
                )).mappings().all()
            notifications = [
                {
                    "user_id": r["id"],
                    "title": "Defective Device Return — Pending Receipt",
                    "message": (
                        f"Defect {defect['report_id']} approved. The operator has been instructed to return "
                        f"device to PDIC. Please confirm receipt when device arrives."
                    ),
                    "notification_type": "info",
                    "category": "return",
                    "link": "/returns"
                }
                for r in staff_rows
                if int(r["id"]) != int(defect["reported_by"])
            ]
            if notifications:
                await notification_service.bulk_create_notifications(notifications)

        return await get_defect_by_id(defect_id)
    return None


async def set_defect_payment_bill_url(defect_id: str, bill_url: str) -> Optional[Dict[str, Any]]:
    now = datetime.now().replace(tzinfo=None)
    async with async_session_factory() as session:
        result = await session.execute(
            text("UPDATE defects SET payment_bill_url = :url, updated_at = :now WHERE id = :id"),
            {"url": bill_url, "now": now, "id": int(defect_id)}
        )
        await bump_cache_version(session)
        await session.commit()
        if result.rowcount <= 0:
            return None
    return await get_defect_by_id(defect_id)


async def confirm_defect_payment(
    defect_id: str,
    confirmer: Dict[str, Any],
    notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = datetime.now().replace(tzinfo=None)
    confirmer_id = int(confirmer.get("_id") or confirmer.get("id"))
    confirmer_name = str(confirmer.get("name") or "Management")

    async with async_session_factory() as session:
        defect_row = (await session.execute(
            text("SELECT * FROM defects WHERE id = :id"), {"id": int(defect_id)}
        )).mappings().first()
        if not defect_row:
            return None
        defect = dict(defect_row)

        amount = float(defect.get("return_amount") or 0)
        if amount <= 0:
            raise ValueError("No payment amount is configured for this defect")
        if int(defect.get("payment_confirmed") or 0) == 1:
            raise ValueError("Payment has already been confirmed for this defect")

        return_id = defect.get("auto_return_id")
        if return_id:
            ret_row = (await session.execute(
                text("SELECT status FROM returns WHERE return_id = :rid"), {"rid": return_id}
            )).mappings().first()
            if ret_row and str(ret_row.get("status") or "") != "received":
                raise ValueError("Cannot confirm payment before defective device is marked received at PDIC")

        await session.execute(
            text("""
                UPDATE defects
                SET payment_confirmed = 1,
                    payment_confirmed_at = :now,
                    payment_confirmed_by = :cid,
                    payment_confirmed_by_name = :cname,
                    updated_at = :now2
                WHERE id = :id
            """),
            {"now": now, "cid": confirmer_id, "cname": confirmer_name, "now2": now, "id": int(defect_id)}
        )
        await bump_cache_version(session)
        await session.commit()

    due_user_id = int(defect.get("payment_due_user_id") or defect.get("reported_by") or 0)
    if due_user_id:
        await notification_service.create_notification(
            user_id=due_user_id,
            title="Defect Return Payment Confirmed",
            message=(
                f"Payment for defect {defect.get('report_id')} has been confirmed by {confirmer_name}."
                + (f" Notes: {notes}" if notes else "")
            ),
            notification_type="success",
            category="defect",
            link=f"/defects?defectId={defect_id}"
        )

    return await get_defect_by_id(defect_id)


async def get_pending_dues_users(current_user: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    async with async_session_factory() as session:
        scope_user_ids = await _get_report_scope_user_ids(session, current_user) if current_user else None
        if scope_user_ids is not None and len(scope_user_ids) == 0:
            return []

        conditions = [
            "COALESCE(d.return_amount, 0) > 0",
            "COALESCE(d.payment_confirmed, 0) = 0",
            "COALESCE(r.status, '') = 'received'",
        ]
        params: Dict[str, Any] = {}

        if scope_user_ids is not None:
            ph = ",".join([f":sr_{i}" for i in range(len(scope_user_ids))])
            conditions.append(
                f"COALESCE(d.payment_due_user_id, d.reported_by) IN ({ph})"
            )
            for i, sid in enumerate(sorted(scope_user_ids)):
                params[f"sr_{i}"] = sid

        where_clause = " AND ".join(conditions)

        rows = (await session.execute(
            text(f"""
                SELECT
                    due.id AS user_id,
                    COALESCE(NULLIF(d.payment_due_user_name, ''), d.reported_by_name, due.name) AS user_name,
                    due.role AS user_role,
                    due.parent_id AS parent_id,
                    parent.name AS parent_name,
                    COUNT(*) AS due_count,
                    SUM(COALESCE(d.return_amount, 0)) AS total_due
                FROM defects d
                LEFT JOIN returns r ON ((CAST(r.defect_id AS UNSIGNED) = d.id) OR r.return_id = d.auto_return_id)
                LEFT JOIN users due ON due.id = COALESCE(d.payment_due_user_id, d.reported_by)
                LEFT JOIN users parent ON parent.id = due.parent_id
                WHERE {where_clause}
                GROUP BY due.id,
                         COALESCE(NULLIF(d.payment_due_user_name, ''), d.reported_by_name, due.name),
                         due.role,
                         due.parent_id,
                         parent.name
                ORDER BY total_due DESC, due_count DESC
            """),
            params
        )).mappings().all()
        result = [dict(r) for r in rows]

        due_user_ids = [int(r["user_id"]) for r in result if r["user_id"] is not None]
        if due_user_ids:
            ph = ",".join([f":di_{i}" for i in range(len(due_user_ids))])
            id_rows = (await session.execute(
                text(f"SELECT user_id, digital_id, broadband_id FROM digital_identities WHERE user_id IN ({ph})"),
                {f"di_{i}": v for i, v in enumerate(due_user_ids)},
            )).mappings().all()
            digital_map: Dict[int, list] = {}
            for r in id_rows:
                digital_map.setdefault(int(r["user_id"]), []).append({
                    "digital_id": r["digital_id"],
                    "broadband_id": r["broadband_id"],
                })
            for row in result:
                row["digital_ids"] = digital_map.get(int(row["user_id"]), [])
        else:
            for row in result:
                row["digital_ids"] = []

        return result


async def get_pending_dues_for_user(user_id: str, current_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    async with async_session_factory() as session:
        scope_user_ids = await _get_report_scope_user_ids(session, current_user) if current_user else None
        requested_user_id = int(user_id)
        # scope_user_ids is a set of string ids; compare as strings to avoid an
        # int-vs-str mismatch that wrongly rejected every non-management caller.
        if scope_user_ids is not None and str(requested_user_id) not in scope_user_ids:
            raise PermissionError("Requested user is outside your hierarchy scope")

        rows = (await session.execute(
            text("""
                SELECT
                    d.id,
                    d.report_id,
                    d.device_id,
                    d.device_serial,
                    d.device_nuid,
                    d.device_type,
                    d.reported_by,
                    d.reported_by_name,
                    d.return_amount,
                    d.payment_bill_url,
                    d.payment_confirmed,
                    d.payment_confirmed_at,
                    d.auto_return_id,
                    d.status,
                    d.created_at,
                    r.return_id,
                    r.status AS return_status,
                    r.received_date,
                    dev.model AS device_model,
                    dev.manufacturer AS device_manufacturer
                FROM defects d
                LEFT JOIN returns r ON ((CAST(r.defect_id AS UNSIGNED) = d.id) OR r.return_id = d.auto_return_id)
                LEFT JOIN devices dev ON dev.id = d.device_id
                WHERE COALESCE(d.payment_due_user_id, d.reported_by) = :uid
                  AND COALESCE(d.return_amount, 0) > 0
                  AND COALESCE(d.payment_confirmed, 0) = 0
                  AND COALESCE(r.status, '') = 'received'
                ORDER BY r.received_date DESC, d.updated_at DESC
            """),
            {"uid": requested_user_id}
        )).mappings().all()
        dues = [dict(r) for r in rows]

        total_due = sum(float(item.get("return_amount") or 0) for item in dues)
        user_name = dues[0].get("reported_by_name") if dues else None

        return {
            "user_id": requested_user_id,
            "user_name": user_name,
            "total_due": total_due,
            "count": len(dues),
            "items": dues,
        }


async def resolve_defect(
    defect_id: str,
    resolution: str,
    resolver: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        defect = (await session.execute(
            text("SELECT * FROM defects WHERE id = :id"), {"id": int(defect_id)}
        )).mappings().first()
        if not defect:
            return None
        defect = dict(defect)

        now = datetime.now().replace(tzinfo=None)
        result = await session.execute(
            text("""
                UPDATE defects SET status = :status, resolution = :resolution, resolved_at = :resolved_at, updated_at = :updated_at WHERE id = :id
            """),
            {
                "status": DefectStatus.RESOLVED.value,
                "resolution": resolution,
                "resolved_at": now,
                "updated_at": now,
                "id": int(defect_id)
            }
        )
        await bump_cache_version(session)
        await session.commit()

        if result.rowcount > 0:
            await device_service.update_device_status(
                device_id=defect["device_id"],
                status=DeviceStatus.MAINTENANCE.value,
                performed_by=int(resolver["_id"]),
                performed_by_name=resolver["name"],
                notes=f"Defect resolved: {defect['report_id']}"
            )

            await notification_service.create_notification(
                user_id=defect["reported_by"],
                title="Defect Resolved",
                message=f"Your defect report {defect['report_id']} has been resolved",
                notification_type="success",
                category="defect",
                link=f"/defects?defectId={defect_id}"
            )
            return await get_defect_by_id(defect_id)
    return None


async def replace_defect_device(
    defect_id: str,
    replacement_device_id: Optional[str],
    mac_address: Optional[str],
    serial_number: Optional[str],
    register_device: Optional[Dict[str, Any]],
    notes: Optional[str],
    return_amount: Optional[float],
    payment_bill_url: Optional[str],
    resolver: Dict[str, Any]
) -> Dict[str, Any]:
    """Replace a defective device by selecting existing stock or registering a new device."""
    resolver_id = int(resolver.get("_id") or resolver.get("id"))
    resolver_name = resolver.get("name") or "System"
    pre_created_device: Optional[Dict[str, Any]] = None

    if register_device:
        raw_type = str(register_device.get("device_type") or "").strip().lower()
        is_sb = raw_type in {"sb", "set-top box", "set top box", "stb"}
        if not is_sb:
            register_device.setdefault("band_type", "single_band")
        else:
            register_device["band_type"] = None
        create_payload = DeviceCreate(**register_device)
        pre_created_device = await device_service.create_device(
            device_data=create_payload,
            created_by=resolver_id,
            created_by_name=resolver_name
        )

    async with async_session_factory() as session:
        defect = (await session.execute(
            text("SELECT * FROM defects WHERE id = :id"), {"id": int(defect_id)}
        )).mappings().first()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        if defect.get("status") != DefectStatus.APPROVED.value:
            raise ValueError(
                f"Cannot replace device — defect must be in 'approved' status. "
                f"Current status: {defect.get('status')}"
            )

        auto_return_id = defect.get("auto_return_id")
        if auto_return_id:
            ret_row = (await session.execute(
                text("SELECT status FROM returns WHERE return_id = :rid"), {"rid": auto_return_id}
            )).mappings().first()
            if ret_row and str(ret_row.get("status") or "") != "received":
                raise ValueError(
                    "Cannot replace device — the defective device must be returned and received "
                    "at PDIC first. Please confirm return receipt before replacing."
                )

        old_device = (await session.execute(
            text("SELECT * FROM devices WHERE id = :id"), {"id": int(defect["device_id"])}
        )).mappings().first()
        if not old_device:
            raise ValueError("Original defective device not found")
        old_device = dict(old_device)

        new_device = None
        if replacement_device_id:
            nd = (await session.execute(
                text("SELECT * FROM devices WHERE id = :id"), {"id": int(replacement_device_id)}
            )).mappings().first()
            if not nd:
                raise ValueError("Selected replacement device was not found")
            new_device = dict(nd)
        elif pre_created_device:
            new_device = pre_created_device
        elif mac_address:
            nd = (await session.execute(
                text("SELECT * FROM devices WHERE mac_address = :mac"), {"mac": mac_address}
            )).mappings().first()
            new_device = dict(nd) if nd else None
        elif serial_number:
            nd = (await session.execute(
                text("SELECT * FROM devices WHERE serial_number = :sn"), {"sn": serial_number}
            )).mappings().first()
            new_device = dict(nd) if nd else None
        else:
            raise ValueError("Replacement target not provided")

        if not new_device:
            raise ValueError("Replacement device not found in system")

        is_same_device_reassignment = str(new_device["id"]) == str(old_device["id"])

        if (not is_same_device_reassignment) and new_device.get("status") not in [DeviceStatus.AVAILABLE.value, DeviceStatus.RETURNED.value]:
            raise ValueError(
                f"Replacement device must be available. Current status: {new_device.get('status')}"
            )

        original_holder_id = old_device.get("current_holder_id")
        original_holder_name = old_device.get("current_holder_name")
        original_holder_type = old_device.get("current_holder_type") or "operator"
        original_location = old_device.get("current_location") or "Field"

        resolution_note = notes or (
            (
                f"Serviced and reassigned same device {new_device.get('device_id')} "
                f"(Serial: {new_device.get('serial_number')}, MAC: {new_device.get('mac_address')})"
            )
            if is_same_device_reassignment else
            (
                f"Replaced with device {new_device.get('device_id')} "
                f"(Serial: {new_device.get('serial_number')}, MAC: {new_device.get('mac_address')})"
            )
        )
        now = datetime.now().replace(tzinfo=None)

        update_parts = [
            "status = :status",
            "replacement_device_id = :replacement_device_id",
            "resolution = :resolution",
            "replacement_by = :replacement_by",
            "replacement_by_name = :replacement_by_name",
            "resolved_at = :resolved_at",
            "updated_at = :updated_at",
        ]
        update_params: Dict[str, Any] = {
            "status": DefectStatus.REPLACEMENT_PENDING_CONFIRMATION.value,
            "replacement_device_id": str(new_device["id"]),
            "resolution": resolution_note,
            "replacement_by": resolver_id,
            "replacement_by_name": resolver_name,
            "resolved_at": None,
            "updated_at": now,
            "id": int(defect_id),
        }

        if return_amount is not None:
            stored_amount = float(return_amount) if float(return_amount) > 0 else None
            update_parts.append("return_amount = :return_amount")
            update_params["return_amount"] = stored_amount
            if float(return_amount) > 0:
                update_parts.append("payment_due_user_id = :payment_due_user_id")
                update_parts.append("payment_due_user_name = :payment_due_user_name")
                update_parts.append("payment_confirmed = 0")
                update_params["payment_due_user_id"] = defect.get("reported_by")
                update_params["payment_due_user_name"] = str(defect.get("reported_by_name") or "Unknown")

        if payment_bill_url:
            update_parts.append("payment_bill_url = :payment_bill_url")
            update_params["payment_bill_url"] = str(payment_bill_url)

        set_clause = ", ".join(update_parts)
        await session.execute(text(f"UPDATE defects SET {set_clause} WHERE id = :id"), update_params)
        await bump_cache_version(session)
        await session.commit()

    if not is_same_device_reassignment:
        old_device_metadata = _parse_json_metadata(old_device.get("metadata"))
        old_device_metadata["replaced_by"] = {
            "device_id": str(new_device.get("id")),
            "device_code": new_device.get("device_id"),
            "serial_number": new_device.get("serial_number"),
            "defect_id": str(defect_id),
            "defect_report_id": defect.get("report_id"),
            "replaced_at": datetime.now().replace(tzinfo=None).isoformat(),
            "replaced_by_user_id": resolver_id,
            "replaced_by_user_name": resolver_name
        }
        async with async_session_factory() as session:
            await session.execute(
                text("UPDATE devices SET metadata = :meta, updated_at = :now WHERE id = :id"),
                {"meta": json.dumps(old_device_metadata), "now": datetime.now().replace(tzinfo=None), "id": int(old_device["id"])}
            )
            await bump_cache_version(session)
            await session.commit()

    await device_service.update_device_status(
        device_id=defect["device_id"],
        status=DeviceStatus.MAINTENANCE.value if is_same_device_reassignment else DeviceStatus.REPLACED.value,
        performed_by=resolver_id,
        performed_by_name=resolver_name,
        notes=(
            f"Device serviced and reassigned for defect {defect.get('report_id')}"
            if is_same_device_reassignment
            else f"Device replaced by {new_device.get('device_id')} for defect {defect.get('report_id')}"
        )
    )

    holder_user_id = int(original_holder_id) if original_holder_id else None
    holder_user_name = original_holder_name or defect.get("reported_by_name") or "Operator"

    reported_by_str = int(defect["reported_by"]) if defect.get("reported_by") else None
    recipient_ids = {uid for uid in [holder_user_id, reported_by_str] if uid is not None}

    title = (
        "Serviced Device Ready - Confirmation Required"
        if is_same_device_reassignment
        else "Replacement Device Ready - Confirmation Required"
    )
    await notification_service.bulk_create_notifications([
        {
            "user_id": rid,
            "title": title,
            "message": (
                f"Operator update for {holder_user_name}: "
                f"{'serviced device' if is_same_device_reassignment else 'replacement device'} {new_device.get('device_id')} "
                f"(Serial: {new_device.get('serial_number')}) is prepared for defect {defect['report_id']}. "
                "Confirm only after you physically receive the replacement device. "
                "Do not confirm before receiving it."
            ),
            "notification_type": "warning",
            "category": "defect",
            "link": "/replacement-confirmation"
        }
        for rid in recipient_ids
    ])

    return await get_defect_by_id(defect_id)


async def confirm_replacement_receipt(
    defect_id: str,
    confirmer: Dict[str, Any],
    notes: Optional[str] = None
) -> Dict[str, Any]:
    confirmer_id = int(confirmer.get("_id") or confirmer.get("id"))
    confirmer_name = confirmer.get("name") or "Operator"
    confirmer_role = str(confirmer.get("role") or "operator")

    async with async_session_factory() as session:
        defect = (await session.execute(
            text("SELECT * FROM defects WHERE id = :id"), {"id": int(defect_id)}
        )).mappings().first()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        if defect.get("status") != DefectStatus.REPLACEMENT_PENDING_CONFIRMATION.value:
            raise ValueError("Replacement confirmation is not pending for this defect")

        replacement_device_id = defect.get("replacement_device_id")
        if not replacement_device_id:
            raise ValueError("No replacement device is linked to this defect")

        old_device = (await session.execute(
            text("SELECT * FROM devices WHERE id = :id"), {"id": int(defect["device_id"])}
        )).mappings().first()
        if not old_device:
            raise ValueError("Original defective device not found")
        old_device = dict(old_device)

        holder_user_id = int(old_device.get("current_holder_id")) if old_device.get("current_holder_id") else None
        reporter_user_id = int(defect.get("reported_by")) if defect.get("reported_by") else None
        allowed_confirmer_ids = {uid for uid in [holder_user_id, reporter_user_id] if uid is not None}
        if confirmer_id not in allowed_confirmer_ids:
            raise ValueError("Only the current holder or original defect reporter can confirm replacement receipt")

        new_device = (await session.execute(
            text("SELECT * FROM devices WHERE id = :id"), {"id": int(replacement_device_id)}
        )).mappings().first()
        if not new_device:
            raise ValueError("Replacement device not found")
        new_device = dict(new_device)

        is_same_device_reassignment = str(new_device.get("id")) == str(old_device.get("id"))

        if (not is_same_device_reassignment) and new_device.get("status") not in [DeviceStatus.AVAILABLE.value, DeviceStatus.RETURNED.value]:
            raise ValueError(
                f"Replacement device is not available for confirmation. Current status: {new_device.get('status')}"
            )

        now = datetime.now().replace(tzinfo=None)

        await session.execute(
            text("""
                UPDATE defects SET status = :status, replacement_confirmed_at = :rca, replacement_confirmed_by = :rcb,
                replacement_confirmed_by_name = :rcbn, resolved_at = :ra,
                updated_at = :ua, resolution = COALESCE(NULLIF(:resolution, ''), resolution)
                WHERE id = :id
            """),
            {
                "status": DefectStatus.RESOLVED.value,
                "rca": now,
                "rcb": confirmer_id,
                "rcbn": confirmer_name,
                "ra": now,
                "ua": now,
                "resolution": notes,
                "id": int(defect_id)
            }
        )
        await bump_cache_version(session)
        await session.commit()

    replacement_status = DeviceStatus.IN_USE.value if confirmer_role == "operator" else DeviceStatus.DISTRIBUTED.value
    updated_device = await device_service.update_device_holder(
        device_id=str(new_device["id"]),
        holder_id=int(confirmer_id),
        holder_name=confirmer_name,
        holder_type=confirmer_role,
        location=confirmer_name,
        status=replacement_status,
        performed_by=int(confirmer_id),
        performed_by_name=confirmer_name,
        from_user_id=None,
        from_user_name=None,
        notes=f"Replacement confirmed and activated for defect {defect.get('report_id')}"
    )

    if not updated_device:
        raise ValueError(
            "Replacement device holder transfer failed — device may not exist. "
            "Please contact admin to manually reassign the device."
        )

    async with async_session_factory() as session:
        recipients = (await session.execute(
            text("SELECT id FROM users WHERE role IN ('super_admin', 'manager', 'pdic_staff')")
        )).mappings().all()

    await notification_service.bulk_create_notifications([
        {
            "user_id": r["id"],
            "title": "Replacement Receipt Confirmed",
            "message": (
                f"{confirmer_name} ({confirmer_role.replace('_', ' ')}) confirmed receipt of replacement device "
                f"for defect {defect.get('report_id')}."
            ),
            "notification_type": "success",
            "category": "defect",
            "link": "/defects"
        }
        for r in recipients
    ])

    return await get_defect_by_id(defect_id)


async def enquire_replacement_status(
    defect_id: str,
    enquirer: Dict[str, Any],
    message: str
) -> Dict[str, Any]:
    enquirer_id = int(enquirer.get("_id") or enquirer.get("id"))
    enquirer_name = enquirer.get("name") or "Operator"

    async with async_session_factory() as session:
        defect = (await session.execute(
            text("SELECT * FROM defects WHERE id = :id"), {"id": int(defect_id)}
        )).mappings().first()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        if defect.get("status") not in [
            DefectStatus.REPLACEMENT_PENDING_CONFIRMATION.value,
            DefectStatus.REPLACEMENT_WAITING_FOR_DEVICE.value
        ]:
            raise ValueError("Enquiry is only allowed for replacement-pending defects")

        old_device = (await session.execute(
            text("SELECT * FROM devices WHERE id = :id"), {"id": int(defect["device_id"])}
        )).mappings().first()
        if not old_device:
            raise ValueError("Original defective device not found")
        old_device = dict(old_device)

        holder_user_id = int(old_device.get("current_holder_id")) if old_device.get("current_holder_id") else None
        reporter_user_id = int(defect.get("reported_by")) if defect.get("reported_by") else None
        allowed_ids = {uid for uid in [holder_user_id, reporter_user_id] if uid is not None}
        if enquirer_id not in allowed_ids:
            raise ValueError("Only the operator involved in this defect can send an enquiry")

        management_rows = (await session.execute(
            text("SELECT id FROM users WHERE role IN ('pdic_staff', 'manager', 'super_admin')")
        )).mappings().all()

    await notification_service.bulk_create_notifications([
        {
            "user_id": r["id"],
            "title": "Replacement Enquiry from Operator",
            "message": f"{enquirer_name} sent an enquiry for {defect.get('report_id')}: {message}",
            "notification_type": "warning",
            "category": "defect",
            "link": "/defects",
            "metadata": {
                "action": "replacement_enquiry",
                "defect_id": str(defect_id),
                "report_id": defect.get("report_id"),
                "message": message,
                "enquirer_id": enquirer_id,
                "enquirer_name": enquirer_name
            }
        }
        for r in management_rows
    ])

    return await get_defect_by_id(defect_id)


async def resend_replacement_confirmation(
    defect_id: str,
    sender: Dict[str, Any]
) -> Dict[str, Any]:
    sender_name = sender.get("name") or "Management"

    async with async_session_factory() as session:
        defect = (await session.execute(
            text("SELECT * FROM defects WHERE id = :id"), {"id": int(defect_id)}
        )).mappings().first()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        if defect.get("status") != DefectStatus.REPLACEMENT_PENDING_CONFIRMATION.value:
            raise ValueError("Resend confirmation is only available for pending confirmation defects")

        old_device = (await session.execute(
            text("SELECT * FROM devices WHERE id = :id"), {"id": int(defect["device_id"])}
        )).mappings().first()
        if not old_device:
            raise ValueError("Original defective device not found")
        old_device = dict(old_device)

        replacement_device = (await session.execute(
            text("SELECT * FROM devices WHERE id = :id"), {"id": int(defect["replacement_device_id"])}
        )).mappings().first()
        if not replacement_device:
            raise ValueError("Replacement device not found")
        replacement_device = dict(replacement_device)

        holder_user_id = int(old_device.get("current_holder_id")) if old_device.get("current_holder_id") else None
        reporter_user_id = int(defect.get("reported_by")) if defect.get("reported_by") else None
        recipient_ids = {uid for uid in [holder_user_id, reporter_user_id] if uid is not None}

    await notification_service.bulk_create_notifications([
        {
            "user_id": rid,
            "title": "Replacement Confirmation Reminder",
            "message": (
                f"{sender_name} resent the confirmation reminder for defect {defect.get('report_id')}. "
                f"Please confirm only after receiving replacement device {replacement_device.get('device_id')} physically."
            ),
            "notification_type": "warning",
            "category": "defect",
            "link": "/replacement-confirmation",
            "metadata": {
                "action": "replacement_confirmation_resent",
                "defect_id": str(defect_id),
                "report_id": defect.get("report_id"),
                "replacement_device_id": str(replacement_device.get("id")),
                "replacement_device_code": replacement_device.get("device_id")
            }
        }
        for rid in recipient_ids
    ])

    return await get_defect_by_id(defect_id)


async def mark_replacement_waiting(
    defect_id: str,
    manager: Dict[str, Any],
    notes: Optional[str] = None
) -> Dict[str, Any]:
    manager_name = manager.get("name") or "Management"

    async with async_session_factory() as session:
        defect = (await session.execute(
            text("SELECT * FROM defects WHERE id = :id"), {"id": int(defect_id)}
        )).mappings().first()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        if defect.get("status") != DefectStatus.REPLACEMENT_PENDING_CONFIRMATION.value:
            raise ValueError("Only pending confirmation defects can be marked as waiting")

        now = datetime.now().replace(tzinfo=None)
        waiting_note = notes or "Device is being shipped, please wait"
        await session.execute(
            text("UPDATE defects SET status = :status, resolution = COALESCE(:note, resolution), updated_at = :now WHERE id = :id"),
            {"status": DefectStatus.REPLACEMENT_WAITING_FOR_DEVICE.value, "note": waiting_note, "now": now, "id": int(defect_id)}
        )
        await bump_cache_version(session)
        await session.commit()

        old_device = (await session.execute(
            text("SELECT * FROM devices WHERE id = :id"), {"id": int(defect["device_id"])}
        )).mappings().first()
        old_device = dict(old_device) if old_device else {}

        holder_user_id = int(old_device.get("current_holder_id")) if old_device.get("current_holder_id") else None
        reporter_user_id = int(defect.get("reported_by")) if defect.get("reported_by") else None
        recipient_ids = {uid for uid in [holder_user_id, reporter_user_id] if uid is not None}

    await notification_service.bulk_create_notifications([
        {
            "user_id": rid,
            "title": "Replacement Shipment In Progress",
            "message": (
                f"Update from {manager_name} on defect {defect.get('report_id')}: "
                "Device is being shipped, please wait"
            ),
            "notification_type": "info",
            "category": "defect",
            "link": "/defects",
            "metadata": {
                "action": "replacement_waiting",
                "defect_id": str(defect_id),
                "report_id": defect.get("report_id"),
                "notes": waiting_note
            }
        }
        for rid in recipient_ids
    ])

    return await get_defect_by_id(defect_id)


async def get_replacement_defects(
    current_user: Dict[str, Any],
    page: int = 1,
    page_size: int = 100,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        conditions = ["replacement_device_id IS NOT NULL"]
        params: Dict[str, Any] = {}

        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date

        scoped_user_ids = await _get_report_scope_user_ids(session, current_user)
        if scoped_user_ids is not None:
            ph = ",".join([f":sr_{i}" for i in range(len(scoped_user_ids))])
            conditions.append(f"CAST(reported_by AS CHAR) IN ({ph})")
            for i, sid in enumerate(scoped_user_ids):
                params[f"sr_{i}"] = sid

        where = " AND ".join(conditions)

        total = (await session.execute(
            text(f"SELECT COUNT(*) FROM defects WHERE {where}"), params
        )).scalar() or 0

        offset = (page - 1) * page_size
        params["_limit"] = page_size
        params["_offset"] = offset
        rows = (await session.execute(
            text(f"SELECT * FROM defects WHERE {where} ORDER BY updated_at DESC LIMIT :_limit OFFSET :_offset"),
            params
        )).mappings().all()
        data = [dict(r) for r in rows]
        data = await _enrich_defect_rows(session, data)

        return {
            "data": data,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_pending_replacement_defects(
    current_user: Dict[str, Any],
    page: int = 1,
    page_size: int = 100
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        conditions = [
            "status = 'approved'",
            "replacement_device_id IS NULL",
        ]
        params: Dict[str, Any] = {}

        scoped_user_ids = await _get_report_scope_user_ids(session, current_user)
        if scoped_user_ids is not None:
            ph = ",".join([f":sr_{i}" for i in range(len(scoped_user_ids))])
            conditions.append(f"CAST(reported_by AS CHAR) IN ({ph})")
            for i, sid in enumerate(scoped_user_ids):
                params[f"sr_{i}"] = sid

        where = " AND ".join(conditions)

        total = (await session.execute(
            text(f"SELECT COUNT(*) FROM defects WHERE {where}"), params
        )).scalar() or 0

        offset = (page - 1) * page_size
        params["_limit"] = page_size
        params["_offset"] = offset
        rows = (await session.execute(
            text(f"SELECT * FROM defects WHERE {where} ORDER BY updated_at DESC LIMIT :_limit OFFSET :_offset"),
            params
        )).mappings().all()
        data = [dict(r) for r in rows]
        data = await _enrich_defect_rows(session, data)

        for defect in data:
            auto_return_status = defect.get("auto_return_status")
            defect["replacement_ready"] = auto_return_status in [None, "received"]

        return {
            "data": data,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_defect_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
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
            text(f"SELECT status, COUNT(*) AS cnt FROM defects WHERE {date_filter} GROUP BY status"),
            params
        )).mappings().all()
        for row in rows:
            status = str(row["status"])
            count = int(row["cnt"])
            total += count
            by_status[status] = count

        by_severity: Dict[str, int] = {}
        rows = (await session.execute(
            text(f"SELECT severity, COUNT(*) AS cnt FROM defects WHERE {date_filter} GROUP BY severity"),
            params
        )).mappings().all()
        for row in rows:
            by_severity[str(row["severity"])] = int(row["cnt"])

        return {
            "total": total,
            "by_status": {
                "reported": by_status.get("reported", 0),
                "under_review": by_status.get("under_review", 0),
                "resolved": by_status.get("resolved", 0),
            },
            "by_severity": {
                "critical": by_severity.get("critical", 0),
                "high": by_severity.get("high", 0),
                "medium": by_severity.get("medium", 0),
                "low": by_severity.get("low", 0),
            }
        }

