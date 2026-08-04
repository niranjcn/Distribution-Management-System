import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from sqlalchemy import text

from app.core.cache_version import bump_cache_version
from app.database_sqlalchemy import async_session_factory
from app.models.inventory import (
    ExternalBulkDistributionCreate,
    ExternalDistributionCreate,
    InventoryItemCreate,
    InventoryItemUpdate,
)
from app.services import notification_service
from app.utils.helpers import (
    generate_external_distribution_id,
    get_pagination,
)

logger = logging.getLogger(__name__)

MANAGEMENT_ROLES = {"super_admin", "manager", "pdic_staff"}

MANAGEMENT_ITEM_FIELDS = [
    "id",
    "name",
    "identifier_type",
    "identifier",
    "device_type",
    "price",
    "quantity",
    "supplier_name",
    "location",
    "status",
    "notes",
    "created_by",
    "created_at",
    "updated_at",
]

NON_MANAGEMENT_ITEM_FIELDS = ["id", "name", "price"]

SEARCH_FIELD_MAP = {
    "name": "name",
    "identifier": "identifier",
    "identifier_type": "identifier_type",
    "device_type": "device_type",
    "supplier_name": "supplier_name",
    "location": "location",
}


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


def _is_management(user: Dict[str, Any]) -> bool:
    role = str(user.get("role") or "").strip().lower()
    return role in MANAGEMENT_ROLES


def _mask_item_fields(item: Dict[str, Any], management: bool) -> Dict[str, Any]:
    fields = MANAGEMENT_ITEM_FIELDS if management else NON_MANAGEMENT_ITEM_FIELDS
    return {k: item.get(k) for k in fields}


async def get_items(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    device_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    management: bool = True,
) -> Dict[str, Any]:
    """List catalog items. Depleted items (quantity = 0) are hidden from the
    catalog and from distribution dropdowns but remain in the database for
    historical reporting."""
    async with async_session_factory() as session:
        conditions = ["quantity > 0"]
        params: Dict[str, Any] = {}
        param_idx = 0

        if search:
            like = f"%{search}%"
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by and normalized_search_by != "all" and normalized_search_by in SEARCH_FIELD_MAP:
                pname = f"p_{param_idx}"
                conditions.append(f"{SEARCH_FIELD_MAP[normalized_search_by]} LIKE :{pname}")
                params[pname] = like
                param_idx += 1
            else:
                like_clauses = []
                for field in SEARCH_FIELD_MAP.values():
                    pname = f"p_{param_idx}"
                    like_clauses.append(f"{field} LIKE :{pname}")
                    params[pname] = like
                    param_idx += 1
                conditions.append(f"({' OR '.join(like_clauses)})")

        if device_type:
            pname = f"p_{param_idx}"
            conditions.append(f"device_type = :{pname}")
            params[pname] = device_type
            param_idx += 1

        if status_filter:
            pname = f"p_{param_idx}"
            conditions.append(f"status = :{pname}")
            params[pname] = status_filter
            param_idx += 1

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
            text(f"""SELECT * FROM external_inventory_items
                WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT :{pname_limit} OFFSET :{pname_offset}"""),
            params,
        )
        rows = [dict(r) for r in result.mappings().all()]

        return {
            "data": [_mask_item_fields(r, management) for r in rows],
            "pagination": get_pagination(page, page_size, total),
        }


async def get_item_by_id(item_id: int) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM external_inventory_items WHERE id = :item_id"),
            {"item_id": int(item_id)},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def create_item(item_data: InventoryItemCreate, user: Dict[str, Any]) -> Dict[str, Any]:
    actor = _resolve_actor(user)

    async with async_session_factory() as session:
        now = datetime.now().replace(tzinfo=None)

        result = await session.execute(
            text("""INSERT INTO external_inventory_items (
                     name, identifier_type, identifier, device_type, price, quantity,
                     supplier_name, location, status, notes, created_by, created_at, updated_at
                 ) VALUES (:name, :identifier_type, :identifier, :device_type, :price, :quantity,
                     :supplier_name, :location, 'active', :notes, :created_by, :created_at, :updated_at)"""),
            {
                "name": item_data.name,
                "identifier_type": item_data.identifier_type,
                "identifier": item_data.identifier,
                "device_type": item_data.device_type,
                "price": item_data.price,
                "quantity": item_data.quantity,
                "supplier_name": item_data.supplier_name,
                "location": item_data.location,
                "notes": item_data.notes,
                "created_by": int(actor["id"]),
                "created_at": now,
                "updated_at": now,
            },
        )

        new_item_id = int(result.lastrowid)

        await bump_cache_version(session)
        await session.commit()

        result = await session.execute(
            text("SELECT * FROM external_inventory_items WHERE id = :item_id"),
            {"item_id": new_item_id},
        )
        return dict(result.mappings().first())


