from datetime import datetime, timezone, date
from typing import Optional, List, Dict, Any, Set
import io
import csv
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import text

from app.core.cache_version import bump_cache_version
from app.database_sqlalchemy import async_session_factory
from app.models.distribution import DistributionCreate, DistributionStatus
from app.models.device import DeviceStatus
from app.services import device_service, notification_service
from app.services.bulk_upload_service import build_bulk_result, chunks
from app.services.digital_id_search import build_identity_search_clause
from app.utils.helpers import get_pagination, generate_distribution_id


# Device-facing bulk operations (holder updates, history writes, clearing the
# pending_receipt lock) are executed in bounded batches. Single `IN` statements
# over the entire device list would exceed MySQL prepared-statement / packet
# limits and serialize hundreds of thousands of ids into one query, which is the
# dominant cost when confirming receipt of a large bulk distribution.
_BULK_CHUNK_SIZE = 1000


def _distribution_manifest_dir() -> Path:
    """Directory for generated distribution Excel manifests."""
    manifests_dir = Path(__file__).resolve().parents[2] / "distribution_manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    return manifests_dir


def _build_distribution_manifest(
    distribution_id: str,
    devices: List[Dict[str, Any]],
    from_user_name: str,
    to_user_name: str,
    created_at_iso: str,
) -> str:
    """Create an Excel manifest listing all devices in the distribution."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Device Manifest"

    sheet.append(["Distribution ID", distribution_id])
    sheet.append(["From", from_user_name])
    sheet.append(["To", to_user_name])
    sheet.append(["Created At", created_at_iso])
    sheet.append(["Total Devices", len(devices)])
    sheet.append([])
    sheet.append([
        "#",
        "Device ID",
        "Serial Number",
        "MAC Address",
        "Manufacturer",
        "Model",
        "Device Type",
        "Status",
    ])

    for idx, device in enumerate(devices, start=1):
        sheet.append([
            idx,
            device.get("device_id") or "",
            device.get("serial_number") or "",
            device.get("mac_address") or "",
            device.get("manufacturer") or "",
            device.get("model") or "",
            device.get("device_type") or "",
            device.get("status") or "",
        ])

    file_name = f"{distribution_id}-devices.xlsx"
    file_path = _distribution_manifest_dir() / file_name
    workbook.save(file_path)
    return file_name


def _build_distribution_mac_nuid_file(
    distribution: Dict[str, Any],
    devices: List[Dict[str, Any]],
    file_format: str = "csv",
) -> Dict[str, Any]:
    """Build export containing distribution context and device identifiers/details."""
    normalized = str(file_format or "csv").strip().lower()
    if normalized not in {"csv", "xlsx"}:
        raise ValueError("Unsupported export format. Use 'csv' or 'xlsx'")

    distribution_code = str(distribution.get("distribution_id") or "")
    from_user = str(distribution.get("from_user_name") or "")
    to_user = str(distribution.get("to_user_name") or "")

    headers = [
        "from_user_name",
        "to_user_name",
        "device_type",
        "manufacturer",
        "model",
        "serial_number",
        "mac_address",
        "nuid",
    ]

    rows = [
        {
            "from_user_name": from_user,
            "to_user_name": to_user,
            "device_type": str(device.get("device_type") or "").strip(),
            "manufacturer": str(device.get("manufacturer") or "").strip(),
            "model": str(device.get("model") or "").strip(),
            "serial_number": str(device.get("serial_number") or "").strip(),
            "mac_address": str(device.get("mac_address") or "").strip(),
            "nuid": str(device.get("nuid") or "").strip(),
        }
        for device in devices
    ]

    if normalized == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "DISTRIBUTION_EXPORT"
        sheet.append(headers)
        for row in rows:
            sheet.append([row[header] for header in headers])

        payload = io.BytesIO()
        workbook.save(payload)
        payload.seek(0)
        return {
            "content": payload.getvalue(),
            "filename": f"{distribution_code}-distribution-details.xlsx",
            "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)

    content = csv_buffer.getvalue()
    return {
        "content": content.encode("utf-8"),
        "filename": f"{distribution_code}-distribution-details.csv",
        "media_type": "text/csv",
    }


def _sender_display_name(user: Dict[str, Any]) -> str:
    role = str(user.get("role") or "").strip().lower()
    if role in {"super_admin", "manager", "pdic_staff"}:
        return "PDIC"
    return str(user.get("name") or "Unknown")


async def _bulk_update_device_holders(
    device_ids: List[Any],
    holder_id: int,
    holder_name: str,
    holder_type: str,
    location: str,
    status: str,
    performed_by: int,
    performed_by_name: str,
    from_user_id: Optional[int] = None,
    from_user_name: Optional[str] = None,
    notes: Optional[str] = None,
    action: str = "distributed",
    distribution_id: Optional[str] = None,
) -> List[str]:
    if not device_ids:
        return []

    normalized_ids = []
    for dev_id in device_ids:
        try:
            normalized_ids.append(int(dev_id))
        except (TypeError, ValueError):
            continue

    if not normalized_ids:
        return []

    now = datetime.now().replace(tzinfo=None)

    async with async_session_factory() as session:
        updated_ids: List[str] = []

        # History rows are written straight from `devices` with an INSERT ...
        # SELECT, so the per-device `status_before` is captured in SQL and
        # hundreds of thousands of rows never round-trip through Python. The
        # SELECT runs before the UPDATE below, so it still sees the pre-move
        # status for each device in the batch.
        history_sql = """INSERT INTO device_history (
            device_id, action, distribution_id, from_user_id, from_user_name,
            to_user_id, to_user_name, status_before, status_after,
            location, notes, performed_by, performed_by_name, timestamp
        )
        SELECT id, :action, :distribution_id, :from_user_id, :from_user_name,
            :to_user_id, :to_user_name, status AS status_before, :status_after,
            :location, :notes, :performed_by, :performed_by_name, :ts
        FROM devices WHERE id IN ({ph})"""

        stock_update_sql = """
            UPDATE devices
            SET current_holder_id = :holder_id, current_holder_name = :holder_name,
                current_holder_type = :holder_type, current_location = :location,
                status = :status, updated_at = :now
            WHERE id IN ({ph})"""

        for batch in chunks(normalized_ids, _BULK_CHUNK_SIZE):
            ph = ",".join([f":d_{i}" for i in range(len(batch))])
            params = {f"d_{i}": did for i, did in enumerate(batch)}

            rows = (await session.execute(
                text(f"SELECT id, status FROM devices WHERE id IN ({ph})"),
                params
            )).mappings().all()
            status_map = {str(r["id"]): r["status"] for r in rows if r["id"] is not None}
            if not status_map:
                continue

            existing_ids = [int(dev_id) for dev_id in status_map.keys()]

            hph = ",".join([f":h_{i}" for i in range(len(existing_ids))])
            history_params = {
                "action": action,
                "distribution_id": distribution_id,
                "from_user_id": from_user_id,
                "from_user_name": from_user_name,
                "to_user_id": holder_id,
                "to_user_name": holder_name,
                "status_after": status,
                "location": location,
                "notes": notes,
                "performed_by": performed_by,
                "performed_by_name": performed_by_name,
                "ts": now,
            }
            history_params.update({f"h_{i}": eid for i, eid in enumerate(existing_ids)})
            await session.execute(
                text(history_sql.format(ph=",".join(f":h_{i}" for i in range(len(existing_ids))))),
                history_params
            )

            eph = ",".join([f":e_{i}" for i in range(len(existing_ids))])
            update_params = {
                "holder_id": holder_id,
                "holder_name": holder_name,
                "holder_type": holder_type,
                "location": location,
                "status": status,
                "now": now,
            }
            update_params.update({f"e_{i}": eid for i, eid in enumerate(existing_ids)})
            await session.execute(
                text(stock_update_sql.format(ph=eph)),
                update_params
            )

            updated_ids.extend(str(dev_id) for dev_id in existing_ids)

        await bump_cache_version(session)
        await session.commit()
        return updated_ids


async def _clear_distribution_device_locks(
    session, device_ids: List[Any], now: datetime, distribution_code: Optional[str] = None
) -> None:
    """Chunked clear of `devices.current_distribution_id` for confirmed devices.

    Operates in bounded batches so a large bulk distribution never builds a
    single `IN` clause over the whole device list. When `distribution_code` is
    given, only devices still carrying that lock are cleared.
    """
    if not device_ids:
        return
    for batch in chunks(device_ids, _BULK_CHUNK_SIZE):
        int_ids = []
        for dev_id in batch:
            try:
                int_ids.append(int(dev_id))
            except (TypeError, ValueError):
                continue
        if not int_ids:
            continue
        uph = ",".join([f":r_{i}" for i in range(len(int_ids))])
        rparams = {f"r_{i}": did for i, did in enumerate(int_ids)}
        rparams["now"] = now
        if distribution_code:
            rparams["dist_code"] = distribution_code
            await session.execute(
                text(f"""UPDATE devices
                    SET current_distribution_id = NULL, updated_at = :now
                    WHERE id IN ({uph}) AND current_distribution_id = :dist_code"""),
                rparams
            )
        else:
            await session.execute(
                text(f"""UPDATE devices
                    SET current_distribution_id = NULL, updated_at = :now
                    WHERE id IN ({uph})"""),
                rparams
            )


async def _get_distribution_scope_user_ids(session, user: Dict[str, Any]) -> Optional[Set[int]]:
    role = str(user.get("role") or "")
    user_id = int(user.get("id") or user.get("_id") or 0)
    parent_id = int(user.get("parent_id") or 0)

    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        return None

    scope_root = parent_id if role in ("sub_distribution_manager", "sub_distribution_employee") and parent_id else user_id
    scoped_ids: Set[int] = {scope_root}
    if scope_root:
        desc_rows = (await session.execute(
            text("""
                WITH RECURSIVE descendants AS (
                    SELECT id FROM users WHERE parent_id = :root
                    UNION ALL
                    SELECT u.id FROM users u
                    INNER JOIN descendants d ON u.parent_id = d.id
                )
                SELECT id FROM descendants
            """),
            {"root": scope_root}
        )).scalars().all()
        scoped_ids.update(did for did in desc_rows if did)
    return scoped_ids


async def _user_can_access_distribution(
    user: Dict[str, Any], from_user_id: Any, to_user_id: Any
) -> bool:
    """Grant access to a distribution's device details.

    Management/PDIC roles may always view it. Everyone else may only view a
    distribution they are a direct party to. The sole exception is sub-distribution
    branch staff (employee / sub-distribution manager) who supervise the recipient,
    so they can see deliveries made into their assigned sub-distribution without
    widening access for any other role.
    """
    role = str(user.get("role", "")).lower()
    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        return True
    try:
        user_id = int(user.get("id", user.get("_id", 0)))
    except (TypeError, ValueError):
        user_id = None
    try:
        from_id = int(from_user_id)
    except (TypeError, ValueError):
        from_id = None
    try:
        to_id = int(to_user_id)
    except (TypeError, ValueError):
        to_id = None
    if (user_id is not None) and ((from_id == user_id) or (to_id == user_id)):
        return True
    if role not in ["sub_distribution_employee", "sub_distribution_manager"]:
        return False
    async with async_session_factory() as session:
        scope_ids = await _get_distribution_scope_user_ids(session, user)
    if scope_ids is None:
        return True
    return (from_id is not None and from_id in scope_ids) or (to_id is not None and to_id in scope_ids)


async def user_can_view_distribution(user: Dict[str, Any], distribution: Dict[str, Any]) -> bool:
    """Whether ``user`` may view the given distribution by ID.

    Mirrors the scoped distribution list: management/PDIC roles see all
    distributions; everyone else may only view distributions where the sender
    or recipient falls within their sub-distribution scope.
    """
    role = str(user.get("role") or "")
    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        return True

    async with async_session_factory() as session:
        scope_ids = await _get_distribution_scope_user_ids(session, user)
    if scope_ids is None:
        return True

    try:
        from_id = int(distribution.get("from_user_id"))
    except (TypeError, ValueError):
        from_id = None
    try:
        to_id = int(distribution.get("to_user_id"))
    except (TypeError, ValueError):
        to_id = None

    return (from_id is not None and from_id in scope_ids) or (to_id is not None and to_id in scope_ids)


async def _branch_staff_ids(
    session, user_id: int, exclude: Optional[set] = None
) -> List[int]:
    """Return the ids of a sub-distribution's staff (sub-distribution managers +
    sub-distribution employees) that supervise the branch ``user_id`` belongs to.

    Used to keep branch staff informed when devices are delivered into their
    assigned sub-distribution.
    """
    exclude = set(exclude or {})
    branch_root = int(user_id)
    seen: set = set()
    while branch_root and branch_root not in seen:
        seen.add(branch_root)
        row = (await session.execute(
            text("SELECT id, role, parent_id FROM users WHERE id = :id"),
            {"id": branch_root}
        )).mappings().first()
        if not row:
            branch_root = 0
            break
        if row["role"] == "sub_distributor":
            break
        nxt = int(row["parent_id"] or 0)
        if nxt == branch_root or nxt <= 0:
            branch_root = 0
            break
        branch_root = nxt

    if not branch_root:
        return []

    scope = {int(branch_root)}
    desc = (await session.execute(text("""
        WITH RECURSIVE descendants AS (
            SELECT id FROM users WHERE parent_id = :root
            UNION ALL
            SELECT u.id FROM users u INNER JOIN descendants d ON u.parent_id = d.id
        )
        SELECT id FROM descendants
    """), {"root": branch_root})).scalars().all()
    scope.update(int(x) for x in desc if x)

    staff_ph = ",".join([f":s_{i}" for i in range(len(scope))])
    staff_params = {f"s_{i}": int(s) for i, s in enumerate(scope)}
    staff_rows = (await session.execute(
        text(f"""SELECT id FROM users
            WHERE role IN ('sub_distribution_manager','sub_distribution_employee')
              AND status = 'active'
              AND parent_id IN ({staff_ph})"""),
        staff_params
    )).mappings().all()
    return [int(r["id"]) for r in staff_rows if int(r["id"]) not in exclude]


async def _load_distribution_device_ids(
    session,
    distribution_codes: List[str],
) -> Dict[str, List[str]]:
    """Return {distribution_code: [device_id, ...]}.

    Membership is derived from two sources (the `distribution_devices` junction
    table was removed in migration 0017):
    - `devices.current_distribution_id` for distributions a device is currently
      locked in (pending_receipt / disputed).
    - `device_history.distribution_id` for historical / completed membership.
    """
    result: Dict[str, Set[str]] = {}
    if not distribution_codes:
        return {}
    ph = ",".join([f":c_{i}" for i in range(len(distribution_codes))])
    params = {f"c_{i}": code for i, code in enumerate(distribution_codes)}

    current_rows = (await session.execute(
        text(f"""SELECT current_distribution_id AS distribution_id, id AS device_id
                 FROM devices WHERE current_distribution_id IN ({ph})"""),
        params
    )).mappings().all()
    for r in current_rows:
        result.setdefault(str(r["distribution_id"]), set()).add(str(r["device_id"]))

    history_rows = (await session.execute(
        text(f"""SELECT distribution_id, device_id
                 FROM device_history WHERE distribution_id IN ({ph})"""),
        params
    )).mappings().all()
    for r in history_rows:
        key = str(r["distribution_id"])
        result.setdefault(key, set()).add(str(r["device_id"]))
    return {key: list(ids) for key, ids in result.items()}


async def get_distributions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    from_user_id: Optional[str] = None,
    to_user_id: Optional[str] = None,
    user_id: Optional[str] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    current_user: Optional[Dict[str, Any]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_device_ids: bool = False,
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        conditions = []
        params: Dict[str, Any] = {}

        if status:
            conditions.append("status = :status")
            params["status"] = status
        if from_user_id:
            conditions.append("from_user_id = :from_user_id")
            params["from_user_id"] = from_user_id
        if to_user_id:
            conditions.append("to_user_id = :to_user_id")
            params["to_user_id"] = to_user_id

        scope_ids = await _get_distribution_scope_user_ids(session, current_user) if current_user else None
        if scope_ids is not None:
            if not scope_ids:
                return {"data": [], "pagination": get_pagination(page, page_size, 0)}
            scope_list = sorted(scope_ids)
            ph1 = ",".join([f":sf_{i}" for i in range(len(scope_list))])
            ph2 = ",".join([f":st_{i}" for i in range(len(scope_list))])
            conditions.append(f"(from_user_id IN ({ph1}) OR to_user_id IN ({ph2}))")
            for i, sid in enumerate(scope_list):
                params[f"sf_{i}"] = sid
                params[f"st_{i}"] = sid
        elif user_id:
            conditions.append("(from_user_id = :uid1 OR to_user_id = :uid2)")
            params["uid1"] = user_id
            params["uid2"] = user_id
        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date
        if search:
            like = f"%{search}%"
            search_field_map = {
                "distribution_id": "distribution_id",
                "from_user_name": "from_user_name",
                "to_user_name": "to_user_name",
                "status": "status",
                "confirmed_by_name": "confirmed_by_name",
            }
            identity_user_columns = ["distributions.from_user_id", "distributions.to_user_id"]
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by in {"digital_id", "broadband_id"}:
                clause, iparams = build_identity_search_clause(
                    identity_user_columns, like, fields=[normalized_search_by]
                )
                conditions.append(clause)
                params.update(iparams)
            elif normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE :search_like")
                params["search_like"] = like
            else:
                id_clause, iparams = build_identity_search_clause(identity_user_columns, like)
                conditions.append("(distribution_id LIKE :sl1 OR from_user_name LIKE :sl2 OR to_user_name LIKE :sl3 OR status LIKE :sl4 OR confirmed_by_name LIKE :sl5 OR " + id_clause + ")")
                for i in range(5):
                    params[f"sl{i+1}"] = like
                params.update(iparams)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        total = (await session.execute(
            text(f"SELECT COUNT(*) FROM distributions WHERE {where_clause}"), params
        )).scalar() or 0

        offset = (page - 1) * page_size
        params["_limit"] = page_size
        params["_offset"] = offset
        rows = (await session.execute(
            text(f"SELECT * FROM distributions WHERE {where_clause} ORDER BY created_at DESC LIMIT :_limit OFFSET :_offset"),
            params
        )).mappings().all()

        device_map = {}
        if include_device_ids:
            device_map = await _load_distribution_device_ids(
                session, [str(r["distribution_id"]) for r in rows]
            )

        result = []
        for r in rows:
            d = dict(r)
            if include_device_ids:
                d["device_ids"] = device_map.get(str(d["distribution_id"]), [])
            else:
                d["device_ids"] = []
            result.append(d)

        return {
            "data": result,
            "pagination": get_pagination(page, page_size, total)
        }


async def _attach_device_ids(session, distribution: Dict[str, Any]) -> Dict[str, Any]:
    device_map = await _load_distribution_device_ids(
        session, [str(distribution.get("distribution_id"))]
    )
    distribution["device_ids"] = device_map.get(str(distribution.get("distribution_id")), [])
    return distribution


async def get_distribution_by_id(distribution_id: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        row = (await session.execute(
            text("SELECT * FROM distributions WHERE id = :id"), {"id": int(distribution_id)}
        )).mappings().first()
        if not row:
            return None
        return await _attach_device_ids(session, dict(row))


async def get_distribution_by_code(distribution_code: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        row = (await session.execute(
            text("SELECT * FROM distributions WHERE distribution_id = :code"),
            {"code": str(distribution_code)}
        )).mappings().first()
        if not row:
            return None
        return await _attach_device_ids(session, dict(row))


async def _resolve_sub_distribution_root_id(session, user: Dict[str, Any]) -> Optional[int]:
    """Walk up the parent chain to find the enclosing sub_distributor id."""
    current = user
    for _ in range(20):
        role = str(current.get("role") or "").lower()
        if role == "sub_distributor":
            return int(current["id"])
        parent_id = current.get("parent_id")
        if not parent_id:
            return None
        row = (await session.execute(
            text("SELECT * FROM users WHERE id = :id"), {"id": int(parent_id)}
        )).mappings().first()
        if not row:
            return None
        current = dict(row)
    return None


async def _load_and_validate_recipient(
    session, dist_data: DistributionCreate, from_user: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate the recipient exists and the actor is allowed to distribute to
    them. Returns the recipient user row as a dict."""
    to_user = (await session.execute(
        text("SELECT * FROM users WHERE id = :id"), {"id": int(dist_data.to_user_id)}
    )).mappings().first()
    if not to_user:
        raise ValueError("Recipient user not found")
    to_user = dict(to_user)

    from_role = from_user["role"]
    to_role = to_user["role"]
    from_user_id = int(from_user.get("id", from_user.get("_id", 0)))

    if from_role in {"super_admin", "manager", "pdic_staff"}:
        if to_role not in {"sub_distributor", "cluster", "operator"}:
            raise ValueError("Management can only distribute to sub-distributors, clusters, or operators")

    if from_role == "sub_distribution_manager":
        if to_role == "cluster":
            if int(to_user.get("parent_id", 0)) != from_user_id:
                raise ValueError("You can only distribute to clusters directly under your account")
        elif to_role == "operator":
            parent_cluster = (await session.execute(
                text("SELECT * FROM users WHERE id = :id"), {"id": int(to_user.get("parent_id") or 0)}
            )).mappings().first()
            if not parent_cluster:
                raise ValueError("Operator's cluster not found")
            parent_cluster = dict(parent_cluster)
            if int(parent_cluster.get("parent_id", 0)) != from_user_id:
                raise ValueError("You can only distribute to operators within your sub-distribution manager chain")
        else:
            raise ValueError("Sub distribution managers can only distribute to clusters or operators")

    elif from_role == "sub_distributor":
        if to_role == "cluster":
            if int(to_user.get("parent_id", 0)) != from_user_id:
                raise ValueError("You can only distribute to clusters directly under your account")
        elif to_role == "operator":
            parent_cluster = (await session.execute(
                text("SELECT * FROM users WHERE id = :id"), {"id": int(to_user.get("parent_id") or 0)}
            )).mappings().first()
            if not parent_cluster:
                raise ValueError("Operator's cluster not found")
            parent_cluster = dict(parent_cluster)
            if int(parent_cluster.get("parent_id", 0)) != from_user_id:
                raise ValueError("You can only distribute to operators within your sub-distribution")
        else:
            raise ValueError("Sub-distributors can only distribute to clusters or operators")

    elif from_role == "sub_distribution_employee":
        emp_row = (await session.execute(
            text("SELECT parent_id FROM users WHERE id = :id"), {"id": from_user_id}
        )).mappings().first()
        branch_id = int((dict(emp_row) if emp_row else {}).get("parent_id") or 0)
        if not branch_id:
            branch_id = int(from_user.get("parent_id") or 0)
        if to_role == "cluster":
            if branch_id and int(to_user.get("parent_id", 0)) != branch_id:
                raise ValueError("You can only distribute to clusters directly under your sub distribution")
            if not branch_id and int(to_user.get("parent_id", 0)) != from_user_id:
                raise ValueError("You can only distribute to clusters directly under your sub distribution")
        elif to_role == "operator":
            parent_cluster = (await session.execute(
                text("SELECT * FROM users WHERE id = :id"), {"id": int(to_user.get("parent_id") or 0)}
            )).mappings().first()
            if not parent_cluster:
                raise ValueError("Operator's cluster not found")
            parent_cluster = dict(parent_cluster)
            owner_id = branch_id if branch_id else from_user_id
            if int(parent_cluster.get("parent_id", 0)) != owner_id:
                raise ValueError("You can only distribute to operators within your sub distribution")
        else:
            raise ValueError("Sub distribution employees can only distribute to clusters or operators")

    elif from_role == "cluster":
        if to_role == "operator":
            if int(to_user.get("parent_id", 0)) != from_user_id:
                raise ValueError("You can only distribute to operators directly under your cluster")
        else:
            raise ValueError("Clusters can only distribute to operators")

    elif from_role == "operator":
        if to_role == "operator":
            if int(dist_data.to_user_id) == from_user_id:
                raise ValueError("You cannot distribute to yourself")
            from_root = await _resolve_sub_distribution_root_id(session, from_user)
            to_root = await _resolve_sub_distribution_root_id(session, to_user)
            if not from_root or from_root != to_root:
                raise ValueError("You can only distribute to operators within your sub-distribution")
        else:
            raise ValueError("Operators can only distribute to other operators within their sub-distribution")

    return to_user


async def _insert_distribution_record(
    session,
    dist_data: DistributionCreate,
    from_user: Dict[str, Any],
    to_user: Dict[str, Any],
    validated_devices: List[Dict[str, Any]],
) -> tuple[str, int, Optional[str]]:
    """Insert the distribution row, link the devices, and write the manifest.

    Returns ``(distribution_id, numeric_row_id, manifest_file)``. The manifest
    file is written inside the transaction; the caller must delete it if the
    transaction rolls back so no orphan file is left behind.
    """
    role_to_type = {
        "super_admin": "noc", "manager": "noc", "pdic_staff": "pdic_staff",
        "sub_distribution_manager": "sub_distribution_manager",
        "sub_distributor": "sub_distributor", "sub_distribution_employee": "sub_distributor",
        "cluster": "cluster", "operator": "operator"
    }

    now_dt = datetime.now().replace(tzinfo=None)
    now = now_dt
    today = now_dt.date()
    distribution_date = dist_data.date_of_distribution if dist_data.date_of_distribution else today
    dist_id = generate_distribution_id()

    from_user_id = int(from_user.get("id", from_user.get("_id", 0)))

    result = await session.execute(
        text("""INSERT INTO distributions (distribution_id, device_count,
            from_user_id, from_user_name, from_user_type, to_user_id, to_user_name, to_user_type,
            status, request_date, date_of_distribution,
            notes, created_by, created_at, updated_at)
        VALUES (:dist_id, :device_count, :from_user_id, :from_user_name, :from_user_type,
            :to_user_id, :to_user_name, :to_user_type, :status, :request_date, :date_of_distribution,
            :notes, :created_by, :created_at, :updated_at)"""),
        {
            "dist_id": dist_id,
            "device_count": len(dist_data.device_ids),
            "from_user_id": from_user_id,
            "from_user_name": from_user["name"],
            "from_user_type": role_to_type.get(from_user["role"], "noc"),
            "to_user_id": int(to_user["id"]),
            "to_user_name": to_user["name"],
            "to_user_type": role_to_type.get(to_user["role"], "pdic_staff"),
            "status": DistributionStatus.PENDING_RECEIPT.value,
            "request_date": now,
            "date_of_distribution": distribution_date,
            "notes": dist_data.notes,
            "created_by": from_user_id,
            "created_at": now,
            "updated_at": now,
        }
    )
    new_id = result.lastrowid

    dd_rows = [{"dist_id": dist_id, "device_id": int(dev_id), "now": now} for dev_id in dist_data.device_ids]
    if dd_rows:
        for batch in chunks(dd_rows, 1000):
            uph = ",".join([f":u_{i}" for i in range(len(batch))])
            uparams = {f"u_{i}": int(row["device_id"]) for i, row in enumerate(batch)}
            uparams["dist_id"] = dist_id
            uparams["now"] = now
            await session.execute(
                text(f"""UPDATE devices
                    SET current_distribution_id = :dist_id, updated_at = :now
                    WHERE id IN ({uph})"""),
                uparams
            )

    manifest_file: Optional[str] = None
    try:
        manifest_file = _build_distribution_manifest(
            distribution_id=dist_id,
            devices=validated_devices,
            from_user_name=from_user.get("name", "Unknown"),
            to_user_name=to_user.get("name", "Unknown"),
            created_at_iso=now,
        )
        await session.execute(
            text("UPDATE distributions SET manifest_file = :mf WHERE id = :id"),
            {"mf": manifest_file, "id": int(new_id)}
        )
    except Exception:
        pass

    return dist_id, new_id, manifest_file


def _remove_manifest_file(manifest_file: Optional[str]) -> None:
    """Delete a manifest written during a distribution transaction that rolled back."""
    if not manifest_file:
        return
    try:
        (_distribution_manifest_dir() / str(manifest_file)).unlink(missing_ok=True)
    except Exception:
        logger.exception("Failed to clean up orphan manifest file %s", manifest_file)


async def _notify_recipient(
    dist_id: str, to_user: Dict[str, Any], from_user: Dict[str, Any], device_count: int
) -> None:
    sender_label = _sender_display_name(from_user)
    await notification_service.create_notification(
        user_id=str(to_user["id"]),
        title="Action Required: Confirm Device Receipt",
        message=f"{device_count} device(s) have been sent to you by {sender_label}. "
            f"An Excel manifest is available in Delivery Confirmations. "
            f"Please confirm receipt on your Delivery Confirmations page (Distribution ID: {dist_id}).",
        notification_type="warning", category="distribution",
        link="/delivery-confirmations"
    )

    # Also notify the sub-distribution branch staff (employees / managers) who
    # supervise the recipient, so deliveries into an assigned sub-distribution
    # are not missed when only the named recipient is pinged. This is limited to
    # deliveries addressed to a sub-distributor so no other distribution flow
    # (sub-distributor -> cluster/operator, etc.) gains new notifications.
    if str(to_user.get("role", "")).lower() == "sub_distributor":
        from_user_id = int(from_user.get("id", from_user.get("_id", 0)) or 0)
        async with async_session_factory() as session:
            staff_ids = await _branch_staff_ids(
                session, int(to_user["id"]), exclude={int(to_user["id"]), int(from_user_id) if from_user_id else -1}
            )
        if staff_ids:
            await notification_service.bulk_create_notifications([
                {
                    "user_id": str(sid),
                    "title": "Devices Sent to Your Sub Distribution",
                    "message": f"{device_count} device(s) have been sent by {sender_label} into your "
                        f"assigned sub distribution (Distribution ID: {dist_id}). Please confirm receipt "
                        f"on your Delivery Confirmations page.",
                    "notification_type": "warning",
                    "category": "distribution",
                    "link": "/delivery-confirmations",
                }
                for sid in staff_ids
            ])


