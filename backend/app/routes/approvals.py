import logging
from fastapi import APIRouter, HTTPException, status as http_status, Depends, Query
from typing import Optional
from app.models.approval import ApprovalAction, RoleRoutingUpdateRequest
from app.services import approval_service
from app.middleware.auth_middleware import get_current_user, require_admin, require_management

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("")
async def get_approvals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    approval_type: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(require_management)
):
    """Get all pending approvals with pagination"""
    try:
        result = await approval_service.get_approvals(
            page=page,
            page_size=page_size,
            status=status,
            approval_type=approval_type,
            search=search,
            viewer_role=current_user.get("role")
        )

        return {
            "success": True,
            "message": "Approvals retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/role-routing/config")
async def get_approval_role_routing_config(
    current_user: dict = Depends(require_management)
):
    """Get admin/manager approval-role routing configuration."""
    try:
        config = await approval_service.get_role_routing_config()
        return {
            "success": True,
            "message": "Approval role routing config retrieved successfully",
            "data": config,
        }
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.put("/role-routing/config")
async def update_approval_role_routing_config(
    payload: RoleRoutingUpdateRequest,
    current_user: dict = Depends(require_admin)
):
    """Update admin/manager approval-role routing configuration (admin only)."""
    try:
        incoming = payload.model_dump()
        updated = await approval_service.update_role_routing_config(
            config=incoming,
            actor=current_user,
        )
        return {
            "success": True,
            "message": "Approval role routing config updated successfully",
            "data": updated,
        }
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    current_user: dict = Depends(require_management)
):
    """Get approval by ID with entity details"""
    try:
        approval = await approval_service.get_approval_by_id(approval_id)

        if not approval:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Approval not found"
            )

        return {
            "success": True,
            "message": "Approval retrieved successfully",
            "data": approval
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/{approval_id}/approve")
async def approve_request(
    approval_id: str,
    action: Optional[ApprovalAction] = None,
    current_user: dict = Depends(require_management)
):
    """Approve a pending request"""
    try:
        notes = action.notes if action else None

        approval = await approval_service.approve_request(
            approval_id=approval_id,
            approver=current_user,
            notes=notes
        )

        if not approval:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Approval not found"
            )

        return {
            "success": True,
            "message": "Request approved successfully",
            "data": approval
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    action: ApprovalAction,
    current_user: dict = Depends(require_management)
):
    """Reject a pending request - Admin and Manager only"""
    try:
        approval = await approval_service.reject_request(
            approval_id=approval_id,
            approver=current_user,
            rejection_reason=action.rejection_reason,
            notes=action.notes
        )

        if not approval:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Approval not found"
            )

        return {
            "success": True,
            "message": "Request rejected successfully",
            "data": approval
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )





