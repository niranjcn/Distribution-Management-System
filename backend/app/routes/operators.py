from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.operator import OperatorCreate, OperatorUpdate
from app.services import operator_service
from app.middleware.auth_middleware import get_current_user, require_admin_or_manager

router = APIRouter()


@router.get("")
async def get_operators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all operators with pagination and filters"""
    # Filter by assigned_to for sub-distributors
    assigned_to = None
    if current_user["role"] == "sub_distributor":
        assigned_to = current_user["id"]
    
    result = await operator_service.get_operators(
        page=page,
        page_size=page_size,
        assigned_to=assigned_to,
        status=status,
        search=search
    )
    
    return {
        "success": True,
        "message": "Operators retrieved successfully",
        "data": result["data"],
        "pagination": result["pagination"]
    }


@router.get("/{operator_id}")
async def get_operator(
    operator_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get operator by ID"""
    operator = await operator_service.get_operator_by_id(operator_id)
    
    if not operator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operator not found"
        )
    
    return {
        "success": True,
        "message": "Operator retrieved successfully",
        "data": operator
    }


@router.get("/{operator_id}/devices")
async def get_operator_devices(
    operator_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get devices assigned to an operator"""
    operator = await operator_service.get_operator_by_id(operator_id)
    
    if not operator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operator not found"
        )
    
    devices = await operator_service.get_operator_devices(operator_id)
    
    return {
        "success": True,
        "message": "Operator devices retrieved successfully",
        "data": devices
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_operator(
    operator_data: OperatorCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new operator"""
    # Only sub-distributors and above can create operators
    if current_user["role"] not in ["admin", "manager", "sub_distributor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create operators"
        )
    
    operator = await operator_service.create_operator(
        operator_data=operator_data,
        created_by=current_user
    )
    
    return {
        "success": True,
        "message": "Operator created successfully",
        "data": operator
    }


@router.put("/{operator_id}")
async def update_operator(
    operator_id: str,
    operator_data: OperatorUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update operator"""
    # Check ownership for sub-distributors
    if current_user["role"] == "sub_distributor":
        operator = await operator_service.get_operator_by_id(operator_id)
        if operator and operator.get("assigned_to") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own operators"
            )
    
    operator = await operator_service.update_operator(operator_id, operator_data)
    
    if not operator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operator not found"
        )
    
    return {
        "success": True,
        "message": "Operator updated successfully",
        "data": operator
    }


@router.delete("/{operator_id}")
async def delete_operator(
    operator_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete operator"""
    # Check ownership for sub-distributors
    if current_user["role"] == "sub_distributor":
        operator = await operator_service.get_operator_by_id(operator_id)
        if operator and operator.get("assigned_to") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own operators"
            )
    elif current_user["role"] not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete operators"
        )
    
    success = await operator_service.delete_operator(operator_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operator not found"
        )
    
    return {
        "success": True,
        "message": "Operator deleted successfully"
    }
