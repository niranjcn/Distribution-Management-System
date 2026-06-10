import logging
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.batch import BatchCreate, BatchUpdate
from app.services import batch_service
from app.middleware.auth_middleware import get_current_user, require_admin_or_manager

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("")
async def get_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all batches with pagination"""
    try:
        result = await batch_service.get_batches(
            page=page,
            page_size=page_size,
            search=search
        )

        return {
            "success": True,
            "message": "Batches retrieved successfully",
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


@router.get("/{batch_id}")
async def get_batch(
    batch_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get batch by ID"""
    try:
        batch = await batch_service.get_batch_by_id(batch_id)

        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )

        return {
            "success": True,
            "message": "Batch retrieved successfully",
            "data": batch
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/{batch_id}/devices")
async def get_batch_devices(
    batch_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    current_user: dict = Depends(get_current_user)
):
    """Get all devices in a batch"""
    try:
        result = await batch_service.get_batch_devices(
            batch_id=batch_id,
            page=page,
            page_size=page_size
        )

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )

        return {
            "success": True,
            "message": "Batch devices retrieved successfully",
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


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_batch(
    batch_data: BatchCreate,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Create a new batch"""
    try:
        batch = await batch_service.create_batch(
            batch_data=batch_data,
            created_by=current_user["id"],
            created_by_name=current_user["name"]
        )

        return {
            "success": True,
            "message": "Batch created successfully",
            "data": batch
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


@router.put("/{batch_id}")
async def update_batch(
    batch_id: str,
    batch_data: BatchUpdate,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Update batch"""
    try:
        batch = await batch_service.update_batch(batch_id, batch_data)

        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )

        return {
            "success": True,
            "message": "Batch updated successfully",
            "data": batch
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


@router.delete("/{batch_id}")
async def delete_batch(
    batch_id: str,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Delete batch (only if it has no devices)"""
    try:
        success = await batch_service.delete_batch(batch_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )

        return {
            "success": True,
            "message": "Batch deleted successfully"
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



