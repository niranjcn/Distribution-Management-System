from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.user import UserCreate, UserUpdate, UserStatus
from app.services import user_service
from app.middleware.auth_middleware import get_current_user, require_admin, require_admin_or_manager

router = APIRouter()


@router.get("")
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Get all users with pagination and filters"""
    result = await user_service.get_users(
        page=page,
        page_size=page_size,
        role=role,
        status=status,
        search=search
    )
    
    return {
        "success": True,
        "message": "Users retrieved successfully",
        "data": result["data"],
        "pagination": result["pagination"]
    }


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get user by ID"""
    # Users can only view themselves unless admin/manager
    if current_user["role"] not in ["admin", "manager"] and current_user["id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile"
        )
    
    user = await user_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "success": True,
        "message": "User retrieved successfully",
        "data": user
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Create a new user"""
    try:
        user = await user_service.create_user(user_data)
        
        return {
            "success": True,
            "message": "User created successfully",
            "data": user
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user"""
    # Users can only update themselves unless admin/manager
    if current_user["role"] not in ["admin", "manager"] and current_user["id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )
    
    # Non-admins can't change status
    if current_user["role"] not in ["admin", "manager"] and user_data.status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change account status"
        )
    
    user = await user_service.update_user(user_id, user_data)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "success": True,
        "message": "User updated successfully",
        "data": user
    }


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_admin)
):
    """Delete user (admin only)"""
    # Prevent self-deletion
    if current_user["id"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    success = await user_service.delete_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "success": True,
        "message": "User deleted successfully"
    }


@router.patch("/{user_id}/status")
async def update_user_status(
    user_id: str,
    status_update: dict,
    current_user: dict = Depends(require_admin)
):
    """Update user status (admin only)"""
    status_value = status_update.get("status")
    
    if status_value not in ["active", "inactive", "suspended"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status value"
        )
    
    user = await user_service.update_user_status(user_id, status_value)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "success": True,
        "message": "User status updated successfully",
        "data": user
    }


@router.get("/role/{role}")
async def get_users_by_role(
    role: str,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Get all users by role"""
    users = await user_service.get_users_by_role(role)
    
    return {
        "success": True,
        "message": "Users retrieved successfully",
        "data": users
    }
