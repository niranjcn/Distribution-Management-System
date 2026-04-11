from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
import json

from app.database import get_db, row_to_dict, rows_to_list
from app.models.defect import (
    DefectCreate,
    DefectUpdate,
    DefectStatus,
    DefectSeverity,
    DefectType,
    DefectReportTarget,
)
from app.models.device import DeviceStatus, DeviceCreate
from app.services import approval_service, device_service, notification_service, return_service
from app.utils.helpers import get_pagination, generate_defect_id


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


async def _get_user_role_and_parent(db, user_id: str) -> Optional[Dict[str, Any]]:
    if not user_id or not str(user_id).isdigit():
        return None
    cursor = await db.execute(
        "SELECT id, role, parent_id FROM users WHERE id = ?",
        (int(user_id),)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def _resolve_defect_lineage_ids(
    db,
    reporter_id: str,
    reporter_role: str
) -> Dict[str, Optional[str]]:
    """Resolve operator_id/sub_distributor_id for a defect report."""
    operator_id: Optional[str] = None
    sub_distributor_id: Optional[str] = None

    normalized_role = (reporter_role or "").strip().lower()
    if not normalized_role:
        user_row = await _get_user_role_and_parent(db, reporter_id)
        normalized_role = (user_row.get("role") if user_row else "") or ""

    if normalized_role == "operator":
        operator_id = str(reporter_id)

        # Operator can be directly under sub_distributor or under cluster -> sub_distributor.
        cursor = await db.execute(
            "SELECT id, role, parent_id FROM users WHERE CAST(id AS TEXT) = CAST(? AS TEXT)",
            (str(reporter_id),)
        )
        op_row = await cursor.fetchone()
        if op_row and op_row["parent_id"] is not None:
            parent_id = int(op_row["parent_id"])
            cursor = await db.execute(
                "SELECT id, role, parent_id FROM users WHERE id = ?",
                (parent_id,)
            )
            parent_row = await cursor.fetchone()
            if parent_row:
                if parent_row["role"] == "sub_distributor":
                    sub_distributor_id = str(parent_row["id"])
                elif parent_row["role"] == "cluster" and parent_row["parent_id"] is not None:
                    cursor = await db.execute(
                        "SELECT id FROM users WHERE id = ? AND role = 'sub_distributor'",
                        (int(parent_row["parent_id"]),)
                    )
                    sub_row = await cursor.fetchone()
                    if sub_row:
                        sub_distributor_id = str(sub_row["id"])

    elif normalized_role == "sub_distributor":
        sub_distributor_id = str(reporter_id)

    elif normalized_role == "cluster":
        cursor = await db.execute(
            "SELECT parent_id FROM users WHERE CAST(id AS TEXT) = CAST(? AS TEXT) AND role = 'cluster'",
            (str(reporter_id),)
        )
        row = await cursor.fetchone()
        if row and row["parent_id"] is not None:
            cursor = await db.execute(
                "SELECT id FROM users WHERE id = ? AND role = 'sub_distributor'",
                (int(row["parent_id"]),)
            )
            sub_row = await cursor.fetchone()
            if sub_row:
                sub_distributor_id = str(sub_row["id"])

    return {
        "operator_id": operator_id,
        "sub_distributor_id": sub_distributor_id,
    }


async def _get_sub_distributor_operator_ids(db, sub_distributor_id: str) -> Set[str]:
    """Return operator IDs directly/indirectly under a sub distributor."""
    operator_ids: Set[str] = set()
    cursor = await db.execute(
        """SELECT CAST(id AS TEXT) AS id FROM users
        WHERE role = 'operator' AND (
            CAST(parent_id AS TEXT) = CAST(? AS TEXT)
            OR parent_id IN (
                SELECT id FROM users WHERE role = 'cluster' AND CAST(parent_id AS TEXT) = CAST(? AS TEXT)
            )
        )""",
        (str(sub_distributor_id), str(sub_distributor_id))
    )
    for row in await cursor.fetchall():
        operator_ids.add(str(row["id"]))
    return operator_ids


async def _get_descendant_user_ids(db, root_user_id: str) -> Set[str]:
    """Return all descendant user ids under a root user (recursive by parent_id)."""
    descendants: Set[str] = set()
    if not root_user_id or not str(root_user_id).isdigit():
        return descendants

    pending: List[int] = [int(root_user_id)]
    visited: Set[int] = set()

    while pending:
        current_parent_id = pending.pop()
        if current_parent_id in visited:
            continue
        visited.add(current_parent_id)

        cursor = await db.execute(
            "SELECT id FROM users WHERE parent_id = ?",
            (current_parent_id,)
        )
        rows = await cursor.fetchall()
        for row in rows:
            child_id = int(row["id"])
            child_id_str = str(child_id)
            if child_id_str not in descendants:
                descendants.add(child_id_str)
                pending.append(child_id)

    return descendants


async def _resolve_sub_distributor_targets_for_operator(db, operator_id: str) -> List[str]:
    """Resolve sub distributor recipients for an operator using parent hierarchy."""
    recipients: Set[str] = set()
    cursor = await db.execute(
        "SELECT id, parent_id FROM users WHERE CAST(id AS TEXT) = CAST(? AS TEXT)",
        (str(operator_id),)
    )
    operator_row = await cursor.fetchone()
    if not operator_row:
        return []

    parent_id = operator_row["parent_id"]
    if parent_id is None:
        return []

    cursor = await db.execute("SELECT id, role, parent_id FROM users WHERE id = ?", (int(parent_id),))
    parent_row = await cursor.fetchone()
    if not parent_row:
        return []

    parent_role = parent_row["role"]
    if parent_role == "sub_distributor":
        recipients.add(str(parent_row["id"]))
    elif parent_role == "cluster" and parent_row["parent_id"] is not None:
        cursor = await db.execute(
            "SELECT id FROM users WHERE id = ? AND role = 'sub_distributor'",
            (int(parent_row["parent_id"]),)
        )
        sub_row = await cursor.fetchone()
        if sub_row:
            recipients.add(str(sub_row["id"]))

    return sorted(recipients)


async def _get_report_scope_user_ids(db, user: Dict[str, Any]) -> Optional[Set[str]]:
    role = str(user.get("role") or "").lower()
    user_id = str(user.get("id") or user.get("_id"))
    parent_id = str(user.get("parent_id") or "")

    # Management roles can see all replacement mappings.
    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        return None

    # For hierarchy roles, show own + full branch descendants.
    scope_root = parent_id if role == "sub_distribution_manager" and parent_id.isdigit() else user_id
    scoped_ids: Set[str] = {scope_root}
    descendants = await _get_descendant_user_ids(db, scope_root)
    scoped_ids.update(descendants)
    return scoped_ids


async def _enrich_defect_rows(db, defects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach defective and replacement device details to defect rows."""
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
        placeholders = ",".join(["?"] * len(numeric_device_ids))
        cursor = await db.execute(
            f"SELECT * FROM devices WHERE id IN ({placeholders})",
            tuple(int(device_id) for device_id in numeric_device_ids)
        )
        for row in await cursor.fetchall():
            device = dict(row)
            devices_map[str(device["id"])] = device

    for defect in defects:
        defective_device = devices_map.get(str(defect.get("device_id")))
        replacement_device = devices_map.get(str(defect.get("replacement_device_id"))) if defect.get("replacement_device_id") else None

        defect["defective_device"] = defective_device
        defect["replacement_device"] = replacement_device
        defect["replacement_mapped"] = bool(replacement_device)

        # Keep top-level fields populated for list/report UIs that render direct columns.
        if defective_device:
            if not defect.get("device_serial"):
                defect["device_serial"] = defective_device.get("serial_number")
            if not defect.get("mac_address"):
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

    # Enrich with auto_return_status for replace-button gating
    auto_return_ids = [d.get("auto_return_id") for d in defects if d.get("auto_return_id")]
    if auto_return_ids:
        placeholders = ",".join(["?"] * len(auto_return_ids))
        cursor = await db.execute(
            f"SELECT return_id, status FROM returns WHERE return_id IN ({placeholders})",
            tuple(auto_return_ids)
        )
        return_status_map = {dict(r)["return_id"]: dict(r)["status"] for r in await cursor.fetchall()}
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
    reported_by: Optional[str] = None,
    holder_user_id: Optional[str] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    visibility_user: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Get all defect reports with pagination and filters"""
    async with get_db() as db:
        conditions = ["1=1"]
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if defect_type:
            conditions.append("defect_type = ?")
            params.append(defect_type)
        if reported_by:
            conditions.append("reported_by = ?")
            params.append(str(reported_by))
        if holder_user_id:
            conditions.append(
                "(reported_by = ? OR CAST(device_id AS UNSIGNED) IN (SELECT id FROM devices WHERE current_holder_id = ?))"
            )
            params.extend([str(holder_user_id), str(holder_user_id)])
        if search:
            like = f"%{search}%"
            search_field_map = {
                "report_id": "report_id",
                "device_serial": "device_serial",
                "description": "description",
                "defect_type": "defect_type",
                "severity": "severity",
                "status": "status",
                "reported_by_name": "reported_by_name",
                "device_type": "device_type",
            }
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE ?")
                params.append(like)
            else:
                conditions.append("(report_id LIKE ? OR device_serial LIKE ? OR description LIKE ? OR defect_type LIKE ? OR severity LIKE ? OR status LIKE ? OR reported_by_name LIKE ? OR device_type LIKE ?)")
                params.extend([like, like, like, like, like, like, like, like])

        if visibility_user:
            role = visibility_user.get("role")
            user_id = str(visibility_user.get("id") or visibility_user.get("_id"))
            if role not in ["super_admin", "md_director", "manager", "pdic_staff"]:
                scoped_user_ids = await _get_report_scope_user_ids(db, visibility_user)
                if scoped_user_ids:
                    placeholders = ",".join(["?"] * len(scoped_user_ids))
                    conditions.append(f"CAST(reported_by AS TEXT) IN ({placeholders})")
                    params.extend(sorted(scoped_user_ids))
                else:
                    conditions.append("1=0")

        where = " AND ".join(conditions)

        cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {where}", params)
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"SELECT * FROM defects WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = await cursor.fetchall()
        data = rows_to_list(rows)
        for d in data:
            if isinstance(d.get("images"), str):
                d["images"] = json.loads(d["images"])
        data = await _enrich_defect_rows(db, data)

        return {
            "data": data,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_defect_by_id(defect_id: str) -> Optional[Dict[str, Any]]:
    """Get defect report by ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
        row = await cursor.fetchone()
        if not row:
            return None
        d = row_to_dict(row)
        if isinstance(d.get("images"), str):
            d["images"] = json.loads(d["images"])
        enriched = await _enrich_defect_rows(db, [d])
        if enriched:
            return enriched[0]
        return d


async def create_defect(
    defect_data: DefectCreate,
    reporter: Dict[str, Any],
    sync_device_status: bool = True
) -> Dict[str, Any]:
    """Create a new defect report"""
    reporter_id = str(reporter.get("_id") or reporter.get("id"))
    reporter_name = reporter.get("name") or "System"
    reporter_role = reporter.get("role") or ""
    requested_target = defect_data.report_target.value if defect_data.report_target else None
    report_target = (
        DefectReportTarget.SUB_DISTRIBUTOR.value
        if requested_target == DefectReportTarget.SUB_DISTRIBUTOR.value and reporter_role == "operator"
        else DefectReportTarget.MANAGER_ADMIN.value
    )

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(defect_data.device_id),))
        device = await cursor.fetchone()
        if not device:
            raise ValueError("Device not found")
        device = dict(device)

        # Prevent duplicate active defect reports for the same device
        cursor = await db.execute(
            "SELECT id, report_id, status FROM defects WHERE device_id = ? AND status NOT IN ('resolved', 'rejected') ORDER BY created_at DESC LIMIT 1",
            (defect_data.device_id,)
        )
        existing = await cursor.fetchone()
        if existing:
            existing = dict(existing)
            raise ValueError(
                f"Device already has an active defect report ({existing['report_id']}, status: {existing['status']}). "
                f"A new report can only be submitted after the existing defect is resolved."
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        images_json = json.dumps(defect_data.images or [])
        lineage = await _resolve_defect_lineage_ids(db, reporter_id=reporter_id, reporter_role=reporter_role)

        cursor = await db.execute(
            """INSERT INTO defects (report_id, device_id, device_serial, device_type,
            reported_by, reported_by_name, defect_type, severity, description, symptoms,
            operator_id, sub_distributor_id, report_target, forwarded_to_management, status, resolution, resolved_by,
            resolved_by_name, resolved_at, images, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                generate_defect_id(),
                defect_data.device_id,
                device["serial_number"],
                device["device_type"],
                reporter_id,
                reporter_name,
                defect_data.defect_type.value,
                defect_data.severity.value,
                defect_data.description,
                defect_data.symptoms,
                lineage.get("operator_id"),
                lineage.get("sub_distributor_id"),
                report_target,
                0,
                DefectStatus.REPORTED.value,
                None, None, None, None,
                images_json,
                now, now
            )
        )
        await db.commit()
        new_id = cursor.lastrowid

    # Update device status (also records history internally)
    if sync_device_status:
        await device_service.update_device_status(
            device_id=defect_data.device_id,
            status=DeviceStatus.DEFECTIVE.value,
            performed_by=reporter_id,
            performed_by_name=reporter_name,
            notes=f"Defect reported: {defect_data.defect_type.value} - {defect_data.severity.value}"
        )

    # Notify designated recipients based on report target.
    async with get_db() as db:
        recipient_ids: List[str] = []
        if report_target == DefectReportTarget.SUB_DISTRIBUTOR.value:
            recipient_ids = await _resolve_sub_distributor_targets_for_operator(db, reporter_id)

        if not recipient_ids:
            cursor = await db.execute("SELECT id FROM users WHERE role IN ('super_admin', 'manager', 'pdic_staff')")
            recipient_ids = [str(dict(row)["id"]) for row in await cursor.fetchall()]

        for recipient_id in recipient_ids:
            await notification_service.create_notification(
                user_id=recipient_id,
                title="New Defect Report",
                message=f"A new {defect_data.severity.value} severity defect has been reported for device {device['device_id']}",
                notification_type="warning" if defect_data.severity.value in ["critical", "high"] else "info",
                category="defect",
                link=f"/defects?defectId={new_id}",
                metadata={
                    "action": "new_defect_report",
                    "defect_id": str(new_id),
                    "report_target": report_target
                }
            )

    return await get_defect_by_id(str(new_id))


async def create_or_get_active_defect_for_device(
    device_id: str,
    reporter: Dict[str, Any],
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Ensure there is an active defect report for a defective device.
    Returns existing active report when present, otherwise creates a generic one."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM defects WHERE device_id = ? AND status NOT IN ('resolved', 'rejected') ORDER BY created_at DESC LIMIT 1",
            (str(device_id),)
        )
        existing = await cursor.fetchone()
        if existing:
            return await get_defect_by_id(str(dict(existing)["id"]))

    note_text = (notes or "").strip()
    description = note_text
    if len(description) < 10:
        description = "Device was marked as defective via status update."

    payload = DefectCreate(
        device_id=str(device_id),
        defect_type=DefectType.OTHER,
        severity=DefectSeverity.MEDIUM,
        description=description,
        symptoms=note_text or None,
        images=[]
    )
    return await create_defect(payload, reporter, sync_device_status=False)


async def forward_defect_to_management(
    defect_id: str,
    forwarder: Dict[str, Any],
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Forward a sub-distributor-targeted defect to manager/admin queue."""
    forwarder_role = forwarder.get("role")
    forwarder_id = str(forwarder.get("id") or forwarder.get("_id"))
    forwarder_name = forwarder.get("name") or "Sub Distributor"

    if forwarder_role != "sub_distributor":
        raise ValueError("Only sub distributors can forward defects to manager/admin")

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
        defect = await cursor.fetchone()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        target = defect.get("report_target") or DefectReportTarget.MANAGER_ADMIN.value
        if target != DefectReportTarget.SUB_DISTRIBUTOR.value:
            raise ValueError("This defect is not routed through sub distributor")
        if int(defect.get("forwarded_to_management") or 0) == 1:
            raise ValueError("This defect has already been forwarded to manager/admin")

        operator_ids = await _get_sub_distributor_operator_ids(db, forwarder_id)
        if str(defect.get("reported_by")) not in operator_ids:
            raise ValueError("You can only forward defects reported by operators under your hierarchy")

        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        await db.execute(
            """UPDATE defects
            SET forwarded_to_management = 1,
                forwarded_to_management_at = ?,
                forwarded_to_management_by = ?,
                forwarded_to_management_by_name = ?,
                updated_at = ?
            WHERE id = ?""",
            (now, forwarder_id, forwarder_name, now, int(defect_id))
        )
        await db.commit()

        cursor = await db.execute("SELECT id FROM users WHERE role IN ('super_admin', 'manager', 'pdic_staff')")
        management_users = await cursor.fetchall()

    for row in management_users:
        manager_user_id = str(dict(row)["id"])
        await notification_service.create_notification(
            user_id=manager_user_id,
            title="Defect Forwarded by Sub Distributor",
            message=(
                f"Defect {defect.get('report_id')} was forwarded by {forwarder_name} "
                "for manager/admin review."
            ),
            notification_type="info",
            category="defect",
            link=f"/defects?defectId={defect_id}",
            metadata={
                "action": "forwarded_to_management",
                "defect_id": str(defect_id),
                "notes": notes,
                "forwarded_by": forwarder_name
            }
        )

    if defect.get("reported_by"):
        await notification_service.create_notification(
            user_id=str(defect["reported_by"]),
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
    """Update defect report"""
    update_dict = {k: v for k, v in defect_data.model_dump().items() if v is not None}

    if not update_dict:
        return await get_defect_by_id(defect_id)

    if "defect_type" in update_dict:
        update_dict["defect_type"] = update_dict["defect_type"].value
    if "severity" in update_dict:
        update_dict["severity"] = update_dict["severity"].value
    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value

    update_dict["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    async with get_db() as db:
        set_clause = ", ".join(f"{k} = ?" for k in update_dict)
        values = list(update_dict.values()) + [int(defect_id)]
        cursor = await db.execute(f"UPDATE defects SET {set_clause} WHERE id = ?", values)
        await db.commit()
        if cursor.rowcount > 0:
            return await get_defect_by_id(defect_id)
    return None


async def delete_defect(defect_id: str) -> bool:
    """Delete defect report"""
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM defects WHERE id = ?", (int(defect_id),))
        await db.commit()
        return cursor.rowcount > 0


async def update_defect_status(
    defect_id: str,
    status: str,
    user: Dict[str, Any],
    notes: Optional[str] = None,
    return_amount: Optional[float] = None,
    payment_bill_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update defect status. When approved, automatically creates a return request."""
    user_role = str(user.get("role", "")).lower()
    if status in {DefectStatus.APPROVED.value, DefectStatus.REJECTED.value} and user_role in {"super_admin", "manager", "pdic_staff"}:
        allowed = await approval_service.is_role_allowed_for_approval_type(user_role, "defect")
        if not allowed:
            raise PermissionError(f"{user_role.capitalize()} role is not allowed to process defect approvals")

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
        defect = await cursor.fetchone()
        if not defect:
            return None
        defect = dict(defect)

        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        update_sql = "UPDATE defects SET status = ?, updated_at = ?"
        update_params: List[Any] = [status, now]

        if status == DefectStatus.APPROVED.value:
            amount = float(return_amount) if return_amount is not None else float(defect.get("return_amount") or 0)
            update_sql += ", return_amount = ?, payment_due_user_id = ?, payment_due_user_name = ?, payment_confirmed = 0"
            update_params.extend([
                amount,
                str(defect.get("reported_by") or ""),
                str(defect.get("reported_by_name") or "Unknown"),
            ])
            if payment_bill_url:
                update_sql += ", payment_bill_url = ?"
                update_params.append(payment_bill_url)

        update_sql += " WHERE id = ?"
        update_params.append(int(defect_id))

        cursor = await db.execute(update_sql, update_params)
        await db.commit()
        affected = cursor.rowcount

    if affected > 0:
        extra_msg = ""
        if status == DefectStatus.APPROVED.value:
            await device_service.update_device_status(
                device_id=defect["device_id"],
                status=DeviceStatus.DEFECTIVE.value,
                performed_by=str(user.get("_id") or user.get("id")),
                performed_by_name=user.get("name", "Unknown"),
                notes=f"Defect report {defect.get('report_id', defect_id)} approved"
            )
            try:
                auto_return = await return_service.auto_create_defect_return(
                    device_id=defect["device_id"],
                    defect_id=defect_id,
                    defect_report_id=defect["report_id"],
                    requester_id=defect["reported_by"],
                    requester_name=defect["reported_by_name"]
                )
                if auto_return:
                    async with get_db() as db:
                        await db.execute(
                            "UPDATE defects SET auto_return_id = ? WHERE id = ?",
                            (auto_return["return_id"], int(defect_id))
                        )
                        await db.commit()
                    extra_msg = f" A return request ({auto_return['return_id']}) has been automatically created."
            except Exception:
                pass  # Don't fail status update if auto-return creation fails

        # Notify the reporter
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

        # Notify only enabled return approval roles when approved so they can confirm receipt.
        if status == DefectStatus.APPROVED.value:
            enabled_roles = await approval_service.get_routing_enabled_roles_for_approval_type("return")
            if not enabled_roles:
                enabled_roles = ["super_admin"]
            role_placeholders = ", ".join(["?"] * len(enabled_roles))
            async with get_db() as db:
                cursor = await db.execute(
                    f"SELECT id FROM users WHERE role IN ({role_placeholders})",
                    enabled_roles,
                )
                staff_rows = await cursor.fetchall()
            for row in staff_rows:
                row = dict(row)
                if str(row["id"]) != defect["reported_by"]:
                    await notification_service.create_notification(
                        user_id=str(row["id"]),
                        title="Defective Device Return — Pending Receipt",
                        message=(
                            f"Defect {defect['report_id']} approved. The operator has been instructed to return "
                            f"device to PDIC. Please confirm receipt when device arrives."
                        ),
                        notification_type="info",
                        category="return",
                        link=f"/returns"
                    )

        return await get_defect_by_id(defect_id)
    return None


async def set_defect_payment_bill_url(defect_id: str, bill_url: str) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE defects SET payment_bill_url = ?, updated_at = ? WHERE id = ?",
            (bill_url, now, int(defect_id))
        )
        await db.commit()
        if cursor.rowcount <= 0:
            return None
    return await get_defect_by_id(defect_id)


async def confirm_defect_payment(
    defect_id: str,
    confirmer: Dict[str, Any],
    notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    confirmer_id = str(confirmer.get("_id") or confirmer.get("id") or "")
    confirmer_name = str(confirmer.get("name") or "Management")

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
        defect_row = await cursor.fetchone()
        if not defect_row:
            return None
        defect = dict(defect_row)

        amount = float(defect.get("return_amount") or 0)
        if amount <= 0:
            raise ValueError("No payment amount is configured for this defect")
        if int(defect.get("payment_confirmed") or 0) == 1:
            raise ValueError("Payment has already been confirmed for this defect")

        # Payment confirmation is only valid once defective return has reached PDIC.
        return_id = defect.get("auto_return_id")
        if return_id:
            cursor = await db.execute("SELECT status FROM returns WHERE return_id = ?", (return_id,))
            return_row = await cursor.fetchone()
            if return_row and str(dict(return_row).get("status") or "") != "received":
                raise ValueError("Cannot confirm payment before defective device is marked received at PDIC")

        await db.execute(
            """UPDATE defects
            SET payment_confirmed = 1,
                payment_confirmed_at = ?,
                payment_confirmed_by = ?,
                payment_confirmed_by_name = ?,
                updated_at = ?
            WHERE id = ?""",
            (now, confirmer_id, confirmer_name, now, int(defect_id))
        )
        await db.commit()

    due_user_id = str(defect.get("payment_due_user_id") or defect.get("reported_by") or "")
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
    async with get_db() as db:
        scope_user_ids = await _get_report_scope_user_ids(db, current_user) if current_user else None
        if scope_user_ids is not None and len(scope_user_ids) == 0:
            return []

        conditions = [
            "COALESCE(d.return_amount, 0) > 0",
            "COALESCE(d.payment_confirmed, 0) = 0",
            "COALESCE(r.status, '') = 'received'",
        ]
        params: List[Any] = []

        if scope_user_ids is not None:
            placeholders = ",".join(["?"] * len(scope_user_ids))
            conditions.append(
                f"COALESCE(NULLIF(d.payment_due_user_id, ''), d.reported_by) IN ({placeholders})"
            )
            params.extend(sorted(scope_user_ids))

        where_clause = " AND ".join(conditions)

        cursor = await db.execute(
            f"""
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
            LEFT JOIN users due ON due.id = CAST(COALESCE(NULLIF(d.payment_due_user_id, ''), d.reported_by) AS UNSIGNED)
            LEFT JOIN users parent ON parent.id = due.parent_id
            WHERE {where_clause}
            GROUP BY due.id,
                     COALESCE(NULLIF(d.payment_due_user_name, ''), d.reported_by_name, due.name),
                     due.role,
                     due.parent_id,
                     parent.name
            ORDER BY total_due DESC, due_count DESC
            """,
            params,
        )
        rows = await cursor.fetchall()
        return rows_to_list(rows)


async def get_pending_dues_for_user(user_id: str, current_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    async with get_db() as db:
        scope_user_ids = await _get_report_scope_user_ids(db, current_user) if current_user else None
        requested_user_id = str(user_id)
        if scope_user_ids is not None and requested_user_id not in scope_user_ids:
            raise PermissionError("Requested user is outside your hierarchy scope")

        cursor = await db.execute(
            """
            SELECT
                d.id,
                d.report_id,
                d.device_id,
                d.device_serial,
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
            WHERE COALESCE(NULLIF(d.payment_due_user_id, ''), d.reported_by) = ?
              AND COALESCE(d.return_amount, 0) > 0
              AND COALESCE(d.payment_confirmed, 0) = 0
              AND COALESCE(r.status, '') = 'received'
            ORDER BY r.received_date DESC, d.updated_at DESC
            """,
            (requested_user_id,)
        )
        rows = await cursor.fetchall()
        dues = rows_to_list(rows)

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
    """Resolve a defect report"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
        defect = await cursor.fetchone()
        if not defect:
            return None
        defect = dict(defect)

        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        cursor = await db.execute(
            """UPDATE defects SET status = ?, resolution = ?, resolved_by = ?,
            resolved_by_name = ?, resolved_at = ?, updated_at = ? WHERE id = ?""",
            (DefectStatus.RESOLVED.value, resolution, str(resolver["_id"]),
             resolver["name"], now, now, int(defect_id))
        )
        await db.commit()

        if cursor.rowcount > 0:
            await device_service.update_device_status(
                device_id=defect["device_id"],
                status=DeviceStatus.MAINTENANCE.value,
                performed_by=str(resolver["_id"]),
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
    service_charge: Optional[float],
    payment_bill_url: Optional[str],
    resolver: Dict[str, Any]
) -> Dict[str, Any]:
    """Replace a defective device by selecting existing stock or registering a new device."""
    resolver_id = str(resolver.get("_id") or resolver.get("id"))
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

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
        defect = await cursor.fetchone()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        # Gate: defect must be in 'approved' status before replacement can proceed
        if defect.get("status") != DefectStatus.APPROVED.value:
            raise ValueError(
                f"Cannot replace device — defect must be in 'approved' status. "
                f"Current status: {defect.get('status')}"
            )

        # Gate: the linked return must be received at PDIC first
        auto_return_id = defect.get("auto_return_id")
        if auto_return_id:
            cursor = await db.execute(
                "SELECT status FROM returns WHERE return_id = ?", (auto_return_id,)
            )
            ret_row = await cursor.fetchone()
            if ret_row and dict(ret_row).get("status") != "received":
                raise ValueError(
                    "Cannot replace device — the defective device must be returned and received "
                    "at PDIC first. Please confirm return receipt before replacing."
                )

        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(defect["device_id"]),))
        old_device = await cursor.fetchone()
        if not old_device:
            raise ValueError("Original defective device not found")
        old_device = dict(old_device)

        new_device = None
        if replacement_device_id:
            cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(replacement_device_id),))
            new_device = await cursor.fetchone()
            if not new_device:
                raise ValueError("Selected replacement device was not found")
            new_device = dict(new_device)
        elif pre_created_device:
            new_device = pre_created_device
        elif mac_address:
            cursor = await db.execute("SELECT * FROM devices WHERE mac_address = ?", (mac_address,))
            new_device = await cursor.fetchone()
        elif serial_number:
            cursor = await db.execute("SELECT * FROM devices WHERE serial_number = ?", (serial_number,))
            new_device = await cursor.fetchone()
        else:
            raise ValueError("Replacement target not provided")

        if not new_device:
            raise ValueError("Replacement device not found in system")
        if not isinstance(new_device, dict):
            new_device = dict(new_device)

        is_same_device_reassignment = str(new_device["id"]) == str(old_device["id"])

        effective_return_amount = return_amount
        if is_same_device_reassignment and service_charge is not None:
            base_due = float(return_amount) if return_amount is not None else 0.0
            effective_return_amount = base_due + float(service_charge)

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
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        update_sql = (
            """UPDATE defects SET status = ?, replacement_device_id = ?, replacement_requested_at = ?,
            resolution = ?, resolved_by = ?, resolved_by_name = ?, resolved_at = ?, updated_at = ?"""
        )
        update_params: List[Any] = [
            DefectStatus.REPLACEMENT_PENDING_CONFIRMATION.value,
            str(new_device["id"]),
            now,
            resolution_note,
            None,
            None,
            None,
            now,
        ]

        if effective_return_amount is not None:
            update_sql += ", return_amount = ?, payment_due_user_id = ?, payment_due_user_name = ?, payment_confirmed = 0"
            update_params.extend([
                float(effective_return_amount),
                str(defect.get("reported_by") or ""),
                str(defect.get("reported_by_name") or "Unknown"),
            ])

        if service_charge is not None:
            update_sql += ", service_charge = ?"
            update_params.append(float(service_charge))

        if payment_bill_url:
            update_sql += ", payment_bill_url = ?"
            update_params.append(str(payment_bill_url))

        update_sql += " WHERE id = ?"
        update_params.append(int(defect_id))

        await db.execute(update_sql, update_params)
        await db.commit()

    if not is_same_device_reassignment:
        old_device_metadata = _parse_json_metadata(old_device.get("metadata"))
        old_device_metadata["replaced_by"] = {
            "device_id": str(new_device.get("id")),
            "device_code": new_device.get("device_id"),
            "serial_number": new_device.get("serial_number"),
            "defect_id": str(defect_id),
            "defect_report_id": defect.get("report_id"),
            "replaced_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "replaced_by_user_id": resolver_id,
            "replaced_by_user_name": resolver_name
        }
        async with get_db() as db:
            await db.execute(
                "UPDATE devices SET metadata = ?, updated_at = ? WHERE id = ?",
                (json.dumps(old_device_metadata), datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), int(old_device["id"]))
            )
            await db.commit()

    # If the same device is serviced and reassigned, keep it in maintenance until user confirms receipt.
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

    holder_user_id = str(original_holder_id) if original_holder_id else None
    holder_user_name = original_holder_name or defect.get("reported_by_name") or "Operator"

    recipient_ids = set()
    if holder_user_id:
        recipient_ids.add(holder_user_id)
    if defect.get("reported_by"):
        recipient_ids.add(str(defect["reported_by"]))

    for recipient_id in recipient_ids:
        await notification_service.create_notification(
            user_id=recipient_id,
            title="Serviced Device Ready - Confirmation Required" if is_same_device_reassignment else "Replacement Device Ready - Confirmation Required",
            message=(
                f"Operator update for {holder_user_name}: "
                f"{'serviced device' if is_same_device_reassignment else 'replacement device'} {new_device.get('device_id')} "
                f"(Serial: {new_device.get('serial_number')}) is prepared for defect {defect['report_id']}. "
                "Confirm only after you physically receive the replacement device. "
                "Do not confirm before receiving it."
            ),
            notification_type="warning",
            category="defect",
            link="/replacement-confirmation"
        )

    return await get_defect_by_id(defect_id)


async def confirm_replacement_receipt(
    defect_id: str,
    confirmer: Dict[str, Any],
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Defect reporter/current holder confirms replacement receipt; replacement is assigned to confirmer account."""
    confirmer_id = str(confirmer.get("_id") or confirmer.get("id"))
    confirmer_name = confirmer.get("name") or "Operator"
    confirmer_role = str(confirmer.get("role") or "operator")

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
        defect = await cursor.fetchone()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        if defect.get("status") != DefectStatus.REPLACEMENT_PENDING_CONFIRMATION.value:
            raise ValueError("Replacement confirmation is not pending for this defect")

        replacement_device_id = defect.get("replacement_device_id")
        if not replacement_device_id:
            raise ValueError("No replacement device is linked to this defect")

        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(defect["device_id"]),))
        old_device = await cursor.fetchone()
        if not old_device:
            raise ValueError("Original defective device not found")
        old_device = dict(old_device)

        holder_user_id = str(old_device.get("current_holder_id")) if old_device.get("current_holder_id") else None
        reporter_user_id = str(defect.get("reported_by")) if defect.get("reported_by") else None
        allowed_confirmer_ids = {uid for uid in [holder_user_id, reporter_user_id] if uid}
        if confirmer_id not in allowed_confirmer_ids:
            raise ValueError("Only the current holder or original defect reporter can confirm replacement receipt")

        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(replacement_device_id),))
        new_device = await cursor.fetchone()
        if not new_device:
            raise ValueError("Replacement device not found")
        new_device = dict(new_device)

        is_same_device_reassignment = str(new_device.get("id")) == str(old_device.get("id"))

        if (not is_same_device_reassignment) and new_device.get("status") not in [DeviceStatus.AVAILABLE.value, DeviceStatus.RETURNED.value]:
            raise ValueError(
                f"Replacement device is not available for confirmation. Current status: {new_device.get('status')}"
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        await db.execute(
            """UPDATE defects SET status = ?, replacement_confirmed_at = ?, replacement_confirmed_by = ?,
            replacement_confirmed_by_name = ?, resolved_by = ?, resolved_by_name = ?, resolved_at = ?,
            updated_at = ?, resolution = COALESCE(?, resolution)
            WHERE id = ?""",
            (
                DefectStatus.RESOLVED.value,
                now,
                confirmer_id,
                confirmer_name,
                confirmer_id,
                confirmer_name,
                now,
                now,
                notes,
                int(defect_id)
            )
        )
        await db.commit()

    # Assign replacement device to the confirming user account (not stale holder data)
    updated_device = await device_service.update_device_holder(
        device_id=str(new_device["id"]),
        holder_id=confirmer_id,
        holder_name=confirmer_name,
        holder_type=confirmer_role,
        location=confirmer_name,
        status=DeviceStatus.IN_USE.value,
        performed_by=confirmer_id,
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

    # Notify management that receipt was confirmed
    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM users WHERE role IN ('super_admin', 'manager', 'pdic_staff')")
        recipients = await cursor.fetchall()

    for row in recipients:
        row = dict(row)
        await notification_service.create_notification(
            user_id=str(row["id"]),
            title="Replacement Receipt Confirmed",
            message=(
                f"{confirmer_name} ({confirmer_role.replace('_', ' ')}) confirmed receipt of replacement device "
                f"for defect {defect.get('report_id')}."
            ),
            notification_type="success",
            category="defect",
            link="/defects"
        )

    return await get_defect_by_id(defect_id)


async def enquire_replacement_status(
    defect_id: str,
    enquirer: Dict[str, Any],
    message: str
) -> Dict[str, Any]:
    """Operator sends an enquiry about replacement status to management roles."""
    enquirer_id = str(enquirer.get("_id") or enquirer.get("id"))
    enquirer_name = enquirer.get("name") or "Operator"

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
        defect = await cursor.fetchone()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        if defect.get("status") not in [
            DefectStatus.REPLACEMENT_PENDING_CONFIRMATION.value,
            DefectStatus.REPLACEMENT_WAITING_FOR_DEVICE.value
        ]:
            raise ValueError("Enquiry is only allowed for replacement-pending defects")

        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(defect["device_id"]),))
        old_device = await cursor.fetchone()
        if not old_device:
            raise ValueError("Original defective device not found")
        old_device = dict(old_device)

        holder_user_id = str(old_device.get("current_holder_id")) if old_device.get("current_holder_id") else None
        reporter_user_id = str(defect.get("reported_by")) if defect.get("reported_by") else None
        allowed_ids = {uid for uid in [holder_user_id, reporter_user_id] if uid}
        if enquirer_id not in allowed_ids:
            raise ValueError("Only the operator involved in this defect can send an enquiry")

        cursor = await db.execute("SELECT id FROM users WHERE role IN ('pdic_staff', 'manager', 'super_admin')")
        management_users = await cursor.fetchall()

    for manager_row in management_users:
        manager_user_id = str(dict(manager_row)["id"])
        await notification_service.create_notification(
            user_id=manager_user_id,
            title="Replacement Enquiry from Operator",
            message=(
                f"{enquirer_name} sent an enquiry for {defect.get('report_id')}: {message}"
            ),
            notification_type="warning",
            category="defect",
            link="/defects",
            metadata={
                "action": "replacement_enquiry",
                "defect_id": str(defect_id),
                "report_id": defect.get("report_id"),
                "message": message,
                "enquirer_id": enquirer_id,
                "enquirer_name": enquirer_name
            }
        )

    return await get_defect_by_id(defect_id)


