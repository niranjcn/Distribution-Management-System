from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.models.defect import DefectCreate, DefectUpdate, DefectStatus, DefectSeverity
from app.models.device import DeviceStatus
from app.services import device_service, notification_service
from app.utils.helpers import serialize_doc, serialize_docs, get_pagination, generate_defect_id


async def get_defects(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    defect_type: Optional[str] = None,
    reported_by: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Get all defect reports with pagination and filters"""
    db = get_database()
    
    # Build query
    query = {}
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    if defect_type:
        query["defect_type"] = defect_type
    if reported_by:
        query["reported_by"] = reported_by
    if search:
        query["$or"] = [
            {"report_id": {"$regex": search, "$options": "i"}},
            {"device_serial": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.defects.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = db.defects.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    defects = await cursor.to_list(length=page_size)
    
    return {
        "data": serialize_docs(defects),
        "pagination": get_pagination(page, page_size, total)
    }


async def get_defect_by_id(defect_id: str) -> Optional[Dict[str, Any]]:
    """Get defect report by ID"""
    db = get_database()
    
    try:
        defect = await db.defects.find_one({"_id": ObjectId(defect_id)})
        return serialize_doc(defect) if defect else None
    except:
        return None


async def create_defect(defect_data: DefectCreate, reporter: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new defect report"""
    db = get_database()
    
    # Get device info
    device = await db.devices.find_one({"_id": ObjectId(defect_data.device_id)})
    if not device:
        raise ValueError("Device not found")
    
    now = datetime.utcnow()
    defect_doc = {
        "report_id": generate_defect_id(),
        "device_id": defect_data.device_id,
        "device_serial": device["serial_number"],
        "device_type": device["device_type"],
        "reported_by": str(reporter["_id"]),
        "reported_by_name": reporter["name"],
        "defect_type": defect_data.defect_type.value,
        "severity": defect_data.severity.value,
        "description": defect_data.description,
        "symptoms": defect_data.symptoms,
        "status": DefectStatus.REPORTED.value,
        "resolution": None,
        "resolved_by": None,
        "resolved_by_name": None,
        "resolved_at": None,
        "images": defect_data.images or [],
        "created_at": now,
        "updated_at": now
    }
    
    result = await db.defects.insert_one(defect_doc)
    defect_doc["_id"] = result.inserted_id
    
    # Update device status to defective
    await device_service.update_device_status(
        device_id=defect_data.device_id,
        status=DeviceStatus.DEFECTIVE.value,
        performed_by=str(reporter["_id"]),
        performed_by_name=reporter["name"],
        notes=f"Defect reported: {defect_doc['report_id']}"
    )
    
    # Add device history
    await device_service.add_device_history(
        device_id=defect_data.device_id,
        action="defect_reported",
        status_before=device["status"],
        status_after=DeviceStatus.DEFECTIVE.value,
        location=device.get("current_location"),
        notes=f"Defect: {defect_data.defect_type.value} - {defect_data.severity.value}",
        performed_by=str(reporter["_id"]),
        performed_by_name=reporter["name"]
    )
    
    # Notify admins/managers
    admin_users = await db.users.find({"role": {"$in": ["admin", "manager"]}}).to_list(length=100)
    for admin in admin_users:
        await notification_service.create_notification(
            user_id=str(admin["_id"]),
            title="New Defect Report",
            message=f"A new {defect_data.severity.value} severity defect has been reported for device {device['device_id']}",
            notification_type="warning" if defect_data.severity.value in ["critical", "high"] else "info",
            category="defect",
            link=f"/defects/{str(result.inserted_id)}"
        )
    
    return serialize_doc(defect_doc)


async def update_defect(defect_id: str, defect_data: DefectUpdate) -> Optional[Dict[str, Any]]:
    """Update defect report"""
    db = get_database()
    
    update_dict = {k: v for k, v in defect_data.model_dump().items() if v is not None}
    
    if not update_dict:
        return await get_defect_by_id(defect_id)
    
    # Convert enums to values
    if "defect_type" in update_dict:
        update_dict["defect_type"] = update_dict["defect_type"].value
    if "severity" in update_dict:
        update_dict["severity"] = update_dict["severity"].value
    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value
    
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.defects.update_one(
        {"_id": ObjectId(defect_id)},
        {"$set": update_dict}
    )
    
    if result.modified_count > 0 or result.matched_count > 0:
        return await get_defect_by_id(defect_id)
    return None


async def delete_defect(defect_id: str) -> bool:
    """Delete defect report"""
    db = get_database()
    
    result = await db.defects.delete_one({"_id": ObjectId(defect_id)})
    return result.deleted_count > 0


async def update_defect_status(
    defect_id: str,
    status: str,
    user: Dict[str, Any],
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update defect status"""
    db = get_database()
    
    defect = await db.defects.find_one({"_id": ObjectId(defect_id)})
    if not defect:
        return None
    
    update_data = {
        "status": status,
        "updated_at": datetime.utcnow()
    }
    
    result = await db.defects.update_one(
        {"_id": ObjectId(defect_id)},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        # Notify reporter
        await notification_service.create_notification(
            user_id=defect["reported_by"],
            title=f"Defect Status Updated",
            message=f"Your defect report {defect['report_id']} status has been updated to {status}",
            notification_type="info",
            category="defect",
            link=f"/defects/{defect_id}"
        )
        
        return await get_defect_by_id(defect_id)
    return None


async def resolve_defect(
    defect_id: str,
    resolution: str,
    resolver: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Resolve a defect report"""
    db = get_database()
    
    defect = await db.defects.find_one({"_id": ObjectId(defect_id)})
    if not defect:
        return None
    
    now = datetime.utcnow()
    update_data = {
        "status": DefectStatus.RESOLVED.value,
        "resolution": resolution,
        "resolved_by": str(resolver["_id"]),
        "resolved_by_name": resolver["name"],
        "resolved_at": now,
        "updated_at": now
    }
    
    result = await db.defects.update_one(
        {"_id": ObjectId(defect_id)},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        # Update device status back to available/maintenance
        await device_service.update_device_status(
            device_id=defect["device_id"],
            status=DeviceStatus.MAINTENANCE.value,
            performed_by=str(resolver["_id"]),
            performed_by_name=resolver["name"],
            notes=f"Defect resolved: {defect['report_id']}"
        )
        
        # Notify reporter
        await notification_service.create_notification(
            user_id=defect["reported_by"],
            title="Defect Resolved",
            message=f"Your defect report {defect['report_id']} has been resolved",
            notification_type="success",
            category="defect",
            link=f"/defects/{defect_id}"
        )
        
        return await get_defect_by_id(defect_id)
    return None


async def get_defect_stats() -> Dict[str, Any]:
    """Get defect statistics"""
    db = get_database()
    
    total = await db.defects.count_documents({})
    reported = await db.defects.count_documents({"status": "reported"})
    under_review = await db.defects.count_documents({"status": "under_review"})
    resolved = await db.defects.count_documents({"status": "resolved"})
    
    # By severity
    critical = await db.defects.count_documents({"severity": "critical"})
    high = await db.defects.count_documents({"severity": "high"})
    medium = await db.defects.count_documents({"severity": "medium"})
    low = await db.defects.count_documents({"severity": "low"})
    
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
