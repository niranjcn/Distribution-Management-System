from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.services import notification_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.get("")
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get user notifications with pagination"""
    result = await notification_service.get_notifications(
        user_id=current_user["id"],
        page=page,
        page_size=page_size,
        is_read=is_read
    )
    
    return {
        "success": True,
        "message": "Notifications retrieved successfully",
        "data": result["data"],
        "pagination": result["pagination"]
    }


@router.get("/unread")
async def get_unread_count(
    current_user: dict = Depends(get_current_user)
):
    """Get count of unread notifications"""
    count = await notification_service.get_unread_count(current_user["id"])
    
    return {
        "success": True,
        "message": "Unread count retrieved",
        "data": {"count": count}
    }


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark notification as read"""
    success = await notification_service.mark_as_read(
        notification_id=notification_id,
        user_id=current_user["id"]
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {
        "success": True,
        "message": "Notification marked as read"
    }


@router.patch("/read-all")
async def mark_all_as_read(
    current_user: dict = Depends(get_current_user)
):
    """Mark all user notifications as read"""
    count = await notification_service.mark_all_as_read(current_user["id"])
    
    return {
        "success": True,
        "message": f"{count} notifications marked as read",
        "data": {"count": count}
    }


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete notification"""
    success = await notification_service.delete_notification(
        notification_id=notification_id,
        user_id=current_user["id"]
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {
        "success": True,
        "message": "Notification deleted successfully"
    }
