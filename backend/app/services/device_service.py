from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import json

from app.database import get_db, row_to_dict, rows_to_list
from app.models.device import DeviceCreate, DeviceUpdate, DeviceStatus, HolderType
from app.utils.helpers import get_pagination, generate_device_id
from app.utils.hierarchy import get_descendant_user_ids as _get_descendant_user_ids


async def _get_locked_distribution_device_ids(db) -> set:
    cursor = await db.execute("""
        SELECT dd.device_id
        FROM distribution_devices dd
        INNER JOIN distributions d ON dd.distribution_id = d.distribution_id
        WHERE d.status IN ('pending_receipt', 'disputed')
    """)
    rows = await cursor.fetchall()
    return {str(row[0]) for row in rows}


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
    async with get_db() as db:
        conditions = []
        params = []
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        if device_type:
            conditions.append("device_type = ?")
            params.append(device_type)
        if manufacturer:
            conditions.append("manufacturer = ?")
            params.append(manufacturer)
        if holder_id:
            conditions.append("current_holder_id = ?")
            params.append(holder_id)
        if holder_ids:
            normalized_holder_ids = [str(item).strip() for item in holder_ids if str(item).strip()]
            if normalized_holder_ids:
                placeholders = ",".join(["?"] * len(normalized_holder_ids))
                conditions.append(f"current_holder_id IN ({placeholders})")
                params.extend(normalized_holder_ids)
        if start_date:
            conditions.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= ?")
            params.append(end_date)
        if search:
            pattern = f"%{str(search).strip()}%"
            search_field_map = {
                "nuid": "nuid",
                "mac": "mac_address",
                "mac_address": "mac_address",
                "serial": "serial_number",
                "serial_number": "serial_number",
                "vendor": "manufacturer",
                "manufacturer": "manufacturer",
                "type": "device_type",
                "device_type": "device_type",
                "device_id": "device_id",
                "model": "model",
            }
            normalized_search_by = str(search_by or "").strip().lower()
            selected_column = search_field_map.get(normalized_search_by)

            if selected_column:
                conditions.append(f"COALESCE(CAST({selected_column} AS TEXT), '') LIKE ?")
                params.append(pattern)
            else:
                conditions.append(
                    "(" +
                    " OR ".join([
                        "COALESCE(CAST(device_id AS TEXT), '') LIKE ?",
                        "COALESCE(CAST(serial_number AS TEXT), '') LIKE ?",
                        "COALESCE(CAST(mac_address AS TEXT), '') LIKE ?",
                        "COALESCE(CAST(model AS TEXT), '') LIKE ?",
                        "COALESCE(CAST(nuid AS TEXT), '') LIKE ?",
                        "COALESCE(CAST(manufacturer AS TEXT), '') LIKE ?",
                        "COALESCE(CAST(device_type AS TEXT), '') LIKE ?",
                    ]) +
                    ")"
                )
                params.extend([pattern] * 7)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        cursor = await db.execute(f"SELECT COUNT(*) FROM devices WHERE {where_clause}", params)
        total = (await cursor.fetchone())[0]
        
        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"SELECT * FROM devices WHERE {where_clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = await cursor.fetchall()
        
        devices = [_augment_device_record(item) for item in rows_to_list(rows)]
        return {
            "data": devices,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_device_by_id(device_id: str) -> Optional[Dict[str, Any]]:
    """Get device by ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(device_id),))
        row = await cursor.fetchone()
        return _augment_device_record(row_to_dict(row))


async def get_device_by_serial(serial_number: str) -> Optional[Dict[str, Any]]:
    """Get device by serial number"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM devices WHERE serial_number = ?", (serial_number,))
        row = await cursor.fetchone()
        return _augment_device_record(row_to_dict(row))


