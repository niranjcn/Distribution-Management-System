import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

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
from app.services.bulk_upload_service import build_bulk_result, chunks
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
    "warranty_start_date",
    "warranty_duration",
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


def _compute_warranty_status(warranty_start_date, warranty_duration) -> str:
    """Classify an item's warranty as active, expired, or none based on
    warranty_start_date + warranty_duration months vs today."""
    if not warranty_start_date:
        return "none"
    try:
        start = warranty_start_date.date() if hasattr(warranty_start_date, "date") else date.fromisoformat(str(warranty_start_date)[:10])
    except ValueError:
        return "none"
    duration = int(warranty_duration or 0)
    try:
        expiry = start.replace(
            year=start.year + (start.month - 1 + duration) // 12,
            month=(start.month - 1 + duration) % 12 + 1,
        )
    except ValueError:
        return "none"
    return "expired" if expiry < date.today() else "active"

_EXTERNAL_HISTORY_INSERT_SQL = """INSERT INTO external_device_history (
     history_id, item_id, item_name, identifier_type, identifier, device_type, price,
     quantity, recipient_user_id, recipient_name, previous_quantity, remaining_quantity,
     distributed_by, distributed_by_name, distributed_at, notes, status
 ) VALUES (:history_id, :item_id, :item_name, :identifier_type, :identifier, :device_type, :price,
     :quantity, :recipient_user_id, :recipient_name, :previous_quantity, :remaining_quantity,
     :distributed_by, :distributed_by_name, :distributed_at, :notes, 'completed')"""


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


