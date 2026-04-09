import logging
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.operator import OperatorCreate, OperatorUpdate
from app.services import operator_service
from app.middleware.auth_middleware import get_current_user, require_admin_or_manager

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("")
async def get_operators(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all operators with pagination and filters"""
    try:
        # Filter by assigned_to for sub-distributors/clusters
        assigned_to = None
        if current_user["role"] in ["sub_distributor", "cluster"]:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/{operator_id}")
async def get_operator(
    operator_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get operator by ID"""
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/{operator_id}/devices")
async def get_operator_devices(
    operator_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get devices assigned to an operator"""
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_operator(
    operator_data: OperatorCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new operator"""
    # Only clusters, sub-distributors and above can create operators
    if current_user["role"] not in ["super_admin", "manager", "pdic_staff", "sub_distributor", "cluster"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create operators"
        )

    try:
        operator = await operator_service.create_operator(
            operator_data=operator_data,
            created_by=current_user
        )

        return {
            "success": True,
            "message": "Operator created successfully",
            "data": operator
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


@router.put("/{operator_id}")
async def update_operator(
    operator_id: str,
    operator_data: OperatorUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update operator"""
    # Check ownership for sub-distributors/clusters
    if current_user["role"] in ["sub_distributor", "cluster"]:
        operator = await operator_service.get_operator_by_id(operator_id)
        if operator and operator.get("assigned_to") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own operators"
            )

    try:
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


@router.delete("/{operator_id}")
async def delete_operator(
    operator_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete operator"""
    # Check ownership for sub-distributors/clusters
    if current_user["role"] in ["sub_distributor", "cluster"]:
        operator = await operator_service.get_operator_by_id(operator_id)
        if operator and operator.get("assigned_to") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own operators"
            )
    elif current_user["role"] not in ["super_admin", "manager", "pdic_staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete operators"
        )

    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )




