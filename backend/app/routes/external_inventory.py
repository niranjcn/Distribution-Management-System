import logging
import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.middleware.auth_middleware import require_any_role, require_management
from app.models.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    PurchaseOrderCreate,
    ReceiptCreate,
    StockAdjustmentCreate,
)
from app.services import inventory_service

router = APIRouter()
logger = logging.getLogger(__name__)


UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "external_inventory"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/dashboard")
async def get_external_inventory_dashboard(
    current_user: dict = Depends(require_management),
):
    try:
        data = await inventory_service.get_dashboard_summary()
        return {
            "success": True,
            "message": "External inventory dashboard retrieved successfully",
            "data": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/items")
async def get_external_inventory_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    device_type: Optional[str] = Query(None, alias="type"),
    status_filter: Optional[str] = Query(None, alias="status"),
    low_stock_only: bool = False,
    current_user: dict = Depends(require_any_role),
):
    try:
        result = await inventory_service.get_items(
            page=page,
            page_size=page_size,
            search=search,
            device_type=device_type,
            status_filter=status_filter,
            low_stock_only=low_stock_only,
        )
        return {
            "success": True,
            "message": "External inventory items retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/items", status_code=status.HTTP_201_CREATED)
async def create_external_inventory_item(
    item_data: InventoryItemCreate,
    current_user: dict = Depends(require_management),
):
    try:
        item = await inventory_service.create_item(item_data=item_data, user=current_user)
        return {
            "success": True,
            "message": "External inventory item created successfully",
            "data": item,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/items/bulk-upload", status_code=status.HTTP_201_CREATED)
async def bulk_upload_external_inventory_items(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_management),
):
    """Bulk upload external inventory items from CSV.

    Required columns: item_id, name, serial_number, device_type
    Conditional column: mac_id (required for all types except Others)
    Optional columns: custom_device_type, price, unit, supplier_name, location, notes
    """
    filename_lower = (file.filename or "").lower()
    if not filename_lower.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV (.csv) files are supported",
        )

    try:
        contents = await file.read()
        decoded = contents.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(decoded))
        all_rows = list(reader)
        if not all_rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file is empty",
            )

        headers = [h.strip().lower() for h in all_rows[0]]
        data_rows = all_rows[1:]

        required = {"item_id", "name", "serial_number", "device_type"}
        missing = required - set(headers)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(sorted(missing))}",
            )

        created = []
        errors = []

        for row_idx, row in enumerate(data_rows, start=2):
            padded = row + [""] * (len(headers) - len(row))
            row_data = {
                headers[i]: (str(padded[i]).strip() if padded[i] is not None else "")
                for i in range(len(headers))
            }

            if not any(row_data.values()):
                continue

            try:
                device_type_value = row_data.get("device_type", "")
                custom_device_type = row_data.get("custom_device_type", "")

                item_payload = InventoryItemCreate(
                    item_id=row_data.get("item_id", ""),
                    name=row_data.get("name", ""),
                    serial_number=row_data.get("serial_number", ""),
                    mac_id=row_data.get("mac_id", ""),
                    device_type=device_type_value,
                    custom_device_type=custom_device_type or None,
                    price=float(row_data.get("price", "0") or 0),
                    unit=row_data.get("unit", "pcs") or "pcs",
                    supplier_name=row_data.get("supplier_name") or None,
                    location=row_data.get("location") or None,
                    notes=row_data.get("notes") or None,
                )
                created_item = await inventory_service.create_item(item_data=item_payload, user=current_user)
                created.append(created_item.get("inventory_id"))
            except Exception as e:
                errors.append(
                    {
                        "row": row_idx,
                        "item_id": row_data.get("item_id", ""),
                        "error": str(e),
                    }
                )

        return {
            "success": True,
            "message": f"Import complete: {len(created)} created, {len(errors)} errors",
            "data": {
                "created_count": len(created),
                "error_count": len(errors),
                "created": created,
                "errors": errors,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.put("/items/{inventory_id}")
async def update_external_inventory_item(
    inventory_id: str,
    item_data: InventoryItemUpdate,
    current_user: dict = Depends(require_management),
):
    try:
        updated = await inventory_service.update_item(
            inventory_id=inventory_id,
            item_data=item_data,
            user=current_user,
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="External inventory item not found",
            )

        return {
            "success": True,
            "message": "External inventory item updated successfully",
            "data": updated,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/items/{inventory_id}/image")
async def upload_external_inventory_item_image(
    inventory_id: str,
    image: UploadFile = File(...),
    current_user: dict = Depends(require_management),
):
    try:
        item = await inventory_service.get_item_by_inventory_id(inventory_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="External inventory item not found",
            )

        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image uploads are allowed",
            )

        suffix = Path(image.filename or "").suffix.lower() or ".jpg"
        file_name = f"{inventory_id}_{datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}{suffix}"
        file_path = UPLOAD_DIR / file_name

        content = await image.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image size must be 5MB or less",
            )

        with open(file_path, "wb") as f:
            f.write(content)

        image_url = f"/api/uploads/external_inventory/{file_name}"
        updated = await inventory_service.update_item_image(inventory_id, image_url)

        return {
            "success": True,
            "message": "Item image uploaded successfully",
            "data": updated,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/adjustments")
async def create_external_inventory_adjustment(
    payload: StockAdjustmentCreate,
    current_user: dict = Depends(require_management),
):
    try:
        updated_item = await inventory_service.create_stock_adjustment(
            payload=payload,
            user=current_user,
        )
        return {
            "success": True,
            "message": "Stock adjustment applied successfully",
            "data": updated_item,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/purchase-orders")
async def get_external_inventory_purchase_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    current_user: dict = Depends(require_any_role),
):
    try:
        user_role = str(current_user.get("role") or "").lower()
        is_management_user = user_role in {"super_admin", "manager", "pdic_staff"}
        user_id = str(
            current_user.get("id")
            or current_user.get("_id")
            or current_user.get("user_id")
            or current_user.get("sub")
            or ""
        )

        result = await inventory_service.get_purchase_orders(
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            search=search,
            ordered_by=None if is_management_user else user_id,
        )
        return {
            "success": True,
            "message": "External inventory purchase orders retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/purchase-orders", status_code=status.HTTP_201_CREATED)
async def create_external_inventory_purchase_order(
    po_data: PurchaseOrderCreate,
    current_user: dict = Depends(require_any_role),
):
    try:
        po = await inventory_service.create_purchase_order(po_data=po_data, user=current_user)
        return {
            "success": True,
            "message": "Purchase order created successfully",
            "data": po,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create external inventory purchase order", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/purchase-orders/{po_id}/receive")
async def receive_external_inventory_purchase_order(
    po_id: str,
    receipt_data: ReceiptCreate,
    current_user: dict = Depends(require_management),
):
    try:
        po = await inventory_service.receive_purchase_order(
            po_id=po_id,
            receipt_data=receipt_data,
            user=current_user,
        )
        return {
            "success": True,
            "message": "Purchase order submitted successfully",
            "data": po,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/receipts")
async def get_external_inventory_receipts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    po_id: Optional[str] = None,
    current_user: dict = Depends(require_management),
):
    try:
        result = await inventory_service.get_receipts(
            page=page,
            page_size=page_size,
            po_id=po_id,
        )
        return {
            "success": True,
            "message": "External inventory receipts retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/movements")
async def get_external_inventory_movements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    item_inventory_id: Optional[str] = None,
    movement_type: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(require_management),
):
    try:
        result = await inventory_service.get_stock_movements(
            page=page,
            page_size=page_size,
            item_inventory_id=item_inventory_id,
            movement_type=movement_type,
            search=search,
        )
        return {
            "success": True,
            "message": "External inventory movements retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )





