from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.models.notification import NotificationCreate, NotificationType, NotificationCategory
from app.utils.helpers import serialize_doc, serialize_docs, get_pagination


async def get_notifications(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    is_read: Optional[bool] = None
) -> Dict[str, Any]:
    """Get user notifications with pagination"""
    db = get_database()
    
    # Build query
    query = {"user_id": user_id}
    if is_read is not None:
        query["is_read"] = is_read
    
    # Get total count
    total = await db.notifications.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = db.notifications.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    notifications = await cursor.to_list(length=page_size)
    
    return {
        "data": serialize_docs(notifications),
        "pagination": get_pagination(page, page_size, total)
    }


async def get_unread_count(user_id: str) -> int:
    """Get count of unread notifications"""
    db = get_database()
    return await db.notifications.count_documents({"user_id": user_id, "is_read": False})


async def create_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    category: str = "system",
    link: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a new notification"""
    db = get_database()
    
    notification_doc = {
        "user_id": user_id,
        "title": title,
        "message": message,
        "type": notification_type,
        "category": category,
        "is_read": False,
        "link": link,
        "metadata": metadata,
        "created_at": datetime.utcnow()
    }
    
    result = await db.notifications.insert_one(notification_doc)
    notification_doc["_id"] = result.inserted_id
    
    return serialize_doc(notification_doc)


async def mark_as_read(notification_id: str, user_id: str) -> bool:
    """Mark notification as read"""
    db = get_database()
    
    result = await db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": user_id},
        {"$set": {"is_read": True}}
    )
    
    return result.modified_count > 0


async def mark_all_as_read(user_id: str) -> int:
    """Mark all user notifications as read"""
    db = get_database()
    
    result = await db.notifications.update_many(
        {"user_id": user_id, "is_read": False},
        {"$set": {"is_read": True}}
    )
    
    return result.modified_count


async def delete_notification(notification_id: str, user_id: str) -> bool:
    """Delete notification"""
    db = get_database()
    
    result = await db.notifications.delete_one(
        {"_id": ObjectId(notification_id), "user_id": user_id}
    )
    
    return result.deleted_count > 0


async def delete_old_notifications(days: int = 30) -> int:
    """Delete notifications older than specified days"""
    db = get_database()
    
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.notifications.delete_many(
        {"created_at": {"$lt": cutoff_date}}
    )
    
    return result.deleted_count


async def send_bulk_notification(
    user_ids: List[str],
    title: str,
    message: str,
    notification_type: str = "info",
    category: str = "system",
    link: Optional[str] = None
) -> int:
    """Send notification to multiple users"""
    db = get_database()
    
    notifications = []
    now = datetime.utcnow()
    
    for user_id in user_ids:
        notifications.append({
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": notification_type,
            "category": category,
            "is_read": False,
            "link": link,
            "metadata": None,
            "created_at": now
        })
    
    if notifications:
        result = await db.notifications.insert_many(notifications)
        return len(result.inserted_ids)
    
    return 0