async def create_distribution_from_identifiers(
    to_user_id: str,
    identifier_rows: List[Dict[str, Any]],
    from_user: Dict[str, Any],
    notes: Optional[str] = None,
    date_of_distribution: Optional[date] = None,
) -> Dict[str, Any]:
    """Create a distribution from uploaded rows containing MAC, serial number, and/or NUID.

    If any row fails validation, distribution is not created and row-level errors are returned.
    """
    errors: List[Dict[str, Any]] = []
    resolved_device_ids: List[str] = []
    resolved_devices: List[Dict[str, Any]] = []
    resolved_row_info: Dict[str, Dict[str, Any]] = {}
    seen_device_ids = set()

    all_macs: List[str] = []
    all_serials: List[str] = []
    all_nuids: List[str] = []
    row_lookup: List[Dict[str, Any]] = []

    for row in identifier_rows:
        mac_address = str(row.get("mac_address") or "").strip()
        serial_number = str(row.get("serial_number") or "").strip()
        nuid = str(row.get("nuid") or "").strip()

        if not mac_address and not serial_number and not nuid:
            errors.append({
                "row": int(row.get("row") or 0),
                "identifier": "",
                "error": "Provide at least one identifier: mac_address, serial_number, or nuid",
            })
            continue

        if mac_address:
            all_macs.append(mac_address.lower())
        if serial_number:
            all_serials.append(serial_number.lower())
        if nuid:
            all_nuids.append(nuid.lower())

        row_lookup.append({
            "row": int(row.get("row") or 0),
            "mac_address": mac_address,
            "serial_number": serial_number,
            "nuid": nuid,
        })

    async with async_session_factory() as session:
        mac_map: Dict[str, Any] = {}
        serial_map: Dict[str, Any] = {}
        nuid_map: Dict[str, Any] = {}

        all_macs = list(set(all_macs))
        all_serials = list(set(all_serials))
        all_nuids = list(set(all_nuids))

        for batch in chunks(all_macs, 1000):
            ph = ",".join([f":mac_{i}" for i in range(len(batch))])
            params = {f"mac_{i}": m for i, m in enumerate(batch)}
            rows = (await session.execute(
                text(f"SELECT * FROM devices WHERE lower(trim(mac_address)) IN ({ph})"),
                params
            )).mappings().all()
            for dev in rows:
                mac_map[dev["mac_address"].strip().lower()] = dict(dev)

        for batch in chunks(all_serials, 1000):
            ph = ",".join([f":ser_{i}" for i in range(len(batch))])
            params = {f"ser_{i}": s for i, s in enumerate(batch)}
            rows = (await session.execute(
                text(f"SELECT * FROM devices WHERE lower(trim(serial_number)) IN ({ph})"),
                params
            )).mappings().all()
            for dev in rows:
                serial_map[dev["serial_number"].strip().lower()] = dict(dev)

        for batch in chunks(all_nuids, 1000):
            ph = ",".join([f":nuid_{i}" for i in range(len(batch))])
            params = {f"nuid_{i}": n for i, n in enumerate(batch)}
            rows = (await session.execute(
                text(f"SELECT * FROM devices WHERE lower(trim(nuid)) IN ({ph})"),
                params
            )).mappings().all()
            for dev in rows:
                nuid_map[dev["nuid"].strip().lower()] = dict(dev)

        from_role = str(from_user.get("role") or "").lower()
        from_user_id = int(from_user.get("id") or from_user.get("_id") or 0)

        # Devices currently locked in an unconfirmed / disputed distribution.
        open_lock_rows = (await session.execute(
            text("""SELECT d.id AS device_id
                    FROM devices d
                    INNER JOIN distributions dist ON d.current_distribution_id = dist.distribution_id
                    WHERE dist.status IN (:s1, :s2)"""),
            {"s1": DistributionStatus.PENDING_RECEIPT.value, "s2": DistributionStatus.DISPUTED.value}
        )).mappings().all()
        open_lock_device_ids = {str(r["device_id"]) for r in open_lock_rows}

        # For non-management uploaders, block devices awaiting their receipt confirmation.
        pending_blocked: Set[str] = set()
        if from_role not in ["super_admin", "manager", "pdic_staff"]:
            blocked_rows = (await session.execute(
                text("""SELECT d.id AS device_id
                        FROM devices d
                        INNER JOIN distributions dist ON d.current_distribution_id = dist.distribution_id
                        WHERE dist.to_user_id = :uid AND dist.status = :status"""),
                {"uid": from_user_id, "status": DistributionStatus.PENDING_RECEIPT.value}
            )).mappings().all()
            pending_blocked = {str(r["device_id"]) for r in blocked_rows}

        for item in row_lookup:
            row_number = item["row"]
            mac_address = item["mac_address"]
            serial_number = item["serial_number"]
            nuid = item["nuid"]

            device_by_mac = mac_map.get(mac_address.lower()) if mac_address else None
            device_by_serial = serial_map.get(serial_number.lower()) if serial_number else None
            device_by_nuid = nuid_map.get(nuid.lower()) if nuid else None

            resolved_candidates = [d for d in [device_by_mac, device_by_serial, device_by_nuid] if d]
            if resolved_candidates:
                first_id = str(resolved_candidates[0].get("id"))
                if any(str(d.get("id")) != first_id for d in resolved_candidates[1:]):
                    parts = []
                    if mac_address:
                        parts.append(f"MAC={mac_address}")
                    if serial_number:
                        parts.append(f"SERIAL={serial_number}")
                    if nuid:
                        parts.append(f"NUID={nuid}")
                    errors.append({
                        "row": row_number,
                        "identifier": ", ".join(parts),
                        "error": "Provided identifiers map to different devices",
                    })
                    continue

            resolved_device = device_by_mac or device_by_serial or device_by_nuid

            if not resolved_device:
                identifier_value = mac_address or serial_number or nuid
                if mac_address:
                    identifier_label = "mac_address"
                elif serial_number:
                    identifier_label = "serial_number"
                else:
                    identifier_label = "nuid"
                errors.append({
                    "row": row_number,
                    "identifier": f"{identifier_label}={identifier_value}",
                    "error": "Device not registered",
                })
                continue

            resolved_id = str(resolved_device.get("id") or resolved_device.get("_id") or "")
            if not resolved_id:
                errors.append({
                    "row": row_number,
                    "identifier": mac_address or nuid,
                    "error": "Resolved device is missing an id",
                })
                continue

            if resolved_id in seen_device_ids:
                duplicate_identifier = mac_address or serial_number or nuid
                errors.append({
                    "row": row_number,
                    "identifier": duplicate_identifier,
                    "error": "Duplicate device in upload",
                })
                continue

            device_status = str(resolved_device.get("status") or "")
            device_display_id = str(resolved_device.get("device_id") or "")
            identifier_value = mac_address or serial_number or nuid

            if device_status == DeviceStatus.DEFECTIVE.value:
                errors.append({
                    "row": row_number,
                    "identifier": identifier_value,
                    "error": f"Device {device_display_id} is marked defective and cannot be transferred",
                })
                continue
            if resolved_id in open_lock_device_ids:
                errors.append({
                    "row": row_number,
                    "identifier": identifier_value,
                    "error": f"Device {device_display_id} is already in an unconfirmed or disputed distribution",
                })
                continue
            if from_role in ["super_admin", "manager", "pdic_staff"]:
                if device_status != DeviceStatus.AVAILABLE.value:
                    errors.append({
                        "row": row_number,
                        "identifier": identifier_value,
                        "error": f"Device {device_display_id} is not available",
                    })
                    continue
            else:
                if from_role == "sub_distribution_employee":
                    emp_row = (await session.execute(
                        text("SELECT parent_id FROM users WHERE id = :id"), {"id": from_user_id}
                    )).mappings().first()
                    branch_id = int((dict(emp_row) if emp_row else {}).get("parent_id") or from_user.get("parent_id") or 0)
                    allowed_holder_ids = {from_user_id, branch_id} if branch_id else {from_user_id}
                else:
                    allowed_holder_ids = {from_user_id}
                if int(resolved_device.get("current_holder_id") or 0) not in allowed_holder_ids:
                    errors.append({
                        "row": row_number,
                        "identifier": identifier_value,
                        "error": f"Device {device_display_id} is not in your possession",
                    })
                    continue
                if resolved_id in pending_blocked:
                    errors.append({
                        "row": row_number,
                        "identifier": identifier_value,
                        "error": (
                            f"Device {device_display_id} is awaiting your receipt confirmation. "
                            "Confirm receipt before redistributing."
                        ),
                    })
                    continue

            seen_device_ids.add(resolved_id)
            resolved_device_ids.append(resolved_id)
            resolved_devices.append(resolved_device)
            resolved_row_info[resolved_id] = {
                "row": row_number,
                "identifier": identifier_value,
                "device_id": device_display_id,
            }

        if not resolved_device_ids:
            data = build_bulk_result([], [], errors, total=len(identifier_rows))
            data.update({
                "created": False,
                "distribution": None,
                "created_count": 0,
                "total_rows": len(identifier_rows),
                "valid_count": 0,
            })
            return data

        # Lock the resolved device rows and re-check distribution state while
        # they are locked. The identifier lookups and validation above used
        # consistent (non-locking) reads, so between resolution and insert a
        # concurrent request could have claimed one of these devices. Locking
        # reads serialize concurrent creates on the same devices and always see
        # the latest committed state, so a device claimed in the meantime is
        # excluded here instead of being allocated to two distributions.
        locked_devices, locked_open_ids = await _lock_devices_and_recheck_open_locks(
            session, resolved_device_ids
        )

        recheck_errors: List[Dict[str, Any]] = []
        keep_devices: List[Dict[str, Any]] = []
        keep_device_ids: List[str] = []
        if from_role not in ["super_admin", "manager", "pdic_staff"]:
            if from_role == "sub_distribution_employee":
                emp_row = (await session.execute(
                    text("SELECT parent_id FROM users WHERE id = :id"), {"id": from_user_id}
                )).mappings().first()
                branch_id = int((dict(emp_row) if emp_row else {}).get("parent_id") or from_user.get("parent_id") or 0)
                allowed_holder_ids = {from_user_id, branch_id} if branch_id else {from_user_id}
            else:
                allowed_holder_ids = {from_user_id}

        for resolved_id, resolved_device in zip(resolved_device_ids, resolved_devices):
            row_info = resolved_row_info.get(resolved_id, {})
            row_number = row_info.get("row", 0)
            identifier_value = row_info.get("identifier", "")
            device_display_id = row_info.get("device_id", "")
            locked = locked_devices.get(resolved_id)
            if not locked:
                recheck_errors.append({
                    "row": row_number,
                    "identifier": identifier_value,
                    "error": f"Device {device_display_id} was not found",
                })
                continue
            if resolved_id in locked_open_ids:
                recheck_errors.append({
                    "row": row_number,
                    "identifier": identifier_value,
                    "error": f"Device {device_display_id} is already in an unconfirmed or disputed distribution",
                })
                continue
            device_status = str(locked.get("status") or "")
            if device_status == DeviceStatus.DEFECTIVE.value:
                recheck_errors.append({
                    "row": row_number,
                    "identifier": identifier_value,
                    "error": f"Device {device_display_id} is marked defective and cannot be transferred",
                })
                continue
            if from_role in ["super_admin", "manager", "pdic_staff"]:
                if device_status != DeviceStatus.AVAILABLE.value:
                    recheck_errors.append({
                        "row": row_number,
                        "identifier": identifier_value,
                        "error": f"Device {device_display_id} is not available",
                    })
                    continue
            else:
                if int(locked.get("current_holder_id") or 0) not in allowed_holder_ids:
                    recheck_errors.append({
                        "row": row_number,
                        "identifier": identifier_value,
                        "error": f"Device {device_display_id} is not in your possession",
                    })
                    continue
                if resolved_id in pending_blocked:
                    recheck_errors.append({
                        "row": row_number,
                        "identifier": identifier_value,
                        "error": (
                            f"Device {device_display_id} is awaiting your receipt confirmation. "
                            "Confirm receipt before redistributing."
                        ),
                    })
                    continue
            keep_devices.append(locked)
            keep_device_ids.append(resolved_id)

        if recheck_errors:
            errors.extend(recheck_errors)

        resolved_device_ids = keep_device_ids
        resolved_devices = keep_devices

        if not resolved_device_ids:
            data = build_bulk_result([], [], errors, total=len(identifier_rows))
            data.update({
                "created": False,
                "distribution": None,
                "created_count": 0,
                "total_rows": len(identifier_rows),
                "valid_count": 0,
            })
            return data

        dist_data = DistributionCreate(
            to_user_id=str(to_user_id),
            device_ids=resolved_device_ids,
            notes=notes,
            date_of_distribution=date_of_distribution,
        )

        # Recipient + role validation and the insert run in the SAME transaction
        # as the identifier resolution, so the devices cannot change between
        # validation and commit and the validation pass is never duplicated.
        to_user = await _load_and_validate_recipient(session, dist_data, from_user)
        dist_id, new_id, manifest_file = await _insert_distribution_record(
            session, dist_data, from_user, to_user, resolved_devices
        )
        try:
            await bump_cache_version(session)
            await session.commit()
        except Exception:
            await session.rollback()
            _remove_manifest_file(manifest_file)
            raise

    await _notify_recipient(dist_id, to_user, from_user, len(resolved_device_ids))

    distribution = await get_distribution_by_id(new_id)
    if not distribution:
        distribution = await get_distribution_by_code(dist_id)

    data = build_bulk_result([], [], errors, total=len(identifier_rows))
    data["created_count"] = len(resolved_device_ids)
    data.update({
        "created": True,
        "distribution": distribution,
        "total_rows": len(identifier_rows),
        "valid_count": len(resolved_device_ids),
    })
    return data


