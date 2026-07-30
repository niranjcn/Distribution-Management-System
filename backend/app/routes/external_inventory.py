import logging
import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from app.core.activity_logger import build_field_change_summary, log_business_activity

from app.middleware.auth_middleware import require_any_role, require_management
from app.models.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    PurchaseOrderCreate,
    ReceiptCreate,
    StockAdjustmentCreate,
)
from app.database_sqlalchemy import async_session_factory
from sqlalchemy import text
from app.utils.helpers import generate_inventory_item_id
from app.services import inventory_service

router = APIRouter()
logger = logging.getLogger(__name__)


UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "external_inventory"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _chunks(values, chunk_size: int):
    for i in range(0, len(values), chunk_size):
        yield values[i:i + chunk_size]


def _uses_mac_id(device_type: Optional[str]) -> bool:
    normalized = str(device_type or "").strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    return normalized in {"olt", "adapter"}


def _resolve_device_type(device_type: str, custom_device_type: str) -> str:
    base = str(device_type or "").strip()
    if base.lower() == "others":
        custom = str(custom_device_type or "").strip()
        if custom:
            return custom
    return base


async def _fetch_existing_values(session, column: str, values: list[str]) -> set:
    if not values:
        return set()

    existing = set()
    for batch in _chunks(values, 500):
        named_params = {f"val{i}": v for i, v in enumerate(batch)}
        placeholder_list = [f":val{i}" for i in range(len(batch))]
        placeholders = ",".join(placeholder_list)
        result = await session.execute(
            text(f"SELECT {column} FROM external_inventory_items WHERE {column} IN ({placeholders})"),
            named_params,
        )
        rows = result.mappings().all()
        for row in rows:
            value = row.get(column)
            if value:
                existing.add(str(value).strip())
    return existing


@router.get("/dashboard", summary="Get external inventory dashboard")
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


@router.get("/items", summary="Get external inventory items")
async def get_external_inventory_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    search: Optional[str] = None,
    search_by: Optional[str] = Query("all"),
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
            search_by=search_by,
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


@router.post("/items", status_code=status.HTTP_201_CREATED, summary="Create external inventory item")
async def create_external_inventory_item(
    item_data: InventoryItemCreate,
    current_user: dict = Depends(require_management),
):
    try:
        item = await inventory_service.create_item(item_data=item_data, user=current_user)
        actor_name = current_user.get("name") or current_user.get("email") or "User"
        await log_business_activity(
            user=current_user,
            path="/activity/external-inventory/item-create",
            description=(
                f"{actor_name} created external inventory item "
                f"{item.get('serial_number') or item.get('inventory_id') or item.get('name') or 'unknown'}"
            ),
        )
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


