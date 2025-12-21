from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.models.return_device import ReturnCreate, ReturnUpdate, ReturnStatus, ReturnReason
from app.models.device import DeviceStatus
from app.services import device_service, notification_service
from app.utils.helpers import serialize_doc, serialize_docs, get_pagination, generate_return_id


async def get_returns(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    reason: Optional[str] = None,
    requested_by: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Get all return requests with pagination and filters"""
    db = get_database()
    
    # Build query
    query = {}
    if status:
        query["status"] = status
    if reason:
        query["reason"] = reason
    if requested_by:
        query["requested_by"] = requested_by
    if search:
        query["$or"] = [
            {"return_id": {"$regex": search, "$options": "i"}},
            {"device_serial": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.returns.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = db.returns.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    returns = await cursor.to_list(length=page_size)
    
    return {
        "data": serialize_docs(returns),
        "pagination": get_pagination(page, page_size, total)
    }


async def get_return_by_id(return_id: str) -> Optional[Dict[str, Any]]:
    """Get return request by ID"""
    db = get_database()
    
    try:
        return_req = await db.returns.find_one({"_id": ObjectId(return_id)})
        return serialize_doc(return_req) if return_req else None
    except:
        return None


async def create_return(return_data: ReturnCreate, requester: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new return request"""
    db = get_database()
    
    # Get device info
    device = await db.devices.find_one({"_id": ObjectId(return_data.device_id)})
    if not device:
        raise ValueError("Device not found")
    
    # Determine who to return to based on current holder type
    # Returns go up the chain: operator -> sub_distributor -> distributor -> noc
    return_to_user = None
    
    # For simplicity, find a manager or admin to return to
    return_to_user = await db.users.find_one({"role": {"$in": ["admin", "manager"]}})
    if not return_to_user:
        raise ValueError("No admin/manager found to process return")
    
    now = datetime.utcnow()
    return_doc = {
        "return_id": generate_return_id(),
        "device_id": return_data.device_id,
        "device_serial": device["serial_number"],
        "device_type": device["device_type"],
        "requested_by": str(requester["_id"]),
        "requested_by_name": requester["name"],
        "return_to": str(return_to_user["_id"]),
        "return_to_name": return_to_user["name"],
        "reason": return_data.reason.value,
        "description": return_data.description,
        "status": ReturnStatus.PENDING.value,
        "request_date": now,
        "approval_date": None,
        "received_date": None,
        "approved_by": None,
        "approved_by_name": None,
        "created_at": now,
        "updated_at": now
    }
    
    result = await db.returns.insert_one(return_doc)
    return_doc["_id"] = result.inserted_id
    
    # Create approval entry
    approval_doc = {
        "approval_type": "return",
        "entity_id": str(result.inserted_id),
        "entity_type": "return",
        "requested_by": str(requester["_id"]),
        "requested_by_name": requester["name"],
        "status": "pending",
        "priority": "medium",
        "request_date": now,
        "approved_by": None,
        "approved_by_name": None,
        "approval_date": None,
        "rejection_reason": None,
        "notes": return_data.description,
        "created_at": now,
        "updated_at": now
    }
    await db.approvals.insert_one(approval_doc)
    
    # Notify return_to user
    await notification_service.create_notification(
        user_id=str(return_to_user["_id"]),
        title="New Return Request",
        message=f"A return request has been submitted by {requester['name']} for device {device['device_id']}",
        notification_type="info",
        category="return",
        link=f"/returns/{str(result.inserted_id)}"
    )
    
    return serialize_doc(return_doc)


async def update_return_status(
    return_id: str,
    status: str,
    user: Dict[str, Any],
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update return request status"""
    db = get_database()
    
    return_req = await db.returns.find_one({"_id": ObjectId(return_id)})
    if not return_req:
        return None
    
    update_data = {
        "status": status,
        "updated_at": datetime.utcnow()
    }
    
    if status == ReturnStatus.APPROVED.value:
        update_data["approval_date"] = datetime.utcnow()
        update_data["approved_by"] = str(user["_id"])
        update_data["approved_by_name"] = user["name"]
        
        # Update approval record
        await db.approvals.update_one(
            {"entity_id": return_id, "approval_type": "return"},
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
    
    elif status == ReturnStatus.RECEIVED.value:
        update_data["received_date"] = datetime.utcnow()
        
        # Update device status and holder
        await device_service.update_device_holder(
            device_id=return_req["device_id"],
            holder_id=None,
            holder_name=None,
            holder_type="noc",
            location="NOC",
            status=DeviceStatus.RETURNED.value,
            performed_by=str(user["_id"]),
            performed_by_name=user["name"],
            from_user_id=return_req["requested_by"],
            from_user_name=return_req["requested_by_name"],
            notes=f"Returned via {return_req['return_id']}"
        )
    
    elif status == ReturnStatus.REJECTED.value:
        # Update approval record
        await db.approvals.update_one(
            {"entity_id": return_id, "approval_type": "return"},
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
    
    result = await db.returns.update_one(
        {"_id": ObjectId(return_id)},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        # Notify requester
        await notification_service.create_notification(
            user_id=return_req["requested_by"],
            title=f"Return Request {status.capitalize()}",
            message=f"Your return request {return_req['return_id']} has been {status}",
            notification_type="success" if status in ["approved", "received"] else "warning",
            category="return",
            link=f"/returns/{return_id}"
        )
        
        return await get_return_by_id(return_id)
    return None


async def cancel_return(return_id: str, user_id: str) -> bool:
    """Cancel a return request (only by creator)"""
    db = get_database()
    
    return_req = await db.returns.find_one({"_id": ObjectId(return_id)})
    if not return_req:
        return False
    
    # Check if user is the creator
    if return_req["requested_by"] != user_id:
        raise ValueError("Only the requester can cancel this return request")
    
    # Check if return is still pending
    if return_req["status"] != ReturnStatus.PENDING.value:
        raise ValueError("Only pending return requests can be cancelled")
    
    result = await db.returns.update_one(
        {"_id": ObjectId(return_id)},
        {
            "$set": {
                "status": ReturnStatus.CANCELLED.value,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count > 0:
        # Update approval record
        await db.approvals.delete_one({"entity_id": return_id, "approval_type": "return"})
        return True
    return False


async def get_return_stats() -> Dict[str, Any]:
    """Get return statistics"""
    db = get_database()
    
    total = await db.returns.count_documents({})
    pending = await db.returns.count_documents({"status": "pending"})
    approved = await db.returns.count_documents({"status": "approved"})
    received = await db.returns.count_documents({"status": "received"})
    rejected = await db.returns.count_documents({"status": "rejected"})
    
    # By reason
    defective = await db.returns.count_documents({"reason": "defective"})
    unused = await db.returns.count_documents({"reason": "unused"})
    end_of_contract = await db.returns.count_documents({"reason": "end_of_contract"})
    
    return {
        "total": total,
        "by_status": {
            "pending": pending,
            "approved": approved,
            "received": received,
            "rejected": rejected
        },
        "by_reason": {
            "defective": defective,
            "unused": unused,
            "end_of_contract": end_of_contract
        }
    }
