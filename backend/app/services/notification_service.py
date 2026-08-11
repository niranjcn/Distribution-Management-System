import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select, delete, func, and_, insert

from app.core.cache_version import bump_cache_version
from app.database_sqlalchemy import async_session_factory
from app.db_models.notification import Notification
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
    return [_parse_notification_metadata(n) for n in notifications]


async def get_notifications(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    is_read: Optional[bool] = None
) -> Dict[str, Any]:
    """Get user notifications with pagination"""
    async with async_session_factory() as session:
        conditions = [Notification.user_id == user_id]

        if is_read is not None:
            conditions.append(Notification.is_read == (1 if is_read else 0))

        where = and_(*conditions)

        count_q = select(func.count()).select_from(Notification).where(where)
        total = (await session.execute(count_q)).scalar()

        offset = (page - 1) * page_size
        q = (
            select(Notification)
            .where(where)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await session.execute(q)).scalars().all()
        data = _parse_notification_list([r.to_dict() for r in rows])

        return {
            "data": data,
            "pagination": get_pagination(page, page_size, total),
        }


async def get_unread_count(user_id: int) -> int:
    """Get count of unread notifications"""
    async with async_session_factory() as session:
        q = (
            select(func.count())
            .select_from(Notification)
            .where(and_(Notification.user_id == user_id, Notification.is_read == 0))
        )
        return (await session.execute(q)).scalar()


async def get_latest_notifications(user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Get latest notifications for a user"""
    async with async_session_factory() as session:
        q = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        rows = (await session.execute(q)).scalars().all()
        return _parse_notification_list([r.to_dict() for r in rows])


async def create_notification(
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "info",
    category: str = "system",
    link: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a new notification"""
    now = datetime.now().replace(tzinfo=None)
    metadata_json = json.dumps(metadata) if metadata else None

    async with async_session_factory() as session:
        n = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            category=category,
            is_read=0,
            link=link,
            notif_metadata=metadata_json,
            created_at=now,
        )
        session.add(n)
        await session.flush()
        await bump_cache_version(session)
        await session.commit()
        return _parse_notification_metadata(n.to_dict())


async def bulk_create_notifications(
    notifications: List[Dict[str, Any]]
) -> None:
    """Create multiple notifications in a single batch INSERT."""
    if not notifications:
        return

    now = datetime.now().replace(tzinfo=None)
    values = []
    for n in notifications:
        metadata_json = json.dumps(n.get("metadata")) if n.get("metadata") else None
        values.append(
            {
                "user_id": int(n["user_id"]),
                "title": n["title"],
                "message": n["message"],
                "type": n.get("notification_type", "info"),
                "category": n.get("category", "system"),
                "is_read": 0,
                "link": n.get("link"),
                "notif_metadata": metadata_json,
                "created_at": now,
            }
        )

    async with async_session_factory() as session:
        stmt = insert(Notification)
        await session.execute(stmt, values)
        await bump_cache_version(session)
        await session.commit()


async def mark_as_read(notification_id: str, user_id: int) -> bool:
    """Mark notification as read"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Notification).where(
                and_(Notification.id == int(notification_id), Notification.user_id == user_id)
            )
        )
        n = result.scalar_one_or_none()
        if not n:
            return False
        n.is_read = 1
        await bump_cache_version(session)
        await session.commit()
        return True


async def mark_all_as_read(user_id: int) -> int:
    """Mark all user notifications as read"""
    async with async_session_factory() as session:
        q = select(Notification).where(
            and_(Notification.user_id == user_id, Notification.is_read == 0)
        )
        rows = (await session.execute(q)).scalars().all()
        count = len(rows)
        for n in rows:
            n.is_read = 1
        await bump_cache_version(session)
        await session.commit()
        return count


async def delete_notification(notification_id: str, user_id: int) -> bool:
    """Delete notification"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Notification).where(
                and_(Notification.id == int(notification_id), Notification.user_id == user_id)
            )
        )
        n = result.scalar_one_or_none()
        if not n:
            return False
        await session.delete(n)
        await bump_cache_version(session)
        await session.commit()
        return True


async def delete_old_notifications(days: int = 30) -> int:
    """Delete notifications older than specified days"""
    cutoff = (datetime.now().replace(tzinfo=None) - timedelta(days=days)).isoformat()
    async with async_session_factory() as session:
        result = await session.execute(delete(Notification).where(Notification.created_at < cutoff))
        count = result.rowcount or 0
        if count:
            await bump_cache_version(session)
        await session.commit()
        return count


async def send_bulk_notification(
    user_ids: List[int],
    title: str,
    message: str,
    notification_type: str = "info",
    category: str = "system",
    link: Optional[str] = None
) -> int:
    """Send notification to multiple users"""
    notifications = [
        {
            "user_id": uid,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "category": category,
            "link": link,
        }
        for uid in user_ids
    ]
    await bulk_create_notifications(notifications)
    return len(user_ids)