@router.post("/items/bulk-upload", status_code=status.HTTP_201_CREATED, summary="Bulk upload external inventory items from CSV")
async def bulk_upload_external_inventory_items(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_management),
):
    """Bulk upload external inventory items from CSV.

    Required columns: item_id, name, serial_number, device_type
    Conditional columns:
    - mac_id (required only for OLT and Adapter)
    - identifier_type + identifier (required for all non-OLT/Adapter types)
    Optional columns: custom_device_type, price, supplier_name, location, notes
    """
    filename_lower = (file.filename or "").lower()
    if not filename_lower.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV (.csv) files are supported",
        )

    try:
        contents = await file.read()

        from app.services.bulk_upload_service import MAX_UPLOAD_FILE_SIZE, check_bulk_upload_row_count
        if len(contents) > MAX_UPLOAD_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_FILE_SIZE // (1024 * 1024)} MB",
            )

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
        check_bulk_upload_row_count(data_rows)

        required = {"item_id", "name", "serial_number", "device_type"}
        missing = required - set(headers)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(sorted(missing))}",
            )

        created = []
        skipped = []
        errors = []
        prepared_rows = []
        seen_item_ids = set()
        seen_serials = set()
        seen_macs = set()
        seen_identifiers = set()

        for row_idx, row in enumerate(data_rows, start=2):
            padded = row + [""] * (len(headers) - len(row))
            row_data = {
                headers[i]: (str(padded[i]).strip() if padded[i] is not None else "")
                for i in range(len(headers))
            }

            if not any(row_data.values()):
                continue

            item_id = str(row_data.get("item_id", "")).strip()
            name = str(row_data.get("name", "")).strip()
            serial_number = str(row_data.get("serial_number", "")).strip()
            device_type_value = str(row_data.get("device_type", "")).strip()
            custom_device_type = str(row_data.get("custom_device_type", "")).strip()
            effective_device_type = _resolve_device_type(device_type_value, custom_device_type)

            if not item_id:
                errors.append({"row": row_idx, "item_id": "", "error": "Missing item_id"})
                continue
            if not name:
                errors.append({"row": row_idx, "item_id": item_id, "error": "Missing name"})
                continue
            if not serial_number:
                errors.append({"row": row_idx, "item_id": item_id, "error": "Missing serial_number"})
                continue
            if not effective_device_type:
                errors.append({"row": row_idx, "item_id": item_id, "error": "Missing device_type"})
                continue

            mac_id_value = str(row_data.get("mac_id", "")).strip()
            identifier_type_value = str(row_data.get("identifier_type", "")).strip()
            identifier_value = str(row_data.get("identifier", "")).strip()

            if _uses_mac_id(effective_device_type):
                if not mac_id_value:
                    errors.append({
                        "row": row_idx,
                        "item_id": item_id,
                        "error": "mac_id is required when device_type is OLT or Adapter",
                    })
                    continue
                identifier_type_value = ""
                identifier_value = ""
            else:
                if not identifier_type_value or not identifier_value:
                    errors.append({
                        "row": row_idx,
                        "item_id": item_id,
                        "error": "identifier_type and identifier are required for non-OLT/Adapter device_type",
                    })
                    continue
                mac_id_value = ""

            if item_id in seen_item_ids:
                skipped.append({"row": row_idx, "item_id": item_id, "reason": "Duplicate item_id in file"})
                continue
            seen_item_ids.add(item_id)

            if serial_number in seen_serials:
                skipped.append({"row": row_idx, "item_id": item_id, "reason": "Duplicate serial_number in file"})
                continue
            seen_serials.add(serial_number)

            if mac_id_value:
                if mac_id_value in seen_macs:
                    skipped.append({"row": row_idx, "item_id": item_id, "reason": "Duplicate mac_id in file"})
                    continue
                seen_macs.add(mac_id_value)

            if identifier_value:
                identifier_key = f"{identifier_type_value.lower()}::{identifier_value.lower()}"
                if identifier_key in seen_identifiers:
                    skipped.append({"row": row_idx, "item_id": item_id, "reason": "Duplicate identifier in file"})
                    continue
                seen_identifiers.add(identifier_key)

            price_raw = str(row_data.get("price", "") or "").strip()
            if price_raw:
                try:
                    price_value = float(price_raw)
                except ValueError:
                    errors.append({"row": row_idx, "item_id": item_id, "error": "Invalid price value"})
                    continue
            else:
                price_value = 0.0

            prepared_rows.append({
                "row": row_idx,
                "item_id": item_id,
                "name": name,
                "serial_number": serial_number,
                "mac_id": mac_id_value,
                "identifier_type": identifier_type_value,
                "identifier": identifier_value,
                "device_type": effective_device_type,
                "price": price_value,
                "unit": str(row_data.get("unit") or "pcs").strip() or "pcs",
                "supplier_name": row_data.get("supplier_name") or None,
                "location": row_data.get("location") or None,
                "notes": row_data.get("notes") or None,
            })

        if not prepared_rows:
            return {
                "success": True,
                "message": f"Import complete: 0 created, {len(skipped)} skipped, {len(errors)} errors",
                "data": {
                    "created_count": 0,
                    "skipped_count": len(skipped),
                    "error_count": len(errors),
                    "created": created,
                    "skipped": skipped,
                    "errors": errors,
                },
            }

        async with async_session_factory() as session:
            existing_item_ids = await _fetch_existing_values(session, "item_id", [row["item_id"] for row in prepared_rows])
            existing_serials = await _fetch_existing_values(session, "serial_number", [row["serial_number"] for row in prepared_rows])
            existing_macs = await _fetch_existing_values(session, "mac_id", [row["mac_id"] for row in prepared_rows if row["mac_id"]])
            existing_identifiers = await _fetch_existing_values(
                session, "identifier", [row["identifier"] for row in prepared_rows if row["identifier"]]
            )

            insertable_rows = []
            for row in prepared_rows:
                if row["item_id"] in existing_item_ids:
                    skipped.append({"row": row["row"], "item_id": row["item_id"], "reason": "item_id already exists"})
                    continue
                if row["serial_number"] in existing_serials:
                    skipped.append({
                        "row": row["row"],
                        "item_id": row["item_id"],
                        "reason": "serial_number already exists",
                    })
                    continue
                if row["mac_id"] and row["mac_id"] in existing_macs:
                    skipped.append({"row": row["row"], "item_id": row["item_id"], "reason": "mac_id already exists"})
                    continue
                if row["identifier"] and row["identifier"] in existing_identifiers:
                    skipped.append({"row": row["row"], "item_id": row["item_id"], "reason": "identifier already exists"})
                    continue

                insertable_rows.append(row)

            if not insertable_rows:
                return {
                    "success": True,
                    "message": f"Import complete: 0 created, {len(skipped)} skipped, {len(errors)} errors",
                    "data": {
                        "created_count": 0,
                        "skipped_count": len(skipped),
                        "error_count": len(errors),
                        "created": created,
                        "skipped": skipped,
                        "errors": errors,
                    },
                }

            now = datetime.now().replace(tzinfo=None)
            actor_id = int(current_user.get("id") or current_user.get("_id") or current_user.get("user_id") or current_user.get("sub") or 0)
            if not actor_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authenticated user id is missing",
                )
            insert_sql = """INSERT INTO external_inventory_items (
                inventory_id, item_id, name, serial_number, mac_id, identifier_type, identifier, device_type, price,
                sku, category, unit, quantity_on_hand, reorder_level, unit_cost, supplier_name, location, status,
                notes, image_url, created_by, created_at, updated_at
            ) VALUES (:inventory_id, :item_id, :name, :serial_number, :mac_id, :identifier_type, :identifier, :device_type, :price,
                :sku, :category, :unit, :quantity_on_hand, :reorder_level, :unit_cost, :supplier_name, :location, 'active',
                :notes, :image_url, :created_by, :created_at, :updated_at)"""

            for batch in _chunks(insertable_rows, 500):
                batch_payload = []
                batch_inventory_ids = []
                for item in batch:
                    inventory_id = generate_inventory_item_id()
                    batch_inventory_ids.append(inventory_id)
                    batch_payload.append({
                        "inventory_id": inventory_id,
                        "item_id": item["item_id"],
                        "name": item["name"],
                        "serial_number": item["serial_number"],
                        "mac_id": item["mac_id"],
                        "identifier_type": item["identifier_type"],
                        "identifier": item["identifier"],
                        "device_type": item["device_type"],
                        "price": item["price"],
                        "sku": item["item_id"],
                        "category": item["device_type"],
                        "unit": item["unit"],
                        "quantity_on_hand": 1,
                        "reorder_level": 0,
                        "unit_cost": item["price"],
                        "supplier_name": item["supplier_name"],
                        "location": item["location"],
                        "notes": item["notes"],
                        "image_url": None,
                        "created_by": actor_id,
                        "created_at": now,
                        "updated_at": now,
                    })

                try:
                    await session.execute(text(insert_sql), batch_payload)
                    created.extend(batch_inventory_ids)
                except Exception as batch_error:
                    for idx, item in enumerate(batch):
                        inventory_id = batch_inventory_ids[idx]
                        try:
                            await session.execute(text(insert_sql), batch_payload[idx])
                            created.append(inventory_id)
                        except Exception as single_error:
                            errors.append({
                                "row": item["row"],
                                "item_id": item["item_id"],
                                "error": str(single_error),
                            })
                    logger.warning("External inventory bulk insert fallback triggered: %s", str(batch_error))

            await session.commit()

        actor_name = current_user.get("name") or current_user.get("email") or "User"
        await log_business_activity(
            user=current_user,
            path="/activity/external-inventory/item-bulk-import",
            description=(
                f"{actor_name} imported external inventory items: "
                f"{len(created)} created, {len(skipped)} skipped, {len(errors)} errors"
            ),
        )

        return {
            "success": True,
            "message": f"Import complete: {len(created)} created, {len(skipped)} skipped, {len(errors)} errors",
            "data": {
                "created_count": len(created),
                "skipped_count": len(skipped),
                "error_count": len(errors),
                "created": created,
                "skipped": skipped,
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


@router.put("/items/{inventory_id}", summary="Update external inventory item")
async def update_external_inventory_item(
    inventory_id: str,
    item_data: InventoryItemUpdate,
    current_user: dict = Depends(require_management),
):
    try:
        before = await inventory_service.get_item_by_inventory_id(inventory_id)
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

        actor_name = current_user.get("name") or current_user.get("email") or "User"
        edited_fields = list(item_data.model_dump(exclude_unset=True).keys())
        change_summary = build_field_change_summary(
            before=before or {},
            after=updated or {},
            fields=edited_fields,
            exclude_fields={"updated_at"},
        )
        await log_business_activity(
            user=current_user,
            path="/activity/external-inventory/item-update",
            description=(
                f"{actor_name} updated external inventory item "
                f"{updated.get('serial_number') or (before or {}).get('serial_number') or inventory_id}; "
                f"changes: {change_summary}"
            ),
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


@router.delete("/items/{inventory_id}", summary="Delete external inventory item")
async def delete_external_inventory_item(
    inventory_id: str,
    current_user: dict = Depends(require_management),
):
    try:
        deleted = await inventory_service.delete_item(inventory_id=inventory_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="External inventory item not found",
            )

        actor_name = current_user.get("name") or current_user.get("email") or "User"
        serial_ref = deleted.get("serial_number") or inventory_id
        await log_business_activity(
            user=current_user,
            path="/activity/external-inventory/item-delete",
            description=f"{actor_name} deleted external inventory item {serial_ref}",
        )

        return {
            "success": True,
            "message": "External inventory item deleted successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/items/{inventory_id}/image", summary="Upload external inventory item image")
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
        file_name = f"{inventory_id}_{datetime.now().replace(tzinfo=None).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}{suffix}"
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


@router.post("/adjustments", summary="Create external inventory adjustment")
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


@router.get("/purchase-orders", summary="Get external inventory purchase orders")
async def get_external_inventory_purchase_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    search_by: Optional[str] = Query("all"),
    current_user: dict = Depends(require_any_role),
):
    try:
        user_role = str(current_user.get("role") or "").lower()
        is_management_user = user_role in {"super_admin", "manager", "pdic_staff"}
        user_id = int(
            current_user.get("id")
            or current_user.get("_id")
            or current_user.get("user_id")
            or current_user.get("sub")
            or 0
        )

        result = await inventory_service.get_purchase_orders(
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            search=search,
            search_by=search_by,
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


@router.post("/purchase-orders", status_code=status.HTTP_201_CREATED, summary="Create external inventory purchase order")
async def create_external_inventory_purchase_order(
    po_data: PurchaseOrderCreate,
    current_user: dict = Depends(require_any_role),
):
    try:
        po = await inventory_service.create_purchase_order(po_data=po_data, user=current_user)
        actor_name = current_user.get("name") or current_user.get("email") or "User"
        await log_business_activity(
            user=current_user,
            path="/activity/external-inventory/purchase-order-create",
            description=(
                f"{actor_name} created purchase order {po.get('po_id')} "
                f"for {po.get('supplier_name') or 'unknown supplier'}"
            ),
        )
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


@router.post("/purchase-orders/{po_id}/receive", summary="Receive external inventory purchase order")
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
        actor_name = current_user.get("name") or current_user.get("email") or "User"
        await log_business_activity(
            user=current_user,
            path="/activity/external-inventory/purchase-order-confirm",
            description=(
                f"{actor_name} confirmed purchase order {po.get('po_id') or po_id}"
            ),
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


@router.get("/receipts", summary="Get external inventory receipts")
async def get_external_inventory_receipts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
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


@router.get("/movements", summary="Get external inventory movements")
async def get_external_inventory_movements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    item_inventory_id: Optional[str] = None,
    movement_type: Optional[str] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = Query("all"),
    current_user: dict = Depends(require_management),
):
    try:
        result = await inventory_service.get_stock_movements(
            page=page,
            page_size=page_size,
            item_inventory_id=item_inventory_id,
            movement_type=movement_type,
            search=search,
            search_by=search_by,
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