async def _lock_devices_and_recheck_open_locks(
    session, device_ids: List[str]
) -> tuple[Dict[str, Dict[str, Any]], Set[str]]:
    """Lock the given device rows and re-check the active-distribution lock.

    Both statements are locking reads, which serialize concurrent distribution
    creates on the same devices and always see the latest committed state (unlike
    the transaction's earlier consistent reads). The re-check uses ``FOR UPDATE
    OF d`` so it locks only the device rows already held, introducing no new lock
    ordering or deadlock vector.

    Returns ``(device_rows_by_id, open_lock_device_ids)``; the second set holds
    the device ids currently linked to an unconfirmed or disputed distribution.
    """
    device_rows: Dict[str, Dict[str, Any]] = {}
    device_ids_int: List[int] = []
    for dev_id in device_ids:
        try:
            device_ids_int.append(int(dev_id))
        except (TypeError, ValueError):
            continue
    device_ids_int.sort()

    for batch in chunks(device_ids_int, 1000):
        dph = ",".join([f":d_{i}" for i in range(len(batch))])
        dparams = {f"d_{i}": did for i, did in enumerate(batch)}
        dev_rows = (await session.execute(
            text(f"SELECT * FROM devices WHERE id IN ({dph}) FOR UPDATE"), dparams
        )).mappings().all()
        for r in dev_rows:
            device_rows[str(r["id"])] = dict(r)

    open_lock_device_ids: Set[str] = set()
    for batch in chunks(device_ids_int, 1000):
        lph = ",".join([f":l_{i}" for i in range(len(batch))])
        lparams = {f"l_{i}": did for i, did in enumerate(batch)}
        lparams["s1"] = DistributionStatus.PENDING_RECEIPT.value
        lparams["s2"] = DistributionStatus.DISPUTED.value
        lock_rows = (await session.execute(
            text(f"""SELECT d.id AS device_id
                FROM devices d
                INNER JOIN distributions dist ON d.current_distribution_id = dist.distribution_id
                WHERE dist.status IN (:s1, :s2)
                  AND d.id IN ({lph})
                FOR UPDATE OF d"""),
            lparams
        )).mappings().all()
        for lr in lock_rows:
            open_lock_device_ids.add(str(lr["device_id"]))

    return device_rows, open_lock_device_ids