async def _check_identifier_conflict(
    session,
    identifier_type: Optional[str],
    identifier: Optional[str],
    exclude_item_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Return a conflicting row for the same non-null (identifier_type,
    identifier) pair, optionally excluding a specific item (used when editing)."""
    if not identifier_type or not identifier:
        return None

    result = await session.execute(
        text("""
            SELECT id FROM external_inventory_items
            WHERE identifier_type = :identifier_type AND identifier = :identifier
              AND (:exclude_item_id IS NULL OR id != :exclude_item_id)
            LIMIT 1
        """),
        {
            "identifier_type": identifier_type,
            "identifier": identifier,
            "exclude_item_id": exclude_item_id,
        },
    )
    return result.mappings().first()


async def get_items(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    device_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    identifier_type: Optional[str] = None,
    warranty: Optional[str] = None,
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

        if identifier_type:
            pname = f"p_{param_idx}"
            conditions.append(f"identifier_type = :{pname}")
            params[pname] = identifier_type
            param_idx += 1

        if warranty:
            normalized_warranty = str(warranty).strip().lower()
            if normalized_warranty == "expired":
                conditions.append(
                    "(warranty_start_date IS NOT NULL "
                    "AND DATE_ADD(warranty_start_date, INTERVAL COALESCE(warranty_duration, 0) MONTH) < CURDATE())"
                )
            elif normalized_warranty == "active":
                conditions.append(
                    "(warranty_start_date IS NULL "
                    "OR DATE_ADD(warranty_start_date, INTERVAL COALESCE(warranty_duration, 0) MONTH) >= CURDATE())"
                )

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

        conflict = await _check_identifier_conflict(
            session,
            item_data.identifier_type,
            item_data.identifier,
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An item with this identifier type and identifier already exists",
            )

        result = await session.execute(
            text("""INSERT INTO external_inventory_items (
                     name, identifier_type, identifier, device_type, price, quantity,
                     supplier_name, location, status, notes, warranty_start_date, warranty_duration,
                     created_by, created_at, updated_at
                 ) VALUES (:name, :identifier_type, :identifier, :device_type, :price, :quantity,
                     :supplier_name, :location, 'active', :notes, :warranty_start_date, :warranty_duration,
                     :created_by, :created_at, :updated_at)"""),
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
                "warranty_start_date": item_data.warranty_start_date,
                "warranty_duration": item_data.warranty_duration,
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
    update_dict = item_data.model_dump(exclude_unset=True)
    if not update_dict:
        return await get_item_by_id(item_id)

    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value

    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM external_inventory_items WHERE id = :item_id"),
            {"item_id": int(item_id)},
        )
        existing = result.mappings().first()
        if not existing:
            return None

        conflict = await _check_identifier_conflict(
            session,
            update_dict.get("identifier_type", existing.get("identifier_type")),
            update_dict.get("identifier", existing.get("identifier")),
            exclude_item_id=int(item_id),
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An item with this identifier type and identifier already exists",
            )

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


async def _notify_recipient_batch(recipient: Dict[str, Any], records: List[Dict[str, Any]]) -> None:
    """Send a single aggregated notification for a bulk distribution instead of
    one notification per distributed record, so a large upload does not create
    hundreds of rows in the notifications table for the same recipient."""
    if not records:
        return
    try:
        per_name: Dict[str, int] = {}
        for r in records:
            name = str(r.get("item_name") or "item")
            per_name[name] = per_name.get(name, 0) + int(r.get("quantity") or 0)

        if len(per_name) == 1:
            (name, qty), = per_name.items()
            message = f"You have been assigned {qty} x {name} from external inventory."
        else:
            parts = ", ".join(f"{qty} x {name}" for name, qty in sorted(per_name.items()))
            message = f"You have been assigned {len(records)} item(s) from external inventory: {parts}."

        await notification_service.create_notification(
            user_id=int(recipient["id"]),
            title="External Inventory Items Assigned",
            message=message,
            notification_type="info",
            category="external_inventory",
            link="/external-inventory/items",
        )
    except Exception:
        logger.warning("Failed to notify recipient for external inventory bulk distribution", exc_info=True)


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

        # Resolve all referenced items and recipients up front with a handful
        # of batched queries instead of one round trip per entry. The items are
        # locked with FOR UPDATE and the locks are held until commit, so the
        # quantities read here are authoritative and the batched decrement
        # below cannot oversell even with concurrent requests.
        parsed_entries = []
        for entry in payload.items:
            try:
                item_id = int(entry.item_id)
            except (ValueError, TypeError):
                errors.append({"item_id": entry.item_id, "error": "Invalid item id"})
                continue
            parsed_entries.append((entry, item_id))

        item_ids = sorted({item_id for _, item_id in parsed_entries})
        recipient_ids = sorted({int(e.to_user_id) for e in payload.items if e.to_user_id is not None})
        recipient_emails = sorted({
            (e.recipient_email or "").strip().lower()
            for e in payload.items if e.to_user_id is None and (e.recipient_email or "").strip()
        })

        locked_items: Dict[int, Dict[str, Any]] = {}
        for batch in chunks(item_ids, 1000):
            ph = ",".join([f":i_{i}" for i in range(len(batch))])
            params = {f"i_{i}": v for i, v in enumerate(batch)}
            rows = (await session.execute(
                text(f"SELECT * FROM external_inventory_items WHERE id IN ({ph}) FOR UPDATE"),
                params,
            )).mappings().all()
            for row in rows:
                locked_items[int(row["id"])] = dict(row)

        recipients_by_id: Dict[int, Dict[str, Any]] = {}
        for batch in chunks(recipient_ids, 1000):
            ph = ",".join([f":u_{i}" for i in range(len(batch))])
            params = {f"u_{i}": v for i, v in enumerate(batch)}
            rows = (await session.execute(
                text(f"SELECT id, name, email, role, status FROM users WHERE id IN ({ph})"),
                params,
            )).mappings().all()
            for row in rows:
                recipients_by_id[int(row["id"])] = dict(row)

        recipients_by_email: Dict[str, Dict[str, Any]] = {}
        for batch in chunks(recipient_emails, 1000):
            ph = ",".join([f":e_{i}" for i in range(len(batch))])
            params = {f"e_{i}": v for i, v in enumerate(batch)}
            rows = (await session.execute(
                text(f"SELECT id, name, email, role, status FROM users WHERE LOWER(email) IN ({ph})"),
                params,
            )).mappings().all()
            for row in rows:
                recipients_by_email[str(row.get("email") or "").lower()] = dict(row)

        history_rows: List[Dict[str, Any]] = []
        # Track the running quantity per item as entries are validated so
        # repeated entries for the same item cannot oversell within one request
        # and history records the true previous/remaining quantities.
        running_qty: Dict[int, int] = {
            iid: int(item.get("quantity") or 0) for iid, item in locked_items.items()
        }
        pending_decrements: Dict[int, int] = {}

        for entry, item_id in parsed_entries:
            try:
                item = locked_items.get(item_id)
                if not item:
                    errors.append({"item_id": item_id, "error": "Item not found"})
                    continue
                if item.get("status") != "active":
                    errors.append({"item_id": item_id, "error": "Item is not active"})
                    continue

                current_qty = running_qty.get(item_id, 0)
                if current_qty <= 0:
                    errors.append({"item_id": item_id, "error": "Item is out of stock"})
                    continue
                if entry.quantity > current_qty:
                    errors.append({
                        "item_id": item_id,
                        "error": f"Cannot distribute more than the available quantity ({current_qty})",
                    })
                    continue

                if entry.to_user_id is not None:
                    recipient = recipients_by_id.get(int(entry.to_user_id))
                else:
                    recipient = recipients_by_email.get((entry.recipient_email or "").strip().lower())
                if not recipient:
                    errors.append({"item_id": item_id, "error": "Recipient not found"})
                    continue
                if recipient.get("status") != "active":
                    errors.append({"item_id": item_id, "error": "Recipient account is not active"})
                    continue

                running_qty[item_id] = current_qty - entry.quantity
                pending_decrements[item_id] = pending_decrements.get(item_id, 0) + entry.quantity
                remaining = running_qty[item_id]

                history_id = generate_external_distribution_id()
                history_rows.append({
                    "history_id": history_id,
                    "item_id": item_id,
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
                })
                created.append({
                    "history_id": history_id,
                    "item_id": item_id,
                    "item_name": item["name"],
                    "quantity": entry.quantity,
                    "recipient_id": int(recipient["id"]),
                    "recipient_name": recipient.get("name") or recipient.get("email"),
                    "previous_quantity": current_qty,
                    "remaining_quantity": remaining,
                })
            except Exception as exc:
                logger.exception("Bulk external inventory distribution row failed")
                errors.append({"item_id": entry.item_id, "error": "An internal error occurred"})

        if pending_decrements:
            # Apply all decrements in one multi-row UPDATE per batch. The rows
            # are already locked (FOR UPDATE above), so no guard is needed and
            # each id is subtracted exactly by its validated quantity.
            for batch in chunks(sorted(pending_decrements), 500):
                case_clauses = []
                params: Dict[str, Any] = {"updated_at": now}
                for i, iid in enumerate(batch):
                    case_clauses.append(f"WHEN :did_{i} THEN :dqty_{i}")
                    params[f"did_{i}"] = iid
                    params[f"dqty_{i}"] = pending_decrements[iid]
                await session.execute(
                    text(f"""UPDATE external_inventory_items
                            SET quantity = quantity - CASE id {' '.join(case_clauses)} ELSE 0 END,
                                updated_at = :updated_at
                            WHERE id IN ({', '.join(f':did_{i}' for i in range(len(batch)))})"""),
                    params,
                )

        for batch in chunks(history_rows, 500):
            await session.execute(text(_EXTERNAL_HISTORY_INSERT_SQL), batch)

        await bump_cache_version(session)
        await session.commit()

    by_recipient: Dict[int, List[Dict[str, Any]]] = {}
    for record in created:
        by_recipient.setdefault(int(record["recipient_id"]), []).append(record)
    for recipient_id, records in by_recipient.items():
        await _notify_recipient_batch({"id": recipient_id}, records)

    return build_bulk_result(created, [], errors)


async def bulk_distribute_from_file(
    identifier_rows: List[Dict[str, Any]],
    to_user_id: int,
    user: Dict[str, Any],
) -> Dict[str, Any]:
    """Bulk-distribute external inventory items to a single recipient from
    uploaded rows. Each row identifies an item by its ``identifier_type`` and
    ``identifier`` (e.g. ``MAC ID`` + ``AA:BB:CC``) and an optional ``quantity``
    (default 1). Items with insufficient stock, unknown identifiers, or
    repeated identifier pairs are reported as per-row errors without aborting
    the batch. The ``(identifier_type, identifier)`` pair is unique per item.
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

        # Parse rows once, isolating per-row validation errors.
        entries: List[Dict[str, Any]] = []
        for entry in identifier_rows:
            row_idx = int(entry["row"])
            identifier_type = str(entry.get("identifier_type") or "").strip()
            identifier = str(entry.get("identifier") or "").strip()
            if not identifier_type or not identifier:
                errors.append({
                    "row": row_idx,
                    "name": "",
                    "error": "Both identifier_type and identifier are required",
                })
                continue

            try:
                quantity_raw = entry.get("quantity")
                quantity_value = 1 if quantity_raw in (None, "") else int(quantity_raw)
                if quantity_value < 1:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append({"row": row_idx, "name": "", "error": "Quantity must be a positive integer"})
                continue

            entries.append({
                "row": row_idx,
                "identifier_type": identifier_type,
                "identifier": identifier,
                "quantity": quantity_value,
                "notes": entry.get("notes"),
            })

        # Lock the referenced items in batched queries instead of one SELECT
        # per row. The locks are held until commit, so the quantities read here
        # are authoritative and the batched decrement below cannot oversell.
        # The (identifier_type, identifier) pair uniquely identifies an item.
        locked_by_pair: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for batch in chunks([(e["identifier_type"], e["identifier"]) for e in entries], 500):
            conditions = []
            params: Dict[str, Any] = {}
            for i, (idt, idf) in enumerate(batch):
                conditions.append(f"(identifier_type = :t_{i} AND identifier = :i_{i})")
                params[f"t_{i}"] = idt
                params[f"i_{i}"] = idf
            rows = (await session.execute(
                text(f"SELECT * FROM external_inventory_items WHERE {' OR '.join(conditions)} FOR UPDATE"),
                params,
            )).mappings().all()
            for row in rows:
                pair = (row.get("identifier_type"), row.get("identifier"))
                if pair[0] and pair[1]:
                    locked_by_pair[pair] = dict(row)

        history_rows: List[Dict[str, Any]] = []
        pending_decrements: Dict[int, int] = {}
        seen_pairs: set = set()
        for entry in entries:
            row_idx = entry["row"]
            identifier_type = entry["identifier_type"]
            identifier = entry["identifier"]
            quantity_value = entry["quantity"]
            pair = (identifier_type, identifier)

            if pair in seen_pairs:
                errors.append({
                    "row": row_idx,
                    "name": "",
                    "error": f"Duplicate identifier ({identifier_type} {identifier}) in file",
                })
                continue

            item = locked_by_pair.get(pair)
            if not item:
                errors.append({
                    "row": row_idx,
                    "name": "",
                    "error": f"Item not found ({identifier_type} {identifier})",
                })
                continue

            # A single recipient is resolved above; an item already
            # distributed in this batch is rejected to avoid distributing the
            # same item twice.
            row_error = None
            if item.get("status") != "active":
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

            seen_pairs.add(pair)

            item_id = int(item["id"])
            current_qty = int(item.get("quantity") or 0)
            remaining = current_qty - quantity_value
            pending_decrements[item_id] = quantity_value

            history_id = generate_external_distribution_id()
            history_rows.append({
                "history_id": history_id,
                "item_id": item_id,
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
                "notes": entry["notes"],
            })
            created.append({
                "history_id": history_id,
                "item_id": item_id,
                "item_name": item["name"],
                "quantity": quantity_value,
                "recipient_id": int(recipient["id"]),
                "recipient_name": recipient.get("name") or recipient.get("email"),
                "previous_quantity": current_qty,
                "remaining_quantity": remaining,
            })

        if pending_decrements:
            # Apply all decrements in one multi-row UPDATE per batch. The rows
            # are already locked (FOR UPDATE above), so no guard is needed.
            for batch in chunks(sorted(pending_decrements), 500):
                case_clauses = []
                params: Dict[str, Any] = {"updated_at": now}
                for i, iid in enumerate(batch):
                    case_clauses.append(f"WHEN :did_{i} THEN :dqty_{i}")
                    params[f"did_{i}"] = iid
                    params[f"dqty_{i}"] = pending_decrements[iid]
                await session.execute(
                    text(f"""UPDATE external_inventory_items
                            SET quantity = quantity - CASE id {' '.join(case_clauses)} ELSE 0 END,
                                updated_at = :updated_at
                            WHERE id IN ({', '.join(f':did_{i}' for i in range(len(batch)))})"""),
                    params,
                )

        for batch in chunks(history_rows, 500):
            await session.execute(text(_EXTERNAL_HISTORY_INSERT_SQL), batch)

        await bump_cache_version(session)
        await session.commit()

    if created:
        await _notify_recipient_batch(recipient, created)

    data = build_bulk_result(created, [], errors)
    data["total_rows"] = total_rows
    data["recipient_id"] = int(recipient["id"])
    data["recipient_name"] = recipient.get("name") or recipient.get("email")
    return data


async def get_distribution_history(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    item_id: Optional[int] = None,
    identifier_type: Optional[str] = None,
    device_type: Optional[str] = None,
    warranty: Optional[str] = None,
) -> Dict[str, Any]:
    """List the completed external inventory distribution history (audit/report)."""
    async with async_session_factory() as session:
        conditions = ["1=1"]
        params: Dict[str, Any] = {}
        param_idx = 0
        join_clause = (
            " LEFT JOIN external_inventory_items i ON i.id = h.item_id"
        )

        if item_id is not None:
            pname = f"p_{param_idx}"
            conditions.append(f"h.item_id = :{pname}")
            params[pname] = int(item_id)
            param_idx += 1

        if identifier_type:
            pname = f"p_{param_idx}"
            conditions.append(f"h.identifier_type = :{pname}")
            params[pname] = identifier_type
            param_idx += 1

        if device_type:
            pname = f"p_{param_idx}"
            conditions.append(f"h.device_type = :{pname}")
            params[pname] = device_type
            param_idx += 1

        if warranty:
            normalized_warranty = str(warranty).strip().lower()
            if normalized_warranty == "expired":
                conditions.append(
                    "(i.warranty_start_date IS NOT NULL "
                    "AND DATE_ADD(i.warranty_start_date, INTERVAL COALESCE(i.warranty_duration, 0) MONTH) < CURDATE())"
                )
            elif normalized_warranty == "active":
                conditions.append(
                    "(i.warranty_start_date IS NULL "
                    "OR DATE_ADD(i.warranty_start_date, INTERVAL COALESCE(i.warranty_duration, 0) MONTH) >= CURDATE())"
                )

        if search:
            like = f"%{search}%"
            search_field_map = {
                "history_id": "h.history_id",
                "item_name": "h.item_name",
                "recipient_name": "h.recipient_name",
                "distributed_by_name": "h.distributed_by_name",
                "status": "h.status",
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
            text(f"SELECT COUNT(*) FROM external_device_history h{join_clause} WHERE {where_clause}"),
            params,
        )
        total = result.scalar()

        offset = (page - 1) * page_size
        pname_limit = f"p_{param_idx}"
        pname_offset = f"p_{param_idx + 1}"
        params[pname_limit] = page_size
        params[pname_offset] = offset

        result = await session.execute(
            text(f"""SELECT h.*, i.warranty_start_date, i.warranty_duration
                FROM external_device_history h{join_clause}
                WHERE {where_clause}
                ORDER BY h.distributed_at DESC
                LIMIT :{pname_limit} OFFSET :{pname_offset}"""),
            params,
        )
        rows = []
        for r in result.mappings().all():
            row = dict(r)
            row["warranty_status"] = _compute_warranty_status(row.get("warranty_start_date"), row.get("warranty_duration"))
            rows.append(row)

        return {
            "data": rows,
            "pagination": get_pagination(page, page_size, total),
        }
