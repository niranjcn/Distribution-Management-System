import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth_middleware import get_current_user
from app.models.digital_id import DigitalIdCreate, DigitalIdUpdate
from app.services import digital_id_service

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create digital ID entry")
async def create_digital_id(data: DigitalIdCreate, current_user: dict = Depends(get_current_user)):
    try:
        entry = await digital_id_service.create_digital_id(data)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {"success": True, "message": "Digital ID entry created", "data": entry}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.get("/user/{user_id}", summary="Get digital IDs by user")
async def get_digital_ids_by_user(user_id: str, current_user: dict = Depends(get_current_user)):
    try:
        entries = await digital_id_service.get_digital_ids_by_user(user_id)
        return {"success": True, "message": "Digital IDs retrieved", "data": entries}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.get("/{entry_id}", summary="Get digital ID entry")
async def get_digital_id(entry_id: str, current_user: dict = Depends(get_current_user)):
    try:
        entry = await digital_id_service.get_digital_id_by_id(entry_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digital ID entry not found")
        return {"success": True, "message": "Digital ID retrieved", "data": entry}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.put("/{entry_id}", summary="Update digital ID entry")
async def update_digital_id(entry_id: str, data: DigitalIdUpdate, current_user: dict = Depends(get_current_user)):
    try:
        entry = await digital_id_service.update_digital_id(entry_id, data)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digital ID entry not found")
        return {"success": True, "message": "Digital ID entry updated", "data": entry}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.delete("/{entry_id}", summary="Delete digital ID entry")
async def delete_digital_id(entry_id: str, current_user: dict = Depends(get_current_user)):
    try:
        deleted = await digital_id_service.delete_digital_id(entry_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digital ID entry not found")
        return {"success": True, "message": "Digital ID entry deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")
