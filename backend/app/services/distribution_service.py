from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
import json
import io
from pathlib import Path

from openpyxl import Workbook

from app.database import get_db, row_to_dict, rows_to_list
from app.models.distribution import DistributionCreate, DistributionStatus
from app.models.device import DeviceStatus
from app.services import approval_service, device_service, notification_service
from app.utils.helpers import get_pagination, generate_distribution_id


def _distribution_manifest_dir() -> Path:
    """Directory for generated distribution Excel manifests."""
    manifests_dir = Path(__file__).resolve().parents[2] / "distribution_manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    return manifests_dir


def _build_distribution_manifest(
    distribution_id: str,
    devices: List[Dict[str, Any]],
    from_user_name: str,
    to_user_name: str,
    created_at_iso: str,
) -> str:
    """Create an Excel manifest listing all devices in the distribution."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Device Manifest"

    sheet.append(["Distribution ID", distribution_id])
    sheet.append(["From", from_user_name])
    sheet.append(["To", to_user_name])
    sheet.append(["Created At", created_at_iso])
    sheet.append(["Total Devices", len(devices)])
    sheet.append([])
    sheet.append([
        "#",
        "Device ID",
        "Serial Number",
        "MAC Address",
        "Manufacturer",
        "Model",
        "Device Type",
        "Status",
    ])

    for idx, device in enumerate(devices, start=1):
        sheet.append([
            idx,
            device.get("device_id") or "",
            device.get("serial_number") or "",
            device.get("mac_address") or "",
            device.get("manufacturer") or "",
            device.get("model") or "",
            device.get("device_type") or "",
            device.get("status") or "",
        ])

    file_name = f"{distribution_id}-devices.xlsx"
    file_path = _distribution_manifest_dir() / file_name
    workbook.save(file_path)
    return file_name


def _build_distribution_mac_nuid_file(
    distribution_code: str,
    devices: List[Dict[str, Any]],
    file_format: str = "csv",
) -> Dict[str, Any]:
    """Build export containing serial_number, mac_address, and nuid for a distribution."""
    normalized = str(file_format or "csv").strip().lower()
    if normalized not in {"csv", "xlsx"}:
        raise ValueError("Unsupported export format. Use 'csv' or 'xlsx'")

    rows = [
        {
            "serial_number": str(device.get("serial_number") or "").strip(),
            "mac_address": str(device.get("mac_address") or "").strip(),
            "nuid": str(device.get("nuid") or "").strip(),
        }
        for device in devices
    ]

    if normalized == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "DEVICE_IDENTIFIERS"
        sheet.append(["serial_number", "mac_address", "nuid"])
        for row in rows:
            sheet.append([row["serial_number"], row["mac_address"], row["nuid"]])

        payload = io.BytesIO()
        workbook.save(payload)
        payload.seek(0)
        return {
            "content": payload.getvalue(),
            "filename": f"{distribution_code}-mac-nuid.xlsx",
            "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

    content = "serial_number,mac_address,nuid\n" + "\n".join(
        f"{row['serial_number']},{row['mac_address']},{row['nuid']}" for row in rows
    )
    return {
        "content": content.encode("utf-8"),
        "filename": f"{distribution_code}-mac-nuid.csv",
        "media_type": "text/csv",
    }


def _sender_display_name(user: Dict[str, Any]) -> str:
    role = str(user.get("role") or "").strip().lower()
    if role in {"super_admin", "manager", "pdic_staff"}:
        return "PDIC"
    return str(user.get("name") or "Unknown")


async def _device_has_open_distribution_lock(db, device_id: str) -> bool:
    cursor = await db.execute(
        "SELECT device_ids FROM distributions WHERE status IN (?, ?)",
        (DistributionStatus.PENDING_RECEIPT.value, DistributionStatus.DISPUTED.value),
    )
    rows = await cursor.fetchall()
    target = str(device_id)
    for row in rows:
        try:
            device_ids = [str(x) for x in json.loads(row[0] or "[]")]
        except (json.JSONDecodeError, TypeError):
            device_ids = []
        if target in device_ids:
            return True
    return False


async def _get_descendant_user_ids(db, root_user_id: str) -> Set[str]:
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


async def _get_distribution_scope_user_ids(db, user: Dict[str, Any]) -> Optional[Set[str]]:
    role = str(user.get("role") or "")
    user_id = str(user.get("id") or user.get("_id") or "")
    parent_id = str(user.get("parent_id") or "")

    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        return None

    scope_root = parent_id if role == "sub_distribution_manager" and parent_id.isdigit() else user_id
    scoped_ids: Set[str] = {scope_root}
    scoped_ids.update(await _get_descendant_user_ids(db, scope_root))
    return scoped_ids


async def get_distributions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    from_user_id: Optional[str] = None,
    to_user_id: Optional[str] = None,
    user_id: Optional[str] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    current_user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get all distributions with pagination and filters"""
    async with get_db() as db:
        conditions = []
        params = []
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        if from_user_id:
            conditions.append("from_user_id = ?")
            params.append(from_user_id)
        if to_user_id:
            conditions.append("to_user_id = ?")
            params.append(to_user_id)

        scope_ids = await _get_distribution_scope_user_ids(db, current_user) if current_user else None
        if scope_ids is not None:
            if not scope_ids:
                return {"data": [], "pagination": get_pagination(page, page_size, 0)}
            scope_list = sorted(scope_ids)
            placeholders = ",".join(["?"] * len(scope_list))
            conditions.append(f"(from_user_id IN ({placeholders}) OR to_user_id IN ({placeholders}))")
            params.extend(scope_list)
            params.extend(scope_list)
        elif user_id:
            conditions.append("(from_user_id = ? OR to_user_id = ?)")
            params.extend([user_id, user_id])
        if search:
            like = f"%{search}%"
            search_field_map = {
                "distribution_id": "distribution_id",
                "from_user_name": "from_user_name",
                "to_user_name": "to_user_name",
                "status": "status",
                "approved_by_name": "approved_by_name",
            }
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE ?")
                params.append(like)
            else:
                conditions.append("(distribution_id LIKE ? OR from_user_name LIKE ? OR to_user_name LIKE ? OR status LIKE ? OR approved_by_name LIKE ?)")
                params.extend([like, like, like, like, like])
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {where_clause}", params)
        total = (await cursor.fetchone())[0]
        
        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"SELECT * FROM distributions WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = await cursor.fetchall()
        
        result = []
        for r in rows_to_list(rows):
            if r.get("device_ids"):
                try:
                    r["device_ids"] = json.loads(r["device_ids"])
                except (json.JSONDecodeError, TypeError):
                    r["device_ids"] = []
            result.append(r)
        
        return {
            "data": result,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_distribution_by_id(distribution_id: str) -> Optional[Dict[str, Any]]:
    """Get distribution by ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM distributions WHERE id = ?", (int(distribution_id),))
        row = await cursor.fetchone()
        if row:
            d = row_to_dict(row)
            if d.get("device_ids"):
                try:
                    d["device_ids"] = json.loads(d["device_ids"])
                except (json.JSONDecodeError, TypeError):
                    d["device_ids"] = []
            return d
        return None


async def create_distribution_from_identifiers(
    to_user_id: str,
    identifier_rows: List[Dict[str, Any]],
    from_user: Dict[str, Any],
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a distribution from uploaded rows containing MAC, serial number, and/or NUID.

    If any row fails validation, distribution is not created and row-level errors are returned.
    """
    errors: List[Dict[str, Any]] = []
    resolved_device_ids: List[str] = []
    seen_device_ids = set()

    async with get_db() as db:
        for row in identifier_rows:
            row_number = int(row.get("row") or 0)
            mac_address = str(row.get("mac_address") or "").strip()
            serial_number = str(row.get("serial_number") or "").strip()
            nuid = str(row.get("nuid") or "").strip()

            if not mac_address and not serial_number and not nuid:
                errors.append({
                    "row": row_number,
                    "identifier": "",
                    "error": "Provide at least one identifier: mac_address, serial_number, or nuid",
                })
                continue

            device_by_mac = None
            device_by_serial = None
            device_by_nuid = None

            if mac_address:
                cursor = await db.execute(
                    "SELECT * FROM devices WHERE lower(trim(mac_address)) = lower(trim(?))",
                    (mac_address,),
                )
                row_mac = await cursor.fetchone()
                if row_mac:
                    device_by_mac = row_to_dict(row_mac)

            if nuid:
                cursor = await db.execute(
                    "SELECT * FROM devices WHERE lower(trim(nuid)) = lower(trim(?))",
                    (nuid,),
                )
                row_nuid = await cursor.fetchone()
                if row_nuid:
                    device_by_nuid = row_to_dict(row_nuid)

            if serial_number:
                cursor = await db.execute(
                    "SELECT * FROM devices WHERE lower(trim(serial_number)) = lower(trim(?))",
                    (serial_number,),
                )
                row_serial = await cursor.fetchone()
                if row_serial:
                    device_by_serial = row_to_dict(row_serial)

            resolved_candidates = [d for d in [device_by_mac, device_by_serial, device_by_nuid] if d]
            if resolved_candidates:
                first_id = str(resolved_candidates[0].get("id"))
                if any(str(d.get("id")) != first_id for d in resolved_candidates[1:]):
                    parts = []
                    if mac_address:
                        parts.append(f"MAC={mac_address}")
                    if serial_number:
                        parts.append(f"SERIAL={serial_number}")
                    if nuid:
                        parts.append(f"NUID={nuid}")
                    errors.append({
                        "row": row_number,
                        "identifier": ", ".join(parts),
                        "error": "Provided identifiers map to different devices",
                    })
                    continue

            resolved_device = device_by_mac or device_by_serial or device_by_nuid

            if not resolved_device:
                identifier_value = mac_address or serial_number or nuid
                if mac_address:
                    identifier_label = "mac_address"
                elif serial_number:
                    identifier_label = "serial_number"
                else:
                    identifier_label = "nuid"
                errors.append({
                    "row": row_number,
                    "identifier": f"{identifier_label}={identifier_value}",
                    "error": "Device not registered",
                })
                continue

            resolved_id = str(resolved_device.get("id") or resolved_device.get("_id") or "")
            if not resolved_id:
                errors.append({
                    "row": row_number,
                    "identifier": mac_address or nuid,
                    "error": "Resolved device is missing an id",
                })
                continue

            if resolved_id in seen_device_ids:
                duplicate_identifier = mac_address or serial_number or nuid
                errors.append({
                    "row": row_number,
                    "identifier": duplicate_identifier,
                    "error": "Duplicate device in upload",
                })
                continue

            seen_device_ids.add(resolved_id)
            resolved_device_ids.append(resolved_id)

    if errors:
        return {
            "created": False,
            "distribution": None,
            "created_count": 0,
            "error_count": len(errors),
            "errors": errors,
            "total_rows": len(identifier_rows),
            "valid_count": len(resolved_device_ids),
        }

    dist_data = DistributionCreate(
        to_user_id=str(to_user_id),
        device_ids=resolved_device_ids,
        notes=notes,
    )
    distribution = await create_distribution(dist_data=dist_data, from_user=from_user)

    return {
        "created": True,
        "distribution": distribution,
        "created_count": len(resolved_device_ids),
        "error_count": 0,
        "errors": [],
        "total_rows": len(identifier_rows),
        "valid_count": len(resolved_device_ids),
    }


async def create_distribution(dist_data: DistributionCreate, from_user: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new distribution request"""
    async with get_db() as db:
        # Get recipient user
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (int(dist_data.to_user_id),))
        to_user = await cursor.fetchone()
        if not to_user:
            raise ValueError("Recipient user not found")
        to_user = row_to_dict(to_user)

        from_role = from_user["role"]
        to_role = to_user["role"]
        from_user_id = str(from_user.get("id", from_user.get("_id", "")))

        if from_role in {"super_admin", "manager", "pdic_staff"}:
            if to_role not in {"sub_distributor", "cluster", "operator"}:
                raise ValueError(
                    "Management can only distribute to sub-distributors, clusters, or operators"
                )

        # ── Hierarchy validation for sub-level roles ──────────────────────────
        if from_role == "sub_distribution_manager":
            if to_role == "cluster":
                if str(to_user.get("parent_id", "")) != from_user_id:
                    raise ValueError("You can only distribute to clusters directly under your account")
            elif to_role == "operator":
                cursor = await db.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (int(to_user.get("parent_id") or 0),)
                )
                parent_cluster = await cursor.fetchone()
                if not parent_cluster:
                    raise ValueError("Operator's cluster not found")
                parent_cluster = row_to_dict(parent_cluster)
                if str(parent_cluster.get("parent_id", "")) != from_user_id:
                    raise ValueError("You can only distribute to operators within your sub-distribution manager chain")
            else:
                raise ValueError("Sub distribution managers can only distribute to clusters or operators")

        elif from_role == "sub_distributor":
            if to_role == "cluster":
                if str(to_user.get("parent_id", "")) != from_user_id:
                    raise ValueError("You can only distribute to clusters directly under your account")
            elif to_role == "operator":
                # Operator lives under a cluster that belongs to this sub_distributor
                cursor = await db.execute(
                    "SELECT * FROM users WHERE id = ?", (int(to_user.get("parent_id") or 0),)
                )
                parent_cluster = await cursor.fetchone()
                if not parent_cluster:
                    raise ValueError("Operator's cluster not found")
                parent_cluster = row_to_dict(parent_cluster)
                if str(parent_cluster.get("parent_id", "")) != from_user_id:
                    raise ValueError("You can only distribute to operators within your sub-distribution")
            else:
                raise ValueError("Sub-distributors can only distribute to clusters or operators")

        elif from_role == "cluster":
            if to_role == "operator":
                if str(to_user.get("parent_id", "")) != from_user_id:
                    raise ValueError("You can only distribute to operators directly under your cluster")
            else:
                raise ValueError("Clusters can only distribute to operators")

        elif from_role == "operator":
            if to_role == "operator":
                if str(dist_data.to_user_id) == from_user_id:
                    raise ValueError("You cannot distribute to yourself")
                if str(to_user.get("parent_id", "")) != str(from_user.get("parent_id", "")):
                    raise ValueError("You can only distribute to operators in the same cluster")
            else:
                raise ValueError("Operators can only distribute to other operators in the same cluster")
        # ─── End hierarchy validation ─────────────────────────────────────────

        # Validate devices
        validated_devices: List[Dict[str, Any]] = []
        for dev_id in dist_data.device_ids:
            cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(dev_id),))
            device = await cursor.fetchone()
            if not device:
                raise ValueError(f"Device {dev_id} not found")
            device = row_to_dict(device)
            if device.get("status") == DeviceStatus.DEFECTIVE.value:
                raise ValueError(
                    f"Device {device['device_id']} is marked defective and cannot be transferred"
                )
            if await _device_has_open_distribution_lock(db, str(dev_id)):
                raise ValueError(
                    f"Device {device['device_id']} is already in an unconfirmed or disputed distribution"
                )
            if from_role in ["super_admin", "manager", "pdic_staff"]:
                # Management distributes from PDIC stock — must be available
                if device["status"] != DeviceStatus.AVAILABLE.value:
                    raise ValueError(f"Device {device['device_id']} is not available")
            else:
                # Sub-level roles redistribute from their own stock
                if str(device.get("current_holder_id", "")) != from_user_id:
                    raise ValueError(f"Device {device['device_id']} is not in your possession")
                # Block redistribution if a pending_receipt distribution exists for this device to this user
                cursor2 = await db.execute(
                    "SELECT device_ids FROM distributions WHERE to_user_id = ? AND status = ?",
                    (from_user_id, DistributionStatus.PENDING_RECEIPT.value)
                )
                pending_rows = await cursor2.fetchall()
                for prow in pending_rows:
                    try:
                        pending_ids = [str(x) for x in json.loads(prow[0] or '[]')]
                    except (json.JSONDecodeError, TypeError):
                        pending_ids = []
                    if str(dev_id) in pending_ids:
                        raise ValueError(
                            f"Device {device['device_id']} is awaiting your receipt confirmation. "
                            f"Please confirm receipt of the incoming transfer before redistributing."
                        )
            validated_devices.append(device)
        
        role_to_type = {
            "super_admin": "noc", "manager": "noc", "pdic_staff": "pdic_staff",
            "sub_distribution_manager": "sub_distribution_manager",
            "sub_distributor": "sub_distributor", "cluster": "cluster", "operator": "operator"
        }
        
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        dist_id = generate_distribution_id()
        
        cursor = await db.execute(
            """INSERT INTO distributions (distribution_id, device_ids, device_count,
                from_user_id, from_user_name, from_user_type, to_user_id, to_user_name, to_user_type,
                status, request_date, approval_date, approved_by, approved_by_name,
                notes, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dist_id, json.dumps(dist_data.device_ids),
                len(dist_data.device_ids), from_user_id, from_user["name"],
                role_to_type.get(from_user["role"], "noc"),
                str(to_user["id"]), to_user["name"],
                role_to_type.get(to_user["role"], "pdic_staff"),
                DistributionStatus.PENDING_RECEIPT.value, now, now,
                from_user_id, from_user["name"],
                dist_data.notes, from_user_id, now, now
            )
        )
        new_id = str(cursor.lastrowid)

        manifest_file = None
        try:
            manifest_file = _build_distribution_manifest(
                distribution_id=dist_id,
                devices=validated_devices,
                from_user_name=from_user.get("name", "Unknown"),
                to_user_name=to_user.get("name", "Unknown"),
                created_at_iso=now,
            )
            await db.execute(
                "UPDATE distributions SET manifest_file = ? WHERE id = ?",
                (manifest_file, int(new_id))
            )
        except Exception:
            # Distribution should still succeed even if manifest generation fails.
            manifest_file = None

        await db.commit()
    
    # NOTE: Device holders are NOT moved here. They move only when the recipient
    # confirms receipt (confirm_receipt with received=True). This ensures devices
    # do not appear in the recipient's account before they acknowledge them.
    
    # Notify recipient — ask them to confirm receipt
    sender_label = _sender_display_name(from_user)
    await notification_service.create_notification(
        user_id=str(to_user["id"]),
        title="Action Required: Confirm Device Receipt",
        message=f"{len(dist_data.device_ids)} device(s) have been sent to you by {sender_label}. "
            f"An Excel manifest is available in Delivery Confirmations. "
                f"Please confirm receipt on your Delivery Confirmations page (Distribution ID: {dist_id}).",
        notification_type="warning", category="distribution",
        link="/delivery-confirmations"
    )
    
    return await get_distribution_by_id(new_id)


async def update_distribution_status(
    distribution_id: str, status: str, user: Dict[str, Any], notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update distribution status"""
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        return None
    
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    user_id = str(user.get("id", user.get("_id", "")))
    user_role = str(user.get("role", "")).lower()

    if status in {DistributionStatus.APPROVED.value, DistributionStatus.REJECTED.value} and user_role in {"super_admin", "manager", "pdic_staff"}:
        allowed = await approval_service.is_role_allowed_for_approval_type(user_role, "distribution")
        if not allowed:
            raise PermissionError(f"{user_role.capitalize()} role is not allowed to process distribution approvals")
    
    async with get_db() as db:
        update_fields = ["status = ?", "updated_at = ?"]
        params = [status, now]
        
        if status == DistributionStatus.APPROVED.value:
            update_fields.extend(["approval_date = ?", "approved_by = ?", "approved_by_name = ?"])
            params.extend([now, user_id, user["name"]])
            
            await db.execute(
                """UPDATE approvals SET status = 'approved', approved_by = ?, approved_by_name = ?,
                    approval_date = ?, updated_at = ? WHERE entity_id = ? AND approval_type = 'distribution'""",
                (user_id, user["name"], now, now, distribution_id)
            )
        
        elif status == DistributionStatus.DELIVERED.value:
            update_fields.append("delivery_date = ?")
            params.append(now)
        
        elif status == DistributionStatus.REJECTED.value:
            await db.execute(
                """UPDATE approvals SET status = 'rejected', approved_by = ?, approved_by_name = ?,
                    approval_date = ?, rejection_reason = ?, updated_at = ?
                    WHERE entity_id = ? AND approval_type = 'distribution'""",
                (user_id, user["name"], now, notes, now, distribution_id)
            )
            # Devices were never moved (holder update is deferred until recipient confirms receipt),
            # so no device reset is needed on rejection.
        
        if notes:
            update_fields.append("notes = ?")
            params.append(notes)
        
        params.append(int(distribution_id))
        await db.execute(f"UPDATE distributions SET {', '.join(update_fields)} WHERE id = ?", params)
        await db.commit()
    
    # NOTE: Device holders are moved immediately when a distribution is CREATED.
    # Re-updating holders here on APPROVED would corrupt the chain if devices
    # have already been redistributed onward. Only REJECTED reverts holders.
    
    # Notification
    await notification_service.create_notification(
        user_id=dist["from_user_id"],
        title=f"Distribution {status.capitalize()}",
        message=f"Distribution {dist['distribution_id']} has been {status}",
        notification_type="success" if status in ["approved", "delivered"] else "warning",
        category="distribution", link=f"/distributions?distributionId={distribution_id}"
    )
    
    return await get_distribution_by_id(distribution_id)


async def confirm_receipt(
    distribution_id: str, received: bool, user: Dict[str, Any], notes: Optional[str] = None
) -> Dict[str, Any]:
    """Receiver confirms or disputes receipt of a distribution.
    - received=True  → status APPROVED, devices moved to recipient, sender notified
    - received=False → status DISPUTED, all admins/managers + sender notified
    Without confirming, receiver cannot redistribute the devices and devices stay with sender.
    """
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        raise ValueError("Distribution not found")

    user_id = str(user.get("id", user.get("_id", "")))

    if str(dist["to_user_id"]) != user_id:
        raise ValueError("Only the recipient can confirm receipt of this distribution")

    if dist["status"] != DistributionStatus.PENDING_RECEIPT.value:
        raise ValueError("This distribution is not awaiting receipt confirmation")

    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    role_to_type = {
        "super_admin": "noc", "manager": "noc", "pdic_staff": "pdic_staff",
        "sub_distribution_manager": "sub_distribution_manager",
        "sub_distributor": "sub_distributor", "cluster": "cluster", "operator": "operator"
    }

    async with get_db() as db:
        if received:
            # Look up to_user role so we can set the correct device status
            cursor = await db.execute(
                "SELECT role FROM users WHERE id = ?", (int(dist["to_user_id"]),)
            )
            to_user_row = await cursor.fetchone()
            to_user_role = dict(to_user_row)["role"] if to_user_row else "operator"

            await db.execute(
                """UPDATE distributions
                   SET status = ?, approval_date = ?, approved_by = ?, approved_by_name = ?,
                       notes = COALESCE(?, notes), updated_at = ?
                   WHERE id = ?""",
                (
                    DistributionStatus.APPROVED.value, now, user_id, user["name"],
                    notes, now, int(distribution_id)
                )
            )
            await db.commit()

        else:
            to_user_role = None
            await db.execute(
                """UPDATE distributions
                   SET status = 'disputed', notes = COALESCE(?, notes), updated_at = ?
                   WHERE id = ?""",
                (notes, now, int(distribution_id))
            )
            cursor = await db.execute(
                "SELECT id FROM users WHERE role IN ('super_admin', 'manager', 'pdic_staff') AND status = 'active'"
            )
            admin_rows = await cursor.fetchall()
            await db.commit()

            sender_label = (
                "PDIC" if str(dist.get("from_user_type") or "").lower() in {"noc", "pdic_staff"}
                else dist.get("from_user_name")
            )
            dispute_msg = (
                f"DISPUTE: {user['name']} reported NOT receiving {dist['device_count']} device(s) "
                f"sent by {sender_label}. Distribution: {dist['distribution_id']}."
            )
            for row in admin_rows:
                await notification_service.create_notification(
                    user_id=str(row[0]),
                    title="Device Not Received — Dispute",
                    message=dispute_msg,
                    notification_type="error", category="distribution",
                    link=f"/distributions?distributionId={distribution_id}"
                )
            # Also notify sender
            await notification_service.create_notification(
                user_id=dist["from_user_id"],
                title="Receipt Disputed",
                message=f"{user['name']} reported NOT receiving your device(s) in distribution "
                        f"{dist['distribution_id']}. Admin, manager, and PDIC staff have been notified.",
                notification_type="error", category="distribution",
                link=f"/distributions?distributionId={distribution_id}"
            )

    if received and to_user_role:
        # NOW move devices to the recipient — only after they confirm receipt
        device_status_for_recipient = (
            DeviceStatus.IN_USE.value if to_user_role == "operator" else DeviceStatus.DISTRIBUTED.value
        )
        holder_type = role_to_type.get(to_user_role, "pdic_staff")
        device_ids = dist.get("device_ids", [])
        for dev_id in device_ids:
            try:
                await device_service.update_device_holder(
                    device_id=str(dev_id),
                    holder_id=dist["to_user_id"],
                    holder_name=dist["to_user_name"],
                    holder_type=holder_type,
                    location=dist["to_user_name"],
                    status=device_status_for_recipient,
                    performed_by=user_id,
                    performed_by_name=user["name"],
                    from_user_id=dist["from_user_id"],
                    from_user_name=dist["from_user_name"],
                    notes=f"Receipt confirmed for distribution {dist['distribution_id']}"
                )
            except Exception:
                pass  # Log but don't fail the confirmation

        # Notify sender: receipt confirmed
        await notification_service.create_notification(
            user_id=dist["from_user_id"],
            title="Receipt Confirmed",
            message=f"{user['name']} confirmed receipt of {dist['device_count']} device(s) "
                    f"(Distribution: {dist['distribution_id']}).",
            notification_type="success", category="distribution",
            link=f"/distributions?distributionId={distribution_id}"
        )

    return await get_distribution_by_id(distribution_id)


async def confirm_disputed_return(
    distribution_id: str,
    user: Dict[str, Any],
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """PDIC management confirms disputed devices are back with sender and unlocks redistribution."""
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        raise ValueError("Distribution not found")

    if dist["status"] != DistributionStatus.DISPUTED.value:
        raise ValueError("Only disputed distributions can be marked as returned")

    role = str(user.get("role", "")).lower()
    if role not in {"super_admin", "manager", "pdic_staff"}:
        raise ValueError("Only PDIC management can confirm disputed return receipt")

    role_to_type = {
        "super_admin": "noc", "manager": "noc", "pdic_staff": "pdic_staff",
        "sub_distribution_manager": "sub_distribution_manager",
        "sub_distributor": "sub_distributor", "cluster": "cluster", "operator": "operator"
    }

    sender_role = str(dist.get("from_user_type") or "")
    if sender_role == "noc":
        sender_role = "manager"

    sender_status = DeviceStatus.AVAILABLE.value if sender_role in {"manager", "super_admin", "pdic_staff"} else (
        DeviceStatus.IN_USE.value if sender_role == "operator" else DeviceStatus.DISTRIBUTED.value
    )

    sender_holder_type = role_to_type.get(sender_role, "pdic_staff")
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    async with get_db() as db:
        await db.execute(
            """UPDATE distributions
               SET status = ?, notes = COALESCE(?, notes), updated_at = ?, delivery_date = ?
               WHERE id = ?""",
            (DistributionStatus.REJECTED.value, notes, now, now, int(distribution_id)),
        )
        await db.commit()

    device_ids = dist.get("device_ids", []) or []
    for dev_id in device_ids:
        try:
            await device_service.update_device_holder(
                device_id=str(dev_id),
                holder_id=dist["from_user_id"],
                holder_name=dist["from_user_name"],
                holder_type=sender_holder_type,
                location=dist["from_user_name"],
                status=sender_status,
                performed_by=str(user.get("id", user.get("_id", ""))),
                performed_by_name=str(user.get("name") or "PDIC"),
                from_user_id=dist.get("to_user_id"),
                from_user_name=dist.get("to_user_name"),
                notes=f"Disputed return confirmed for distribution {dist.get('distribution_id')}",
            )
        except Exception:
            pass

    await notification_service.create_notification(
        user_id=str(dist["from_user_id"]),
        title="Disputed Return Confirmed",
        message=(
            f"PDIC confirmed devices for distribution {dist['distribution_id']} are back with you. "
            "You can distribute these devices again."
        ),
        notification_type="success",
        category="distribution",
        link=f"/distributions?distributionId={distribution_id}",
    )

    return await get_distribution_by_id(distribution_id)


async def cancel_distribution(distribution_id: str, user: dict) -> bool:
    """Cancel a distribution"""
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        return False
    user_id = str(user.get("id", user.get("_id", "")))
    if dist["created_by"] != user_id and user.get("role") not in ["super_admin", "manager"]:
        raise ValueError("Only the creator can cancel this distribution")
    if dist["status"] == DistributionStatus.CANCELLED.value:
        raise ValueError("Distribution is already cancelled")
    if dist["status"] == DistributionStatus.APPROVED.value:
        raise ValueError("Cannot cancel a distribution that has already been confirmed")
    
    async with get_db() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        await db.execute(
            "UPDATE distributions SET status = ?, updated_at = ? WHERE id = ?",
            (DistributionStatus.CANCELLED.value, now, int(distribution_id))
        )
        await db.commit()
    
    # Devices were never moved (hold is deferred until receipt confirmation),
    # so no device holder reset is needed on cancel.
    return True


async def get_distribution_manifest_file(distribution_id: str, user: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Get manifest file metadata if requester is permitted to access distribution."""
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        return None

    role = user.get("role")
    user_id = str(user.get("id", user.get("_id", "")))
    if role not in ["super_admin", "manager", "pdic_staff"]:
        if user_id not in [str(dist.get("from_user_id", "")), str(dist.get("to_user_id", ""))]:
            raise ValueError("You are not allowed to access this distribution manifest")

    manifest_file = dist.get("manifest_file")
    if not manifest_file:
        return None

    file_path = _distribution_manifest_dir() / str(manifest_file)
    if not file_path.exists():
        return None

    return {
        "path": str(file_path),
        "filename": str(manifest_file),
    }


async def get_distribution_mac_nuid_export(
    distribution_id: str,
    user: Dict[str, Any],
    file_format: str = "csv",
) -> Dict[str, Any]:
    """Get an identifier export payload (serial_number, mac_address, nuid) for distribution devices if requester is permitted."""
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        raise ValueError("Distribution not found")

    role = str(user.get("role", "")).lower()
    user_id = str(user.get("id", user.get("_id", "")))

    if role not in ["super_admin", "manager", "pdic_staff"]:
        if user_id not in [str(dist.get("from_user_id", "")), str(dist.get("to_user_id", ""))]:
            raise ValueError("You are not allowed to access this distribution export")

    device_ids = dist.get("device_ids") or []
    if isinstance(device_ids, str):
        try:
            device_ids = json.loads(device_ids)
        except (json.JSONDecodeError, TypeError):
            device_ids = []

    devices: List[Dict[str, Any]] = []
    if device_ids:
        placeholders = ",".join(["?"] * len(device_ids))
        async with get_db() as db:
            cursor = await db.execute(
                f"SELECT id, serial_number, mac_address, nuid FROM devices WHERE id IN ({placeholders})",
                tuple(int(device_id) for device_id in device_ids)
            )
            devices = rows_to_list(await cursor.fetchall())

    distribution_code = str(dist.get("distribution_id") or f"distribution-{distribution_id}")
    return _build_distribution_mac_nuid_file(
        distribution_code=distribution_code,
        devices=devices,
        file_format=file_format,
    )


async def get_pending_distributions() -> List[Dict[str, Any]]:
    """Get all pending distributions"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM distributions WHERE status = ? ORDER BY created_at DESC",
            (DistributionStatus.PENDING.value,)
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows_to_list(rows):
            if r.get("device_ids"):
                try:
                    r["device_ids"] = json.loads(r["device_ids"])
                except (json.JSONDecodeError, TypeError):
                    r["device_ids"] = []
            result.append(r)
        return result


async def get_distribution_stats() -> Dict[str, int]:
    """Get distribution statistics"""
    async with get_db() as db:
        stats = {}
        for key in ["total", "pending", "pending_receipt", "approved", "delivered", "rejected", "disputed"]:
            if key == "total":
                cursor = await db.execute("SELECT COUNT(*) FROM distributions")
            else:
                cursor = await db.execute("SELECT COUNT(*) FROM distributions WHERE status = ?", (key,))
            stats[key] = (await cursor.fetchone())[0]
        return stats


async def sync_approved_distributions(user: Dict[str, Any]) -> Dict[str, Any]:
    """Re-process all approved distributions to sync device holders."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM distributions WHERE status = ?", (DistributionStatus.APPROVED.value,))
        rows = await cursor.fetchall()
    
    distributions = rows_to_list(rows)
    synced_count = 0
    errors = []
    user_id = str(user.get("id", user.get("_id", "system")))
    
    for dist in distributions:
        device_ids = dist.get("device_ids", "[]")
        if isinstance(device_ids, str):
            try:
                device_ids = json.loads(device_ids)
            except (json.JSONDecodeError, TypeError):
                device_ids = []
        
        for dev_id in device_ids:
            try:
                await device_service.update_device_holder(
                    device_id=dev_id, holder_id=dist["to_user_id"],
                    holder_name=dist["to_user_name"],
                    holder_type=dist.get("to_user_type", "pdic_staff"),
                    location=dist["to_user_name"],
                    status=DeviceStatus.DISTRIBUTED.value,
                    performed_by=user_id, performed_by_name=user.get("name", "System"),
                    from_user_id=dist.get("from_user_id"),
                    from_user_name=dist.get("from_user_name"),
                    notes=f"Synced from approved distribution {dist.get('distribution_id', '')}"
                )
                synced_count += 1
            except Exception as e:
                errors.append(f"Device {dev_id}: {str(e)}")
    
    return {"total_distributions": len(distributions), "devices_synced": synced_count, "errors": errors}

