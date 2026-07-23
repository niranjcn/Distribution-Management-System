import logging
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.services import notification_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("", summary="Get user notifications with pagination")
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    is_read: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get user notifications with pagination"""
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/unread", summary="Get count of unread notifications")
async def get_unread_count(
    current_user: dict = Depends(get_current_user)
):
    """Get count of unread notifications"""
    try:
        count = await notification_service.get_unread_count(current_user["id"])

        return {
            "success": True,
            "message": "Unread count retrieved",
            "data": {"count": count}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/latest", summary="Get latest notifications for the user")
async def get_latest_notifications(
    limit: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(get_current_user)
):
    """Get latest notifications for the user"""
    try:
        notifications = await notification_service.get_latest_notifications(
            user_id=current_user["id"],
            limit=limit
        )

        return {
            "success": True,
            "message": "Latest notifications retrieved",
            "data": notifications
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.patch("/{notification_id}/read", summary="Mark notification as read")
async def mark_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark notification as read"""
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.patch("/read-all", summary="Mark all user notifications as read")
async def mark_all_as_read(
    current_user: dict = Depends(get_current_user)
):
    """Mark all user notifications as read"""
    try:
        count = await notification_service.mark_all_as_read(current_user["id"])

        return {
            "success": True,
            "message": f"{count} notifications marked as read",
            "data": {"count": count}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.delete("/{notification_id}", summary="Delete notification")
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



