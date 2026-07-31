from datetime import datetime, timezone, date
from typing import Optional, List, Dict, Any, Set
import json
import io
import csv
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import text

from app.database_sqlalchemy import async_session_factory
from app.models.distribution import DistributionCreate, DistributionStatus
from app.models.device import DeviceStatus
from app.services import device_service, notification_service
from app.services.digital_id_search import build_identity_search_clause
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
    distribution: Dict[str, Any],
    devices: List[Dict[str, Any]],
    file_format: str = "csv",
) -> Dict[str, Any]:
    """Build export containing distribution context and device identifiers/details."""
    normalized = str(file_format or "csv").strip().lower()
    if normalized not in {"csv", "xlsx"}:
        raise ValueError("Unsupported export format. Use 'csv' or 'xlsx'")

    distribution_code = str(distribution.get("distribution_id") or "")
    from_user = str(distribution.get("from_user_name") or "")
    to_user = str(distribution.get("to_user_name") or "")

    headers = [
        "from_user_name",
        "to_user_name",
        "device_type",
        "manufacturer",
        "model",
        "serial_number",
        "mac_address",
        "nuid",
    ]

    rows = [
        {
            "from_user_name": from_user,
            "to_user_name": to_user,
            "device_type": str(device.get("device_type") or "").strip(),
            "manufacturer": str(device.get("manufacturer") or "").strip(),
            "model": str(device.get("model") or "").strip(),
            "serial_number": str(device.get("serial_number") or "").strip(),
            "mac_address": str(device.get("mac_address") or "").strip(),
            "nuid": str(device.get("nuid") or "").strip(),
        }
        for device in devices
    ]

    if normalized == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "DISTRIBUTION_EXPORT"
        sheet.append(headers)
        for row in rows:
            sheet.append([row[header] for header in headers])

        payload = io.BytesIO()
        workbook.save(payload)
        payload.seek(0)
        return {
            "content": payload.getvalue(),
            "filename": f"{distribution_code}-distribution-details.xlsx",
            "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)

    content = csv_buffer.getvalue()
    return {
        "content": content.encode("utf-8"),
        "filename": f"{distribution_code}-distribution-details.csv",
        "media_type": "text/csv",
    }


def _sender_display_name(user: Dict[str, Any]) -> str:
    role = str(user.get("role") or "").strip().lower()
    if role in {"super_admin", "manager", "pdic_staff"}:
        return "PDIC"
    return str(user.get("name") or "Unknown")


async def _bulk_update_device_holders(
    device_ids: List[Any],
    holder_id: int,
    holder_name: str,
    holder_type: str,
    location: str,
    status: str,
    performed_by: int,
    performed_by_name: str,
    from_user_id: Optional[int] = None,
    from_user_name: Optional[str] = None,
    notes: Optional[str] = None,
) -> List[str]:
    if not device_ids:
        return []

    normalized_ids = []
    for dev_id in device_ids:
        try:
            normalized_ids.append(int(dev_id))
        except (TypeError, ValueError):
            continue

    if not normalized_ids:
        return []

    async with async_session_factory() as session:
        ph = ",".join([f":d_{i}" for i in range(len(normalized_ids))])
        params = {f"d_{i}": did for i, did in enumerate(normalized_ids)}
        rows = (await session.execute(
            text(f"SELECT id, status FROM devices WHERE id IN ({ph})"),
            params
        )).mappings().all()
        status_map = {str(r["id"]): r["status"] for r in rows if r["id"] is not None}
        if not status_map:
            return []

        existing_ids = [int(dev_id) for dev_id in status_map.keys()]
        now = datetime.now().replace(tzinfo=None)

        uph = ",".join([f":e_{i}" for i in range(len(existing_ids))])
        update_params: Dict[str, Any] = {
            "holder_id": holder_id,
            "holder_name": holder_name,
            "holder_type": holder_type,
            "location": location,
            "status": status,
            "now": now,
        }
        for i, eid in enumerate(existing_ids):
            update_params[f"e_{i}"] = eid

        await session.execute(
            text(f"""UPDATE devices
                SET current_holder_id = :holder_id, current_holder_name = :holder_name, current_holder_type = :holder_type,
                    current_location = :location, status = :status, updated_at = :now
                WHERE id IN ({uph})"""),
            update_params
        )

        history_rows = []
        for dev_id in existing_ids:
            history_rows.append({
                "device_id": dev_id,
                "action": "distributed",
                "from_user_id": from_user_id,
                "from_user_name": from_user_name,
                "to_user_id": holder_id,
                "to_user_name": holder_name,
                "status_before": status_map.get(str(dev_id)),
                "status_after": status,
                "location": location,
                "notes": notes,
                "performed_by": performed_by,
                "performed_by_name": performed_by_name,
                "ts": now,
            })

        if history_rows:
            await session.execute(
                text("""INSERT INTO device_history (
                    device_id, action, from_user_id, from_user_name,
                    to_user_id, to_user_name, status_before, status_after,
                    location, notes, performed_by, performed_by_name, timestamp
                ) VALUES (:device_id, :action, :from_user_id, :from_user_name,
                    :to_user_id, :to_user_name, :status_before, :status_after,
                    :location, :notes, :performed_by, :performed_by_name, :ts)"""),
                history_rows
            )

        await session.commit()
        return [str(dev_id) for dev_id in existing_ids]


async def _get_distribution_scope_user_ids(session, user: Dict[str, Any]) -> Optional[Set[int]]:
    role = str(user.get("role") or "")
    user_id = int(user.get("id") or user.get("_id") or 0)
    parent_id = int(user.get("parent_id") or 0)

    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        return None

    scope_root = parent_id if role == "sub_distribution_manager" and parent_id else user_id
    scoped_ids: Set[int] = {scope_root}
    if scope_root:
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
            {"root": scope_root}
        )).scalars().all()
        scoped_ids.update(did for did in desc_rows if did)
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
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        conditions = []
        params: Dict[str, Any] = {}

        if status:
            conditions.append("status = :status")
            params["status"] = status
        if from_user_id:
            conditions.append("from_user_id = :from_user_id")
            params["from_user_id"] = from_user_id
        if to_user_id:
            conditions.append("to_user_id = :to_user_id")
            params["to_user_id"] = to_user_id

        scope_ids = await _get_distribution_scope_user_ids(session, current_user) if current_user else None
        if scope_ids is not None:
            if not scope_ids:
                return {"data": [], "pagination": get_pagination(page, page_size, 0)}
            scope_list = sorted(scope_ids)
            ph1 = ",".join([f":sf_{i}" for i in range(len(scope_list))])
            ph2 = ",".join([f":st_{i}" for i in range(len(scope_list))])
            conditions.append(f"(from_user_id IN ({ph1}) OR to_user_id IN ({ph2}))")
            for i, sid in enumerate(scope_list):
                params[f"sf_{i}"] = sid
                params[f"st_{i}"] = sid
        elif user_id:
            conditions.append("(from_user_id = :uid1 OR to_user_id = :uid2)")
            params["uid1"] = user_id
            params["uid2"] = user_id
        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date
        if search:
            like = f"%{search}%"
            search_field_map = {
                "distribution_id": "distribution_id",
                "from_user_name": "from_user_name",
                "to_user_name": "to_user_name",
                "status": "status",
                "approved_by_name": "approved_by_name",
            }
            identity_user_columns = ["distributions.from_user_id", "distributions.to_user_id"]
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by in {"digital_id", "broadband_id"}:
                clause, iparams = build_identity_search_clause(
                    identity_user_columns, like, fields=[normalized_search_by]
                )
                conditions.append(clause)
                params.update(iparams)
            elif normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE :search_like")
                params["search_like"] = like
            else:
                id_clause, iparams = build_identity_search_clause(identity_user_columns, like)
                conditions.append("(distribution_id LIKE :sl1 OR from_user_name LIKE :sl2 OR to_user_name LIKE :sl3 OR status LIKE :sl4 OR approved_by_name LIKE :sl5 OR " + id_clause + ")")
                for i in range(5):
                    params[f"sl{i+1}"] = like
                params.update(iparams)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        total = (await session.execute(
            text(f"SELECT COUNT(*) FROM distributions WHERE {where_clause}"), params
        )).scalar() or 0

        offset = (page - 1) * page_size
        params["_limit"] = page_size
        params["_offset"] = offset
        rows = (await session.execute(
            text(f"SELECT * FROM distributions WHERE {where_clause} ORDER BY created_at DESC LIMIT :_limit OFFSET :_offset"),
            params
        )).mappings().all()

        result = []
        for r in rows:
            d = dict(r)
            if d.get("device_ids"):
                try:
                    d["device_ids"] = json.loads(d["device_ids"])
                except (json.JSONDecodeError, TypeError):
                    d["device_ids"] = []
            result.append(d)

        return {
            "data": result,
            "pagination": get_pagination(page, page_size, total)
        }