async def update_item(
    item_id: int,
    item_data: InventoryItemUpdate,
    user: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    update_dict = {k: v for k, v in item_data.model_dump().items() if v is not None}
    if not update_dict:
        return await get_item_by_id(item_id)

    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value

    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT id FROM external_inventory_items WHERE id = :item_id"),
            {"item_id": int(item_id)},
        )
        existing = result.mappings().first()
        if not existing:
            return None

        update_dict["updated_at"] = datetime.now().replace(tzinfo=None)
        set_clause = ", ".join([f"{k} = :{k}" for k in update_dict.keys()])
        set_params = {**update_dict, "item_id_where": int(item_id)}

        await session.execute(
            text(f"UPDATE external_inventory_items SET {set_clause} WHERE id = :item_id_where"),
            set_params,
        )

        await bump_cache_version(session)
        await session.commit()

    return await get_item_by_id(item_id)


async def delete_item(item_id: int) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM external_inventory_items WHERE id = :item_id"),
            {"item_id": int(item_id)},
        )
        existing = result.mappings().first()
        if not existing:
            return None

        await session.execute(
            text("DELETE FROM external_inventory_items WHERE id = :item_id"),
            {"item_id": int(item_id)},
        )
        await bump_cache_version(session)
        await session.commit()

    return dict(existing)


async def _resolve_recipient(session, to_user_id: Optional[int], recipient_email: Optional[str]) -> Dict[str, Any]:
    if to_user_id is not None:
        result = await session.execute(
            text("SELECT id, name, email, role, status FROM users WHERE id = :user_id"),
            {"user_id": int(to_user_id)},
        )
        row = result.mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")
        return dict(row)

    email = str(recipient_email or "").strip().lower()
    result = await session.execute(
        text("SELECT id, name, email, role, status FROM users WHERE LOWER(email) = :email"),
        {"email": email},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient with email '{recipient_email}' not found",
        )
    return dict(row)


async def _notify_recipient(recipient: Dict[str, Any], item: Dict[str, Any], quantity: int) -> None:
    try:
        await notification_service.create_notification(
            user_id=int(recipient["id"]),
            title="External Inventory Item Assigned",
            message=f"You have been assigned {quantity} x {item.get('name')} from external inventory.",
            notification_type="info",
            category="external_inventory",
            link="/external-inventory/items",
        )
    except Exception:
        logger.warning("Failed to notify recipient for external inventory distribution", exc_info=True)


