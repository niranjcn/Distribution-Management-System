from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import select, func, and_, or_, text, String

from app.database_sqlalchemy import async_session_factory
from app.db_models.device import Device, DeviceHistory
from app.models.device import DeviceCreate, DeviceUpdate, DeviceStatus, HolderType
from app.utils.helpers import get_pagination, generate_device_id



async def _get_locked_distribution_device_ids(session) -> set:
    result = await session.execute(text("""
        SELECT dd.device_id
        FROM distribution_devices dd
        INNER JOIN distributions d ON dd.distribution_id = d.distribution_id
        WHERE d.status IN ('pending_receipt', 'disputed')
    """))
    return {row[0] for row in result}


def _augment_device_record(device: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not device:
        return device
    metadata_raw = device.get("metadata")
    metadata_obj = None
    if isinstance(metadata_raw, str) and metadata_raw.strip():
        try:
            metadata_obj = json.loads(metadata_raw)
        except Exception:
            metadata_obj = None
    elif isinstance(metadata_raw, dict):
        metadata_obj = metadata_raw

    box_type = None
    if isinstance(metadata_obj, dict):
        raw_box = str(metadata_obj.get("box_type") or "").strip().upper()
        if raw_box in {"HD", "OTT"}:
            box_type = raw_box
    device["box_type"] = box_type
    return device


async def get_devices(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    device_type: Optional[str] = None,
    manufacturer: Optional[str] = None,
    holder_id: Optional[str] = None,
    holder_ids: Optional[List[str]] = None,
    search_by: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """Get all devices with pagination and filters"""
    async with async_session_factory() as session:
        conditions = []

        if status:
            conditions.append(Device.status == status)
        if device_type:
            conditions.append(Device.device_type == _normalize_device_type_filter(device_type))
        if manufacturer:
            conditions.append(Device.manufacturer == manufacturer)
        if holder_id:
            conditions.append(Device.current_holder_id == int(holder_id))
        if holder_ids:
            normalized = [int(h) for h in holder_ids if str(h).strip()]
            if normalized:
                conditions.append(Device.current_holder_id.in_(normalized))
        if start_date:
            conditions.append(Device.created_at >= start_date)
        if end_date:
            conditions.append(Device.created_at <= end_date)
        if search:
            pattern = f"%{str(search).strip()}%"
            search_field_map = {
                "nuid": Device.nuid, "mac": Device.mac_address, "mac_address": Device.mac_address,
                "serial": Device.serial_number, "serial_number": Device.serial_number,
                "vendor": Device.manufacturer, "manufacturer": Device.manufacturer,
                "type": Device.device_type, "device_type": Device.device_type,
                "device_id": Device.device_id, "model": Device.model,
            }
            normalized_search_by = str(search_by or "").strip().lower()
            selected_column = search_field_map.get(normalized_search_by)

            if selected_column:
                conditions.append(selected_column.cast(String).like(pattern))
            else:
                conditions.append(or_(
                    Device.device_id.cast(String).like(pattern),
                    Device.serial_number.cast(String).like(pattern),
                    Device.mac_address.cast(String).like(pattern),
                    Device.model.cast(String).like(pattern),
                    Device.nuid.cast(String).like(pattern),
                    Device.manufacturer.cast(String).like(pattern),
                    Device.device_type.cast(String).like(pattern),
                ))

        where = and_(*conditions) if conditions else True

        count_q = select(func.count()).select_from(Device).where(where)
        total = (await session.execute(count_q)).scalar()

        offset = (page - 1) * page_size
        q = (
            select(Device)
            .where(where)
            .order_by(Device.created_at.desc(), Device.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await session.execute(q)).scalars().all()

        devices = [_augment_device_record(r.to_dict()) for r in rows]
        return {
            "data": devices,
            "pagination": get_pagination(page, page_size, total),
        }


async def get_device_by_id(device_id: str) -> Optional[Dict[str, Any]]:
    """Get device by ID"""
    async with async_session_factory() as session:
        inst = await session.get(Device, int(device_id))
        return _augment_device_record(inst.to_dict()) if inst else None


async def get_device_by_serial(serial_number: str) -> Optional[Dict[str, Any]]:
    """Get device by serial number"""
    async with async_session_factory() as session:
        q = select(Device).where(Device.serial_number == serial_number)
        inst = (await session.execute(q)).scalar_one_or_none()
        return _augment_device_record(inst.to_dict()) if inst else None


async def create_device(device_data: DeviceCreate, created_by: int, created_by_name: str) -> Dict[str, Any]:
    """Create a new device"""
    async with async_session_factory() as session:
        is_sb = device_data.device_type.value == "Set-top box"
        if is_sb and not (device_data.nuid and device_data.nuid.strip()):
            raise ValueError("NUID is required for SB devices")
        if is_sb:
            nuid_value = str(device_data.nuid or "").strip()
            existing = (await session.execute(select(Device.id).where(Device.nuid == nuid_value))).scalar_one_or_none()
            if existing:
                raise ValueError("NUID already exists")

        serial_number = (device_data.serial_number or "").strip()
        mac_address = (device_data.mac_address or "").strip()
        box_type = (device_data.box_type or "").strip().upper() if is_sb else None

        if is_sb:
            serial_number = None
            mac_address = None
        else:
            if not serial_number:
                raise ValueError("Serial number is required for non-SB devices")
            device_data.nuid = None

        if serial_number:
            existing = (await session.execute(select(Device.id).where(Device.serial_number == serial_number))).scalar_one_or_none()
            if existing:
                raise ValueError("Serial number already exists")

        if mac_address:
            existing = (await session.execute(select(Device.id).where(Device.mac_address == mac_address))).scalar_one_or_none()
            if existing:
                raise ValueError("MAC address already exists")

        now = datetime.now().replace(tzinfo=None)
        dev_id = generate_device_id(device_data.device_type.value)
        metadata_payload = dict(device_data.metadata or {})
        if is_sb and box_type in {"HD", "OTT"}:
            metadata_payload["box_type"] = box_type
        metadata_json = json.dumps(metadata_payload) if metadata_payload else None
        purchase_date = device_data.purchase_date
        warranty_expiry = device_data.warranty_expiry

        band_type_val = (
            None if is_sb else (
                device_data.band_type.value if hasattr(device_data.band_type, "value")
                else (device_data.band_type or "single_band")
            )
        )

        d = Device(
            device_id=dev_id,
            device_type=device_data.device_type.value,
            model=device_data.model,
            serial_number=serial_number,
            mac_address=mac_address,
            manufacturer=device_data.manufacturer,
            band_type=band_type_val,
            nuid=device_data.nuid,
            status=DeviceStatus.AVAILABLE.value,
            current_location="PDIC",
            current_holder_id=None,
            current_holder_name="PDIC (Distribution)",
            current_holder_type=HolderType.NOC.value,
            registered_by_name=created_by_name,
            purchase_date=purchase_date,
            warranty_expiry=warranty_expiry,
            device_metadata=metadata_json,
            created_at=now,
            updated_at=now,
        )
        session.add(d)
        await session.flush()
        new_id = d.id

        await _add_device_history(session, new_id, "registered", performed_by=created_by,
                                  performed_by_name=created_by_name, status_after=DeviceStatus.AVAILABLE.value,
                                  location="PDIC", notes="Device registered in system")
        await session.commit()

        # Read back using same session
        inst = await session.get(Device, new_id)
        if inst:
            return _augment_device_record(inst.to_dict())

        return {
            "id": new_id, "device_id": dev_id, "device_type": device_data.device_type.value,
            "model": device_data.model, "serial_number": serial_number, "mac_address": mac_address,
            "manufacturer": device_data.manufacturer, "band_type": band_type_val,
            "nuid": device_data.nuid, "status": DeviceStatus.AVAILABLE.value,
            "current_location": "PDIC", "current_holder_id": None,
            "current_holder_name": "PDIC (Distribution)", "current_holder_type": HolderType.NOC.value,
            "registered_by_name": created_by_name, "metadata": metadata_payload if metadata_payload else None,
            "created_at": now, "updated_at": now,
        }


async def update_device(device_id: str, device_data: DeviceUpdate) -> Optional[Dict[str, Any]]:
    """Update device"""
    async with async_session_factory() as session:
        inst = await session.get(Device, int(device_id))
        if not inst:
            return None

        current = inst.to_dict()
        data = device_data.model_dump(exclude_unset=True)

        next_device_type = data.get("device_type", current.get("device_type"))
        if hasattr(next_device_type, "value"):
            next_device_type = next_device_type.value
        next_nuid = data.get("nuid", current.get("nuid"))
        next_box_type = data.get("box_type", current.get("box_type"))

        if next_device_type == "Set-top box" and not (next_nuid and str(next_nuid).strip()):
            raise ValueError("NUID is required for SB devices")
        if next_device_type == "Set-top box":
            normalized_box = str(next_box_type or "").strip().upper()
            if normalized_box not in {"HD", "OTT"}:
                raise ValueError("box_type is required for SB devices and must be HD or OTT")
            normalized_nuid = str(next_nuid or "").strip()
            existing = (await session.execute(
                select(Device.id).where(and_(Device.nuid == normalized_nuid, Device.id != int(device_id)))
            )).scalar_one_or_none()
            if existing:
                raise ValueError("NUID already exists")

        if next_device_type == "Set-top box":
            inst.serial_number = None
        elif "serial_number" in data and data["serial_number"] is not None:
            serial_number = str(data["serial_number"]).strip()
            if not serial_number:
                raise ValueError("Serial number cannot be empty")
            existing = (await session.execute(
                select(Device.id).where(and_(Device.serial_number == serial_number, Device.id != int(device_id)))
            )).scalar_one_or_none()
            if existing:
                raise ValueError("Serial number already exists")
            inst.serial_number = serial_number

        if next_device_type == "Set-top box":
            inst.mac_address = None
        elif "mac_address" in data and data["mac_address"] is not None:
            mac_address = str(data["mac_address"]).strip()
            if not mac_address:
                raise ValueError("MAC address cannot be empty")
            existing = (await session.execute(
                select(Device.id).where(and_(Device.mac_address == mac_address, Device.id != int(device_id)))
            )).scalar_one_or_none()
            if existing:
                raise ValueError("MAC address already exists")
            inst.mac_address = mac_address

        for field in ["model", "manufacturer", "current_location"]:
            if field in data and data[field] is not None:
                setattr(inst, field, data[field])

        if "status" in data and data["status"] is not None:
            inst.status = data["status"].value if hasattr(data["status"], "value") else data["status"]
        if "device_type" in data and data["device_type"] is not None:
            inst.device_type = data["device_type"].value if hasattr(data["device_type"], "value") else data["device_type"]
        if "band_type" in data and data["band_type"] is not None:
            inst.band_type = data["band_type"].value if hasattr(data["band_type"], "value") else data["band_type"]
        elif next_device_type == "Set-top box":
            inst.band_type = None
        if "warranty_expiry" in data and data["warranty_expiry"] is not None:
            inst.warranty_expiry = data["warranty_expiry"]

        if "metadata" in data and data["metadata"] is not None:
            base_metadata = data["metadata"] if isinstance(data["metadata"], dict) else {}
        else:
            existing_metadata = current.get("metadata")
            if isinstance(existing_metadata, str) and existing_metadata.strip():
                try:
                    base_metadata = json.loads(existing_metadata)
                except Exception:
                    base_metadata = {}
            elif isinstance(existing_metadata, dict):
                base_metadata = dict(existing_metadata)
            else:
                base_metadata = {}

        if next_device_type == "Set-top box":
            normalized_box = str(data.get("box_type", next_box_type) or "").strip().upper()
            if normalized_box:
                base_metadata["box_type"] = normalized_box
            if "nuid" in data and data["nuid"] is not None:
                inst.nuid = str(data["nuid"]).strip() or None
        else:
            base_metadata.pop("box_type", None)
            inst.nuid = None

        inst.device_metadata = json.dumps(base_metadata) if base_metadata else None
        inst.updated_at = datetime.now().replace(tzinfo=None)
        await session.commit()

        return await get_device_by_id(device_id)


async def delete_device(device_id: str) -> bool:
    """Delete device"""
    async with async_session_factory() as session:
        inst = await session.get(Device, int(device_id))
        if not inst:
            return False
        await session.delete(inst)
        await session.execute(text("DELETE FROM device_history WHERE device_id = :did"), {"did": int(device_id)})
        await session.commit()
        return True


async def update_device_status(
    device_id: str,
    status: str,
    performed_by: int,
    performed_by_name: str,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update device status"""
    valid_statuses = {item.value for item in DeviceStatus}
    if status not in valid_statuses:
        raise ValueError(
            f"Invalid device status '{status}'. Allowed values: {', '.join(sorted(valid_statuses))}"
        )

    async with async_session_factory() as session:
        inst = await session.get(Device, int(device_id))
        if not inst:
            return None

        device = inst.to_dict()
        old_status = device.get("status")
        now = datetime.now().replace(tzinfo=None)

        inst.status = status
        inst.updated_at = now

        await _add_device_history(session, int(device_id), "status_changed",
                                  performed_by=performed_by, performed_by_name=performed_by_name,
                                  status_before=old_status, status_after=status,
                                  location=device.get("current_location"),
                                  notes=notes or f"Status changed from {old_status} to {status}")
        await session.commit()

        return await get_device_by_id(device_id)


async def _update_device_holder_impl(
    session,
    device_id: str,
    holder_id: Optional[int],
    holder_name: Optional[str],
    holder_type: str,
    location: str,
    status: str,
    performed_by: int,
    performed_by_name: str,
    from_user_id: Optional[int] = None,
    from_user_name: Optional[str] = None,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    inst = await session.get(Device, int(device_id))
    if not inst:
        return None

    device = inst.to_dict()
    old_status = device.get("status")
    now = datetime.now().replace(tzinfo=None)

    inst.current_holder_id = holder_id
    inst.current_holder_name = holder_name
    inst.current_holder_type = holder_type
    inst.current_location = location
    inst.status = status
    inst.updated_at = now

    await _add_device_history(session, int(device_id), "distributed",
                              from_user_id=from_user_id, from_user_name=from_user_name,
                              to_user_id=holder_id, to_user_name=holder_name,
                              performed_by=performed_by, performed_by_name=performed_by_name,
                              status_before=old_status, status_after=status,
                              location=location, notes=notes)
    await session.commit()

    return await get_device_by_id(device_id)


async def update_device_holder(
    device_id: str,
    holder_id: Optional[int],
    holder_name: Optional[str],
    holder_type: str,
    location: str,
    status: str,
    performed_by: int,
    performed_by_name: str,
    from_user_id: Optional[int] = None,
    from_user_name: Optional[str] = None,
    notes: Optional[str] = None,
    db_session=None
) -> Optional[Dict[str, Any]]:
    """Update device holder (for distributions)"""
    if db_session is None:
        async with async_session_factory() as session:
            return await _update_device_holder_impl(
                session, device_id, holder_id, holder_name, holder_type, location, status,
                performed_by, performed_by_name, from_user_id=from_user_id,
                from_user_name=from_user_name, notes=notes
            )
    return await _update_device_holder_impl(
        db_session, device_id, holder_id, holder_name, holder_type, location, status,
        performed_by, performed_by_name, from_user_id=from_user_id,
        from_user_name=from_user_name, notes=notes
    )


async def get_available_devices(holder_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get available devices for distribution (PDIC stock only)"""
    async with async_session_factory() as session:
        q = select(Device).where(Device.status == DeviceStatus.AVAILABLE.value)
        if holder_id:
            q = q.where(Device.current_holder_id == int(holder_id))
        q = q.order_by(Device.created_at.desc()).limit(2000)
        rows = (await session.execute(q)).scalars().all()
        locked_ids = await _get_locked_distribution_device_ids(session)
        return [
            _augment_device_record(r.to_dict())
            for r in rows
            if r.id not in locked_ids
        ]


def _normalize_device_type_filter(device_type: str) -> str:
    normalized = device_type.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    if normalized in {"settopbox", "setupbox", "sb", "stb"}:
        return "Set-top box"
    return device_type


async def get_devices_for_replacement(
    exclude_device_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    device_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Get devices eligible as replacements (available or returned status) with pagination and search"""
    async with async_session_factory() as session:
        conditions = [Device.status.in_([DeviceStatus.AVAILABLE.value, DeviceStatus.RETURNED.value])]

        if exclude_device_id:
            conditions.append(Device.id != int(exclude_device_id))

        if device_type:
            conditions.append(Device.device_type == _normalize_device_type_filter(device_type))

        if search:
            pattern = f"%{str(search).strip()}%"
            search_field_map = {
                "nuid": Device.nuid, "mac": Device.mac_address, "mac_address": Device.mac_address,
                "serial": Device.serial_number, "serial_number": Device.serial_number,
                "vendor": Device.manufacturer, "manufacturer": Device.manufacturer,
                "type": Device.device_type, "device_type": Device.device_type,
                "device_id": Device.device_id, "model": Device.model,
            }
            normalized_search_by = str(search_by or "").strip().lower()
            selected_column = search_field_map.get(normalized_search_by)

            if selected_column:
                conditions.append(selected_column.cast(String).like(pattern))
            else:
                conditions.append(or_(
                    Device.device_id.cast(String).like(pattern),
                    Device.serial_number.cast(String).like(pattern),
                    Device.mac_address.cast(String).like(pattern),
                    Device.model.cast(String).like(pattern),
                    Device.nuid.cast(String).like(pattern),
                    Device.manufacturer.cast(String).like(pattern),
                    Device.device_type.cast(String).like(pattern),
                ))

        where = and_(*conditions)

        count_q = select(func.count()).select_from(Device).where(where)
        total = (await session.execute(count_q)).scalar()

        offset = (page - 1) * page_size
        q = (
            select(Device)
            .where(where)
            .order_by(Device.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await session.execute(q)).scalars().all()

        devices = [_augment_device_record(r.to_dict()) for r in rows]
        return {
            "data": devices,
            "pagination": get_pagination(page, page_size, total),
        }


async def get_held_devices(holder_id: str) -> List[Dict[str, Any]]:
    """Get all devices currently held by a user (any status) — for sub-level redistribution"""
    async with async_session_factory() as session:
        q = (select(Device).where(Device.current_holder_id == int(holder_id))
             .order_by(Device.updated_at.desc()).limit(2000))
        rows = (await session.execute(q)).scalars().all()
        locked_ids = await _get_locked_distribution_device_ids(session)
        return [
            _augment_device_record(r.to_dict())
            for r in rows
            if r.id not in locked_ids
        ]


async def get_user_device_overview(user_id: str, user_role: str, limit: int = 100) -> Dict[str, Any]:
    """Get comprehensive device overview: devices in hand + under hierarchy + distribution stats."""
    async with async_session_factory() as session:
        uid = int(user_id)

        # Devices directly held by this user
        held_q = select(Device).where(Device.current_holder_id == uid).order_by(Device.updated_at.desc()).limit(limit)
        held_rows = (await session.execute(held_q)).scalars().all()
        held_devices = [r.to_dict() for r in held_rows]
        held_device_ids = {str(d["id"]) for d in held_devices}

        # Defective devices reported by this user
        defective_q = text("""
            SELECT d.* FROM devices d
            JOIN defects def ON CAST(def.device_id AS CHAR) = CAST(d.id AS CHAR)
            WHERE (CAST(def.reported_by AS CHAR) = :uid OR CAST(d.current_holder_id AS CHAR) = :uid2)
            AND d.status = 'defective'
        """)
        def_rows = (await session.execute(defective_q, {"uid": user_id, "uid2": user_id})).mappings().all()
        for row in def_rows:
            row_dict = dict(row)
            if str(row_dict.get("id")) not in held_device_ids:
                held_devices.append(row_dict)
                held_device_ids.add(str(row_dict.get("id")))

        subordinate_devices = []

        if user_role == "sub_distributor":
            cluster_q = text("""
                SELECT d.* FROM devices d
                JOIN users u ON CAST(d.current_holder_id AS CHAR) = CAST(u.id AS CHAR)
                WHERE u.parent_id = :uid AND u.role = 'cluster'
                ORDER BY d.updated_at DESC LIMIT :lim
            """)
            cluster_rows = (await session.execute(cluster_q, {"uid": uid, "lim": limit})).mappings().all()
            cluster_devices = [dict(r) for r in cluster_rows]
            cluster_device_ids = {str(d["id"]) for d in cluster_devices}

            operator_q = text("""
                SELECT d.* FROM devices d
                JOIN users op ON CAST(d.current_holder_id AS CHAR) = CAST(op.id AS CHAR)
                JOIN users cl ON op.parent_id = cl.id
                WHERE cl.parent_id = :uid AND op.role = 'operator'
                ORDER BY d.updated_at DESC LIMIT :lim
            """)
            operator_rows = (await session.execute(operator_q, {"uid": uid, "lim": limit})).mappings().all()
            operator_devices = [dict(r) for r in operator_rows]
            operator_device_ids = {str(d["id"]) for d in operator_devices}

            defective_sub_q = text("""
                SELECT DISTINCT d.* FROM devices d
                JOIN defects def ON CAST(def.device_id AS CHAR) = CAST(d.id AS CHAR)
                JOIN users op ON CAST(def.reported_by AS CHAR) = CAST(op.id AS CHAR)
                LEFT JOIN users cl ON op.parent_id = cl.id
                WHERE ((op.role = 'operator' AND cl.parent_id = :uid)
                  OR (op.role = 'cluster' AND op.parent_id = :uid2))
                AND d.status = 'defective'
                LIMIT :lim
            """)
            def_sub_rows = (await session.execute(defective_sub_q, {"uid": uid, "uid2": uid, "lim": limit})).mappings().all()

            all_sub_ids = cluster_device_ids | operator_device_ids
            for r in def_sub_rows:
                rd = dict(r)
                if str(rd["id"]) not in all_sub_ids and str(rd["id"]) not in held_device_ids:
                    operator_devices.append(rd)
                    all_sub_ids.add(str(rd["id"]))

            subordinate_devices = cluster_devices + operator_devices

        elif user_role == "sub_distribution_manager":
            mgr_q = text("SELECT parent_id FROM users WHERE id = :uid")
            mgr_row = (await session.execute(mgr_q, {"uid": uid})).mappings().first()
            scope_root_id = str(uid)
            if mgr_row and mgr_row.get("parent_id") is not None:
                scope_root_id = str(mgr_row["parent_id"])

            descendants_q = text("""
                WITH RECURSIVE descendants AS (
                    SELECT id FROM users WHERE parent_id = :root
                    UNION ALL
                    SELECT u.id FROM users u
                    INNER JOIN descendants d ON u.parent_id = d.id
                )
                SELECT id FROM descendants
            """)
            desc_rows = (await session.execute(descendants_q, {"root": int(scope_root_id)})).scalars().all()
            scope_user_ids = {scope_root_id} | {str(did) for did in desc_rows if did}
            scope_user_ids.discard(str(user_id))
            scoped_user_list = sorted(scope_user_ids)

            if scoped_user_list:
                import re
                ph = ",".join([f":su_{i}" for i in range(len(scoped_user_list))])
                params = {f"su_{i}": uid for i, uid in enumerate(scoped_user_list)}
                params["lim"] = limit
                sub_q = text(f"""
                    SELECT * FROM devices
                    WHERE CAST(current_holder_id AS CHAR) IN ({ph})
                    ORDER BY updated_at DESC
                    LIMIT :lim
                """)
                sub_rows = (await session.execute(sub_q, params)).mappings().all()
                subordinate_devices = [dict(r) for r in sub_rows]

                defective_sub_q = text(f"""
                    SELECT DISTINCT d.* FROM devices d
                    JOIN defects def ON CAST(def.device_id AS CHAR) = CAST(d.id AS CHAR)
                    WHERE CAST(def.reported_by AS CHAR) IN ({ph})
                    AND d.status = 'defective'
                    LIMIT :lim
                """)
                def_sub_rows = (await session.execute(defective_sub_q, params)).mappings().all()
            else:
                subordinate_devices = []
                def_sub_rows = []

            subordinate_device_ids = {str(d["id"]) for d in subordinate_devices}
            for r in def_sub_rows:
                rd = dict(r)
                did = str(rd["id"])
                if did not in subordinate_device_ids and did not in held_device_ids:
                    subordinate_devices.append(rd)
                    subordinate_device_ids.add(did)

        elif user_role == "cluster":
            sub_q = text("""
                SELECT d.* FROM devices d
                JOIN users u ON CAST(d.current_holder_id AS CHAR) = CAST(u.id AS CHAR)
                WHERE u.parent_id = :uid AND u.role = 'operator'
                ORDER BY d.updated_at DESC LIMIT :lim
            """)
            sub_rows = (await session.execute(sub_q, {"uid": uid, "lim": limit})).mappings().all()
            subordinate_devices = [dict(r) for r in sub_rows]
            sub_device_ids = {str(d["id"]) for d in subordinate_devices}

            defective_sub_q = text("""
                SELECT DISTINCT d.* FROM devices d
                JOIN defects def ON CAST(def.device_id AS CHAR) = CAST(d.id AS CHAR)
                JOIN users op ON CAST(def.reported_by AS CHAR) = CAST(op.id AS CHAR)
                WHERE op.parent_id = :uid AND op.role = 'operator'
                AND d.status = 'defective'
                LIMIT :lim
            """)
            def_sub_rows = (await session.execute(defective_sub_q, {"uid": uid, "lim": limit})).mappings().all()
            for r in def_sub_rows:
                rd = dict(r)
                if str(rd["id"]) not in sub_device_ids and str(rd["id"]) not in held_device_ids:
                    subordinate_devices.append(rd)
                    sub_device_ids.add(str(rd["id"]))

        # Distribution stats
        distrib_q = text("""
            SELECT
                SUM(CASE WHEN to_user_id = :uid1 THEN 1 ELSE 0 END) as received_count,
                COALESCE(SUM(CASE WHEN to_user_id = :uid2 THEN device_count ELSE 0 END), 0) as received_devices,
                SUM(CASE WHEN from_user_id = :uid3 THEN 1 ELSE 0 END) as sent_count,
                COALESCE(SUM(CASE WHEN from_user_id = :uid4 THEN device_count ELSE 0 END), 0) as sent_devices
            FROM distributions
            WHERE :uid5 IN (to_user_id, from_user_id)
        """)
        dist_row = (await session.execute(distrib_q, {"uid1": user_id, "uid2": user_id, "uid3": user_id, "uid4": user_id, "uid5": user_id})).mappings().first()

        total_distrib_received = int(dist_row["received_count"]) if dist_row and dist_row["received_count"] else 0
        total_devices_received = int(dist_row["received_devices"]) if dist_row and dist_row["received_devices"] else 0
        total_distrib_sent = int(dist_row["sent_count"]) if dist_row and dist_row["sent_count"] else 0
        total_devices_sent = int(dist_row["sent_devices"]) if dist_row and dist_row["sent_devices"] else 0

        # Deduplicate
        seen_ids = set()
        all_under_me = []
        for d in held_devices + subordinate_devices:
            if str(d["id"]) not in seen_ids:
                seen_ids.add(str(d["id"]))
                all_under_me.append(d)

        # Count queries
        held_count_q = select(func.count()).select_from(Device).where(Device.current_holder_id == uid)
        held_count = (await session.execute(held_count_q)).scalar()

        subordinate_count = 0
        if user_role == "sub_distributor":
            ct_q = text("""
                SELECT COUNT(*) FROM devices d
                JOIN users u ON CAST(d.current_holder_id AS CHAR) = CAST(u.id AS CHAR)
                WHERE (u.parent_id = :uid AND u.role = 'cluster')
                   OR (u.role = 'operator' AND u.parent_id IN (
                       SELECT id FROM users WHERE parent_id = :uid2 AND role = 'cluster'
                   ))
            """)
            subordinate_count = (await session.execute(ct_q, {"uid": uid, "uid2": uid})).scalar()
        elif user_role == "sub_distribution_manager":
            mgr_q2 = text("SELECT parent_id FROM users WHERE id = :uid")
            mgr_row2 = (await session.execute(mgr_q2, {"uid": uid})).mappings().first()
            scope_root_id2 = str(uid)
            if mgr_row2 and mgr_row2.get("parent_id") is not None:
                scope_root_id2 = str(mgr_row2["parent_id"])
            desc_q2 = text("""
                WITH RECURSIVE descendants AS (
                    SELECT id FROM users WHERE parent_id = :root
                    UNION ALL
                    SELECT u.id FROM users u
                    INNER JOIN descendants d ON u.parent_id = d.id
                )
                SELECT id FROM descendants
            """)
            desc_rows2 = (await session.execute(desc_q2, {"root": int(scope_root_id2)})).scalars().all()
            scope_user_ids2 = {scope_root_id2} | {str(did) for did in desc_rows2 if did}
            scope_user_ids2.discard(str(user_id))
            scoped_list2 = sorted(scope_user_ids2)
            if scoped_list2:
                ph2 = ",".join([f":sd_{i}" for i in range(len(scoped_list2))])
                params2 = {f"sd_{i}": sid for i, sid in enumerate(scoped_list2)}
                ct_q2 = text(f"SELECT COUNT(*) FROM devices WHERE CAST(current_holder_id AS CHAR) IN ({ph2})")
                subordinate_count = (await session.execute(ct_q2, params2)).scalar()
        elif user_role == "cluster":
            ct_q3 = text("""
                SELECT COUNT(*) FROM devices d
                JOIN users u ON CAST(d.current_holder_id AS CHAR) = CAST(u.id AS CHAR)
                WHERE u.parent_id = :uid AND u.role = 'operator'
            """)
            subordinate_count = (await session.execute(ct_q3, {"uid": uid})).scalar()

        return {
            "held_by_me": held_devices,
            "under_subordinates": subordinate_devices,
            "all_under_me": all_under_me,
            "stats": {
                "in_my_hand": held_count,
                "under_subordinates": subordinate_count,
                "total_in_chain": held_count + subordinate_count,
                "total_devices_received": total_devices_received,
                "total_devices_sent": total_devices_sent,
                "total_distributions_received": total_distrib_received,
                "total_distributions_sent": total_distrib_sent,
            },
        }


async def get_device_history(device_id: str) -> List[Dict[str, Any]]:
    """Get device history"""
    async with async_session_factory() as session:
        q = (select(DeviceHistory).where(DeviceHistory.device_id == int(device_id))
             .order_by(DeviceHistory.timestamp.desc()))
        rows = (await session.execute(q)).scalars().all()
        return [r.to_dict() for r in rows]


async def _add_device_history(
    session, device_id: int, action: str,
    performed_by: int = None, performed_by_name: str = None,
    from_user_id: Optional[int] = None, from_user_name: str = None,
    to_user_id: Optional[int] = None, to_user_name: str = None,
    status_before: str = None, status_after: str = None,
    location: str = None, notes: str = None
):
    """Add device history entry (uses existing session)"""
    now = datetime.now().replace(tzinfo=None)
    h = DeviceHistory(
        device_id=device_id, action=action,
        from_user_id=from_user_id, from_user_name=from_user_name,
        to_user_id=to_user_id, to_user_name=to_user_name,
        status_before=status_before, status_after=status_after,
        location=location, notes=notes,
        performed_by=performed_by, performed_by_name=performed_by_name,
        timestamp=now,
    )
    session.add(h)


async def repair_device_holder_from_history(device_id: str) -> Optional[Dict[str, Any]]:
    """Repair device holder by applying the most recent 'distributed' history entry."""
    async with async_session_factory() as session:
        hq = (select(DeviceHistory).where(and_(
            DeviceHistory.device_id == int(device_id), DeviceHistory.action == "distributed"
        )).order_by(DeviceHistory.timestamp.desc()).limit(1))
        entry = (await session.execute(hq)).scalar_one_or_none()
        if not entry:
            return None

        to_user_id = entry.to_user_id
        to_user_name = entry.to_user_name
        if not to_user_id:
            return None

        from app.db_models.auth import User
        user = await session.get(User, int(to_user_id))
        if not user:
            return None

        user_dict = user.to_dict()
        role_to_type = {
            "super_admin": "noc", "manager": "noc", "pdic_staff": "pdic_staff",
            "sub_distribution_manager": "sub_distribution_manager",
            "sub_distributor": "sub_distributor", "cluster": "cluster", "operator": "operator",
        }
        holder_type = role_to_type.get(user_dict["role"], "noc")
        device_status = DeviceStatus.IN_USE.value if user_dict["role"] == "operator" else DeviceStatus.DISTRIBUTED.value
        now = datetime.now().replace(tzinfo=None)

        inst = await session.get(Device, int(device_id))
        if not inst:
            return None

        inst.current_holder_id = to_user_id
        inst.current_holder_name = to_user_name
        inst.current_holder_type = holder_type
        inst.current_location = to_user_name
        inst.status = device_status
        inst.updated_at = now
        await session.commit()

    return await get_device_by_id(device_id)


async def track_device_by_serial(serial_number: str) -> Optional[Dict[str, Any]]:
    """Track device by serial number, NUID, or MAC with full history."""
    async with async_session_factory() as session:
        lookup = str(serial_number or "").strip()
        q = select(Device).where(or_(
            Device.serial_number == lookup, Device.nuid == lookup, Device.mac_address == lookup
        )).limit(1)
        inst = (await session.execute(q)).scalar_one_or_none()
        if not inst:
            return None

        device = inst.to_dict()

        hq = (select(DeviceHistory).where(DeviceHistory.device_id == int(device["id"]))
              .order_by(DeviceHistory.timestamp.desc()))
        history_rows = (await session.execute(hq)).scalars().all()
        device["history"] = [r.to_dict() for r in history_rows]

        return device


async def get_device_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, int]:
    """Get device statistics"""
    async with async_session_factory() as session:
        conditions = []
        if start_date:
            conditions.append(Device.created_at >= start_date)
        if end_date:
            conditions.append(Device.created_at <= end_date)
        where = and_(*conditions) if conditions else True

        q = select(Device.status, func.count().label("cnt")).where(where).group_by(Device.status)
        rows = (await session.execute(q)).all()

        stats = {"total": 0, "available": 0, "distributed": 0, "in_use": 0, "defective": 0, "returned": 0}
        for row in rows:
            status = row.status or ""
            count = int(row.cnt)
            stats["total"] += count
            if status in stats:
                stats[status] = count
        return stats


async def get_management_insights() -> Dict[str, Any]:
    """Get system-wide aggregate insights for management dashboards."""
    async with async_session_factory() as session:
        by_type_q = text("""
            SELECT
                COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown') AS device_type,
                COUNT(*) AS total
            FROM devices
            GROUP BY COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown')
            ORDER BY total DESC
        """)
        by_type_rows = (await session.execute(by_type_q)).mappings().all()

        by_vendor_q = text("""
            SELECT
                COALESCE(NULLIF(TRIM(manufacturer), ''), 'Unknown') AS manufacturer,
                COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown') AS device_type,
                COUNT(*) AS total
            FROM devices
            GROUP BY
                COALESCE(NULLIF(TRIM(manufacturer), ''), 'Unknown'),
                COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown')
            ORDER BY manufacturer ASC, total DESC
        """)
        by_vendor_rows = (await session.execute(by_vendor_q)).mappings().all()

        by_type = [
            {"type": row["device_type"], "total": int(row["total"] or 0)}
            for row in by_type_rows
        ]

        vendor_map: Dict[str, Dict[str, Any]] = {}
        for row in by_vendor_rows:
            manufacturer = row["manufacturer"]
            device_type = row["device_type"]
            count = int(row["total"] or 0)

            if manufacturer not in vendor_map:
                vendor_map[manufacturer] = {"manufacturer": manufacturer, "total": 0, "byType": {}}
            vendor_map[manufacturer]["total"] += count
            vendor_map[manufacturer]["byType"][device_type] = (
                vendor_map[manufacturer]["byType"].get(device_type, 0) + count
            )

        by_vendor = [
            {
                "manufacturer": vendor,
                "total": payload["total"],
                "distinctTypes": len(payload["byType"]),
                "typeBreakdown": [
                    {"type": t, "count": c}
                    for t, c in sorted(payload["byType"].items(), key=lambda item: item[1], reverse=True)
                ],
            }
            for vendor, payload in sorted(vendor_map.items(), key=lambda item: item[1]["total"], reverse=True)
        ]

        return {"by_type": by_type, "by_vendor": by_vendor}


async def get_management_holder_insights() -> Dict[str, Any]:
    """Get aggregate device totals by hierarchy holder groups for management dashboards."""
    async with async_session_factory() as session:
        result = await session.execute(text("""
            WITH RECURSIVE hierarchy AS (
                SELECT id, role, name,
                       id AS sub_id,
                       CAST(NULL AS CHAR(50)) AS cluster_id
                FROM users WHERE role = 'sub_distributor'
                UNION ALL
                SELECT u.id, u.role, u.name,
                       h.sub_id,
                       CASE WHEN u.role = 'cluster' THEN CAST(u.id AS CHAR(50))
                            ELSE h.cluster_id END
                FROM users u
                INNER JOIN hierarchy h ON u.parent_id = h.id
                WHERE u.role IN ('cluster', 'operator')
            )
            SELECT
                h.sub_id,
                sd.name AS sub_name,
                h.cluster_id,
                c.name AS cluster_name,
                COALESCE(NULLIF(TRIM(d.device_type), ''), 'Unknown') AS device_type,
                COUNT(*) AS total
            FROM hierarchy h
            LEFT JOIN users sd ON h.sub_id = sd.id
            LEFT JOIN users c ON h.cluster_id = c.id
            JOIN devices d ON CAST(d.current_holder_id AS CHAR) = CAST(h.id AS CHAR)
            WHERE d.current_holder_id IS NOT NULL
            AND TRIM(CAST(d.current_holder_id AS CHAR)) != ''
            GROUP BY h.sub_id, sd.name, h.cluster_id, c.name, device_type
        """))
        rows = result.mappings().all()

        sub_map: Dict[str, Dict[str, Any]] = {}
        cluster_map: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            sub_id = str(row["sub_id"])
            sub_name = str(row["sub_name"] or "Unknown Sub Distribution")
            cluster_id = str(row["cluster_id"]) if row.get("cluster_id") else None
            cluster_name = str(row["cluster_name"] or "Unknown Cluster") if cluster_id else None
            device_type = str(row["device_type"] or "Unknown")
            total = int(row["total"])

            if sub_id not in sub_map:
                sub_map[sub_id] = {"total": 0, "byType": {}}
            sub_map[sub_id]["total"] += total
            sub_map[sub_id]["byType"][device_type] = sub_map[sub_id]["byType"].get(device_type, 0) + total
            sub_map[sub_id]["name"] = sub_name

            if cluster_id:
                if cluster_id not in cluster_map:
                    cluster_map[cluster_id] = {"total": 0, "byType": {}}
                cluster_map[cluster_id]["total"] += total
                cluster_map[cluster_id]["byType"][device_type] = cluster_map[cluster_id]["byType"].get(device_type, 0) + total
                cluster_map[cluster_id]["name"] = cluster_name

        entry_ids = sorted({int(sid) for sid in sub_map} | {int(cid) for cid in cluster_map})
        digital_map = {}
        if entry_ids:
            ph = ",".join([f":di_{i}" for i in range(len(entry_ids))])
            id_rows = (await session.execute(
                text(f"SELECT user_id, digital_id, broadband_id FROM digital_identities WHERE user_id IN ({ph})"),
                {f"di_{i}": v for i, v in enumerate(entry_ids)},
            )).mappings().all()
            for r in id_rows:
                digital_map.setdefault(int(r["user_id"]), []).append({
                    "digital_id": r["digital_id"],
                    "broadband_id": r["broadband_id"],
                })

        def to_entry(entry_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": entry_id,
                "name": entry.get("name", "Unknown"),
                "total": entry["total"],
                "typeBreakdown": [
                    {"type": dtype, "count": count}
                    for dtype, count in sorted(entry["byType"].items(), key=lambda item: item[1], reverse=True)
                ],
                "digital_ids": digital_map.get(int(entry_id), []),
            }

        sub_summary = sorted(
            [to_entry(sid, data) for sid, data in sub_map.items() if data["total"] > 0],
            key=lambda item: item["total"], reverse=True,
        )
        cluster_summary = sorted(
            [to_entry(cid, data) for cid, data in cluster_map.items() if data["total"] > 0],
            key=lambda item: item["total"], reverse=True,
        )

        return {"sub_distributors": sub_summary, "clusters": cluster_summary}
