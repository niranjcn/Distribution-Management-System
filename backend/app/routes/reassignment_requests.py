import logging
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional

from app.services import reassignment_request_service
from app.middleware.auth_middleware import get_current_user
from app.core.activity_logger import log_business_activity

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", summary="Get reassignment requests")
async def get_reassignment_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    req_status: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
):
    actor_role = current_user.get("role", "")
    if actor_role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can view reassignment requests")

    try:
        result = await reassignment_request_service.get_reassignment_requests(
            page=page, page_size=page_size, status=req_status
        )
        return {
            "success": True,
            "message": "Reassignment requests retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred")


@router.get("/{request_id}", summary="Get reassignment request")
async def get_reassignment_request(
    request_id: str,
    current_user: dict = Depends(get_current_user),
):
    actor_role = current_user.get("role", "")
    if actor_role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can view reassignment requests")

    try:
        req = await reassignment_request_service.get_reassignment_request(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reassignment request not found")
        return {"success": True, "message": "Reassignment request retrieved", "data": req}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred")


@router.post("/{request_id}/reassign", summary="Reassign users")
async def reassign_users(
    request_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    actor_role = current_user.get("role", "")
    if actor_role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can reassign users")

    new_parent_id = body.get("reassign_to_id")
    new_parent_name = body.get("reassign_to_name", "")
    new_parent_role = body.get("reassign_to_role", "")

    if not new_parent_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reassign_to_id is required")

    try:
        success, message = await reassignment_request_service.reassign_users(
            request_id=request_id,
            new_parent_id=int(new_parent_id),
            new_parent_name=new_parent_name,
            new_parent_role=new_parent_role,
            deleted_by_user=current_user,
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
        await log_business_activity(
            user=current_user,
            path="/activity/users/reassign",
            description=f"{current_user.get('name') or current_user.get('email')} approved reassignment request #{request_id}: {message}",
        )
        return {"success": True, "message": message}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred")


@router.post("/{request_id}/reject", summary="Reject request")
async def reject_request(
    request_id: str,
    current_user: dict = Depends(get_current_user),
):
    actor_role = current_user.get("role", "")
    if actor_role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can reject reassignment requests")

    try:
        success, message = await reassignment_request_service.reject_request(request_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
        await log_business_activity(
            user=current_user,
            path="/activity/users/reassign",
            description=f"{current_user.get('name') or current_user.get('email')} rejected reassignment request #{request_id}",
        )
        return {"success": True, "message": message}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred")