async def distribute_item(payload: ExternalDistributionCreate, user: Dict[str, Any]) -> Dict[str, Any]:
    actor = _resolve_actor(user)

    async with async_session_factory() as session:
        item_result = await session.execute(
            text("SELECT * FROM external_inventory_items WHERE id = :item_id"),
            {"item_id": int(payload.item_id)},
        )
        item_row = item_result.mappings().first()
        if not item_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External inventory item not found")

        item = dict(item_row)
        if item.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item is not available for distribution",
            )

        current_qty = int(item.get("quantity") or 0)
        if current_qty <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item is out of stock",
            )
        if payload.quantity > current_qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot distribute more than the available quantity ({current_qty})",
            )

        recipient = await _resolve_recipient(session, payload.to_user_id, None)
        if recipient.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recipient account is not active",
            )

        remaining = current_qty - payload.quantity
        now = datetime.now().replace(tzinfo=None)

        await session.execute(
            text("UPDATE external_inventory_items SET quantity = :quantity, updated_at = :updated_at WHERE id = :item_id"),
            {"quantity": remaining, "updated_at": now, "item_id": int(payload.item_id)},
        )

        history_id = generate_external_distribution_id()
        await session.execute(
            text("""INSERT INTO external_device_history (
                     history_id, item_id, item_name, identifier_type, identifier, device_type, price,
                     quantity, recipient_user_id, recipient_name, previous_quantity, remaining_quantity,
                     distributed_by, distributed_by_name, distributed_at, notes, status
                 ) VALUES (:history_id, :item_id, :item_name, :identifier_type, :identifier, :device_type, :price,
                     :quantity, :recipient_user_id, :recipient_name, :previous_quantity, :remaining_quantity,
                     :distributed_by, :distributed_by_name, :distributed_at, :notes, 'completed')"""),
            {
                "history_id": history_id,
                "item_id": int(item["id"]),
                "item_name": item["name"],
                "identifier_type": item.get("identifier_type"),
                "identifier": item.get("identifier"),
                "device_type": item.get("device_type"),
                "price": item.get("price"),
                "quantity": payload.quantity,
                "recipient_user_id": int(recipient["id"]),
                "recipient_name": recipient.get("name") or recipient.get("email"),
                "previous_quantity": current_qty,
                "remaining_quantity": remaining,
                "distributed_by": int(actor["id"]),
                "distributed_by_name": actor["name"],
                "distributed_at": now,
                "notes": payload.notes,
            },
        )

        await bump_cache_version(session)
        await session.commit()

    await _notify_recipient(recipient, item, payload.quantity)

    return {
        "history_id": history_id,
        "item_id": int(item["id"]),
        "item_name": item["name"],
        "quantity": payload.quantity,
        "recipient_id": int(recipient["id"]),
        "recipient_name": recipient.get("name") or recipient.get("email"),
        "previous_quantity": current_qty,
        "remaining_quantity": remaining,
    }


async def bulk_distribute(payload: ExternalBulkDistributionCreate, user: Dict[str, Any]) -> Dict[str, Any]:
    actor = _resolve_actor(user)

    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk distribution must include at least one item",
        )

    created: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    async with async_session_factory() as session:
        now = datetime.now().replace(tzinfo=None)

        for entry in payload.items:
            try:
                item_result = await session.execute(
                    text("SELECT * FROM external_inventory_items WHERE id = :item_id"),
                    {"item_id": int(entry.item_id)},
                )
                item_row = item_result.mappings().first()
                if not item_row:
                    errors.append({"item_id": entry.item_id, "error": "Item not found"})
                    continue

                item = dict(item_row)
                if item.get("status") != "active":
                    errors.append({"item_id": entry.item_id, "error": "Item is not active"})
                    continue

                current_qty = int(item.get("quantity") or 0)
                if current_qty <= 0:
                    errors.append({"item_id": entry.item_id, "error": "Item is out of stock"})
                    continue
                if entry.quantity > current_qty:
                    errors.append({
                        "item_id": entry.item_id,
                        "error": f"Cannot distribute more than the available quantity ({current_qty})",
                    })
                    continue

                recipient = await _resolve_recipient(session, entry.to_user_id, entry.recipient_email)
                if recipient.get("status") != "active":
                    errors.append({"item_id": entry.item_id, "error": "Recipient account is not active"})
                    continue

                remaining = current_qty - entry.quantity

                await session.execute(
                    text("UPDATE external_inventory_items SET quantity = :quantity, updated_at = :updated_at WHERE id = :item_id"),
                    {"quantity": remaining, "updated_at": now, "item_id": int(entry.item_id)},
                )

                history_id = generate_external_distribution_id()
                await session.execute(
                    text("""INSERT INTO external_device_history (
                             history_id, item_id, item_name, identifier_type, identifier, device_type, price,
                             quantity, recipient_user_id, recipient_name, previous_quantity, remaining_quantity,
                             distributed_by, distributed_by_name, distributed_at, notes, status
                         ) VALUES (:history_id, :item_id, :item_name, :identifier_type, :identifier, :device_type, :price,
                             :quantity, :recipient_user_id, :recipient_name, :previous_quantity, :remaining_quantity,
                             :distributed_by, :distributed_by_name, :distributed_at, :notes, 'completed')"""),
                    {
                        "history_id": history_id,
                        "item_id": int(item["id"]),
                        "item_name": item["name"],
                        "identifier_type": item.get("identifier_type"),
                        "identifier": item.get("identifier"),
                        "device_type": item.get("device_type"),
                        "price": item.get("price"),
                        "quantity": entry.quantity,
                        "recipient_user_id": int(recipient["id"]),
                        "recipient_name": recipient.get("name") or recipient.get("email"),
                        "previous_quantity": current_qty,
                        "remaining_quantity": remaining,
                        "distributed_by": int(actor["id"]),
                        "distributed_by_name": actor["name"],
                        "distributed_at": now,
                        "notes": entry.notes,
                    },
                )

                created.append({
                    "history_id": history_id,
                    "item_id": int(item["id"]),
                    "item_name": item["name"],
                    "quantity": entry.quantity,
                    "recipient_id": int(recipient["id"]),
                    "recipient_name": recipient.get("name") or recipient.get("email"),
                    "previous_quantity": current_qty,
                    "remaining_quantity": remaining,
                })
            except HTTPException as exc:
                errors.append({"item_id": entry.item_id, "error": exc.detail})
            except Exception as exc:
                logger.exception("Bulk external inventory distribution row failed")
                errors.append({"item_id": entry.item_id, "error": "An internal error occurred"})

        await bump_cache_version(session)
        await session.commit()

    for record in created:
        await _notify_recipient(
            {"id": record["recipient_id"]},
            {"name": record["item_name"]},
            record["quantity"],
        )

    return {
        "created_count": len(created),
        "error_count": len(errors),
        "created": created,
        "errors": errors,
    }


