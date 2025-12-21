from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.models.distribution import DistributionCreate, DistributionUpdate, DistributionStatus, UserType
from app.models.device import DeviceStatus, HolderType
from app.services import device_service, notification_service
from app.utils.helpers import serialize_doc, serialize_docs, get_pagination, generate_distribution_id


async def get_distributions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    from_user_id: Optional[str] = None,
    to_user_id: Optional[str] = None,
    user_id: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Get all distributions with pagination and filters"""
    db = get_database()
    
    # Build query
    query = {}
    if status:
        query["status"] = status
    if from_user_id:
        query["from_user_id"] = from_user_id
    if to_user_id:
        query["to_user_id"] = to_user_id
    if user_id:
        # User can see distributions where they are sender or recipient
        query["$or"] = [
            {"from_user_id": user_id},
            {"to_user_id": user_id}
        ]
    if search:
        query["$or"] = [
            {"distribution_id": {"$regex": search, "$options": "i"}},
            {"from_user_name": {"$regex": search, "$options": "i"}},
            {"to_user_name": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.distributions.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = db.distributions.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    distributions = await cursor.to_list(length=page_size)
    
    return {
        "data": serialize_docs(distributions),
        "pagination": get_pagination(page, page_size, total)
    }


async def get_distribution_by_id(distribution_id: str) -> Optional[Dict[str, Any]]:
    """Get distribution by ID"""
    db = get_database()
    
    try:
        distribution = await db.distributions.find_one({"_id": ObjectId(distribution_id)})
        return serialize_doc(distribution) if distribution else None
    except:
        return None


async def create_distribution(
    dist_data: DistributionCreate,
    from_user: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a new distribution request"""
    db = get_database()
    
    # Get recipient user
    to_user = await db.users.find_one({"_id": ObjectId(dist_data.to_user_id)})
    if not to_user:
        raise ValueError("Recipient user not found")
    
    # Validate devices exist and are available
    for device_id in dist_data.device_ids:
        device = await db.devices.find_one({"_id": ObjectId(device_id)})
        if not device:
            raise ValueError(f"Device {device_id} not found")
        if device["status"] != DeviceStatus.AVAILABLE.value:
            raise ValueError(f"Device {device['device_id']} is not available")
    
    # Determine user types based on roles
    role_to_type = {
        "admin": "noc",
        "manager": "noc",
        "distributor": "distributor",
        "sub_distributor": "sub_distributor",
        "operator": "operator"
    }
    
    now = datetime.utcnow()
    dist_doc = {
        "distribution_id": generate_distribution_id(),
        "device_ids": dist_data.device_ids,
        "device_count": len(dist_data.device_ids),
        "from_user_id": str(from_user["_id"]),
        "from_user_name": from_user["name"],
        "from_user_type": role_to_type.get(from_user["role"], "noc"),
        "to_user_id": str(to_user["_id"]),
        "to_user_name": to_user["name"],
        "to_user_type": role_to_type.get(to_user["role"], "distributor"),
        "status": DistributionStatus.PENDING.value,
        "request_date": now,
        "approval_date": None,
        "delivery_date": None,
        "notes": dist_data.notes,
        "approved_by": None,
        "approved_by_name": None,
        "created_by": str(from_user["_id"]),
        "created_at": now,
        "updated_at": now
    }
    
    result = await db.distributions.insert_one(dist_doc)
    dist_doc["_id"] = result.inserted_id
    
    # Create approval entry
    approval_doc = {
        "approval_type": "distribution",
        "entity_id": str(result.inserted_id),
        "entity_type": "distribution",
        "requested_by": str(from_user["_id"]),
        "requested_by_name": from_user["name"],
        "status": "pending",
        "priority": "medium",
        "request_date": now,
        "approved_by": None,
        "approved_by_name": None,
        "approval_date": None,
        "rejection_reason": None,
        "notes": dist_data.notes,
        "created_at": now,
        "updated_at": now
    }
    await db.approvals.insert_one(approval_doc)
    
    # Send notification to recipient
    await notification_service.create_notification(
        user_id=str(to_user["_id"]),
        title="New Distribution Request",
        message=f"You have a new distribution request from {from_user['name']} for {len(dist_data.device_ids)} device(s)",
        notification_type="info",
        category="distribution",
        link=f"/distributions/{str(result.inserted_id)}"
    )
    
    return serialize_doc(dist_doc)


async def update_distribution_status(
    distribution_id: str,
    status: str,
    user: Dict[str, Any],
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update distribution status"""
    db = get_database()
    
    distribution = await db.distributions.find_one({"_id": ObjectId(distribution_id)})
    if not distribution:
        return None
    
    update_data = {
        "status": status,
        "updated_at": datetime.utcnow()
    }
    
    if status == DistributionStatus.APPROVED.value:
        update_data["approval_date"] = datetime.utcnow()
        update_data["approved_by"] = str(user["_id"])
        update_data["approved_by_name"] = user["name"]
        
        # Update approval record
        await db.approvals.update_one(
            {"entity_id": distribution_id, "approval_type": "distribution"},
            {
                "$set": {
                    "status": "approved",
                    "approved_by": str(user["_id"]),
                    "approved_by_name": user["name"],
                    "approval_date": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    elif status == DistributionStatus.DELIVERED.value:
        update_data["delivery_date"] = datetime.utcnow()
        
        # Update device holders
        for device_id in distribution["device_ids"]:
            await device_service.update_device_holder(
                device_id=device_id,
                holder_id=distribution["to_user_id"],
                holder_name=distribution["to_user_name"],
                holder_type=distribution["to_user_type"],
                location=distribution["to_user_name"],
                status=DeviceStatus.DISTRIBUTED.value,
                performed_by=str(user["_id"]),
                performed_by_name=user["name"],
                from_user_id=distribution["from_user_id"],
                from_user_name=distribution["from_user_name"],
                notes=f"Distributed via {distribution['distribution_id']}"
            )
    
    elif status == DistributionStatus.REJECTED.value:
        # Update approval record
        await db.approvals.update_one(
            {"entity_id": distribution_id, "approval_type": "distribution"},
            {
                "$set": {
                    "status": "rejected",
                    "approved_by": str(user["_id"]),
                    "approved_by_name": user["name"],
                    "approval_date": datetime.utcnow(),
                    "rejection_reason": notes,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    if notes:
        update_data["notes"] = notes
    
    result = await db.distributions.update_one(
        {"_id": ObjectId(distribution_id)},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        # Send notification
        await notification_service.create_notification(
            user_id=distribution["from_user_id"],
            title=f"Distribution {status.capitalize()}",
            message=f"Your distribution request {distribution['distribution_id']} has been {status}",
            notification_type="success" if status in ["approved", "delivered"] else "warning",
            category="distribution",
            link=f"/distributions/{distribution_id}"
        )
        
        return await get_distribution_by_id(distribution_id)
    return None


async def cancel_distribution(distribution_id: str, user_id: str) -> bool:
    """Cancel a distribution (only by creator)"""
    db = get_database()
    
    distribution = await db.distributions.find_one({"_id": ObjectId(distribution_id)})
    if not distribution:
        return False
    
    # Check if user is the creator
    if distribution["created_by"] != user_id:
        raise ValueError("Only the creator can cancel this distribution")
    
    # Check if distribution is still pending
    if distribution["status"] != DistributionStatus.PENDING.value:
        raise ValueError("Only pending distributions can be cancelled")
    
    result = await db.distributions.update_one(
        {"_id": ObjectId(distribution_id)},
        {
            "$set": {
                "status": DistributionStatus.CANCELLED.value,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count > 0:
        # Update approval record
        await db.approvals.delete_one({"entity_id": distribution_id, "approval_type": "distribution"})
        return True
    return False


async def get_pending_distributions() -> List[Dict[str, Any]]:
    """Get all pending distributions"""
    db = get_database()
    
    cursor = db.distributions.find({"status": DistributionStatus.PENDING.value}).sort("created_at", -1)
    distributions = await cursor.to_list(length=100)
    
    return serialize_docs(distributions)


async def get_distribution_stats() -> Dict[str, int]:
    """Get distribution statistics"""
    db = get_database()
    
    total = await db.distributions.count_documents({})
    pending = await db.distributions.count_documents({"status": "pending"})
    approved = await db.distributions.count_documents({"status": "approved"})
    delivered = await db.distributions.count_documents({"status": "delivered"})
    rejected = await db.distributions.count_documents({"status": "rejected"})
    
    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "delivered": delivered,
        "rejected": rejected
    }