async def resend_replacement_confirmation(
    defect_id: str,
    sender: Dict[str, Any]
) -> Dict[str, Any]:
    """Resend replacement confirmation notification to operator/reporter."""
    sender_name = sender.get("name") or "Management"

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
        defect = await cursor.fetchone()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        if defect.get("status") != DefectStatus.REPLACEMENT_PENDING_CONFIRMATION.value:
            raise ValueError("Resend confirmation is only available for pending confirmation defects")

        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(defect["device_id"]),))
        old_device = await cursor.fetchone()
        if not old_device:
            raise ValueError("Original defective device not found")
        old_device = dict(old_device)

        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(defect["replacement_device_id"]),))
        replacement_device = await cursor.fetchone()
        if not replacement_device:
            raise ValueError("Replacement device not found")
        replacement_device = dict(replacement_device)

        holder_user_id = str(old_device.get("current_holder_id")) if old_device.get("current_holder_id") else None
        reporter_user_id = str(defect.get("reported_by")) if defect.get("reported_by") else None
        recipient_ids = {uid for uid in [holder_user_id, reporter_user_id] if uid}

    for recipient_id in recipient_ids:
        await notification_service.create_notification(
            user_id=recipient_id,
            title="Replacement Confirmation Reminder",
            message=(
                f"{sender_name} resent the confirmation reminder for defect {defect.get('report_id')}. "
                f"Please confirm only after receiving replacement device {replacement_device.get('device_id')} physically."
            ),
            notification_type="warning",
            category="defect",
            link="/replacement-confirmation",
            metadata={
                "action": "replacement_confirmation_resent",
                "defect_id": str(defect_id),
                "report_id": defect.get("report_id"),
                "replacement_device_id": str(replacement_device.get("id")),
                "replacement_device_code": replacement_device.get("device_id")
            }
        )

    return await get_defect_by_id(defect_id)