async def bulk_distribute_from_file(
    identifier_rows: List[Dict[str, Any]],
    to_user_id: int,
    user: Dict[str, Any],
) -> Dict[str, Any]:
    """Bulk-distribute external inventory items to a single recipient from
    uploaded rows. Each row identifies an item by its `id` and an optional
    `quantity` (default 1). Items with insufficient stock, invalid ids, or
    repeated rows are reported as per-row errors without aborting the batch.
    """
    actor = _resolve_actor(user)

    if not identifier_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No item rows found in file",
        )

    total_rows = len(identifier_rows)
    created: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    async with async_session_factory() as session:
        now = datetime.now().replace(tzinfo=None)

        recipient = await _resolve_recipient(session, int(to_user_id), None)
        if recipient.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recipient account is not active",
            )

        resolved_items: dict = {}
        for entry in identifier_rows:
            row_idx = int(entry["row"])
            try:
                item_id = int(entry.get("id"))
                if item_id < 1:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append({"row": row_idx, "name": "", "error": "Missing or invalid item id"})
                continue

            if item_id in resolved_items:
                errors.append({"row": row_idx, "name": "", "error": f"Duplicate item id in file ({item_id})"})
                continue

            item_result = await session.execute(
                text("SELECT * FROM external_inventory_items WHERE id = :item_id"),
                {"item_id": item_id},
            )
            item_row = item_result.mappings().first()
            if not item_row:
                errors.append({"row": row_idx, "name": "", "error": f"Item not found (id {item_id})"})
                continue
            resolved_items[item_id] = dict(item_row)

        seen_items = set()
        for entry in identifier_rows:
            row_idx = int(entry["row"])
            try:
                item_id = int(entry.get("id"))
                if item_id < 1:
                    raise ValueError
            except (ValueError, TypeError):
                continue

            try:
                quantity_raw = entry.get("quantity")
                if quantity_raw in (None, ""):
                    quantity_value = 1
                else:
                    quantity_value = int(quantity_raw)
                    if quantity_value < 1:
                        raise ValueError
            except (ValueError, TypeError):
                errors.append({"row": row_idx, "name": resolved_items.get(item_id, {}).get("name", ""), "error": "Quantity must be a positive integer"})
                continue

            item = resolved_items.get(item_id)
            if not item:
                continue

            # A single recipient already resolved above; an item already
            # distributed in this batch is rejected to avoid distributing the
            # same item twice.
            row_error = None
            if item_id in seen_items:
                row_error = "Duplicate item id in file"
            elif item.get("status") != "active":
                row_error = "Item is not active"
            else:
                current_qty = int(item.get("quantity") or 0)
                if current_qty <= 0:
                    row_error = "Item is out of stock"
                elif quantity_value > current_qty:
                    row_error = f"Cannot distribute more than the available quantity ({current_qty})"

            if row_error:
                errors.append({"row": row_idx, "name": item.get("name", ""), "error": row_error})
                continue

            seen_items.add(item_id)
            current_qty = int(item.get("quantity") or 0)
            remaining = current_qty - quantity_value

            await session.execute(
                text("UPDATE external_inventory_items SET quantity = :quantity, updated_at = :updated_at WHERE id = :item_id"),
                {"quantity": remaining, "updated_at": now, "item_id": int(item["id"])},
            )

            history_id = generate_external_distribution_id()
            await session.execute(
                text("""INSERT INTO external_device_history (
                         history_id, item_id, item_name, identifier_type, identifier, device_type, price,
                         quantity, recipient_user_id, recipient_name, previous_quantity, remaining_quantity,
                         distributed_by, distributed_by_name, distributed_at, notes, status
                     ) VALUES (:history_id, :item_id, :item_name, :identifier_type, :identifier, :device_type, :price,
                         :quantity, :recipient_user_id, :recipient_name, :previous_quantity, :remaining_quantity,
                         :distributed_by, :distributed_by_name, :distributed_at, :notes, 'completed')"""),
                {
                    "history_id": history_id,
                    "item_id": int(item["id"]),
                    "item_name": item["name"],
                    "identifier_type": item.get("identifier_type"),
                    "identifier": item.get("identifier"),
                    "device_type": item.get("device_type"),
                    "price": item.get("price"),
                    "quantity": quantity_value,
                    "recipient_user_id": int(recipient["id"]),
                    "recipient_name": recipient.get("name") or recipient.get("email"),
                    "previous_quantity": current_qty,
                    "remaining_quantity": remaining,
                    "distributed_by": int(actor["id"]),
                    "distributed_by_name": actor["name"],
                    "distributed_at": now,
                    "notes": entry.get("notes"),
                },
            )

            created.append({
                "history_id": history_id,
                "item_id": int(item["id"]),
                "item_name": item["name"],
                "quantity": quantity_value,
                "recipient_id": int(recipient["id"]),
                "recipient_name": recipient.get("name") or recipient.get("email"),
                "previous_quantity": current_qty,
                "remaining_quantity": remaining,
            })

        await bump_cache_version(session)
        await session.commit()

    for record in created:
        await _notify_recipient(
            {"id": record["recipient_id"]},
            {"name": record["item_name"]},
            record["quantity"],
        )

    return {
        "total_rows": total_rows,
        "created_count": len(created),
        "error_count": len(errors),
        "recipient_id": int(recipient["id"]),
        "recipient_name": recipient.get("name") or recipient.get("email"),
        "created": created,
        "errors": errors,
    }


