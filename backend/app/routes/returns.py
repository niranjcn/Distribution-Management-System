from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.return_device import ReturnCreate, ReturnStatusUpdate
from app.services import return_service
from app.middleware.auth_middleware import get_current_user, require_admin_or_manager

router = APIRouter()


@router.get("")
async def get_returns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    reason: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all return requests with pagination and filters"""
    # Filter by requester for non-admin/manager
    requested_by = None
    if current_user["role"] not in ["admin", "manager"]:
        requested_by = current_user["id"]
    
    result = await return_service.get_returns(
        page=page,
        page_size=page_size,
        status=status,
        reason=reason,
        requested_by=requested_by,
        search=search
    )
    
    return {
        "success": True,
        "message": "Return requests retrieved successfully",
        "data": result["data"],
        "pagination": result["pagination"]
    }


@router.get("/{return_id}")
async def get_return(
    return_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get return request by ID"""
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


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_return(
    return_data: ReturnCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new return request"""
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
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{return_id}/status")
async def update_return_status(
    return_id: str,
    status_update: ReturnStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update return request status"""
    try:
        return_req = await return_service.update_return_status(
            return_id=return_id,
            status=status_update.status.value,
            user=current_user,
            notes=status_update.notes
        )
        
        if not return_req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Return request not found"
            )
        
        return {
            "success": True,
            "message": "Return status updated successfully",
            "data": return_req
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{return_id}")
async def cancel_return(
    return_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a return request (only by creator)"""
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
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
