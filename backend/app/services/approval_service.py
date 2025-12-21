from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.models.approval import ApprovalStatus, ApprovalType
from app.services import notification_service
from app.utils.helpers import serialize_doc, serialize_docs, get_pagination


async def get_approvals(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    approval_type: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Get all pending approvals with pagination"""
    db = get_database()
    
    # Build query
    query = {}
    if status:
        query["status"] = status
    else:
        query["status"] = ApprovalStatus.PENDING.value
    if approval_type:
        query["approval_type"] = approval_type
    if search:
        query["$or"] = [
            {"requested_by_name": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.approvals.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = db.approvals.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    approvals = await cursor.to_list(length=page_size)
    
    # Enrich with entity details
    enriched_approvals = []
    for approval in approvals:
        approval_data = serialize_doc(approval)
        
        # Get entity details based on type
        if approval["approval_type"] == "distribution":
            entity = await db.distributions.find_one({"_id": ObjectId(approval["entity_id"])})
            if entity:
                approval_data["entity_details"] = {
                    "distribution_id": entity.get("distribution_id"),
                    "device_count": entity.get("device_count"),
                    "from_user_name": entity.get("from_user_name"),
                    "to_user_name": entity.get("to_user_name")
                }
        elif approval["approval_type"] == "return":
            entity = await db.returns.find_one({"_id": ObjectId(approval["entity_id"])})
            if entity:
                approval_data["entity_details"] = {
                    "return_id": entity.get("return_id"),
                    "device_serial": entity.get("device_serial"),
                    "reason": entity.get("reason"),
                    "requested_by_name": entity.get("requested_by_name")
                }
        elif approval["approval_type"] == "defect":
            entity = await db.defects.find_one({"_id": ObjectId(approval["entity_id"])})
            if entity:
                approval_data["entity_details"] = {
                    "report_id": entity.get("report_id"),
                    "device_serial": entity.get("device_serial"),
                    "defect_type": entity.get("defect_type"),
                    "severity": entity.get("severity")
                }
        
        enriched_approvals.append(approval_data)
    
    return {
        "data": enriched_approvals,
        "pagination": get_pagination(page, page_size, total)
    }


async def get_approval_by_id(approval_id: str) -> Optional[Dict[str, Any]]:
    """Get approval by ID with entity details"""
    db = get_database()
    
    try:
        approval = await db.approvals.find_one({"_id": ObjectId(approval_id)})
        if not approval:
            return None
        
        approval_data = serialize_doc(approval)
        
        # Get entity details
        if approval["approval_type"] == "distribution":
            entity = await db.distributions.find_one({"_id": ObjectId(approval["entity_id"])})
            if entity:
                approval_data["entity_details"] = serialize_doc(entity)
        elif approval["approval_type"] == "return":
            entity = await db.returns.find_one({"_id": ObjectId(approval["entity_id"])})
            if entity:
                approval_data["entity_details"] = serialize_doc(entity)
        elif approval["approval_type"] == "defect":
            entity = await db.defects.find_one({"_id": ObjectId(approval["entity_id"])})
            if entity:
                approval_data["entity_details"] = serialize_doc(entity)
        
        return approval_data
    except:
        return None


async def approve_request(
    approval_id: str,
    approver: Dict[str, Any],
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Approve a pending request"""
    db = get_database()
    
    approval = await db.approvals.find_one({"_id": ObjectId(approval_id)})
    if not approval:
        return None
    
    if approval["status"] != ApprovalStatus.PENDING.value:
        raise ValueError("This request has already been processed")
    
    now = datetime.utcnow()
    update_data = {
        "status": ApprovalStatus.APPROVED.value,
        "approved_by": str(approver["_id"]),
        "approved_by_name": approver["name"],
        "approval_date": now,
        "notes": notes,
        "updated_at": now
    }
    
    await db.approvals.update_one(
        {"_id": ObjectId(approval_id)},
        {"$set": update_data}
    )
    
    # Update the related entity
    if approval["approval_type"] == "distribution":
        await db.distributions.update_one(
            {"_id": ObjectId(approval["entity_id"])},
            {
                "$set": {
                    "status": "approved",
                    "approval_date": now,
                    "approved_by": str(approver["_id"]),
                    "approved_by_name": approver["name"],
                    "updated_at": now
                }
            }
        )
    elif approval["approval_type"] == "return":
        await db.returns.update_one(
            {"_id": ObjectId(approval["entity_id"])},
            {
                "$set": {
                    "status": "approved",
                    "approval_date": now,
                    "approved_by": str(approver["_id"]),
                    "approved_by_name": approver["name"],
                    "updated_at": now
                }
            }
        )
    elif approval["approval_type"] == "defect":
        await db.defects.update_one(
            {"_id": ObjectId(approval["entity_id"])},
            {
                "$set": {
                    "status": "approved",
                    "updated_at": now
                }
            }
        )
    
    # Notify requester
    await notification_service.create_notification(
        user_id=approval["requested_by"],
        title="Request Approved",
        message=f"Your {approval['approval_type']} request has been approved by {approver['name']}",
        notification_type="success",
        category="approval"
    )
    
    return await get_approval_by_id(approval_id)


async def reject_request(
    approval_id: str,
    approver: Dict[str, Any],
    rejection_reason: Optional[str] = None,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Reject a pending request"""
    db = get_database()
    
    approval = await db.approvals.find_one({"_id": ObjectId(approval_id)})
    if not approval:
        return None
    
    if approval["status"] != ApprovalStatus.PENDING.value:
        raise ValueError("This request has already been processed")
    
    now = datetime.utcnow()
    update_data = {
        "status": ApprovalStatus.REJECTED.value,
        "approved_by": str(approver["_id"]),
        "approved_by_name": approver["name"],
        "approval_date": now,
        "rejection_reason": rejection_reason,
        "notes": notes,
        "updated_at": now
    }
    
    await db.approvals.update_one(
        {"_id": ObjectId(approval_id)},
        {"$set": update_data}
    )
    
    # Update the related entity
    if approval["approval_type"] == "distribution":
        await db.distributions.update_one(
            {"_id": ObjectId(approval["entity_id"])},
            {
                "$set": {
                    "status": "rejected",
                    "notes": rejection_reason,
                    "updated_at": now
                }
            }
        )
    elif approval["approval_type"] == "return":
        await db.returns.update_one(
            {"_id": ObjectId(approval["entity_id"])},
            {
                "$set": {
                    "status": "rejected",
                    "updated_at": now
                }
            }
        )
    elif approval["approval_type"] == "defect":
        await db.defects.update_one(
            {"_id": ObjectId(approval["entity_id"])},
            {
                "$set": {
                    "status": "rejected",
                    "updated_at": now
                }
            }
        )
    
    # Notify requester
    await notification_service.create_notification(
        user_id=approval["requested_by"],
        title="Request Rejected",
        message=f"Your {approval['approval_type']} request has been rejected by {approver['name']}. Reason: {rejection_reason or 'No reason provided'}",
        notification_type="error",
        category="approval"
    )
    
    return await get_approval_by_id(approval_id)


async def get_approval_stats() -> Dict[str, int]:
    """Get approval statistics"""
    db = get_database()
    
    pending = await db.approvals.count_documents({"status": "pending"})
    approved = await db.approvals.count_documents({"status": "approved"})
    rejected = await db.approvals.count_documents({"status": "rejected"})
    
    # By type
    distributions = await db.approvals.count_documents({"approval_type": "distribution", "status": "pending"})
    returns = await db.approvals.count_documents({"approval_type": "return", "status": "pending"})
    defects = await db.approvals.count_documents({"approval_type": "defect", "status": "pending"})
    
    return {
        "total_pending": pending,
        "approved": approved,
        "rejected": rejected,
        "by_type": {
            "distributions": distributions,
            "returns": returns,
            "defects": defects
        }
    }
