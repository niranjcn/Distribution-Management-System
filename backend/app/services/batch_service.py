from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.models.batch import BatchCreate, BatchUpdate
from app.utils.helpers import serialize_doc, serialize_docs, get_pagination


def generate_batch_id() -> str:
    """Generate unique batch ID"""
    import time
    timestamp = int(time.time() * 1000)
    return f"BATCH-{timestamp}"


async def get_batches(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Get all batches with pagination"""
    db = get_database()
    
    # Build query
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"batch_id": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.batches.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = db.batches.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    batches = await cursor.to_list(length=page_size)
    
    # Get device count for each batch
    for batch in batches:
        device_count = await db.devices.count_documents({"batch_id": str(batch["_id"])})
        batch["device_count"] = device_count
    
    return {
        "data": serialize_docs(batches),
        "pagination": get_pagination(page, page_size, total)
    }


async def get_batch_by_id(batch_id: str) -> Optional[Dict[str, Any]]:
    """Get batch by ID"""
    db = get_database()
    
    try:
        batch = await db.batches.find_one({"_id": ObjectId(batch_id)})
        if batch:
            # Get device count
            device_count = await db.devices.count_documents({"batch_id": batch_id})
            batch["device_count"] = device_count
        return serialize_doc(batch) if batch else None
    except:
        return None


async def create_batch(batch_data: BatchCreate, created_by: str, created_by_name: str) -> Dict[str, Any]:
    """Create a new batch"""
    db = get_database()
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    batch_doc = {
        "batch_id": generate_batch_id(),
        "name": batch_data.name,
        "description": batch_data.description,
        "created_by": created_by,
        "created_by_name": created_by_name,
        "device_count": 0,
        "created_at": now,
        "updated_at": now
    }
    
    result = await db.batches.insert_one(batch_doc)
    batch_doc["_id"] = result.inserted_id
    
    return serialize_doc(batch_doc)


async def update_batch(batch_id: str, batch_data: BatchUpdate) -> Optional[Dict[str, Any]]:
    """Update batch"""
    db = get_database()
    
    update_dict = {k: v for k, v in batch_data.model_dump().items() if v is not None}
    
    if not update_dict:
        return await get_batch_by_id(batch_id)
    
    update_dict["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    
    result = await db.batches.update_one(
        {"_id": ObjectId(batch_id)},
        {"$set": update_dict}
    )
    
    if result.modified_count > 0 or result.matched_count > 0:
        return await get_batch_by_id(batch_id)
    return None


async def delete_batch(batch_id: str) -> bool:
    """Delete batch if it has no devices"""
    db = get_database()
    
    # Check if batch has any devices
    device_count = await db.devices.count_documents({"batch_id": batch_id})
    if device_count > 0:
        raise ValueError("Cannot delete batch with devices. Please remove all devices first.")
    
    result = await db.batches.delete_one({"_id": ObjectId(batch_id)})
    return result.deleted_count > 0


async def get_batch_devices(batch_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """Get all devices in a batch"""
    db = get_database()
    
    # Verify batch exists
    batch = await db.batches.find_one({"_id": ObjectId(batch_id)})
    if not batch:
        return None
    
    query = {"batch_id": batch_id}
    
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


async def get_batch_stats() -> Dict[str, int]:
    """Get batch statistics"""
    db = get_database()
    
    total_batches = await db.batches.count_documents({})
    
    return {
        "total": total_batches
    }
