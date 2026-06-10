from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import json

from app.database import get_db, row_to_dict, rows_to_list
from app.utils.helpers import get_pagination


def _parse_notification_metadata(notification: Dict[str, Any]) -> Dict[str, Any]:
    metadata = notification.get("metadata")
    if isinstance(metadata, str):
        try:
            notification["metadata"] = json.loads(metadata)
        except json.JSONDecodeError:
            notification["metadata"] = None
    return notification


def _parse_notification_list(notifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_parse_notification_metadata(notification) for notification in notifications]


async def get_notifications(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    is_read: Optional[bool] = None
) -> Dict[str, Any]:
    """Get user notifications with pagination"""
    async with get_db() as db:
        conditions = ["user_id = ?"]
        params = [user_id]
        
        if is_read is not None:
            conditions.append("is_read = ?")
            params.append(1 if is_read else 0)
        
        where_clause = " AND ".join(conditions)
        
        cursor = await db.execute(f"SELECT COUNT(*) FROM notifications WHERE {where_clause}", params)
        total = (await cursor.fetchone())[0]
        
        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"SELECT * FROM notifications WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = await cursor.fetchall()
        data = _parse_notification_list(rows_to_list(rows))
        
        return {
            "data": data,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_unread_count(user_id: str) -> int:
    """Get count of unread notifications"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,)
        )
        return (await cursor.fetchone())[0]


async def get_latest_notifications(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get latest notifications for a user"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return _parse_notification_list(rows_to_list(rows))


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
    async with get_db() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        metadata_json = json.dumps(metadata) if metadata else None
        
        cursor = await db.execute(
            """INSERT INTO notifications (user_id, title, message, type, category, is_read, link, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, title, message, notification_type, category, 0, link, metadata_json, now)
        )
        await db.commit()
        
        cursor = await db.execute("SELECT * FROM notifications WHERE id = ?", (cursor.lastrowid,))
        row = await cursor.fetchone()
        return _parse_notification_metadata(row_to_dict(row))


async def mark_as_read(notification_id: str, user_id: str) -> bool:
    """Mark notification as read"""
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (int(notification_id), user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def mark_all_as_read(user_id: str) -> int:
    """Mark all user notifications as read"""
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
            (user_id,)
        )
        await db.commit()
        return cursor.rowcount


async def delete_notification(notification_id: str, user_id: str) -> bool:
    """Delete notification"""
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM notifications WHERE id = ? AND user_id = ?",
            (int(notification_id), user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_old_notifications(days: int = 30) -> int:
    """Delete notifications older than specified days"""
    cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)).isoformat()
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM notifications WHERE created_at < ?", (cutoff,))
        await db.commit()
        return cursor.rowcount


async def send_bulk_notification(
    user_ids: List[str],
    title: str,
    message: str,
    notification_type: str = "info",
    category: str = "system",
    link: Optional[str] = None
) -> int:
    """Send notification to multiple users"""
    async with get_db() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        count = 0
        for uid in user_ids:
            await db.execute(
                """INSERT INTO notifications (user_id, title, message, type, category, is_read, link, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (uid, title, message, notification_type, category, 0, link, now)
            )
            count += 1
        await db.commit()
        return count