async def create_distribution(dist_data: DistributionCreate, from_user: Dict[str, Any]) -> Dict[str, Any]:
    async with async_session_factory() as session:
        to_user = await _load_and_validate_recipient(session, dist_data, from_user)

        from_role = from_user["role"]
        from_user_id = int(from_user.get("id", from_user.get("_id", 0)))
        # Sub-distribution employees act for their assigned branch, so they may
        # redistribute devices held either by themselves or by the branch
        # sub-distributor that the branch inventory belongs to.
        if from_role == "sub_distribution_employee":
            emp_row = (await session.execute(
                text("SELECT parent_id FROM users WHERE id = :id"), {"id": from_user_id}
            )).mappings().first()
            branch_id = int((dict(emp_row) if emp_row else {}).get("parent_id") or 0)
            if not branch_id:
                branch_id = int(from_user.get("parent_id") or 0)
            allowed_holder_ids = {from_user_id, branch_id} if branch_id else {from_user_id}
        else:
            allowed_holder_ids = {from_user_id}

        validated_devices: List[Dict[str, Any]] = []
        pending_blocked: set = set()

        if from_role not in ["super_admin", "manager", "pdic_staff"]:
            blocked_rows = (await session.execute(
                text("""SELECT d.id AS device_id
                   FROM devices d
                   INNER JOIN distributions dist ON d.current_distribution_id = dist.distribution_id
                   WHERE dist.to_user_id = :uid AND dist.status = :status"""),
                {"uid": from_user_id, "status": DistributionStatus.PENDING_RECEIPT.value}
            )).mappings().all()
            for r in blocked_rows:
                pending_blocked.add(str(r["device_id"]))

        # Lock the requested device rows and re-check the active-distribution
        # lock while they are locked. Locking reads serialize concurrent creates
        # on the same devices and always read the latest committed state (unlike
        # the transaction's earlier consistent reads), so a device claimed by a
        # concurrent request is detected here instead of double-allocated.
        device_rows, open_lock_device_ids = await _lock_devices_and_recheck_open_locks(
            session, dist_data.device_ids
        )

        for dev_id in dist_data.device_ids:
            device = device_rows.get(str(dev_id))
            if not device:
                raise ValueError(f"Device {dev_id} not found")
            if device.get("status") == DeviceStatus.DEFECTIVE.value:
                raise ValueError(f"Device {device['device_id']} is marked defective and cannot be transferred")
            if str(dev_id) in open_lock_device_ids:
                raise ValueError(f"Device {device['device_id']} is already in an unconfirmed or disputed distribution")
            if from_role in ["super_admin", "manager", "pdic_staff"]:
                if device["status"] != DeviceStatus.AVAILABLE.value:
                    raise ValueError(f"Device {device['device_id']} is not available")
            else:
                if int(device.get("current_holder_id", 0)) not in allowed_holder_ids:
                    raise ValueError(f"Device {device['device_id']} is not in your possession")
                if str(dev_id) in pending_blocked:
                    raise ValueError(
                        f"Device {device['device_id']} is awaiting your receipt confirmation. "
                        f"Please confirm receipt of the incoming transfer before redistributing."
                    )
            validated_devices.append(device)

        dist_id, new_id, manifest_file = await _insert_distribution_record(
            session, dist_data, from_user, to_user, validated_devices
        )

        try:
            await bump_cache_version(session)
            await session.commit()
        except Exception:
            await session.rollback()
            _remove_manifest_file(manifest_file)
            raise

    await _notify_recipient(dist_id, to_user, from_user, len(dist_data.device_ids))

    distribution = await get_distribution_by_id(new_id)
    if not distribution:
        distribution = await get_distribution_by_code(dist_id)
    return distribution


