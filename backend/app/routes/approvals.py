from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.approval import ApprovalAction
from app.services import approval_service
from app.middleware.auth_middleware import get_current_user, require_management

router = APIRouter()


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
    result = await approval_service.get_approvals(
        page=page,
        page_size=page_size,
        status=status,
        approval_type=approval_type,
        search=search
    )
    
    return {
        "success": True,
        "message": "Approvals retrieved successfully",
        "data": result["data"],
        "pagination": result["pagination"]
    }


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    current_user: dict = Depends(require_management)
):
    """Get approval by ID with entity details"""
    approval = await approval_service.get_approval_by_id(approval_id)
    
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found"
        )
    
    return {
        "success": True,
        "message": "Approval retrieved successfully",
        "data": approval
    }


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
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval not found"
            )
        
        return {
            "success": True,
            "message": "Request approved successfully",
            "data": approval
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    action: ApprovalAction,
    current_user: dict = Depends(require_management)
):
    """Reject a pending request"""
    try:
        approval = await approval_service.reject_request(
            approval_id=approval_id,
            approver=current_user,
            rejection_reason=action.rejection_reason,
            notes=action.notes
        )
        
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval not found"
            )
        
        return {
            "success": True,
            "message": "Request rejected successfully",
            "data": approval
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
