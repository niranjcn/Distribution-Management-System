from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.distribution import DistributionCreate, DistributionStatusUpdate
from app.services import distribution_service
from app.middleware.auth_middleware import get_current_user, require_admin_or_manager, require_management

router = APIRouter()


@router.get("")
async def get_distributions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all distributions with pagination and filters"""
    # Filter by user for non-admin/manager
    user_id = None
    if current_user["role"] not in ["admin", "manager"]:
        user_id = current_user["id"]
    
    result = await distribution_service.get_distributions(
        page=page,
        page_size=page_size,
        status=status,
        user_id=user_id,
        search=search
    )
    
    return {
        "success": True,
        "message": "Distributions retrieved successfully",
        "data": result["data"],
        "pagination": result["pagination"]
    }


@router.get("/pending")
async def get_pending_distributions(
    current_user: dict = Depends(require_management)
):
    """Get pending distributions for approval"""
    distributions = await distribution_service.get_pending_distributions()
    
    return {
        "success": True,
        "message": "Pending distributions retrieved successfully",
        "data": distributions
    }


@router.get("/{distribution_id}")
async def get_distribution(
    distribution_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get distribution by ID"""
    distribution = await distribution_service.get_distribution_by_id(distribution_id)
    
    if not distribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Distribution not found"
        )
    
    return {
        "success": True,
        "message": "Distribution retrieved successfully",
        "data": distribution
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_distribution(
    dist_data: DistributionCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new distribution request"""
    # Check permissions
    if current_user["role"] == "operator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operators cannot create distributions"
        )
    
    try:
        distribution = await distribution_service.create_distribution(
            dist_data=dist_data,
            from_user=current_user
        )
        
        return {
            "success": True,
            "message": "Distribution created successfully",
            "data": distribution
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{distribution_id}/status")
async def update_distribution_status(
    distribution_id: str,
    status_update: DistributionStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update distribution status"""
    try:
        distribution = await distribution_service.update_distribution_status(
            distribution_id=distribution_id,
            status=status_update.status.value,
            user=current_user,
            notes=status_update.notes
        )
        
        if not distribution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Distribution not found"
            )
        
        return {
            "success": True,
            "message": "Distribution status updated successfully",
            "data": distribution
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{distribution_id}")
async def cancel_distribution(
    distribution_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a distribution (only by creator)"""
    try:
        success = await distribution_service.cancel_distribution(
            distribution_id=distribution_id,
            user_id=current_user["id"]
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Distribution not found"
            )
        
        return {
            "success": True,
            "message": "Distribution cancelled successfully"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