def _parse_device_ids(d: Dict[str, Any]) -> Dict[str, Any]:
    if d.get("device_ids"):
        try:
            d["device_ids"] = json.loads(d["device_ids"])
        except (json.JSONDecodeError, TypeError):
            d["device_ids"] = []
    return d


async def get_distribution_by_id(distribution_id: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        row = (await session.execute(
            text("SELECT * FROM distributions WHERE id = :id"), {"id": int(distribution_id)}
        )).mappings().first()
        return _parse_device_ids(dict(row)) if row else None


async def get_distribution_by_code(distribution_code: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        row = (await session.execute(
            text("SELECT * FROM distributions WHERE distribution_id = :code"),
            {"code": str(distribution_code)}
        )).mappings().first()
        return _parse_device_ids(dict(row)) if row else None


async def create_distribution_from_identifiers(
    to_user_id: str,
    identifier_rows: List[Dict[str, Any]],
    from_user: Dict[str, Any],
    notes: Optional[str] = None,
    date_of_distribution: Optional[date] = None,
) -> Dict[str, Any]:
    """Create a distribution from uploaded rows containing MAC, serial number, and/or NUID.

    If any row fails validation, distribution is not created and row-level errors are returned.
    """
    errors: List[Dict[str, Any]] = []
    resolved_device_ids: List[str] = []
    seen_device_ids = set()

    all_macs: List[str] = []
    all_serials: List[str] = []
    all_nuids: List[str] = []
    row_lookup: List[Dict[str, Any]] = []

    for row in identifier_rows:
        mac_address = str(row.get("mac_address") or "").strip()
        serial_number = str(row.get("serial_number") or "").strip()
        nuid = str(row.get("nuid") or "").strip()

        if not mac_address and not serial_number and not nuid:
            errors.append({
                "row": int(row.get("row") or 0),
                "identifier": "",
                "error": "Provide at least one identifier: mac_address, serial_number, or nuid",
            })
            continue

        if mac_address:
            all_macs.append(mac_address.lower())
        if serial_number:
            all_serials.append(serial_number.lower())
        if nuid:
            all_nuids.append(nuid.lower())

        row_lookup.append({
            "row": int(row.get("row") or 0),
            "mac_address": mac_address,
            "serial_number": serial_number,
            "nuid": nuid,
        })

    async with async_session_factory() as session:
        mac_map: Dict[str, Any] = {}
        serial_map: Dict[str, Any] = {}
        nuid_map: Dict[str, Any] = {}

        all_macs = list(set(all_macs))
        all_serials = list(set(all_serials))
        all_nuids = list(set(all_nuids))

        if all_macs:
            ph = ",".join([f":mac_{i}" for i in range(len(all_macs))])
            params = {f"mac_{i}": m for i, m in enumerate(all_macs)}
            rows = (await session.execute(
                text(f"SELECT * FROM devices WHERE lower(trim(mac_address)) IN ({ph})"),
                params
            )).mappings().all()
            for dev in rows:
                mac_map[dev["mac_address"].strip().lower()] = dict(dev)

        if all_serials:
            ph = ",".join([f":ser_{i}" for i in range(len(all_serials))])
            params = {f"ser_{i}": s for i, s in enumerate(all_serials)}
            rows = (await session.execute(
                text(f"SELECT * FROM devices WHERE lower(trim(serial_number)) IN ({ph})"),
                params
            )).mappings().all()
            for dev in rows:
                serial_map[dev["serial_number"].strip().lower()] = dict(dev)

        if all_nuids:
            ph = ",".join([f":nuid_{i}" for i in range(len(all_nuids))])
            params = {f"nuid_{i}": n for i, n in enumerate(all_nuids)}
            rows = (await session.execute(
                text(f"SELECT * FROM devices WHERE lower(trim(nuid)) IN ({ph})"),
                params
            )).mappings().all()
            for dev in rows:
                nuid_map[dev["nuid"].strip().lower()] = dict(dev)

        for item in row_lookup:
            row_number = item["row"]
            mac_address = item["mac_address"]
            serial_number = item["serial_number"]
            nuid = item["nuid"]

            device_by_mac = mac_map.get(mac_address.lower()) if mac_address else None
            device_by_serial = serial_map.get(serial_number.lower()) if serial_number else None
            device_by_nuid = nuid_map.get(nuid.lower()) if nuid else None

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

    if not resolved_device_ids:
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
        date_of_distribution=date_of_distribution,
    )
    distribution = await create_distribution(dist_data=dist_data, from_user=from_user)

    return {
        "created": True,
        "distribution": distribution,
        "created_count": len(resolved_device_ids),
        "error_count": len(errors),
        "errors": errors,
        "total_rows": len(identifier_rows),
        "valid_count": len(resolved_device_ids),
    }


async def create_distribution(dist_data: DistributionCreate, from_user: Dict[str, Any]) -> Dict[str, Any]:
    async with async_session_factory() as session:
        to_user = (await session.execute(
            text("SELECT * FROM users WHERE id = :id"), {"id": int(dist_data.to_user_id)}
        )).mappings().first()
        if not to_user:
            raise ValueError("Recipient user not found")
        to_user = dict(to_user)

        from_role = from_user["role"]
        to_role = to_user["role"]
        from_user_id = int(from_user.get("id", from_user.get("_id", 0)))

        if from_role in {"super_admin", "manager", "pdic_staff"}:
            if to_role not in {"sub_distributor", "cluster", "operator"}:
                raise ValueError("Management can only distribute to sub-distributors, clusters, or operators")

        if from_role == "sub_distribution_manager":
            if to_role == "cluster":
                if int(to_user.get("parent_id", 0)) != from_user_id:
                    raise ValueError("You can only distribute to clusters directly under your account")
            elif to_role == "operator":
                parent_cluster = (await session.execute(
                    text("SELECT * FROM users WHERE id = :id"), {"id": int(to_user.get("parent_id") or 0)}
                )).mappings().first()
                if not parent_cluster:
                    raise ValueError("Operator's cluster not found")
                parent_cluster = dict(parent_cluster)
                if int(parent_cluster.get("parent_id", 0)) != from_user_id:
                    raise ValueError("You can only distribute to operators within your sub-distribution manager chain")
            else:
                raise ValueError("Sub distribution managers can only distribute to clusters or operators")

        elif from_role == "sub_distributor":
            if to_role == "cluster":
                if int(to_user.get("parent_id", 0)) != from_user_id:
                    raise ValueError("You can only distribute to clusters directly under your account")
            elif to_role == "operator":
                parent_cluster = (await session.execute(
                    text("SELECT * FROM users WHERE id = :id"), {"id": int(to_user.get("parent_id") or 0)}
                )).mappings().first()
                if not parent_cluster:
                    raise ValueError("Operator's cluster not found")
                parent_cluster = dict(parent_cluster)
                if int(parent_cluster.get("parent_id", 0)) != from_user_id:
                    raise ValueError("You can only distribute to operators within your sub-distribution")
            else:
                raise ValueError("Sub-distributors can only distribute to clusters or operators")

        elif from_role == "cluster":
            if to_role == "operator":
                if int(to_user.get("parent_id", 0)) != from_user_id:
                    raise ValueError("You can only distribute to operators directly under your cluster")
            else:
                raise ValueError("Clusters can only distribute to operators")

        elif from_role == "operator":
            if to_role == "operator":
                if int(dist_data.to_user_id) == from_user_id:
                    raise ValueError("You cannot distribute to yourself")
                if str(to_user.get("parent_id", "")) != str(from_user.get("parent_id", "")):
                    raise ValueError("You can only distribute to operators in the same cluster")
            else:
                raise ValueError("Operators can only distribute to other operators in the same cluster")

        validated_devices: List[Dict[str, Any]] = []
        open_lock_device_ids: Set[str] = set()
        pending_blocked: set = set()

        if from_role not in ["super_admin", "manager", "pdic_staff"]:
            blocked_rows = (await session.execute(
                text("""SELECT dd.device_id
                   FROM distribution_devices dd
                   INNER JOIN distributions d ON dd.distribution_id = d.distribution_id
                   WHERE d.to_user_id = :uid AND d.status = :status"""),
                {"uid": from_user_id, "status": DistributionStatus.PENDING_RECEIPT.value}
            )).mappings().all()
            for r in blocked_rows:
                pending_blocked.add(str(r["device_id"]))

        lock_ids_int = [int(x) for x in dist_data.device_ids]
        lph = ",".join([f":l_{i}" for i in range(len(lock_ids_int))])
        lparams = {f"l_{i}": did for i, did in enumerate(lock_ids_int)}
        lparams["s1"] = DistributionStatus.PENDING_RECEIPT.value
        lparams["s2"] = DistributionStatus.DISPUTED.value
        lock_rows = (await session.execute(
            text(f"""SELECT dd.device_id
                FROM distribution_devices dd
                INNER JOIN distributions d ON dd.distribution_id = d.distribution_id
                WHERE d.status IN (:s1, :s2)
                  AND dd.device_id IN ({lph})"""),
            lparams
        )).mappings().all()
        for lr in lock_rows:
            open_lock_device_ids.add(str(lr["device_id"]))

        device_ids_int = [int(x) for x in dist_data.device_ids]
        dph = ",".join([f":d_{i}" for i in range(len(device_ids_int))])
        dparams = {f"d_{i}": did for i, did in enumerate(device_ids_int)}
        dev_rows = (await session.execute(
            text(f"SELECT * FROM devices WHERE id IN ({dph})"), dparams
        )).mappings().all()
        device_rows = {str(r["id"]): dict(r) for r in dev_rows}

        for dev_id in dist_data.device_ids:
            device = device_rows.get(str(dev_id))
            if not device:
                raise ValueError(f"Device {dev_id} not found")
            if device.get("status") == DeviceStatus.DEFECTIVE.value:
                raise ValueError(f"Device {device['device_id']} is marked defective and cannot be transferred")
            if str(dev_id) in open_lock_device_ids:
                raise ValueError(f"Device {device['device_id']} is already in an unconfirmed or disputed distribution")
            if from_role in ["super_admin", "manager", "pdic_staff"]:
                if device["status"] != DeviceStatus.AVAILABLE.value:
                    raise ValueError(f"Device {device['device_id']} is not available")
            else:
                if int(device.get("current_holder_id", 0)) != from_user_id:
                    raise ValueError(f"Device {device['device_id']} is not in your possession")
                if str(dev_id) in pending_blocked:
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

        now_dt = datetime.now().replace(tzinfo=None)
        now = now_dt
        today = now_dt.date()
        distribution_date = dist_data.date_of_distribution if dist_data.date_of_distribution else today
        dist_id = generate_distribution_id()

        result = await session.execute(
            text("""INSERT INTO distributions (distribution_id, device_ids, device_count,
                from_user_id, from_user_name, from_user_type, to_user_id, to_user_name, to_user_type,
                status, request_date, date_of_distribution, approval_date, approved_by, approved_by_name,
                notes, created_by, created_at, updated_at)
            VALUES (:dist_id, :device_ids, :device_count, :from_user_id, :from_user_name, :from_user_type,
                :to_user_id, :to_user_name, :to_user_type, :status, :request_date, :date_of_distribution,
                :approval_date, :approved_by, :approved_by_name, :notes, :created_by, :created_at, :updated_at)"""),
            {
                "dist_id": dist_id,
                "device_ids": json.dumps(dist_data.device_ids),
                "device_count": len(dist_data.device_ids),
                "from_user_id": from_user_id,
                "from_user_name": from_user["name"],
                "from_user_type": role_to_type.get(from_user["role"], "noc"),
                "to_user_id": int(to_user["id"]),
                "to_user_name": to_user["name"],
                "to_user_type": role_to_type.get(to_user["role"], "pdic_staff"),
                "status": DistributionStatus.PENDING_RECEIPT.value,
                "request_date": now,
                "date_of_distribution": distribution_date,
                "approval_date": today,
                "approved_by": from_user_id,
                "approved_by_name": from_user["name"],
                "notes": dist_data.notes,
                "created_by": from_user_id,
                "created_at": now,
                "updated_at": now,
            }
        )
        new_id = result.lastrowid

        dd_rows = [{"dist_id": dist_id, "device_id": int(dev_id), "now": now} for dev_id in dist_data.device_ids]
        if dd_rows:
            await session.execute(
                text("INSERT INTO distribution_devices (distribution_id, device_id, created_at) VALUES (:dist_id, :device_id, :now)"),
                dd_rows
            )

        manifest_file = None
        try:
            manifest_file = _build_distribution_manifest(
                distribution_id=dist_id,
                devices=validated_devices,
                from_user_name=from_user.get("name", "Unknown"),
                to_user_name=to_user.get("name", "Unknown"),
                created_at_iso=now,
            )
            await session.execute(
                text("UPDATE distributions SET manifest_file = :mf WHERE id = :id"),
                {"mf": manifest_file, "id": int(new_id)}
            )
        except Exception:
            manifest_file = None

        await session.commit()

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

    distribution = await get_distribution_by_id(new_id)
    if not distribution:
        distribution = await get_distribution_by_code(dist_id)
    return distribution


async def update_distribution_status(
    distribution_id: str, status: str, user: Dict[str, Any], notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        return None

    now = datetime.now().replace(tzinfo=None)
    user_id = int(user.get("id", user.get("_id", 0)))
    user_role = str(user.get("role", "")).lower()

    async with async_session_factory() as session:
        update_parts = ["status = :status", "updated_at = :now"]
        params: Dict[str, Any] = {"status": status, "now": now, "id": int(distribution_id)}

        now_date = now.date()
        if status == DistributionStatus.APPROVED.value:
            update_parts.extend(["approval_date = :now2", "approved_by = :uid", "approved_by_name = :uname"])
            params["now2"] = now_date
            params["uid"] = user_id
            params["uname"] = user["name"]

        elif status == DistributionStatus.DELIVERED.value:
            update_parts.append("delivery_date = :now2")
            params["now2"] = now_date

        if notes:
            update_parts.append("notes = :notes")
            params["notes"] = notes

        set_clause = ", ".join(update_parts)
        await session.execute(text(f"UPDATE distributions SET {set_clause} WHERE id = :id"), params)
        await session.commit()

    await notification_service.create_notification(
        user_id=str(dist["from_user_id"]),
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

    user_id = int(user.get("id", user.get("_id", 0)))

    if int(dist["to_user_id"]) != user_id:
        raise ValueError("Only the recipient can confirm receipt of this distribution")

    if dist["status"] != DistributionStatus.PENDING_RECEIPT.value:
        raise ValueError("This distribution is not awaiting receipt confirmation")

    device_ids = dist.get("device_ids") or []
    if isinstance(device_ids, str):
        try:
            device_ids = json.loads(device_ids)
        except (json.JSONDecodeError, TypeError):
            device_ids = []

    now = datetime.now().replace(tzinfo=None)

    role_to_type = {
        "super_admin": "noc", "manager": "noc", "pdic_staff": "pdic_staff",
        "sub_distribution_manager": "sub_distribution_manager",
        "sub_distributor": "sub_distributor", "cluster": "cluster", "operator": "operator"
    }

    if received:
        async with async_session_factory() as session:
            to_user_row = (await session.execute(
                text("SELECT role FROM users WHERE id = :id"), {"id": int(dist["to_user_id"])}
            )).mappings().first()
            to_user_role = to_user_row["role"] if to_user_row else "operator"

        device_status_for_recipient = (
            DeviceStatus.IN_USE.value if to_user_role == "operator" else DeviceStatus.DISTRIBUTED.value
        )
        holder_type = role_to_type.get(to_user_role, "pdic_staff")
        await _bulk_update_device_holders(
            device_ids=device_ids,
            holder_id=int(dist["to_user_id"]),
            holder_name=dist["to_user_name"],
            holder_type=holder_type,
            location=dist["to_user_name"],
            status=device_status_for_recipient,
            performed_by=user_id,
            performed_by_name=user["name"],
            from_user_id=int(dist["from_user_id"]),
            from_user_name=dist["from_user_name"],
            notes=f"Receipt confirmed for distribution {dist['distribution_id']}",
        )

        async with async_session_factory() as session:
            await session.execute(
                text("""UPDATE distributions
                   SET status = :status, approval_date = :today, approved_by = :uid, approved_by_name = :uname,
                       notes = COALESCE(:notes, notes), updated_at = :now2
                   WHERE id = :id"""),
                {
                    "status": DistributionStatus.APPROVED.value,
                    "today": now.date(),
                    "uid": user_id,
                    "uname": user["name"],
                    "notes": notes,
                    "now2": now,
                    "id": int(distribution_id)
                }
            )
            await session.commit()

        await notification_service.create_notification(
            user_id=str(dist["from_user_id"]),
            title="Receipt Confirmed",
            message=f"{user['name']} confirmed receipt of {dist['device_count']} device(s) "
                    f"(Distribution: {dist['distribution_id']}).",
            notification_type="success", category="distribution",
            link=f"/distributions?distributionId={distribution_id}"
        )

    else:
        async with async_session_factory() as session:
            await session.execute(
                text("""UPDATE distributions
                   SET status = 'disputed', notes = COALESCE(:notes, notes), updated_at = :now
                   WHERE id = :id"""),
                {"notes": notes, "now": now, "id": int(distribution_id)}
            )
            admin_rows = (await session.execute(
                text("SELECT id FROM users WHERE role IN ('super_admin', 'manager', 'pdic_staff') AND status = 'active'")
            )).mappings().all()
            await session.commit()

        sender_label = (
            "PDIC" if str(dist.get("from_user_type") or "").lower() in {"noc", "pdic_staff"}
            else dist.get("from_user_name")
        )
        dispute_msg = (
            f"DISPUTE: {user['name']} reported NOT receiving {dist['device_count']} device(s) "
            f"sent by {sender_label}. Distribution: {dist['distribution_id']}."
        )
        await notification_service.bulk_create_notifications([
            {
                "user_id": str(r["id"]),
                "title": "Device Not Received — Dispute",
                "message": dispute_msg,
                "notification_type": "error",
                "category": "distribution",
                "link": f"/distributions?distributionId={distribution_id}"
            }
            for r in admin_rows
        ] + [
            {
                "user_id": str(dist["from_user_id"]),
                "title": "Receipt Disputed",
                "message": f"{user['name']} reported NOT receiving your device(s) in distribution "
                           f"{dist['distribution_id']}. Admin, manager, and PDIC staff have been notified.",
                "notification_type": "error",
                "category": "distribution",
                "link": f"/distributions?distributionId={distribution_id}"
            }
        ])

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
    now = datetime.now().replace(tzinfo=None)

    async with async_session_factory() as session:
        await session.execute(
            text("""UPDATE distributions
               SET status = :status, notes = COALESCE(:notes, notes), updated_at = :now, delivery_date = :today
               WHERE id = :id"""),
            {"status": DistributionStatus.REJECTED.value, "notes": notes, "now": now, "today": now.date(), "id": int(distribution_id)}
        )
        await session.commit()

        device_ids = dist.get("device_ids", []) or []
        if device_ids:
            await _bulk_update_device_holders(
                device_ids=device_ids,
                holder_id=dist["from_user_id"],
                holder_name=dist["from_user_name"],
                holder_type=sender_holder_type,
                location=dist["from_user_name"],
                status=sender_status,
                performed_by=int(user.get("id", user.get("_id", 0))),
                performed_by_name=str(user.get("name") or "PDIC"),
                from_user_id=int(dist.get("to_user_id") or 0),
                from_user_name=dist.get("to_user_name"),
                notes=f"Disputed return confirmed for distribution {dist.get('distribution_id')}",
            )

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
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        return False
    user_id = int(user.get("id", user.get("_id", 0)))
    if int(dist["created_by"]) != user_id and user.get("role") not in ["super_admin", "manager"]:
        raise ValueError("Only the creator can cancel this distribution")
    if dist["status"] == DistributionStatus.CANCELLED.value:
        raise ValueError("Distribution is already cancelled")
    if dist["status"] == DistributionStatus.APPROVED.value:
        raise ValueError("Cannot cancel a distribution that has already been confirmed")

    async with async_session_factory() as session:
        now = datetime.now().replace(tzinfo=None)
        await session.execute(
            text("UPDATE distributions SET status = :status, updated_at = :now WHERE id = :id"),
            {"status": DistributionStatus.CANCELLED.value, "now": now, "id": int(distribution_id)}
        )
        await session.commit()
    return True


async def get_distribution_manifest_file(distribution_id: str, user: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Get manifest file metadata if requester is permitted to access distribution."""
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        return None

    role = user.get("role")
    user_id = int(user.get("id", user.get("_id", 0)))
    if role not in ["super_admin", "manager", "pdic_staff"]:
        if user_id not in [int(dist.get("from_user_id", 0)), int(dist.get("to_user_id", 0))]:
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
    user_id = int(user.get("id", user.get("_id", 0)))

    if role not in ["super_admin", "manager", "pdic_staff"]:
        if user_id not in [int(dist.get("from_user_id", 0)), int(dist.get("to_user_id", 0))]:
            raise ValueError("You are not allowed to access this distribution export")

    device_ids = dist.get("device_ids") or []
    if isinstance(device_ids, str):
        try:
            device_ids = json.loads(device_ids)
        except (json.JSONDecodeError, TypeError):
            device_ids = []

    devices: List[Dict[str, Any]] = []
    if device_ids:
        ph = ",".join([f":d_{i}" for i in range(len(device_ids))])
        params = {f"d_{i}": int(did) for i, did in enumerate(device_ids)}
        async with async_session_factory() as session:
            rows = (await session.execute(
                text(f"SELECT id, device_id, device_type, manufacturer, model, serial_number, mac_address, nuid FROM devices WHERE id IN ({ph})"),
                params
            )).mappings().all()
            devices = [dict(r) for r in rows]

    return _build_distribution_mac_nuid_file(
        distribution=dist,
        devices=devices,
        file_format=file_format,
    )


async def get_pending_distributions() -> List[Dict[str, Any]]:
    async with async_session_factory() as session:
        rows = (await session.execute(
            text("SELECT * FROM distributions WHERE status = :status ORDER BY created_at DESC LIMIT 1000"),
            {"status": DistributionStatus.PENDING.value}
        )).mappings().all()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("device_ids"):
                try:
                    d["device_ids"] = json.loads(d["device_ids"])
                except (json.JSONDecodeError, TypeError):
                    d["device_ids"] = []
            result.append(d)
        return result


async def get_distribution_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, int]:
    async with async_session_factory() as session:
        params: Dict[str, Any] = {}
        conditions = []
        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date
        where = " AND ".join(conditions) if conditions else "1=1"

        by_status = {}
        rows = (await session.execute(
            text(f"SELECT status, COUNT(*) AS cnt FROM distributions WHERE {where} GROUP BY status"),
            params
        )).mappings().all()
        for row in rows:
            by_status[row["status"]] = row["cnt"]

        total = sum(by_status.values())
        return {
            "total": total,
            "pending": by_status.get("pending", 0),
            "pending_receipt": by_status.get("pending_receipt", 0),
            "approved": by_status.get("approved", 0),
            "delivered": by_status.get("delivered", 0),
            "rejected": by_status.get("rejected", 0),
            "disputed": by_status.get("disputed", 0),
        }


async def sync_approved_distributions(user: Dict[str, Any]) -> Dict[str, Any]:
    async with async_session_factory() as session:
        rows = (await session.execute(
            text("SELECT * FROM distributions WHERE status = :status LIMIT 5000"),
            {"status": DistributionStatus.APPROVED.value}
        )).mappings().all()
        distributions = [dict(r) for r in rows]
        synced_count = 0
        errors = []
        user_id = int(user.get("id", user.get("_id", 0)))

        for dist in distributions:
            device_ids = dist.get("device_ids", "[]")
            if isinstance(device_ids, str):
                try:
                    device_ids = json.loads(device_ids)
                except (json.JSONDecodeError, TypeError):
                    device_ids = []

            if device_ids:
                updated = await _bulk_update_device_holders(
                    device_ids=device_ids,
                    holder_id=dist["to_user_id"],
                    holder_name=dist["to_user_name"],
                    holder_type=dist.get("to_user_type", "pdic_staff"),
                    location=dist["to_user_name"],
                    status=DeviceStatus.DISTRIBUTED.value,
                    performed_by=user_id,
                    performed_by_name=user.get("name", "System"),
                    from_user_id=dist.get("from_user_id"),
                    from_user_name=dist.get("from_user_name"),
                    notes=f"Synced from approved distribution {dist.get('distribution_id', '')}",
                )
                synced_count += len(updated)

    return {"total_distributions": len(distributions), "devices_synced": synced_count, "errors": errors}