async def mark_replacement_waiting(
    defect_id: str,
    manager: Dict[str, Any],
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Mark replacement status as waiting for shipment from PDIC."""
    manager_name = manager.get("name") or "Management"

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM defects WHERE id = ?", (int(defect_id),))
        defect = await cursor.fetchone()
        if not defect:
            raise ValueError("Defect report not found")
        defect = dict(defect)

        if defect.get("status") != DefectStatus.REPLACEMENT_PENDING_CONFIRMATION.value:
            raise ValueError("Only pending confirmation defects can be marked as waiting")

        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        waiting_note = notes or "Device is being shipped, please wait"
        await db.execute(
            "UPDATE defects SET status = ?, resolution = COALESCE(?, resolution), updated_at = ? WHERE id = ?",
            (
                DefectStatus.REPLACEMENT_WAITING_FOR_DEVICE.value,
                waiting_note,
                now,
                int(defect_id)
            )
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(defect["device_id"]),))
        old_device = await cursor.fetchone()
        old_device = dict(old_device) if old_device else {}

        holder_user_id = str(old_device.get("current_holder_id")) if old_device.get("current_holder_id") else None
        reporter_user_id = str(defect.get("reported_by")) if defect.get("reported_by") else None
        recipient_ids = {uid for uid in [holder_user_id, reporter_user_id] if uid}

    for recipient_id in recipient_ids:
        await notification_service.create_notification(
            user_id=recipient_id,
            title="Replacement Shipment In Progress",
            message=(
                f"Update from {manager_name} on defect {defect.get('report_id')}: "
                "Device is being shipped, please wait"
            ),
            notification_type="info",
            category="defect",
            link="/defects",
            metadata={
                "action": "replacement_waiting",
                "defect_id": str(defect_id),
                "report_id": defect.get("report_id"),
                "notes": waiting_note
            }
        )

    return await get_defect_by_id(defect_id)


async def get_replacement_defects(
    current_user: Dict[str, Any],
    page: int = 1,
    page_size: int = 100
) -> Dict[str, Any]:
    """Return defects that have replacement mapping with hierarchy-aware scope."""
    async with get_db() as db:
        conditions = ["replacement_device_id IS NOT NULL"]
        params: List[Any] = []

        scoped_user_ids = await _get_report_scope_user_ids(db, current_user)
        if scoped_user_ids is not None:
            placeholders = ",".join(["?"] * len(scoped_user_ids))
            conditions.append(f"CAST(reported_by AS TEXT) IN ({placeholders})")
            params.extend(list(scoped_user_ids))

        where = " AND ".join(conditions)

        cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {where}", params)
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"SELECT * FROM defects WHERE {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = await cursor.fetchall()
        data = rows_to_list(rows)
        data = await _enrich_defect_rows(db, data)

        return {
            "data": data,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_pending_replacement_defects(
    current_user: Dict[str, Any],
    page: int = 1,
    page_size: int = 100
) -> Dict[str, Any]:
    """Return defective devices awaiting replacement assignment."""
    async with get_db() as db:
        conditions = [
            "status = 'approved'",
            "replacement_device_id IS NULL",
        ]
        params: List[Any] = []

        scoped_user_ids = await _get_report_scope_user_ids(db, current_user)
        if scoped_user_ids is not None:
            placeholders = ",".join(["?"] * len(scoped_user_ids))
            conditions.append(f"CAST(reported_by AS TEXT) IN ({placeholders})")
            params.extend(list(scoped_user_ids))

        where = " AND ".join(conditions)

        cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {where}", params)
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"SELECT * FROM defects WHERE {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = await cursor.fetchall()
        data = rows_to_list(rows)
        data = await _enrich_defect_rows(db, data)

        # Annotate whether defect is ready for immediate replacement assignment.
        for defect in data:
            auto_return_status = defect.get("auto_return_status")
            defect["replacement_ready"] = auto_return_status in [None, "received"]

        return {
            "data": data,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_defect_stats() -> Dict[str, Any]:
    """Get defect statistics"""
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM defects")
        total = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM defects WHERE status = 'reported'")
        reported = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM defects WHERE status = 'under_review'")
        under_review = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM defects WHERE status = 'resolved'")
        resolved = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM defects WHERE severity = 'critical'")
        critical = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM defects WHERE severity = 'high'")
        high = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM defects WHERE severity = 'medium'")
        medium = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM defects WHERE severity = 'low'")
        low = (await cursor.fetchone())[0]

        return {
            "total": total,
            "by_status": {
                "reported": reported,
                "under_review": under_review,
                "resolved": resolved
            },
            "by_severity": {
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low
            }
        }

