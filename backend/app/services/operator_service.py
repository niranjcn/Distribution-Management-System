from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.models.operator import OperatorCreate, OperatorUpdate, OperatorStatus
from app.utils.helpers import serialize_doc, serialize_docs, get_pagination, generate_operator_id


async def get_operators(
    page: int = 1,
    page_size: int = 20,
    assigned_to: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Get all operators with pagination and filters"""
    db = get_database()
    
    # Build query
    query = {}
    if assigned_to:
        query["assigned_to"] = assigned_to
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"area": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.operators.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = db.operators.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    operators = await cursor.to_list(length=page_size)
    
    return {
        "data": serialize_docs(operators),
        "pagination": get_pagination(page, page_size, total)
    }


async def get_operator_by_id(operator_id: str) -> Optional[Dict[str, Any]]:
    """Get operator by ID"""
    db = get_database()
    
    try:
        operator = await db.operators.find_one({"_id": ObjectId(operator_id)})
        return serialize_doc(operator) if operator else None
    except:
        return None


async def create_operator(operator_data: OperatorCreate, created_by: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new operator"""
    db = get_database()
    
    now = datetime.utcnow()
    operator_doc = {
        "operator_id": generate_operator_id(),
        "name": operator_data.name,
        "phone": operator_data.phone,
        "email": operator_data.email,
        "address": operator_data.address,
        "area": operator_data.area,
        "city": operator_data.city,
        "assigned_to": str(created_by["_id"]),
        "assigned_to_name": created_by["name"],
        "status": OperatorStatus.ACTIVE.value,
        "device_count": 0,
        "connection_type": operator_data.connection_type.value if operator_data.connection_type else None,
        "created_at": now,
        "updated_at": now
    }
    
    result = await db.operators.insert_one(operator_doc)
    operator_doc["_id"] = result.inserted_id
    
    return serialize_doc(operator_doc)


async def update_operator(operator_id: str, operator_data: OperatorUpdate) -> Optional[Dict[str, Any]]:
    """Update operator"""
    db = get_database()
    
    update_dict = {k: v for k, v in operator_data.model_dump().items() if v is not None}
    
    if not update_dict:
        return await get_operator_by_id(operator_id)
    
    # Convert enums to values
    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value
    if "connection_type" in update_dict:
        update_dict["connection_type"] = update_dict["connection_type"].value
    
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.operators.update_one(
        {"_id": ObjectId(operator_id)},
        {"$set": update_dict}
    )
    
    if result.modified_count > 0 or result.matched_count > 0:
        return await get_operator_by_id(operator_id)
    return None


async def delete_operator(operator_id: str) -> bool:
    """Delete operator"""
    db = get_database()
    
    result = await db.operators.delete_one({"_id": ObjectId(operator_id)})
    return result.deleted_count > 0


async def get_operator_devices(operator_id: str) -> List[Dict[str, Any]]:
    """Get devices assigned to an operator"""
    db = get_database()
    
    cursor = db.devices.find({"current_holder_id": operator_id})
    devices = await cursor.to_list(length=100)
    
    return serialize_docs(devices)


async def update_operator_device_count(operator_id: str) -> None:
    """Update operator's device count"""
    db = get_database()
    
    count = await db.devices.count_documents({"current_holder_id": operator_id})
    
    await db.operators.update_one(
        {"_id": ObjectId(operator_id)},
        {"$set": {"device_count": count, "updated_at": datetime.utcnow()}}
    )


async def get_operator_stats(assigned_to: Optional[str] = None) -> Dict[str, int]:
    """Get operator statistics"""
    db = get_database()
    
    query = {}
    if assigned_to:
        query["assigned_to"] = assigned_to
    
    total = await db.operators.count_documents(query)
    active = await db.operators.count_documents({**query, "status": "active"})
    inactive = await db.operators.count_documents({**query, "status": "inactive"})
    
    return {
        "total": total,
        "active": active,
        "inactive": inactive
    }