async def get_distribution_history(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    item_id: Optional[int] = None,
) -> Dict[str, Any]:
    """List the completed external inventory distribution history (audit/report)."""
    async with async_session_factory() as session:
        conditions = ["1=1"]
        params: Dict[str, Any] = {}
        param_idx = 0

        if item_id is not None:
            pname = f"p_{param_idx}"
            conditions.append(f"item_id = :{pname}")
            params[pname] = int(item_id)
            param_idx += 1

        if search:
            like = f"%{search}%"
            search_field_map = {
                "history_id": "history_id",
                "item_name": "item_name",
                "recipient_name": "recipient_name",
                "distributed_by_name": "distributed_by_name",
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
                for field in search_field_map.values():
                    pname = f"p_{param_idx}"
                    like_clauses.append(f"{field} LIKE :{pname}")
                    params[pname] = like
                    param_idx += 1
                conditions.append(f"({' OR '.join(like_clauses)})")

        where_clause = " AND ".join(conditions)

        result = await session.execute(
            text(f"SELECT COUNT(*) FROM external_device_history WHERE {where_clause}"),
            params,
        )
        total = result.scalar()

        offset = (page - 1) * page_size
        pname_limit = f"p_{param_idx}"
        pname_offset = f"p_{param_idx + 1}"
        params[pname_limit] = page_size
        params[pname_offset] = offset

        result = await session.execute(
            text(f"""SELECT * FROM external_device_history
                WHERE {where_clause}
                ORDER BY distributed_at DESC
                LIMIT :{pname_limit} OFFSET :{pname_offset}"""),
            params,
        )
        rows = [dict(r) for r in result.mappings().all()]

        return {
            "data": rows,
            "pagination": get_pagination(page, page_size, total),
        }