async def update_distribution_status(
    distribution_id: str, status: str, user: Dict[str, Any], notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        return None

    now = datetime.now().replace(tzinfo=None)
    user_id = int(user.get("id", user.get("_id", 0)))
    user_role = str(user.get("role", "")).lower()

    async with async_session_factory() as session:
        update_parts = ["status = :status", "updated_at = :now"]
        params: Dict[str, Any] = {"status": status, "now": now, "id": int(distribution_id)}

        now_date = now.date()
        if status == DistributionStatus.APPROVED.value:
            update_parts.extend(["confirmed_at = :now2", "confirmed_by = :uid", "confirmed_by_name = :uname"])
            params["now2"] = now_date
            params["uid"] = user_id
            params["uname"] = user["name"]

        elif status == DistributionStatus.DELIVERED.value:
            update_parts.append("delivery_date = :now2")
            params["now2"] = now_date

        if notes:
            update_parts.append("notes = :notes")
            params["notes"] = notes

        set_clause = ", ".join(update_parts)
        await session.execute(text(f"UPDATE distributions SET {set_clause} WHERE id = :id"), params)
        await bump_cache_version(session)
        await session.commit()

    await notification_service.create_notification(
        user_id=str(dist["from_user_id"]),
        title=f"Distribution {status.capitalize()}",
        message=f"Distribution {dist['distribution_id']} has been {status}",
        notification_type="success" if status in ["approved", "delivered"] else "warning",
        category="distribution", link=f"/distributions?distributionId={distribution_id}"
    )

    return await get_distribution_by_id(distribution_id)


async def confirm_receipt(
    distribution_id: str, received: bool, user: Dict[str, Any], notes: Optional[str] = None
) -> Dict[str, Any]:
    """Receiver confirms or disputes receipt of a distribution.
    - received=True  → status APPROVED, devices moved to recipient, sender notified
    - received=False → status DISPUTED, all admins/managers + sender notified
    Without confirming, receiver cannot redistribute the devices and devices stay with sender.
    """
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        raise ValueError("Distribution not found")

    user_id = int(user.get("id", user.get("_id", 0)))
    user_role = str(user.get("role") or "").lower()

    recipient_id = int(dist["to_user_id"])
    if recipient_id != user_id:
        # Sub-distribution employees may confirm deliveries addressed to their
        # branch (their parent sub-distributor) on the branch's behalf.
        if user_role == "sub_distribution_employee":
            async with async_session_factory() as session:
                emp = (await session.execute(
                    text("SELECT parent_id FROM users WHERE id = :id"), {"id": user_id}
                )).mappings().first()
            branch_id = int((dict(emp) if emp else {}).get("parent_id") or user.get("parent_id") or 0)
            if recipient_id != branch_id:
                raise ValueError("Only the recipient can confirm receipt of this distribution")
        else:
            raise ValueError("Only the recipient can confirm receipt of this distribution")

    if dist["status"] != DistributionStatus.PENDING_RECEIPT.value:
        raise ValueError("This distribution is not awaiting receipt confirmation")

    device_ids = dist.get("device_ids") or []

    now = datetime.now().replace(tzinfo=None)

    role_to_type = {
        "super_admin": "noc", "manager": "noc", "pdic_staff": "pdic_staff",
        "sub_distribution_manager": "sub_distribution_manager",
        "sub_distributor": "sub_distributor", "sub_distribution_employee": "sub_distributor",
        "cluster": "cluster", "operator": "operator"
    }

    if received:
        async with async_session_factory() as session:
            to_user_row = (await session.execute(
                text("SELECT role FROM users WHERE id = :id"), {"id": int(dist["to_user_id"])}
            )).mappings().first()
            to_user_role = to_user_row["role"] if to_user_row else "operator"

        device_status_for_recipient = (
            DeviceStatus.IN_USE.value if to_user_role == "operator" else DeviceStatus.DISTRIBUTED.value
        )
        holder_type = role_to_type.get(to_user_role, "pdic_staff")
        await _bulk_update_device_holders(
            device_ids=device_ids,
            holder_id=int(dist["to_user_id"]),
            holder_name=dist["to_user_name"],
            holder_type=holder_type,
            location=dist["to_user_name"],
            status=device_status_for_recipient,
            performed_by=user_id,
            performed_by_name=user["name"],
            from_user_id=int(dist["from_user_id"]),
            from_user_name=dist["from_user_name"],
            notes=f"Receipt confirmed for distribution {dist['distribution_id']}",
            # One per-device history row is written for tracking, but the admin
            # activity feed excludes this bulk action so accepting a large
            # delivery shows up as a single activity entry.
            action="bulk_distributed",
            distribution_id=dist["distribution_id"],
        )

        async with async_session_factory() as session:
            await _clear_distribution_device_locks(session, device_ids, now)
            await session.commit()

        async with async_session_factory() as session:
            await session.execute(
                text("""UPDATE distributions
                   SET status = :status, confirmed_at = :today, confirmed_by = :uid, confirmed_by_name = :uname,
                       notes = COALESCE(:notes, notes), updated_at = :now2
                   WHERE id = :id"""),
                {
                    "status": DistributionStatus.APPROVED.value,
                    "today": now.date(),
                    "uid": user_id,
                    "uname": user["name"],
                    "notes": notes,
                    "now2": now,
                    "id": int(distribution_id)
                }
            )
            await bump_cache_version(session)
            await session.commit()

        await notification_service.create_notification(
            user_id=str(dist["from_user_id"]),
            title="Receipt Confirmed",
            message=f"{user['name']} confirmed receipt of {dist['device_count']} device(s) "
                    f"(Distribution: {dist['distribution_id']}).",
            notification_type="success", category="distribution",
            link=f"/distributions?distributionId={distribution_id}"
        )

    else:
        async with async_session_factory() as session:
            await session.execute(
                text("""UPDATE distributions
                   SET status = 'disputed', notes = COALESCE(:notes, notes), updated_at = :now
                   WHERE id = :id"""),
                {"notes": notes, "now": now, "id": int(distribution_id)}
            )
            admin_rows = (await session.execute(
                text("SELECT id FROM users WHERE role IN ('super_admin', 'manager', 'pdic_staff') AND status = 'active'")
            )).mappings().all()
            await bump_cache_version(session)
            await session.commit()

        sender_label = (
            "PDIC" if str(dist.get("from_user_type") or "").lower() in {"noc", "pdic_staff"}
            else dist.get("from_user_name")
        )
        dispute_msg = (
            f"DISPUTE: {user['name']} reported NOT receiving {dist['device_count']} device(s) "
            f"sent by {sender_label}. Distribution: {dist['distribution_id']}."
        )
        await notification_service.bulk_create_notifications([
            {
                "user_id": r["id"],
                "title": "Device Not Received — Dispute",
                "message": dispute_msg,
                "notification_type": "error",
                "category": "distribution",
                "link": f"/distributions?distributionId={distribution_id}"
            }
            for r in admin_rows
        ] + [
            {
                "user_id": dist["from_user_id"],
                "title": "Receipt Disputed",
                "message": f"{user['name']} reported NOT receiving your device(s) in distribution "
                           f"{dist['distribution_id']}. Admin, manager, and PDIC staff have been notified.",
                "notification_type": "error",
                "category": "distribution",
                "link": f"/distributions?distributionId={distribution_id}"
            }
        ])

    dist["status"] = DistributionStatus.APPROVED.value if received else DistributionStatus.DISPUTED.value
    dist["notes"] = notes if notes is not None else dist.get("notes")
    dist["updated_at"] = now
    if received:
        dist["confirmed_at"] = now.date()
        dist["confirmed_by"] = user_id
        dist["confirmed_by_name"] = user["name"]
    return dist


async def confirm_disputed_return(
    distribution_id: str,
    user: Dict[str, Any],
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """PDIC management confirms disputed devices are back with sender and unlocks redistribution."""
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        raise ValueError("Distribution not found")

    if dist["status"] != DistributionStatus.DISPUTED.value:
        raise ValueError("Only disputed distributions can be marked as returned")

    role = str(user.get("role", "")).lower()
    if role not in {"super_admin", "manager", "pdic_staff"}:
        raise ValueError("Only PDIC management can confirm disputed return receipt")

    role_to_type = {
        "super_admin": "noc", "manager": "noc", "pdic_staff": "pdic_staff",
        "sub_distribution_manager": "sub_distribution_manager",
        "sub_distributor": "sub_distributor", "sub_distribution_employee": "sub_distributor",
        "cluster": "cluster", "operator": "operator"
    }

    sender_role = str(dist.get("from_user_type") or "")
    if sender_role == "noc":
        sender_role = "manager"

    sender_status = DeviceStatus.AVAILABLE.value if sender_role in {"manager", "super_admin", "pdic_staff"} else (
        DeviceStatus.IN_USE.value if sender_role == "operator" else DeviceStatus.DISTRIBUTED.value
    )

    sender_holder_type = role_to_type.get(sender_role, "pdic_staff")
    now = datetime.now().replace(tzinfo=None)

    async with async_session_factory() as session:
        await session.execute(
            text("""UPDATE distributions
               SET status = :status, notes = COALESCE(:notes, notes), updated_at = :now, delivery_date = :today
               WHERE id = :id"""),
            {"status": DistributionStatus.REJECTED.value, "notes": notes, "now": now, "today": now.date(), "id": int(distribution_id)}
        )
        await bump_cache_version(session)
        await session.commit()

        device_ids = dist.get("device_ids", []) or []
        if device_ids:
            await _bulk_update_device_holders(
                device_ids=device_ids,
                holder_id=dist["from_user_id"],
                holder_name=dist["from_user_name"],
                holder_type=sender_holder_type,
                location=dist["from_user_name"],
                status=sender_status,
                performed_by=int(user.get("id", user.get("_id", 0))),
                performed_by_name=str(user.get("name") or "PDIC"),
                from_user_id=int(dist.get("to_user_id") or 0),
                from_user_name=dist.get("to_user_name"),
                notes=f"Disputed return confirmed for distribution {dist.get('distribution_id')}",
                action="bulk_distributed",
                distribution_id=dist.get("distribution_id"),
            )
            if dist.get("distribution_id"):
                await _clear_distribution_device_locks(session, device_ids, now)
            await session.commit()

    await notification_service.create_notification(
        user_id=str(dist["from_user_id"]),
        title="Disputed Return Confirmed",
        message=(
            f"PDIC confirmed devices for distribution {dist['distribution_id']} are back with you. "
            "You can distribute these devices again."
        ),
        notification_type="success",
        category="distribution",
        link=f"/distributions?distributionId={distribution_id}",
    )

    dist["status"] = DistributionStatus.REJECTED.value
    dist["delivery_date"] = now.date()
    dist["notes"] = notes if notes is not None else dist.get("notes")
    dist["updated_at"] = now
    return dist


async def cancel_distribution(distribution_id: str, user: dict) -> bool:
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        return False
    user_id = int(user.get("id", user.get("_id", 0)))
    if int(dist["created_by"]) != user_id and user.get("role") not in ["super_admin", "manager"]:
        raise ValueError("Only the creator can cancel this distribution")
    if dist["status"] == DistributionStatus.CANCELLED.value:
        raise ValueError("Distribution is already cancelled")
    if dist["status"] == DistributionStatus.APPROVED.value:
        raise ValueError("Cannot cancel a distribution that has already been confirmed")

    async with async_session_factory() as session:
        now = datetime.now().replace(tzinfo=None)
        await session.execute(
            text("UPDATE distributions SET status = :status, updated_at = :now WHERE id = :id"),
            {"status": DistributionStatus.CANCELLED.value, "now": now, "id": int(distribution_id)}
        )

        device_ids = dist.get("device_ids") or []
        if dist.get("distribution_id") and device_ids:
            dist_code = dist["distribution_id"]
            for batch in chunks(device_ids, _BULK_CHUNK_SIZE):
                batch_hist = [
                    {
                        "device_id": int(did),
                        "distribution_id": dist_code,
                        "notes": f"Distribution {dist_code} cancelled",
                        "ts": now,
                    }
                    for did in batch
                ]
                await session.execute(
                    text("""INSERT INTO device_history (
                        device_id, action, distribution_id, notes, timestamp
                    ) VALUES (:device_id, 'distribution_record', :distribution_id, :notes, :ts)"""),
                    batch_hist
                )
            await _clear_distribution_device_locks(
                session, device_ids, now, distribution_code=dist_code
            )

        await bump_cache_version(session)
        await session.commit()
    return True


async def get_distribution_manifest_file(distribution_id: str, user: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Get manifest file metadata if requester is permitted to access distribution."""
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        return None

    if not await _user_can_access_distribution(user, dist.get("from_user_id"), dist.get("to_user_id")):
        raise ValueError("You are not allowed to access this distribution manifest")

    manifest_file = dist.get("manifest_file")
    if not manifest_file:
        return None

    file_path = _distribution_manifest_dir() / str(manifest_file)
    if not file_path.exists():
        return None

    return {
        "path": str(file_path),
        "filename": str(manifest_file),
    }


async def get_distribution_mac_nuid_export(
    distribution_id: str,
    user: Dict[str, Any],
    file_format: str = "csv",
) -> Dict[str, Any]:
    """Get an identifier export payload (serial_number, mac_address, nuid) for distribution devices if requester is permitted."""
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        raise ValueError("Distribution not found")

    if not await _user_can_access_distribution(user, dist.get("from_user_id"), dist.get("to_user_id")):
        raise ValueError("You are not allowed to access this distribution export")

    device_ids = dist.get("device_ids") or []
    if isinstance(device_ids, str):
        device_ids = []

    devices: List[Dict[str, Any]] = []
    if device_ids:
        ph = ",".join([f":d_{i}" for i in range(len(device_ids))])
        params = {f"d_{i}": int(did) for i, did in enumerate(device_ids)}
        async with async_session_factory() as session:
            rows = (await session.execute(
                text(f"SELECT id, device_id, device_type, manufacturer, model, serial_number, mac_address, nuid FROM devices WHERE id IN ({ph})"),
                params
            )).mappings().all()
            devices = [dict(r) for r in rows]

    return _build_distribution_mac_nuid_file(
        distribution=dist,
        devices=devices,
        file_format=file_format,
    )


async def get_distribution_devices(
    distribution_id: str,
    user: Dict[str, Any],
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """Return paginated device details for a distribution if the requester is permitted."""
    dist = await get_distribution_by_id(distribution_id)
    if not dist:
        raise ValueError("Distribution not found")

    if not await _user_can_access_distribution(user, dist.get("from_user_id"), dist.get("to_user_id")):
        raise ValueError("You are not allowed to access this distribution's devices")

    device_ids = dist.get("device_ids") or []
    if isinstance(device_ids, str):
        device_ids = []

    total = len(device_ids)
    if not device_ids:
        return {"data": [], "pagination": get_pagination(page, page_size, total)}

    offset = (page - 1) * page_size
    page_device_ids = device_ids[offset: offset + page_size]
    if not page_device_ids:
        return {"data": [], "pagination": get_pagination(page, page_size, total)}

    ph = ",".join([f":d_{i}" for i in range(len(page_device_ids))])
    params = {f"d_{i}": int(did) for i, did in enumerate(page_device_ids)}

    async with async_session_factory() as session:
        rows = (await session.execute(
            text(
                "SELECT id, device_id, device_type, manufacturer, model, "
                "serial_number, mac_address, nuid, box_type, status, current_holder_name "
                f"FROM devices WHERE id IN ({ph})"
            ),
            params
        )).mappings().all()

    by_id = {int(r["id"]): dict(r) for r in rows}
    devices = []
    for did in page_device_ids:
        device = by_id.get(int(did))
        if device is not None:
            devices.append(device_service._augment_device_record(device))

    return {
        "data": devices,
        "pagination": get_pagination(page, page_size, total),
    }


async def get_distribution_device_summary(
    distribution_id: str,
    user: Dict[str, Any],
) -> Dict[str, Any]:
    """Return aggregated device type / vendor counts for a distribution.

    Aggregation is computed entirely in SQL so it stays cheap even for
    distributions with hundreds of thousands of devices. Membership is derived
    from `devices.current_distribution_id` and `device_history.distribution_id`
    (deduplicated via UNION), mirroring `_load_distribution_device_ids`.
    """
    async with async_session_factory() as session:
        row = (await session.execute(
            text("SELECT id, distribution_id, from_user_id, to_user_id FROM distributions WHERE id = :id"),
            {"id": int(distribution_id)}
        )).mappings().first()
        if not row:
            raise ValueError("Distribution not found")

        if not await _user_can_access_distribution(user, row["from_user_id"], row["to_user_id"]):
            raise ValueError("You are not allowed to access this distribution's devices")

        code = str(row["distribution_id"])
        membership = (
            "SELECT id AS device_id FROM devices WHERE current_distribution_id = :code "
            "UNION "
            "SELECT device_id FROM device_history WHERE distribution_id = :code"
        )
        type_rows = (await session.execute(
            text(f"""
                SELECT d.device_type AS bucket, COUNT(*) AS cnt
                FROM ({membership}) u
                JOIN devices d ON d.id = u.device_id
                GROUP BY d.device_type
                ORDER BY cnt DESC
            """),
            {"code": code}
        )).mappings().all()
        manufacturer_rows = (await session.execute(
            text(f"""
                SELECT d.manufacturer AS bucket, COUNT(*) AS cnt
                FROM ({membership}) u
                JOIN devices d ON d.id = u.device_id
                GROUP BY d.manufacturer
                ORDER BY cnt DESC
            """),
            {"code": code}
        )).mappings().all()

    return {
        "device_types": [[str(r["bucket"]), int(r["cnt"])] for r in type_rows],
        "manufacturers": [[str(r["bucket"]), int(r["cnt"])] for r in manufacturer_rows],
    }


async def get_pending_distributions() -> List[Dict[str, Any]]:
    async with async_session_factory() as session:
        rows = (await session.execute(
            text("SELECT * FROM distributions WHERE status = :status ORDER BY created_at DESC LIMIT 1000"),
            {"status": DistributionStatus.PENDING.value}
        )).mappings().all()

        device_map = await _load_distribution_device_ids(
            session, [str(r["distribution_id"]) for r in rows]
        )

        result = []
        for r in rows:
            d = dict(r)
            d["device_ids"] = device_map.get(str(d["distribution_id"]), [])
            result.append(d)
        return result


async def get_distribution_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, int]:
    async with async_session_factory() as session:
        params: Dict[str, Any] = {}
        conditions = []
        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date
        where = " AND ".join(conditions) if conditions else "1=1"

        by_status = {}
        rows = (await session.execute(
            text(f"SELECT status, COUNT(*) AS cnt FROM distributions WHERE {where} GROUP BY status"),
            params
        )).mappings().all()
        for row in rows:
            by_status[row["status"]] = row["cnt"]

        total = sum(by_status.values())
        return {
            "total": total,
            "pending": by_status.get("pending", 0),
            "pending_receipt": by_status.get("pending_receipt", 0),
            "approved": by_status.get("approved", 0),
            "delivered": by_status.get("delivered", 0),
            "rejected": by_status.get("rejected", 0),
            "disputed": by_status.get("disputed", 0),
        }


async def sync_approved_distributions(user: Dict[str, Any]) -> Dict[str, Any]:
    async with async_session_factory() as session:
        rows = (await session.execute(
            text("SELECT * FROM distributions WHERE status = :status LIMIT 5000"),
            {"status": DistributionStatus.APPROVED.value}
        )).mappings().all()
        distributions = [dict(r) for r in rows]
        synced_count = 0
        errors = []
        user_id = int(user.get("id", user.get("_id", 0)))

        device_map = await _load_distribution_device_ids(
            session, [str(dist["distribution_id"]) for dist in distributions]
        )

        for dist in distributions:
            device_ids = device_map.get(str(dist.get("distribution_id")), [])

            if device_ids:
                updated = await _bulk_update_device_holders(
                    device_ids=device_ids,
                    holder_id=dist["to_user_id"],
                    holder_name=dist["to_user_name"],
                    holder_type=dist.get("to_user_type", "pdic_staff"),
                    location=dist["to_user_name"],
                    status=DeviceStatus.DISTRIBUTED.value,
                    performed_by=user_id,
                    performed_by_name=user.get("name", "System"),
                    from_user_id=dist.get("from_user_id"),
                    from_user_name=dist.get("from_user_name"),
                    notes=f"Synced from approved distribution {dist.get('distribution_id', '')}",
                    action="bulk_distributed",
                    distribution_id=dist.get("distribution_id"),
                )
                synced_count += len(updated)

                if dist.get("distribution_id"):
                    await _clear_distribution_device_locks(
                        session, device_ids, datetime.now().replace(tzinfo=None),
                        distribution_code=dist["distribution_id"]
                    )

        await session.commit()

    return {"total_distributions": len(distributions), "devices_synced": synced_count, "errors": errors}

