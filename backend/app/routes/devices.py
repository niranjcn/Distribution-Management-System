from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.device import DeviceCreate, DeviceUpdate
from app.services import device_service
from app.middleware.auth_middleware import get_current_user, require_admin_or_manager

router = APIRouter()


@router.get("")
async def get_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    device_type: Optional[str] = None,
    holder_id: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all devices with pagination and filters"""
    # Filter by holder for non-admin/manager users
    if current_user["role"] not in ["admin", "manager"]:
        holder_id = current_user["id"]
    
    result = await device_service.get_devices(
        page=page,
        page_size=page_size,
        status=status,
        device_type=device_type,
        holder_id=holder_id,
        search=search
    )
    
    return {
        "success": True,
        "message": "Devices retrieved successfully",
        "data": result["data"],
        "pagination": result["pagination"]
    }


@router.get("/available")
async def get_available_devices(
    current_user: dict = Depends(get_current_user)
):
    """Get available devices for distribution"""
    holder_id = None
    if current_user["role"] not in ["admin", "manager"]:
        holder_id = current_user["id"]
    
    devices = await device_service.get_available_devices(holder_id)
    
    return {
        "success": True,
        "message": "Available devices retrieved successfully",
        "data": devices
    }


@router.get("/track/{serial_number}")
async def track_device_by_serial(
    serial_number: str,
    current_user: dict = Depends(get_current_user)
):
    """Track device by serial number with full history"""
    device = await device_service.track_device_by_serial(serial_number)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    return {
        "success": True,
        "message": "Device tracked successfully",
        "data": device
    }


@router.get("/{device_id}")
async def get_device(
    device_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get device by ID"""
    device = await device_service.get_device_by_id(device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    return {
        "success": True,
        "message": "Device retrieved successfully",
        "data": device
    }


@router.get("/{device_id}/history")
async def get_device_history(
    device_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get device history"""
    device = await device_service.get_device_by_id(device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    history = await device_service.get_device_history(device_id)
    
    return {
        "success": True,
        "message": "Device history retrieved successfully",
        "data": history
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_device(
    device_data: DeviceCreate,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Register a new device"""
    try:
        device = await device_service.create_device(
            device_data=device_data,
            created_by=current_user["id"],
            created_by_name=current_user["name"]
        )
        
        return {
            "success": True,
            "message": "Device registered successfully",
            "data": device
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{device_id}")
async def update_device(
    device_id: str,
    device_data: DeviceUpdate,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Update device"""
    device = await device_service.update_device(device_id, device_data)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    return {
        "success": True,
        "message": "Device updated successfully",
        "data": device
    }


@router.delete("/{device_id}")
async def delete_device(
    device_id: str,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Delete device"""
    success = await device_service.delete_device(device_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    return {
        "success": True,
        "message": "Device deleted successfully"
    }


@router.patch("/{device_id}/status")
async def update_device_status(
    device_id: str,
    status_update: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update device status"""
    status_value = status_update.get("status")
    notes = status_update.get("notes")
    
    if not status_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status is required"
        )
    
    device = await device_service.update_device_status(
        device_id=device_id,
        status=status_value,
        performed_by=current_user["id"],
        performed_by_name=current_user["name"],
        notes=notes
    )
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    return {
        "success": True,
        "message": "Device status updated successfully",
        "data": device
    }
