from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.models.device import DeviceCreate, DeviceUpdate, DeviceStatus, HolderType, DeviceHistoryCreate
from app.utils.helpers import (
    serialize_doc, serialize_docs, get_pagination, 
    generate_device_id, to_object_id
)


async def get_devices(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    device_type: Optional[str] = None,
    holder_id: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Get all devices with pagination and filters"""
    db = get_database()
    
    # Build query
    query = {}
    if status:
        query["status"] = status
    if device_type:
        query["device_type"] = device_type
    if holder_id:
        query["current_holder_id"] = holder_id
    if search:
        query["$or"] = [
            {"device_id": {"$regex": search, "$options": "i"}},
            {"serial_number": {"$regex": search, "$options": "i"}},
            {"mac_address": {"$regex": search, "$options": "i"}},
            {"model": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.devices.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = db.devices.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    devices = await cursor.to_list(length=page_size)
    
    return {
        "data": serialize_docs(devices),
        "pagination": get_pagination(page, page_size, total)
    }


async def get_device_by_id(device_id: str) -> Optional[Dict[str, Any]]:
    """Get device by ID"""
    db = get_database()
    
    try:
        device = await db.devices.find_one({"_id": ObjectId(device_id)})
        return serialize_doc(device) if device else None
    except:
        return None


async def get_device_by_serial(serial_number: str) -> Optional[Dict[str, Any]]:
    """Get device by serial number"""
    db = get_database()
    device = await db.devices.find_one({"serial_number": serial_number})
    return serialize_doc(device) if device else None


async def create_device(device_data: DeviceCreate, created_by: str, created_by_name: str) -> Dict[str, Any]:
    """Create a new device"""
    db = get_database()
    
    # Check if serial number exists
    existing = await db.devices.find_one({"serial_number": device_data.serial_number})
    if existing:
        raise ValueError("Serial number already exists")
    
    # Check if MAC address exists
    existing_mac = await db.devices.find_one({"mac_address": device_data.mac_address})
    if existing_mac:
        raise ValueError("MAC address already exists")
    
    now = datetime.utcnow()
    device_doc = {
        "device_id": generate_device_id(device_data.device_type.value),
        "device_type": device_data.device_type.value,
        "model": device_data.model,
        "serial_number": device_data.serial_number,
        "mac_address": device_data.mac_address,
        "manufacturer": device_data.manufacturer,
        "status": DeviceStatus.AVAILABLE.value,
        "current_location": "NOC",
        "current_holder_id": None,
        "current_holder_name": None,
        "current_holder_type": HolderType.NOC.value,
        "purchase_date": device_data.purchase_date,
        "warranty_expiry": device_data.warranty_expiry,
        "created_at": now,
        "updated_at": now,
        "metadata": device_data.metadata
    }
    
    result = await db.devices.insert_one(device_doc)
    device_doc["_id"] = result.inserted_id
    
    # Add to history
    await add_device_history(
        device_id=str(result.inserted_id),
        action="registered",
        status_after=DeviceStatus.AVAILABLE.value,
        location="NOC",
        notes="Device registered in system",
        performed_by=created_by,
        performed_by_name=created_by_name
    )
    
    return serialize_doc(device_doc)


async def update_device(device_id: str, device_data: DeviceUpdate) -> Optional[Dict[str, Any]]:
    """Update device"""
    db = get_database()
    
    update_dict = {k: v for k, v in device_data.model_dump().items() if v is not None}
    
    if not update_dict:
        return await get_device_by_id(device_id)
    
    # Convert enums to values
    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value
    if "device_type" in update_dict:
        update_dict["device_type"] = update_dict["device_type"].value
    
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.devices.update_one(
        {"_id": ObjectId(device_id)},
        {"$set": update_dict}
    )
    
    if result.modified_count > 0 or result.matched_count > 0:
        return await get_device_by_id(device_id)
    return None


async def delete_device(device_id: str) -> bool:
    """Delete device"""
    db = get_database()
    
    result = await db.devices.delete_one({"_id": ObjectId(device_id)})
    
    if result.deleted_count > 0:
        # Also delete history
        await db.device_history.delete_many({"device_id": device_id})
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
    db = get_database()
    
    # Get current device
    device = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not device:
        return None
    
    old_status = device.get("status")
    
    result = await db.devices.update_one(
        {"_id": ObjectId(device_id)},
        {
            "$set": {
                "status": status,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count > 0:
        # Add to history
        await add_device_history(
            device_id=device_id,
            action="status_changed",
            status_before=old_status,
            status_after=status,
            location=device.get("current_location"),
            notes=notes or f"Status changed from {old_status} to {status}",
            performed_by=performed_by,
            performed_by_name=performed_by_name
        )
        return await get_device_by_id(device_id)
    return None


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
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update device holder (for distributions)"""
    db = get_database()
    
    # Get current device
    device = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not device:
        return None
    
    old_status = device.get("status")
    
    result = await db.devices.update_one(
        {"_id": ObjectId(device_id)},
        {
            "$set": {
                "current_holder_id": holder_id,
                "current_holder_name": holder_name,
                "current_holder_type": holder_type,
                "current_location": location,
                "status": status,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count > 0:
        # Add to history
        await add_device_history(
            device_id=device_id,
            action="distributed",
            from_user_id=from_user_id,
            from_user_name=from_user_name,
            to_user_id=holder_id,
            to_user_name=holder_name,
            status_before=old_status,
            status_after=status,
            location=location,
            notes=notes,
            performed_by=performed_by,
            performed_by_name=performed_by_name
        )
        return await get_device_by_id(device_id)
    return None


async def get_available_devices(holder_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get available devices for distribution"""
    db = get_database()
    
    query = {"status": DeviceStatus.AVAILABLE.value}
    if holder_id:
        query["current_holder_id"] = holder_id
    
    cursor = db.devices.find(query).limit(100)
    devices = await cursor.to_list(length=100)
    
    return serialize_docs(devices)


async def get_device_history(device_id: str) -> List[Dict[str, Any]]:
    """Get device history"""
    db = get_database()
    
    cursor = db.device_history.find({"device_id": device_id}).sort("timestamp", -1)
    history = await cursor.to_list(length=100)
    
    return serialize_docs(history)


async def add_device_history(
    device_id: str,
    action: str,
    performed_by: str,
    performed_by_name: str,
    from_user_id: Optional[str] = None,
    from_user_name: Optional[str] = None,
    to_user_id: Optional[str] = None,
    to_user_name: Optional[str] = None,
    status_before: Optional[str] = None,
    status_after: Optional[str] = None,
    location: Optional[str] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Add device history entry"""
    db = get_database()
    
    history_doc = {
        "device_id": device_id,
        "action": action,
        "from_user_id": from_user_id,
        "from_user_name": from_user_name,
        "to_user_id": to_user_id,
        "to_user_name": to_user_name,
        "status_before": status_before,
        "status_after": status_after,
        "location": location,
        "notes": notes,
        "performed_by": performed_by,
        "performed_by_name": performed_by_name,
        "timestamp": datetime.utcnow()
    }
    
    result = await db.device_history.insert_one(history_doc)
    history_doc["_id"] = result.inserted_id
    
    return serialize_doc(history_doc)


async def track_device_by_serial(serial_number: str) -> Optional[Dict[str, Any]]:
    """Track device by serial number with full history"""
    db = get_database()
    
    device = await db.devices.find_one({"serial_number": serial_number})
    if not device:
        return None
    
    device_data = serialize_doc(device)
    
    # Get history
    cursor = db.device_history.find({"device_id": str(device["_id"])}).sort("timestamp", -1)
    history = await cursor.to_list(length=50)
    
    device_data["history"] = serialize_docs(history)
    
    return device_data


async def get_device_stats() -> Dict[str, int]:
    """Get device statistics"""
    db = get_database()
    
    total = await db.devices.count_documents({})
    available = await db.devices.count_documents({"status": "available"})
    distributed = await db.devices.count_documents({"status": "distributed"})
    in_use = await db.devices.count_documents({"status": "in_use"})
    defective = await db.devices.count_documents({"status": "defective"})
    returned = await db.devices.count_documents({"status": "returned"})
    
    return {
        "total": total,
        "available": available,
        "distributed": distributed,
        "in_use": in_use,
        "defective": defective,
        "returned": returned
    }
