import logging
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.return_device import ReturnCreate, ReturnStatusUpdate
from app.services import return_service
from app.middleware.auth_middleware import get_current_user, require_admin_or_manager
from app.core.activity_logger import build_field_change_summary, log_business_activity

router = APIRouter()

logger = logging.getLogger(__name__)


def _ensure_not_md_director(current_user: dict) -> None:
    if current_user.get("role") == "md_director":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MD/Director has read-only access to returns"
        )


@router.get("")
async def get_returns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    return_status: Optional[str] = Query(None, alias="status"),
    reason: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all return requests with pagination and filters"""
    try:
        result = await return_service.get_returns(
            page=page,
            page_size=page_size,
            status=return_status,
            reason=reason,
            requested_by=None,
            search=search,
            current_user=current_user,
        )

        return {
            "success": True,
            "message": "Return requests retrieved successfully",
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


@router.get("/{return_id}")
async def get_return(
    return_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get return request by ID"""
    try:
        return_req = await return_service.get_return_by_id(return_id)

        if not return_req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Return request not found"
            )

        return {
            "success": True,
            "message": "Return request retrieved successfully",
            "data": return_req
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_return(
    return_data: ReturnCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new return request"""
    _ensure_not_md_director(current_user)

    try:
        return_req = await return_service.create_return(
            return_data=return_data,
            requester=current_user
        )

        return {
            "success": True,
            "message": "Return request created successfully",
            "data": return_req
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.patch("/{return_id}/status")
async def update_return_status(
    return_id: str,
    status_update: ReturnStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update return request status"""
    _ensure_not_md_director(current_user)

    try:
        before = await return_service.get_return_by_id(return_id)
        return_req = await return_service.update_return_status(
            return_id=return_id,
            status=status_update.status.value,
            user=current_user,
            notes=status_update.notes,
            return_amount=status_update.return_amount,
            payment_bill_url=status_update.payment_bill_url,
        )

        if not return_req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Return request not found"
            )

        actor_name = current_user.get("name") or current_user.get("email") or "User"
        edited_fields = ["status"]
        if status_update.notes is not None:
            edited_fields.append("notes")
        if status_update.return_amount is not None:
            edited_fields.append("return_amount")
        if status_update.payment_bill_url is not None:
            edited_fields.append("payment_bill_url")

        change_summary = build_field_change_summary(
            before=before or {},
            after=return_req or {},
            fields=edited_fields,
            exclude_fields={"updated_at"},
        )
        await log_business_activity(
            user=current_user,
            path="/activity/returns/status-update",
            description=(
                f"{actor_name} updated return status for "
                f"{return_req.get('return_id') or return_id}; changes: {change_summary}"
            ),
        )

        return {
            "success": True,
            "message": "Return status updated successfully",
            "data": return_req
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.delete("/{return_id}")
async def cancel_return(
    return_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a return request (only by creator)"""
    _ensure_not_md_director(current_user)

    try:
        success = await return_service.cancel_return(
            return_id=return_id,
            user_id=current_user["id"]
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Return request not found"
            )

        return {
            "success": True,
            "message": "Return request cancelled successfully"
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )




