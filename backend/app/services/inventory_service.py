from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from sqlalchemy import text

from app.core.cache_version import bump_cache_version
from app.database_sqlalchemy import async_session_factory
from app.models.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    MovementType,
    PurchaseOrderCreate,
    PurchaseOrderStatus,
    ReceiptCreate,
    StockAdjustmentCreate,
)
from app.utils.helpers import (
    generate_inventory_item_id,
    generate_inventory_movement_id,
    generate_inventory_receipt_id,
    generate_purchase_order_id,
    get_pagination,
)


def _uses_mac_id(device_type: Optional[str]) -> bool:
    normalized = str(device_type or "").strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    return normalized in {"olt", "adapter"}


def _resolve_actor(user: Dict[str, Any]) -> Dict[str, str]:
    """Normalize authenticated user payload to stable actor id/name values."""
    actor_id = user.get("id") or user.get("_id") or user.get("user_id") or user.get("sub")
    if actor_id in (None, ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing",
        )

    actor_name = user.get("name") or user.get("email") or "System"
    return {"id": str(actor_id), "name": str(actor_name)}


async def get_dashboard_summary() -> Dict[str, Any]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM external_inventory_items WHERE status = 'active'")
        )
        total_skus = result.scalar()

        result = await session.execute(
            text("SELECT COUNT(*) FROM external_inventory_items WHERE status = 'active'")
        )
        total_units = result.scalar()

        result = await session.execute(
            text("SELECT 0")
        )
        low_stock_items = result.scalar()

        result = await session.execute(
            text("SELECT COUNT(*) FROM inventory_purchase_orders WHERE status IN ('draft', 'submitted', 'partially_received')")
        )
        pending_purchase_orders = result.scalar()

        result = await session.execute(
            text("SELECT COALESCE(SUM(COALESCE(price, unit_cost, 0)), 0) FROM external_inventory_items WHERE status = 'active'")
        )
        inventory_value = float(result.scalar() or 0)

        result = await session.execute(
            text("""SELECT * FROM inventory_stock_movements
               ORDER BY created_at DESC
               LIMIT 8""")
        )
        recent_movements = [dict(r) for r in result.mappings().all()]

    return {
        "total_skus": total_skus,
        "total_units": total_units,
        "low_stock_items": low_stock_items,
        "pending_purchase_orders": pending_purchase_orders,
        "inventory_value": inventory_value,
        "recent_movements": recent_movements,
    }


async def get_items(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    device_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    low_stock_only: bool = False,
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        conditions = ["1=1"]
        params: Dict[str, Any] = {}
        param_idx = 0

        if search:
            like = f"%{search}%"
            search_field_map = {
                "inventory_id": "inventory_id",
                "item_id": "item_id",
                "name": "name",
                "serial_number": "serial_number",
                "mac_id": "mac_id",
                "identifier": "identifier",
                "identifier_type": "identifier_type",
                "device_type": "device_type",
                "supplier_name": "supplier_name",
                "location": "location",
            }
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                pname = f"p_{param_idx}"
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE :{pname}")
                params[pname] = like
                param_idx += 1
            else:
                like_clauses = []
                for field in ["inventory_id", "item_id", "name", "serial_number", "mac_id", "identifier", "identifier_type", "device_type", "supplier_name", "location"]:
                    pname = f"p_{param_idx}"
                    like_clauses.append(f"{field} LIKE :{pname}")
                    params[pname] = like
                    param_idx += 1
                conditions.append(f"({' OR '.join(like_clauses)})")

        if device_type:
            normalized = device_type.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
            db_device_type = "Set-top box" if normalized in {"settopbox", "setupbox", "sb", "stb"} else device_type
            pname = f"p_{param_idx}"
            conditions.append(f"device_type = :{pname}")
            params[pname] = db_device_type
            param_idx += 1

        if status_filter:
            pname = f"p_{param_idx}"
            conditions.append(f"status = :{pname}")
            params[pname] = status_filter
            param_idx += 1

        if low_stock_only:
            conditions.append("1 = 0")

        where_clause = " AND ".join(conditions)

        result = await session.execute(
            text(f"SELECT COUNT(*) FROM external_inventory_items WHERE {where_clause}"),
            params,
        )
        total = result.scalar()

        offset = (page - 1) * page_size
        pname_limit = f"p_{param_idx}"
        pname_offset = f"p_{param_idx + 1}"
        params[pname_limit] = page_size
        params[pname_offset] = offset

        result = await session.execute(
            text(f"""SELECT *,
                                    0 AS is_low_stock
                FROM external_inventory_items
                WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT :{pname_limit} OFFSET :{pname_offset}"""),
            params,
        )
        rows = result.mappings().all()

        return {
            "data": [dict(r) for r in rows],
            "pagination": get_pagination(page, page_size, total),
        }


async def get_item_by_inventory_id(inventory_id: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM external_inventory_items WHERE inventory_id = :inventory_id"),
            {"inventory_id": inventory_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def create_item(item_data: InventoryItemCreate, user: Dict[str, Any]) -> Dict[str, Any]:
    actor = _resolve_actor(user)
    effective_device_type = (
        str(item_data.custom_device_type or "").strip()
        if str(item_data.device_type or "").strip().lower() == "others"
        else str(item_data.device_type or "").strip()
    ) or str(item_data.device_type or "").strip()

    mac_id = str(item_data.mac_id or "").strip()
    identifier_type = str(item_data.identifier_type or "").strip()
    identifier = str(item_data.identifier or "").strip()

    if _uses_mac_id(effective_device_type):
        if not mac_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAC ID is required for OLT and Adapter",
            )
        identifier_type = ""
        identifier = ""
    else:
        if not identifier_type or not identifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Identifier type and identifier are required for non-OLT/Adapter types",
            )
        mac_id = ""

    async with async_session_factory() as session:
        now = datetime.now().replace(tzinfo=None)
        inventory_id = generate_inventory_item_id()

        await session.execute(
            text("""INSERT INTO external_inventory_items (
                                     inventory_id, item_id, name, serial_number, mac_id, identifier_type, identifier, device_type, price,
                     sku, category, unit, quantity_on_hand, reorder_level,
                   unit_cost, supplier_name, location, status,
                   notes, image_url, created_by, created_at, updated_at
               )
                             VALUES (:inventory_id, :item_id, :name, :serial_number, :mac_id, :identifier_type, :identifier, :device_type, :price,
                     :sku, :category, :unit, :quantity_on_hand, :reorder_level,
                   :unit_cost, :supplier_name, :location, 'active', :notes, :image_url, :created_by, :created_at, :updated_at)"""),
            {
                "inventory_id": inventory_id,
                "item_id": item_data.item_id,
                "name": item_data.name,
                "serial_number": item_data.serial_number,
                "mac_id": mac_id,
                "identifier_type": identifier_type,
                "identifier": identifier,
                "device_type": effective_device_type,
                "price": item_data.price,
                "sku": item_data.item_id,
                "category": effective_device_type,
                "unit": item_data.unit,
                "quantity_on_hand": 1,
                "reorder_level": 0,
                "unit_cost": item_data.price,
                "supplier_name": item_data.supplier_name,
                "location": item_data.location,
                "notes": item_data.notes,
                "image_url": item_data.image_url,
                "created_by": int(actor["id"]),
                "created_at": now,
                "updated_at": now,
            },
        )

        await bump_cache_version(session)
        await session.commit()

        result = await session.execute(
            text("SELECT * FROM external_inventory_items WHERE inventory_id = :inventory_id"),
            {"inventory_id": inventory_id},
        )
        return dict(await result.mappings().first())


async def update_item(
    inventory_id: str,
    item_data: InventoryItemUpdate,
    user: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    update_dict = {k: v for k, v in item_data.model_dump().items() if v is not None}
    if not update_dict:
        return await get_item_by_inventory_id(inventory_id)

    custom_device_type = str(update_dict.pop("custom_device_type", "") or "").strip()
    if str(update_dict.get("device_type", "")).strip().lower() == "others" and custom_device_type:
        update_dict["device_type"] = custom_device_type

    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value

    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM external_inventory_items WHERE inventory_id = :inventory_id"),
            {"inventory_id": inventory_id},
        )
        existing = result.mappings().first()
        if not existing:
            return None

        if "item_id" in update_dict:
            update_dict["sku"] = update_dict["item_id"]
        if "device_type" in update_dict:
            update_dict["category"] = update_dict["device_type"]
        if "price" in update_dict:
            update_dict["unit_cost"] = update_dict["price"]

        final_device_type = str(update_dict.get("device_type", existing.get("device_type")) or "").strip()
        final_mac_id = str(update_dict.get("mac_id", existing.get("mac_id")) or "").strip()
        final_identifier_type = str(update_dict.get("identifier_type", existing.get("identifier_type")) or "").strip()
        final_identifier = str(update_dict.get("identifier", existing.get("identifier")) or "").strip()

        if _uses_mac_id(final_device_type):
            if not final_mac_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MAC ID is required for OLT and Adapter",
                )
            update_dict["identifier_type"] = None
            update_dict["identifier"] = None
        else:
            if not final_identifier_type or not final_identifier:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Identifier type and identifier are required for non-OLT/Adapter types",
                )
            update_dict["mac_id"] = ""

        update_dict["updated_at"] = datetime.now().replace(tzinfo=None)
        set_clause = ", ".join([f"{k} = :{k}" for k in update_dict.keys()])
        set_params = {**update_dict, "inv_id_where": inventory_id}

        await session.execute(
            text(f"UPDATE external_inventory_items SET {set_clause} WHERE inventory_id = :inv_id_where"),
            set_params,
        )

        await bump_cache_version(session)
        await session.commit()

    return await get_item_by_inventory_id(inventory_id)


async def update_item_image(inventory_id: str, image_url: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT id FROM external_inventory_items WHERE inventory_id = :inventory_id"),
            {"inventory_id": inventory_id},
        )
        existing = result.mappings().first()
        if not existing:
            return None

        await session.execute(
            text("UPDATE external_inventory_items SET image_url = :image_url, updated_at = :updated_at WHERE inventory_id = :inventory_id"),
            {"image_url": image_url, "updated_at": datetime.now().replace(tzinfo=None), "inventory_id": inventory_id},
        )
        await bump_cache_version(session)
        await session.commit()

    return await get_item_by_inventory_id(inventory_id)


async def delete_item(inventory_id: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM external_inventory_items WHERE inventory_id = :inventory_id"),
            {"inventory_id": inventory_id},
        )
        existing = result.mappings().first()
        if not existing:
            return None

        for table_name in ["inventory_po_lines", "inventory_receipt_lines", "inventory_stock_movements"]:
            ref_result = await session.execute(
                text(f"SELECT COUNT(*) FROM {table_name} WHERE item_inventory_id = :inventory_id"),
                {"inventory_id": inventory_id},
            )
            ref_count = int(ref_result.scalar() or 0)
            if ref_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Cannot delete item because it is already used in inventory transactions"
                    ),
                )

        await session.execute(
            text("DELETE FROM external_inventory_items WHERE inventory_id = :inventory_id"),
            {"inventory_id": inventory_id},
        )
        await bump_cache_version(session)
        await session.commit()

    return dict(existing)


async def get_purchase_orders(
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    ordered_by: Optional[str] = None,
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        conditions = ["1=1"]
        params: Dict[str, Any] = {}
        param_idx = 0

        if status_filter:
            pname = f"p_{param_idx}"
            conditions.append(f"status = :{pname}")
            params[pname] = status_filter
            param_idx += 1

        if search:
            like = f"%{search}%"
            search_field_map = {
                "po_id": "po_id",
                "supplier_name": "supplier_name",
                "ordered_by_name": "ordered_by_name",
                "status": "status",
            }
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                pname = f"p_{param_idx}"
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE :{pname}")
                params[pname] = like
                param_idx += 1
            else:
                like_clauses = []
                for field in ["po_id", "supplier_name", "ordered_by_name", "status"]:
                    pname = f"p_{param_idx}"
                    like_clauses.append(f"{field} LIKE :{pname}")
                    params[pname] = like
                    param_idx += 1
                conditions.append(f"({' OR '.join(like_clauses)})")

        if ordered_by:
            pname = f"p_{param_idx}"
            conditions.append(f"ordered_by = :{pname}")
            params[pname] = ordered_by
            param_idx += 1

        where_clause = " AND ".join(conditions)

        result = await session.execute(
            text(f"SELECT COUNT(*) FROM inventory_purchase_orders WHERE {where_clause}"),
            params,
        )
        total = result.scalar()

        offset = (page - 1) * page_size
        pname_limit = f"p_{param_idx}"
        pname_offset = f"p_{param_idx + 1}"
        params[pname_limit] = page_size
        params[pname_offset] = offset

        result = await session.execute(
            text(f"""SELECT po.*,
                       (SELECT COUNT(*) FROM inventory_po_lines pol WHERE pol.po_id = po.po_id) AS line_count,
                       (SELECT COALESCE(SUM(pol.quantity_ordered), 0) FROM inventory_po_lines pol WHERE pol.po_id = po.po_id) AS total_quantity
                FROM inventory_purchase_orders po
                WHERE {where_clause}
                ORDER BY po.created_at DESC
                LIMIT :{pname_limit} OFFSET :{pname_offset}"""),
            params,
        )
        rows = [dict(r) for r in result.mappings().all()]

        if rows:
            po_ids = [row["po_id"] for row in rows]
            po_placeholders = ", ".join([f":pid_{i}" for i in range(len(po_ids))])
            po_params = {f"pid_{i}": pid for i, pid in enumerate(po_ids)}
            lines_result = await session.execute(
                text(f"SELECT * FROM inventory_po_lines WHERE po_id IN ({po_placeholders}) ORDER BY id ASC"),
                po_params,
            )
            all_lines = [dict(r) for r in lines_result.mappings().all()]
            lines_by_po: Dict[str, List[Dict]] = {}
            for line in all_lines:
                lines_by_po.setdefault(line["po_id"], []).append(line)
            for row in rows:
                row["lines"] = lines_by_po.get(row["po_id"], [])
        else:
            all_lines = []

        return {
            "data": rows,
            "pagination": get_pagination(page, page_size, total),
        }


async def create_purchase_order(po_data: PurchaseOrderCreate, user: Dict[str, Any]) -> Dict[str, Any]:
    actor = _resolve_actor(user)

    if not po_data.lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase order must include at least one line item",
        )

    async with async_session_factory() as session:
        now = datetime.now().replace(tzinfo=None)
        po_id = generate_purchase_order_id()
        total_amount = 0.0

        item_ids = [line.item_inventory_id for line in po_data.lines]
        item_placeholders = ", ".join([f":iid_{i}" for i in range(len(item_ids))])
        item_params = {f"iid_{i}": iid for i, iid in enumerate(item_ids)}
        item_result = await session.execute(
            text(f"SELECT id, inventory_id, item_id, name, price, unit_cost, status FROM external_inventory_items WHERE inventory_id IN ({item_placeholders})"),
            item_params,
        )
        item_rows = item_result.mappings().all()
        items_map: Dict[str, Dict[str, Any]] = {str(r["inventory_id"]): dict(r) for r in item_rows}

        normalized_lines: List[Dict[str, Any]] = []
        for line in po_data.lines:
            item = items_map.get(line.item_inventory_id)
            if not item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Item '{line.item_inventory_id}' not found",
                )

            if item.get("status") != "active":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Item '{line.item_inventory_id}' is not active",
                )

            quantity_ordered = int(line.quantity_ordered or 1)
            unit_cost = float(
                line.unit_cost
                if line.unit_cost is not None
                else item.get("price")
                if item.get("price") is not None
                else item.get("unit_cost")
                or 0
            )
            line_total = float(quantity_ordered) * unit_cost
            total_amount += line_total

            normalized_lines.append(
                {
                    "item_inventory_id": item["inventory_id"],
                    "item_sku": item.get("item_id") or item.get("sku"),
                    "item_name": item["name"],
                    "quantity_ordered": quantity_ordered,
                    "unit_cost": unit_cost,
                    "line_total": line_total,
                }
            )

        await session.execute(
            text("""INSERT INTO inventory_purchase_orders (
                   po_id, supplier_name, status, expected_date, ordered_by,
                   ordered_by_name, total_amount, notes, created_at, updated_at
               ) VALUES (:po_id, :supplier_name, :status, :expected_date, :ordered_by,
                   :ordered_by_name, :total_amount, :notes, :created_at, :updated_at)"""),
            {
                "po_id": po_id,
                "supplier_name": po_data.name,
                "status": po_data.status.value,
                "expected_date": date.fromisoformat(po_data.expected_date) if po_data.expected_date else None,
                "ordered_by": int(actor["id"]),
                "ordered_by_name": actor["name"],
                "total_amount": total_amount,
                "notes": po_data.notes,
                "created_at": now,
                "updated_at": now,
            },
        )

        for line in normalized_lines:
            await session.execute(
                text("""INSERT INTO inventory_po_lines (
                       po_id, item_inventory_id, item_sku, item_name,
                       quantity_ordered, unit_cost, line_total, created_at
                   ) VALUES (:po_id, :item_inventory_id, :item_sku, :item_name,
                       :quantity_ordered, :unit_cost, :line_total, :created_at)"""),
                {
                    "po_id": po_id,
                    "item_inventory_id": line["item_inventory_id"],
                    "item_sku": line["item_sku"],
                    "item_name": line["item_name"],
                    "quantity_ordered": line["quantity_ordered"],
                    "unit_cost": line["unit_cost"],
                    "line_total": line["line_total"],
                    "created_at": now,
                },
            )

        await bump_cache_version(session)
        await session.commit()

    result = await get_purchase_order_by_id(po_id)
    if not result:
        # Fallback response to avoid failing a successful insert when immediate readback is unavailable.
        result = {
            "po_id": po_id,
            "supplier_name": po_data.name,
            "status": po_data.status.value,
            "expected_date": po_data.expected_date,
            "ordered_by": actor["id"],
            "ordered_by_name": actor["name"],
            "total_amount": total_amount,
            "notes": po_data.notes,
            "created_at": now,
            "updated_at": now,
            "lines": normalized_lines,
            "receipts": [],
        }
    return result


async def get_purchase_order_by_id(po_id: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM inventory_purchase_orders WHERE po_id = :po_id"),
            {"po_id": po_id},
        )
        order_row = result.mappings().first()
        if not order_row:
            return None

        po = dict(order_row)
        lines_result = await session.execute(
            text("SELECT * FROM inventory_po_lines WHERE po_id = :po_id ORDER BY id ASC"),
            {"po_id": po_id},
        )
        po["lines"] = [dict(r) for r in lines_result.mappings().all()]

        receipts_result = await session.execute(
            text("SELECT * FROM inventory_receipts WHERE po_id = :po_id ORDER BY created_at DESC"),
            {"po_id": po_id},
        )
        receipts = [dict(r) for r in receipts_result.mappings().all()]

        if receipts:
            receipt_ids = [r["receipt_id"] for r in receipts]
            rid_placeholders = ", ".join([f":rid_{i}" for i in range(len(receipt_ids))])
            rid_params = {f"rid_{i}": rid for i, rid in enumerate(receipt_ids)}
            rl_result = await session.execute(
                text(f"SELECT * FROM inventory_receipt_lines WHERE receipt_id IN ({rid_placeholders}) ORDER BY id ASC"),
                rid_params,
            )
            all_receipt_lines = [dict(r) for r in rl_result.mappings().all()]
            lines_by_receipt_id: Dict[str, List[Dict]] = {}
            for rl in all_receipt_lines:
                lines_by_receipt_id.setdefault(rl["receipt_id"], []).append(rl)
            for receipt in receipts:
                receipt["lines"] = lines_by_receipt_id.get(receipt["receipt_id"], [])

        po["receipts"] = receipts
        return po


async def receive_purchase_order(
    po_id: str,
    receipt_data: ReceiptCreate,
    user: Dict[str, Any],
) -> Dict[str, Any]:
    actor = _resolve_actor(user)

    if not receipt_data.lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receipt must include at least one line item",
        )

    async with async_session_factory() as session:
        po_result = await session.execute(
            text("SELECT * FROM inventory_purchase_orders WHERE po_id = :po_id"),
            {"po_id": po_id},
        )
        po_row = po_result.mappings().first()
        if not po_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found",
            )

        po = dict(po_row)
        if po["status"] in [PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.RECEIVED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot receive a purchase order in '{po['status']}' status",
            )

        po_lines_result = await session.execute(
            text("SELECT * FROM inventory_po_lines WHERE po_id = :po_id"),
            {"po_id": po_id},
        )
        po_lines = [dict(r) for r in po_lines_result.mappings().all()]
        po_line_map = {line["item_inventory_id"]: line for line in po_lines}

        now = datetime.now().replace(tzinfo=None)
        receipt_id = generate_inventory_receipt_id()

        await session.execute(
            text("""INSERT INTO inventory_receipts (
                   receipt_id, po_id, supplier_name, received_by, received_by_name, notes, created_at
               ) VALUES (:receipt_id, :po_id, :supplier_name, :received_by, :received_by_name, :notes, :created_at)"""),
            {
                "receipt_id": receipt_id,
                "po_id": po_id,
                "supplier_name": po.get("supplier_name"),
                "received_by": int(actor["id"]),
                "received_by_name": actor["name"],
                "notes": receipt_data.notes,
                "created_at": now,
            },
        )

        receipt_item_ids = [line.item_inventory_id for line in receipt_data.lines]
        receipt_item_placeholders = ", ".join([f":ritem_{i}" for i in range(len(receipt_item_ids))])
        receipt_item_params = {f"ritem_{i}": iid for i, iid in enumerate(receipt_item_ids)}
        receipt_item_result = await session.execute(
            text(f"SELECT * FROM external_inventory_items WHERE inventory_id IN ({receipt_item_placeholders})"),
            receipt_item_params,
        )
        receipt_item_rows = receipt_item_result.mappings().all()
        receipt_items_map: Dict[str, Dict[str, Any]] = {str(r["inventory_id"]): dict(r) for r in receipt_item_rows}

        for line in receipt_data.lines:
            item_id = line.item_inventory_id
            if item_id not in po_line_map:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Item '{item_id}' does not belong to this purchase order",
                )

            item = receipt_items_map.get(item_id)
            if not item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Item '{item_id}' not found",
                )
            quantity_received = int(
                line.quantity_received
                or po_line_map[item_id].get("quantity_ordered")
                or 1
            )
            unit_cost = float(
                line.unit_cost
                if line.unit_cost is not None
                else po_line_map[item_id].get("unit_cost")
                or item.get("price")
                or item.get("unit_cost")
                or 0
            )
            line_total = float(quantity_received) * unit_cost

            await session.execute(
                text("""INSERT INTO inventory_receipt_lines (
                       receipt_id, item_inventory_id, item_sku, item_name,
                       quantity_received, unit_cost, line_total
                   ) VALUES (:receipt_id, :item_inventory_id, :item_sku, :item_name,
                       :quantity_received, :unit_cost, :line_total)"""),
                {
                    "receipt_id": receipt_id,
                    "item_inventory_id": item_id,
                    "item_sku": item.get("item_id") or item.get("sku"),
                    "item_name": item.get("name"),
                    "quantity_received": quantity_received,
                    "unit_cost": unit_cost,
                    "line_total": line_total,
                },
            )

            await session.execute(
                text("""UPDATE external_inventory_items
                   SET quantity_on_hand = 0, status = 'inactive', price = :unit_cost, unit_cost = :unit_cost2, updated_at = :updated_at
                   WHERE inventory_id = :inventory_id"""),
                {"unit_cost": unit_cost, "unit_cost2": unit_cost, "updated_at": now, "inventory_id": item_id},
            )

            placed_by_name = po.get("ordered_by_name") or po.get("ordered_by") or "Unknown"
            confirmation_note = f"Order placed by {placed_by_name}. Confirmed by {actor['name']}"
            base_note = receipt_data.notes or f"Stock submitted against PO {po_id}"

            await session.execute(
                text("""INSERT INTO inventory_stock_movements (
                       movement_id, item_inventory_id, item_sku, item_name,
                       movement_type, quantity, reference_type, reference_id,
                       notes, performed_by, performed_by_name, created_at
                   ) VALUES (:movement_id, :item_inventory_id, :item_sku, :item_name,
                       :movement_type, :quantity, :reference_type, :reference_id,
                       :notes, :performed_by, :performed_by_name, :created_at)"""),
                {
                    "movement_id": generate_inventory_movement_id(),
                    "item_inventory_id": item_id,
                    "item_sku": item.get("item_id") or item.get("sku"),
                    "item_name": item.get("name"),
                    "movement_type": MovementType.OUT.value,
                    "quantity": quantity_received,
                    "reference_type": "purchase_submit",
                    "reference_id": receipt_id,
                    "notes": f"{base_note}. {confirmation_note}",
                    "performed_by": int(actor["id"]),
                    "performed_by_name": actor["name"],
                    "created_at": now,
                },
            )

        ordered_result = await session.execute(
            text("SELECT COALESCE(SUM(quantity_ordered), 0) FROM inventory_po_lines WHERE po_id = :po_id"),
            {"po_id": po_id},
        )
        total_ordered_qty = int(ordered_result.scalar() or 0)

        received_result = await session.execute(
            text("""SELECT COALESCE(SUM(quantity_received), 0)
               FROM inventory_receipt_lines irl
               JOIN inventory_receipts ir ON irl.receipt_id = ir.receipt_id
               WHERE ir.po_id = :po_id"""),
            {"po_id": po_id},
        )
        total_received_qty = int(received_result.scalar() or 0)

        new_status = (
            PurchaseOrderStatus.RECEIVED.value
            if total_received_qty >= total_ordered_qty and total_ordered_qty > 0
            else PurchaseOrderStatus.PARTIALLY_RECEIVED.value
        )

        await session.execute(
            text("UPDATE inventory_purchase_orders SET status = :status, updated_at = :updated_at WHERE po_id = :po_id"),
            {"status": new_status, "updated_at": now, "po_id": po_id},
        )

        await bump_cache_version(session)
        await session.commit()

    po = await get_purchase_order_by_id(po_id)
    if not po:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load updated purchase order",
        )
    return po


async def get_receipts(
    page: int = 1,
    page_size: int = 20,
    po_id: Optional[str] = None,
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        conditions = ["1=1"]
        params: Dict[str, Any] = {}
        param_idx = 0

        if po_id:
            pname = f"p_{param_idx}"
            conditions.append(f"po_id = :{pname}")
            params[pname] = po_id
            param_idx += 1

        where_clause = " AND ".join(conditions)

        result = await session.execute(
            text(f"SELECT COUNT(*) FROM inventory_receipts WHERE {where_clause}"),
            params,
        )
        total = result.scalar()

        offset = (page - 1) * page_size
        pname_limit = f"p_{param_idx}"
        pname_offset = f"p_{param_idx + 1}"
        params[pname_limit] = page_size
        params[pname_offset] = offset

        result = await session.execute(
            text(f"""SELECT * FROM inventory_receipts
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT :{pname_limit} OFFSET :{pname_offset}"""),
            params,
        )
        receipts = [dict(r) for r in result.mappings().all()]

        if receipts:
            receipt_ids = [r["receipt_id"] for r in receipts]
            rid_placeholders = ", ".join([f":rid_{i}" for i in range(len(receipt_ids))])
            rid_params = {f"rid_{i}": rid for i, rid in enumerate(receipt_ids)}
            lines_result = await session.execute(
                text(f"SELECT * FROM inventory_receipt_lines WHERE receipt_id IN ({rid_placeholders}) ORDER BY id ASC"),
                rid_params,
            )
            all_lines = [dict(r) for r in lines_result.mappings().all()]
            lines_by_receipt: Dict[str, List[Dict]] = {}
            for line in all_lines:
                lines_by_receipt.setdefault(line["receipt_id"], []).append(line)
            for receipt in receipts:
                receipt["lines"] = lines_by_receipt.get(receipt["receipt_id"], [])

        return {
            "data": receipts,
            "pagination": get_pagination(page, page_size, total),
        }


async def get_stock_movements(
    page: int = 1,
    page_size: int = 20,
    item_inventory_id: Optional[str] = None,
    movement_type: Optional[str] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        conditions = ["1=1"]
        params: Dict[str, Any] = {}
        param_idx = 0

        if item_inventory_id:
            pname = f"p_{param_idx}"
            conditions.append(f"item_inventory_id = :{pname}")
            params[pname] = item_inventory_id
            param_idx += 1

        if movement_type:
            pname = f"p_{param_idx}"
            conditions.append(f"movement_type = :{pname}")
            params[pname] = movement_type
            param_idx += 1

        if search:
            like = f"%{search}%"
            search_field_map = {
                "movement_id": "movement_id",
                "item_sku": "item_sku",
                "item_name": "item_name",
                "movement_type": "movement_type",
                "reference_type": "reference_type",
                "reference_id": "reference_id",
                "notes": "notes",
            }
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                pname = f"p_{param_idx}"
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE :{pname}")
                params[pname] = like
                param_idx += 1
            else:
                like_clauses = []
                for field in ["movement_id", "item_sku", "item_name", "movement_type", "reference_type", "reference_id", "notes"]:
                    pname = f"p_{param_idx}"
                    like_clauses.append(f"{field} LIKE :{pname}")
                    params[pname] = like
                    param_idx += 1
                conditions.append(f"({' OR '.join(like_clauses)})")

        where_clause = " AND ".join(conditions)

        result = await session.execute(
            text(f"SELECT COUNT(*) FROM inventory_stock_movements WHERE {where_clause}"),
            params,
        )
        total = result.scalar()

        offset = (page - 1) * page_size
        pname_limit = f"p_{param_idx}"
        pname_offset = f"p_{param_idx + 1}"
        params[pname_limit] = page_size
        params[pname_offset] = offset

        result = await session.execute(
            text(f"""SELECT * FROM inventory_stock_movements
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT :{pname_limit} OFFSET :{pname_offset}"""),
            params,
        )
        movements = [dict(r) for r in result.mappings().all()]

        return {
            "data": movements,
            "pagination": get_pagination(page, page_size, total),
        }


async def create_stock_adjustment(
    payload: StockAdjustmentCreate,
    user: Dict[str, Any],
) -> Dict[str, Any]:
    actor = _resolve_actor(user)

    if payload.quantity_change == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity change must be non-zero",
        )

    async with async_session_factory() as session:
        item_result = await session.execute(
            text("SELECT * FROM external_inventory_items WHERE inventory_id = :inventory_id"),
            {"inventory_id": payload.item_inventory_id},
        )
        item_row = item_result.mappings().first()
        if not item_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found",
            )

        item = dict(item_row)
        current_qty = int(item.get("quantity_on_hand") or 0)
        new_qty = current_qty + payload.quantity_change
        if new_qty < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Adjustment would result in negative stock",
            )

        now = datetime.now().replace(tzinfo=None)
        await session.execute(
            text("""UPDATE external_inventory_items
               SET quantity_on_hand = :quantity_on_hand, updated_at = :updated_at
               WHERE inventory_id = :inventory_id"""),
            {"quantity_on_hand": new_qty, "updated_at": now, "inventory_id": payload.item_inventory_id},
        )

        movement_type = (
            MovementType.ADJUSTMENT_IN.value
            if payload.quantity_change > 0
            else MovementType.ADJUSTMENT_OUT.value
        )
        await session.execute(
            text("""INSERT INTO inventory_stock_movements (
                   movement_id, item_inventory_id, item_sku, item_name,
                   movement_type, quantity, reference_type, reference_id,
                   notes, performed_by, performed_by_name, created_at
               ) VALUES (:movement_id, :item_inventory_id, :item_sku, :item_name,
                   :movement_type, :quantity, :reference_type, :reference_id,
                   :notes, :performed_by, :performed_by_name, :created_at)"""),
            {
                "movement_id": generate_inventory_movement_id(),
                "item_inventory_id": payload.item_inventory_id,
                "item_sku": item.get("item_id") or item.get("sku"),
                "item_name": item.get("name"),
                "movement_type": movement_type,
                "quantity": abs(payload.quantity_change),
                "reference_type": "manual_adjustment",
                "reference_id": payload.item_inventory_id,
                "notes": payload.reason,
                "performed_by": actor["id"],
                "performed_by_name": actor["name"],
                "created_at": now,
            },
        )

        await bump_cache_version(session)
        await session.commit()

    updated = await get_item_by_inventory_id(payload.item_inventory_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load updated item",
        )
    return updated