async def create_device(device_data: DeviceCreate, created_by: str, created_by_name: str) -> Dict[str, Any]:
    """Create a new device"""
    async with get_db() as db:
        is_sb = device_data.device_type.value == "Set-top box"
        if is_sb and not (device_data.nuid and device_data.nuid.strip()):
            raise ValueError("NUID is required for SB devices")
        if is_sb:
            nuid_value = str(device_data.nuid or "").strip()
            cursor = await db.execute("SELECT id FROM devices WHERE nuid = ?", (nuid_value,))
            if await cursor.fetchone():
                raise ValueError("NUID already exists")

        serial_number = (device_data.serial_number or "").strip()
        mac_address = (device_data.mac_address or "").strip()
        box_type = (device_data.box_type or "").strip().upper() if is_sb else None

        # SB devices do not require serial/MAC. Keep them empty.
        if is_sb:
            serial_number = None
            mac_address = None
        else:
            if not serial_number:
                raise ValueError("Serial number is required for non-SB devices")
            # NUID is only valid for SB devices.
            device_data.nuid = None

        if serial_number:
            cursor = await db.execute("SELECT id FROM devices WHERE serial_number = ?", (serial_number,))
            if await cursor.fetchone():
                raise ValueError("Serial number already exists")

        if mac_address:
            cursor = await db.execute("SELECT id FROM devices WHERE mac_address = ?", (mac_address,))
            if await cursor.fetchone():
                raise ValueError("MAC address already exists")
        
        now = datetime.now().replace(tzinfo=None).isoformat()
        dev_id = generate_device_id(device_data.device_type.value)
        metadata_payload = dict(device_data.metadata or {})
        if is_sb and box_type in {"HD", "OTT"}:
            metadata_payload["box_type"] = box_type
        metadata_json = json.dumps(metadata_payload) if metadata_payload else None
        purchase_date = device_data.purchase_date.isoformat() if device_data.purchase_date else None
        warranty_expiry = device_data.warranty_expiry.isoformat() if device_data.warranty_expiry else None
        
        cursor = await db.execute(
            """INSERT INTO devices (device_id, device_type, model, serial_number, mac_address,
                manufacturer, band_type, nuid, status, current_location, current_holder_id, current_holder_name,
                current_holder_type, registered_by_name, purchase_date, warranty_expiry, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dev_id, device_data.device_type.value, device_data.model,
                serial_number, mac_address,
                device_data.manufacturer,
                (
                    None
                    if is_sb
                    else (
                        device_data.band_type.value
                        if hasattr(device_data.band_type, "value")
                        else (device_data.band_type or "single_band")
                    )
                ),
                device_data.nuid,
                DeviceStatus.AVAILABLE.value,
                "PDIC", None, "PDIC (Distribution)", HolderType.NOC.value,
                created_by_name,
                purchase_date, warranty_expiry, metadata_json, now, now
            )
        )
        await db.commit()
        new_id = str(cursor.lastrowid)
        
        # Add to history
        await _add_device_history(db, new_id, "registered", performed_by=created_by,
                                  performed_by_name=created_by_name, status_after=DeviceStatus.AVAILABLE.value,
                                  location="PDIC", notes="Device registered in system")
        await db.commit()

        # Read back using the same connection to avoid false negatives from a follow-up read path.
        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(new_id),))
        created_row = await cursor.fetchone()
        created_device = _augment_device_record(row_to_dict(created_row)) if created_row else None
        if created_device:
            return created_device

        # Fallback payload so successful inserts never surface as 400 due to readback issues.
        return {
            "id": new_id,
            "device_id": dev_id,
            "device_type": device_data.device_type.value,
            "model": device_data.model,
            "serial_number": serial_number,
            "mac_address": mac_address,
            "manufacturer": device_data.manufacturer,
            "band_type": (
                None
                if is_sb
                else (
                    device_data.band_type.value
                    if hasattr(device_data.band_type, "value")
                    else (device_data.band_type or "single_band")
                )
            ),
            "nuid": device_data.nuid,
            "status": DeviceStatus.AVAILABLE.value,
            "current_location": "PDIC",
            "current_holder_id": None,
            "current_holder_name": "PDIC (Distribution)",
            "current_holder_type": HolderType.NOC.value,
            "registered_by_name": created_by_name,
            "metadata": metadata_payload if metadata_payload else None,
            "created_at": now,
            "updated_at": now,
        }


async def update_device(device_id: str, device_data: DeviceUpdate) -> Optional[Dict[str, Any]]:
    """Update device"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(device_id),))
        current_row = await cursor.fetchone()
        if not current_row:
            return None
        current_device = row_to_dict(current_row)

        update_fields = []
        params = []
        
        data = device_data.model_dump(exclude_unset=True)

        next_device_type = data.get("device_type", current_device.get("device_type"))
        if hasattr(next_device_type, "value"):
            next_device_type = next_device_type.value
        next_nuid = data.get("nuid", current_device.get("nuid"))
        next_box_type = data.get("box_type", current_device.get("box_type"))
        if next_device_type == "Set-top box" and not (next_nuid and str(next_nuid).strip()):
            raise ValueError("NUID is required for SB devices")
        if next_device_type == "Set-top box":
            normalized_box = str(next_box_type or "").strip().upper()
            if normalized_box not in {"HD", "OTT"}:
                raise ValueError("box_type is required for SB devices and must be HD or OTT")
            normalized_nuid = str(next_nuid or "").strip()
            cursor = await db.execute(
                "SELECT id FROM devices WHERE nuid = ? AND id != ?",
                (normalized_nuid, int(device_id))
            )
            if await cursor.fetchone():
                raise ValueError("NUID already exists")

        if next_device_type == "Set-top box":
            update_fields.append("serial_number = ?")
            params.append(None)
        elif "serial_number" in data and data["serial_number"] is not None:
            serial_number = str(data["serial_number"]).strip()
            if not serial_number:
                raise ValueError("Serial number cannot be empty")
            cursor = await db.execute(
                "SELECT id FROM devices WHERE serial_number = ? AND id != ?",
                (serial_number, int(device_id))
            )
            if await cursor.fetchone():
                raise ValueError("Serial number already exists")
            update_fields.append("serial_number = ?")
            params.append(serial_number)

        if next_device_type == "Set-top box":
            update_fields.append("mac_address = ?")
            params.append(None)
        elif "mac_address" in data and data["mac_address"] is not None:
            mac_address = str(data["mac_address"]).strip()
            if not mac_address:
                raise ValueError("MAC address cannot be empty")
            cursor = await db.execute(
                "SELECT id FROM devices WHERE mac_address = ? AND id != ?",
                (mac_address, int(device_id))
            )
            if await cursor.fetchone():
                raise ValueError("MAC address already exists")
            update_fields.append("mac_address = ?")
            params.append(mac_address)
        
        for field in ["model", "manufacturer", "current_location"]:
            if field in data and data[field] is not None:
                update_fields.append(f"{field} = ?")
                params.append(data[field])
        
        if "status" in data and data["status"] is not None:
            update_fields.append("status = ?")
            params.append(data["status"].value if hasattr(data["status"], "value") else data["status"])
        if "device_type" in data and data["device_type"] is not None:
            update_fields.append("device_type = ?")
            params.append(data["device_type"].value if hasattr(data["device_type"], "value") else data["device_type"])
        if "band_type" in data and data["band_type"] is not None:
            update_fields.append("band_type = ?")
            params.append(data["band_type"].value if hasattr(data["band_type"], "value") else data["band_type"])
        elif next_device_type == "Set-top box":
            update_fields.append("band_type = ?")
            params.append(None)
        if "warranty_expiry" in data and data["warranty_expiry"] is not None:
            update_fields.append("warranty_expiry = ?")
            params.append(data["warranty_expiry"].isoformat() if hasattr(data["warranty_expiry"], "isoformat") else data["warranty_expiry"])
        if "metadata" in data and data["metadata"] is not None:
            base_metadata = data["metadata"] if isinstance(data["metadata"], dict) else {}
        else:
            existing_metadata = current_device.get("metadata")
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
            # Ensure NUID field remains populated only for SB.
            if "nuid" in data and data["nuid"] is not None:
                update_fields.append("nuid = ?")
                params.append(str(data["nuid"]).strip() or None)
        else:
            base_metadata.pop("box_type", None)
            update_fields.append("nuid = ?")
            params.append(None)

        update_fields.append("metadata = ?")
        params.append(json.dumps(base_metadata) if base_metadata else None)
        
        if not update_fields:
            return await get_device_by_id(device_id)
        
        update_fields.append("updated_at = ?")
        params.append(datetime.now().replace(tzinfo=None).isoformat())
        params.append(int(device_id))
        
        await db.execute(f"UPDATE devices SET {', '.join(update_fields)} WHERE id = ?", params)
        await db.commit()
        
        return await get_device_by_id(device_id)


async def delete_device(device_id: str) -> bool:
    """Delete device"""
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM devices WHERE id = ?", (int(device_id),))
        if cursor.rowcount > 0:
            await db.execute("DELETE FROM device_history WHERE device_id = ?", (device_id,))
            await db.commit()
            return True
        return False


async def update_device_status(
    device_id: str,
    status: str,
    performed_by: str,
    performed_by_name: str,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update device status"""
    valid_statuses = {item.value for item in DeviceStatus}
    if status not in valid_statuses:
        raise ValueError(
            f"Invalid device status '{status}'. Allowed values: {', '.join(sorted(valid_statuses))}"
        )

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(device_id),))
        row = await cursor.fetchone()
        if not row:
            return None
        
        device = row_to_dict(row)
        old_status = device.get("status")
        now = datetime.now().replace(tzinfo=None).isoformat()
        
        await db.execute(
            "UPDATE devices SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, int(device_id))
        )
        
        await _add_device_history(db, device_id, "status_changed",
                                  performed_by=performed_by, performed_by_name=performed_by_name,
                                  status_before=old_status, status_after=status,
                                  location=device.get("current_location"),
                                  notes=notes or f"Status changed from {old_status} to {status}")
        await db.commit()
        
        return await get_device_by_id(device_id)


async def _update_device_holder_impl(
    db,
    device_id: str,
    holder_id: Optional[str],
    holder_name: Optional[str],
    holder_type: str,
    location: str,
    status: str,
    performed_by: str,
    performed_by_name: str,
    from_user_id: Optional[str] = None,
    from_user_name: Optional[str] = None,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    cursor = await db.execute("SELECT * FROM devices WHERE id = ?", (int(device_id),))
    row = await cursor.fetchone()
    if not row:
        return None
    
    device = row_to_dict(row)
    old_status = device.get("status")
    now = datetime.now().replace(tzinfo=None).isoformat()
    
    await db.execute(
        """UPDATE devices SET current_holder_id = ?, current_holder_name = ?,
            current_holder_type = ?, current_location = ?, status = ?, updated_at = ?
        WHERE id = ?""",
        (holder_id, holder_name, holder_type, location, status, now, int(device_id))
    )
    
    await _add_device_history(db, device_id, "distributed",
                              from_user_id=from_user_id, from_user_name=from_user_name,
                              to_user_id=holder_id, to_user_name=holder_name,
                              performed_by=performed_by, performed_by_name=performed_by_name,
                              status_before=old_status, status_after=status,
                              location=location, notes=notes)
    await db.commit()
    
    return await get_device_by_id(device_id)


async def update_device_holder(
    device_id: str,
    holder_id: Optional[str],
    holder_name: Optional[str],
    holder_type: str,
    location: str,
    status: str,
    performed_by: str,
    performed_by_name: str,
    from_user_id: Optional[str] = None,
    from_user_name: Optional[str] = None,
    notes: Optional[str] = None,
    db=None
) -> Optional[Dict[str, Any]]:
    """Update device holder (for distributions)"""
    if db is None:
        async with get_db() as db:
            return await _update_device_holder_impl(
                db, device_id, holder_id, holder_name, holder_type, location, status,
                performed_by, performed_by_name, from_user_id=from_user_id,
                from_user_name=from_user_name, notes=notes
            )
    return await _update_device_holder_impl(
        db, device_id, holder_id, holder_name, holder_type, location, status,
        performed_by, performed_by_name, from_user_id=from_user_id,
        from_user_name=from_user_name, notes=notes
    )


async def get_available_devices(holder_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get available devices for distribution (PDIC stock only)"""
    async with get_db() as db:
        if holder_id:
            cursor = await db.execute(
                "SELECT * FROM devices WHERE status = ? AND current_holder_id = ? ORDER BY created_at DESC LIMIT 2000",
                (DeviceStatus.AVAILABLE.value, holder_id)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM devices WHERE status = ? ORDER BY created_at DESC LIMIT 2000",
                (DeviceStatus.AVAILABLE.value,)
            )
        rows = await cursor.fetchall()
        locked_ids = await _get_locked_distribution_device_ids(db)
        return [
            _augment_device_record(item)
            for item in rows_to_list(rows)
            if str(item.get("id")) not in locked_ids
        ]


async def get_devices_for_replacement(exclude_device_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all devices eligible as replacements (available or returned status).
    Used exclusively by management (admin/manager/staff) during the replace-device flow."""
    async with get_db() as db:
        statuses = (DeviceStatus.AVAILABLE.value, DeviceStatus.RETURNED.value)
        if exclude_device_id:
            cursor = await db.execute(
                "SELECT * FROM devices WHERE status IN (?, ?) AND id != ? ORDER BY updated_at DESC LIMIT 2000",
                (statuses[0], statuses[1], int(exclude_device_id))
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM devices WHERE status IN (?, ?) ORDER BY updated_at DESC LIMIT 2000",
                statuses
            )
        rows = await cursor.fetchall()
        return [_augment_device_record(item) for item in rows_to_list(rows)]


async def get_held_devices(holder_id: str) -> List[Dict[str, Any]]:
    """Get all devices currently held by a user (any status) — for sub-level redistribution"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM devices WHERE current_holder_id = ? ORDER BY updated_at DESC LIMIT 2000",
            (holder_id,)
        )
        rows = await cursor.fetchall()
        locked_ids = await _get_locked_distribution_device_ids(db)
        return [
            _augment_device_record(item)
            for item in rows_to_list(rows)
            if str(item.get("id")) not in locked_ids
        ]


async def get_user_device_overview(user_id: str, user_role: str, limit: int = 100) -> Dict[str, Any]:
    """Get comprehensive device overview: devices in hand + under hierarchy + distribution stats.
    Also includes defective devices whose original holder is within the user's chain."""
    async with get_db() as db:
        uid = int(user_id)

        # Devices directly held by this user (any status)
        cursor = await db.execute(
            "SELECT * FROM devices WHERE current_holder_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit)
        )
        held_devices = rows_to_list(await cursor.fetchall())
        held_device_ids = {str(d["id"]) for d in held_devices}

        # Also fetch defective devices reported by this user that may have had holder cleared
        cursor = await db.execute(
            """SELECT d.* FROM devices d
               JOIN defects def ON CAST(def.device_id AS TEXT) = CAST(d.id AS TEXT)
               WHERE (CAST(def.reported_by AS TEXT) = ? OR CAST(d.current_holder_id AS TEXT) = ?)
               AND d.status = 'defective'
               AND CAST(d.id AS TEXT) NOT IN ({held_ids})""".format(
                held_ids=",".join(["?" for _ in held_device_ids]) if held_device_ids else "'__none__'"
            ),
            [user_id, user_id] + list(held_device_ids) if held_device_ids else [user_id, user_id]
        )
        my_defective_devices = rows_to_list(await cursor.fetchall())
        for d in my_defective_devices:
            if str(d["id"]) not in held_device_ids:
                held_devices.append(d)
                held_device_ids.add(str(d["id"]))

        subordinate_devices = []
        if user_role == "sub_distributor":
            # Devices held by clusters directly under this sub_distributor
            cursor = await db.execute(
                """SELECT d.* FROM devices d
                   JOIN users u ON CAST(d.current_holder_id AS TEXT) = CAST(u.id AS TEXT)
                   WHERE u.parent_id = ? AND u.role = 'cluster'
                   ORDER BY d.updated_at DESC LIMIT ?""",
                (uid, limit)
            )
            cluster_devices = rows_to_list(await cursor.fetchall())
            cluster_device_ids = {str(d["id"]) for d in cluster_devices}

            # Devices held by operators whose parent cluster belongs to this sub_distributor
            cursor = await db.execute(
                """SELECT d.* FROM devices d
                   JOIN users op ON CAST(d.current_holder_id AS TEXT) = CAST(op.id AS TEXT)
                   JOIN users cl ON op.parent_id = cl.id
                   WHERE cl.parent_id = ? AND op.role = 'operator'
                   ORDER BY d.updated_at DESC LIMIT ?""",
                (uid, limit)
            )
            operator_devices = rows_to_list(await cursor.fetchall())
            operator_device_ids = {str(d["id"]) for d in operator_devices}

            # Also include defective devices reported by operators/clusters in the chain
            cursor = await db.execute(
                """SELECT DISTINCT d.* FROM devices d
                   JOIN defects def ON CAST(def.device_id AS TEXT) = CAST(d.id AS TEXT)
                   JOIN users op ON CAST(def.reported_by AS TEXT) = CAST(op.id AS TEXT)
                   LEFT JOIN users cl ON op.parent_id = cl.id
                   WHERE (
                     (op.role = 'operator' AND cl.parent_id = ?)
                     OR (op.role = 'cluster' AND op.parent_id = ?)
                   )
                   AND d.status = 'defective'
                   LIMIT ?""",
                (uid, uid, limit)
            )
            defective_subordinate = rows_to_list(await cursor.fetchall())

            all_sub_ids = cluster_device_ids | operator_device_ids
            for d in defective_subordinate:
                if str(d["id"]) not in all_sub_ids and str(d["id"]) not in held_device_ids:
                    operator_devices.append(d)
                    all_sub_ids.add(str(d["id"]))

            subordinate_devices = cluster_devices + operator_devices

        elif user_role == "sub_distribution_manager":
            # Sub distribution managers are scoped to the sub distributor root they belong to.
            cursor = await db.execute("SELECT parent_id FROM users WHERE id = ?", (uid,))
            manager_row = await cursor.fetchone()
            scope_root_id = str(uid)
            if manager_row and manager_row["parent_id"] is not None:
                scope_root_id = str(manager_row["parent_id"])

            scope_user_ids = {scope_root_id}
            scope_user_ids.update(await _get_descendant_user_ids(db, scope_root_id))
            scope_user_ids.discard(str(user_id))

            scoped_user_list = sorted(scope_user_ids)
            if scoped_user_list:
                placeholders = ",".join(["?"] * len(scoped_user_list))
                cursor = await db.execute(
                    f"""SELECT * FROM devices
                        WHERE CAST(current_holder_id AS TEXT) IN ({placeholders})
                        ORDER BY updated_at DESC
                        LIMIT ?""",
                    tuple(scoped_user_list) + (limit,),
                )
                subordinate_devices = rows_to_list(await cursor.fetchall())
            else:
                subordinate_devices = []

            subordinate_device_ids = {str(d["id"]) for d in subordinate_devices}

            if scoped_user_list:
                placeholders = ",".join(["?"] * len(scoped_user_list))
                cursor = await db.execute(
                    f"""SELECT DISTINCT d.* FROM devices d
                        JOIN defects def ON CAST(def.device_id AS TEXT) = CAST(d.id AS TEXT)
                        WHERE CAST(def.reported_by AS TEXT) IN ({placeholders})
                          AND d.status = 'defective'
                        LIMIT ?""",
                    tuple(scoped_user_list) + (limit,),
                )
                defective_subordinate = rows_to_list(await cursor.fetchall())
            else:
                defective_subordinate = []

            for d in defective_subordinate:
                did = str(d["id"])
                if did not in subordinate_device_ids and did not in held_device_ids:
                    subordinate_devices.append(d)
                    subordinate_device_ids.add(did)

        elif user_role == "cluster":
            # Devices held by operators directly under this cluster
            cursor = await db.execute(
                """SELECT d.* FROM devices d
                   JOIN users u ON CAST(d.current_holder_id AS TEXT) = CAST(u.id AS TEXT)
                   WHERE u.parent_id = ? AND u.role = 'operator'
                   ORDER BY d.updated_at DESC LIMIT ?""",
                (uid, limit)
            )
            subordinate_devices = rows_to_list(await cursor.fetchall())
            sub_device_ids = {str(d["id"]) for d in subordinate_devices}

            # Also include defective devices reported by operators under this cluster
            cursor = await db.execute(
                """SELECT DISTINCT d.* FROM devices d
                   JOIN defects def ON CAST(def.device_id AS TEXT) = CAST(d.id AS TEXT)
                   JOIN users op ON CAST(def.reported_by AS TEXT) = CAST(op.id AS TEXT)
                   WHERE op.parent_id = ? AND op.role = 'operator'
                   AND d.status = 'defective'
                   LIMIT ?""",
                (uid, limit)
            )
            defective_subordinate = rows_to_list(await cursor.fetchall())
            for d in defective_subordinate:
                if str(d["id"]) not in sub_device_ids and str(d["id"]) not in held_device_ids:
                    subordinate_devices.append(d)
                    sub_device_ids.add(str(d["id"]))

        # Distribution stats from the distributions table (single query)
        cursor = await db.execute(
            """SELECT
                   SUM(CASE WHEN to_user_id = ? THEN 1 ELSE 0 END),
                   COALESCE(SUM(CASE WHEN to_user_id = ? THEN device_count ELSE 0 END), 0),
                   SUM(CASE WHEN from_user_id = ? THEN 1 ELSE 0 END),
                   COALESCE(SUM(CASE WHEN from_user_id = ? THEN device_count ELSE 0 END), 0)
               FROM distributions
               WHERE ? IN (to_user_id, from_user_id)""",
            (user_id, user_id, user_id, user_id, user_id)
        )
        row = await cursor.fetchone()
        total_distrib_received = int(row[0]) if row and row[0] is not None else 0
        total_devices_received = int(row[1]) if row and row[1] is not None else 0
        total_distrib_sent = int(row[2]) if row and row[2] is not None else 0
        total_devices_sent = int(row[3]) if row and row[3] is not None else 0

        # Deduplicate across held + subordinate
        seen_ids = set()
        all_under_me = []
        for d in held_devices + subordinate_devices:
            if str(d["id"]) not in seen_ids:
                seen_ids.add(str(d["id"]))
                all_under_me.append(d)

        return {
            "held_by_me": held_devices,
            "under_subordinates": subordinate_devices,
            "all_under_me": all_under_me,
            "stats": {
                "in_my_hand": len(held_devices),
                "under_subordinates": len(subordinate_devices),
                "total_in_chain": len(all_under_me),
                "total_devices_received": total_devices_received,
                "total_devices_sent": total_devices_sent,
                "total_distributions_received": total_distrib_received,
                "total_distributions_sent": total_distrib_sent,
            }
        }


async def get_device_history(device_id: str) -> List[Dict[str, Any]]:
    """Get device history"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM device_history WHERE device_id = ? ORDER BY timestamp DESC",
            (device_id,)
        )
        rows = await cursor.fetchall()
        return rows_to_list(rows)


async def _add_device_history(
    db, device_id: str, action: str,
    performed_by: str = None, performed_by_name: str = None,
    from_user_id: str = None, from_user_name: str = None,
    to_user_id: str = None, to_user_name: str = None,
    status_before: str = None, status_after: str = None,
    location: str = None, notes: str = None
):
    """Add device history entry (uses existing db connection)"""
    now = datetime.now().replace(tzinfo=None).isoformat()
    await db.execute(
        """INSERT INTO device_history (device_id, action, from_user_id, from_user_name,
            to_user_id, to_user_name, status_before, status_after, location, notes,
            performed_by, performed_by_name, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (device_id, action, from_user_id, from_user_name, to_user_id, to_user_name,
         status_before, status_after, location, notes, performed_by, performed_by_name, now)
    )


async def repair_device_holder_from_history(device_id: str) -> Optional[Dict[str, Any]]:
    """Repair device holder by applying the most recent 'distributed' history entry.
    Use when a device's current_holder has been corrupted by a double-approval."""
    async with get_db() as db:
        # Find the most recent distributed action
        cursor = await db.execute(
            """SELECT * FROM device_history
               WHERE device_id = ? AND action = 'distributed'
               ORDER BY timestamp DESC LIMIT 1""",
            (device_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        entry = row_to_dict(row)

        to_user_id   = entry.get("to_user_id")
        to_user_name = entry.get("to_user_name")
        if not to_user_id:
            return None

        # Look up the user to determine role-based holder_type and device status
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (int(to_user_id),))
        user_row = await cursor.fetchone()
        if not user_row:
            return None
        recipient = row_to_dict(user_row)

        role_to_type = {
            "super_admin": "noc", "manager": "noc", "pdic_staff": "pdic_staff",
            "sub_distribution_manager": "sub_distribution_manager",
            "sub_distributor": "sub_distributor", "cluster": "cluster", "operator": "operator"
        }
        holder_type   = role_to_type.get(recipient["role"], "noc")
        device_status = DeviceStatus.IN_USE.value if recipient["role"] == "operator" else DeviceStatus.DISTRIBUTED.value
        now = datetime.now().replace(tzinfo=None).isoformat()

        await db.execute(
            """UPDATE devices
               SET current_holder_id = ?, current_holder_name = ?,
                   current_holder_type = ?, current_location = ?,
                   status = ?, updated_at = ?
               WHERE id = ?""",
            (str(to_user_id), to_user_name, holder_type, to_user_name,
             device_status, now, int(device_id))
        )
        await db.commit()

    return await get_device_by_id(device_id)


async def track_device_by_serial(serial_number: str) -> Optional[Dict[str, Any]]:
    """Track device by serial number, NUID, or MAC with full history."""
    async with get_db() as db:
        lookup = str(serial_number or "").strip()
        cursor = await db.execute(
            """SELECT * FROM devices
               WHERE serial_number = ? OR nuid = ? OR mac_address = ?
               LIMIT 1""",
            (lookup, lookup, lookup),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        
        device = row_to_dict(row)
        
        cursor = await db.execute(
            "SELECT * FROM device_history WHERE device_id = ? ORDER BY timestamp DESC",
            (device["id"],)
        )
        history_rows = await cursor.fetchall()
        device["history"] = rows_to_list(history_rows)
        
        return device


async def get_device_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, int]:
    """Get device statistics"""
    async with get_db() as db:
        conditions = []
        params = []
        if start_date:
            conditions.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= ?")
            params.append(end_date)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(
            f"SELECT COALESCE(status, '') AS status, COUNT(*) AS cnt FROM devices WHERE {where} GROUP BY status",
            params
        )
        rows = await cursor.fetchall()
        stats = {"total": 0, "available": 0, "distributed": 0, "in_use": 0, "defective": 0, "returned": 0}
        for row in rows:
            status = row[0]
            count = int(row[1])
            stats["total"] += count
            if status in stats:
                stats[status] = count
        return stats


async def get_management_insights() -> Dict[str, Any]:
    """Get system-wide aggregate insights for management dashboards."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT
                   COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown') AS device_type,
                   COUNT(*) AS total
               FROM devices
               GROUP BY COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown')
               ORDER BY total DESC"""
        )
        by_type_rows = await cursor.fetchall()

        cursor = await db.execute(
            """SELECT
                   COALESCE(NULLIF(TRIM(manufacturer), ''), 'Unknown') AS manufacturer,
                   COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown') AS device_type,
                   COUNT(*) AS total
               FROM devices
               GROUP BY
                   COALESCE(NULLIF(TRIM(manufacturer), ''), 'Unknown'),
                   COALESCE(NULLIF(TRIM(device_type), ''), 'Unknown')
               ORDER BY manufacturer ASC, total DESC"""
        )
        by_vendor_rows = await cursor.fetchall()

        by_type = [
            {
                "type": row.get("device_type", "Unknown"),
                "total": int(row.get("total", 0) or 0),
            }
            for row in by_type_rows
        ]

        vendor_map: Dict[str, Dict[str, Any]] = {}
        for row in by_vendor_rows:
            manufacturer = row.get("manufacturer", "Unknown")
            device_type = row.get("device_type", "Unknown")
            count = int(row.get("total", 0) or 0)

            if manufacturer not in vendor_map:
                vendor_map[manufacturer] = {
                    "manufacturer": manufacturer,
                    "total": 0,
                    "byType": {},
                }

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
            for vendor, payload in vendor_map.items()
        ]
        by_vendor.sort(key=lambda item: item["total"], reverse=True)

        return {
            "by_type": by_type,
            "by_vendor": by_vendor,
        }


async def get_management_holder_insights() -> Dict[str, Any]:
    """Get aggregate device totals by hierarchy holder groups for management dashboards.
    Uses a single recursive CTE to build the hierarchy and aggregate device counts in SQL."""
    async with get_db() as db:
        cursor = await db.execute(
            """WITH RECURSIVE hierarchy AS (
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
            JOIN devices d ON CAST(d.current_holder_id AS TEXT) = CAST(h.id AS TEXT)
            WHERE d.current_holder_id IS NOT NULL
            AND TRIM(CAST(d.current_holder_id AS TEXT)) != ''
            GROUP BY h.sub_id, sd.name, h.cluster_id, c.name, device_type"""
        )
        rows = rows_to_list(await cursor.fetchall())

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

        def to_entry(entry_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": entry_id,
                "name": entry.get("name", "Unknown"),
                "total": entry["total"],
                "typeBreakdown": [
                    {"type": dtype, "count": count}
                    for dtype, count in sorted(entry["byType"].items(), key=lambda item: item[1], reverse=True)
                ],
            }

        sub_summary = sorted(
            [to_entry(sid, data) for sid, data in sub_map.items() if data["total"] > 0],
            key=lambda item: item["total"], reverse=True,
        )
        cluster_summary = sorted(
            [to_entry(cid, data) for cid, data in cluster_map.items() if data["total"] > 0],
            key=lambda item: item["total"], reverse=True,
        )

        return {
            "sub_distributors": sub_summary,
            "clusters": cluster_summary,
        }

