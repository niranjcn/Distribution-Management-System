import asyncio
import csv
import io
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Set

from fastapi import HTTPException, status

from app.database_sqlalchemy import async_session_factory
from sqlalchemy import text
from app.core.activity_logger import log_business_activity
from app.core.audit import audit_logger
from app.core.cache_version import bump_cache_version
from app.utils.roles import normalize_role

logger = logging.getLogger(__name__)

MAX_UPLOAD_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_BULK_ROWS = 300000
_MAX_XLSX_UNCOMPRESSED_SIZE = 500 * 1024 * 1024  # 500 MB

# Uploads at or below this row count keep a single atomic transaction. Larger
# uploads commit per batch so one bad row cannot roll back many minutes of work;
# the existing DB pre-checks make re-runs safe (already-committed rows are
# reported as skipped duplicates).
BULK_UPLOAD_CHUNKED_COMMIT_THRESHOLD = 10000

# How many per-row results are embedded in the bulk upload response body.
# Anything beyond this count is omitted so a 150k-row upload never returns a
# giant JSON body.
BULK_RESULT_INLINE_LIMIT = 500


def build_bulk_result(
    created: List[Any],
    skipped: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
    total: Optional[int] = None,
    created_count: Optional[int] = None,
    skipped_count: Optional[int] = None,
    error_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Build the ``data`` payload for a bulk operation response.

    Counts are always full. The per-row ``created`` / ``skipped`` / ``errors``
    lists are capped at ``BULK_RESULT_INLINE_LIMIT`` so large uploads return a
    small body; the ``*_truncated`` flags tell the frontend more rows exist.
    """
    created_capped = created[:BULK_RESULT_INLINE_LIMIT]
    skipped_capped = skipped[:BULK_RESULT_INLINE_LIMIT]
    errors_capped = errors[:BULK_RESULT_INLINE_LIMIT]

    data = {
        "created_count": len(created) if created_count is None else created_count,
        "skipped_count": len(skipped) if skipped_count is None else skipped_count,
        "error_count": len(errors) if error_count is None else error_count,
        "created_truncated": len(created) > BULK_RESULT_INLINE_LIMIT,
        "skipped_truncated": len(skipped) > BULK_RESULT_INLINE_LIMIT,
        "errors_truncated": len(errors) > BULK_RESULT_INLINE_LIMIT,
        "created": created_capped,
        "skipped": skipped_capped,
        "errors": errors_capped,
    }
    if total is not None:
        data["total"] = total
    return data

DIGITAL_IDENTITY_INSERT_SQL = """INSERT INTO digital_identities (
    user_id, digital_id, broadband_id, is_primary, created_at
) VALUES (:user_id, :digital_id, :broadband_id, :is_primary, :created_at)"""


def check_bulk_upload_file(contents: bytes, filename_lower: str) -> None:
    if len(contents) > MAX_UPLOAD_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_FILE_SIZE // (1024 * 1024)} MB",
        )
    if filename_lower.endswith(".xlsx"):
        with zipfile.ZipFile(io.BytesIO(contents)) as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > _MAX_XLSX_UNCOMPRESSED_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File contains excessively large decompressed data",
                )


def chunks(values: List[Any], chunk_size: int) -> Iterable[List[Any]]:
    for i in range(0, len(values), chunk_size):
        yield values[i:i + chunk_size]


async def chunked_executemany(
    session: Any,
    sql: str,
    rows: List[Dict[str, Any]],
    chunk_size: int = 500,
    *,
    on_batch_success: Optional[Callable[..., Awaitable[None]]] = None,
    on_row_duplicate: Optional[Callable[..., Awaitable[None]]] = None,
    on_row_error: Optional[Callable[..., Awaitable[None]]] = None,
    on_batch_start: Optional[Callable[[], Awaitable[None]]] = None,
    on_batch_complete: Optional[Callable[[bool], Awaitable[None]]] = None,
    abort_on_error: bool = True,
) -> bool:
    """Insert ``rows`` in chunks with a binary-split fallback.

    Runs ``session.execute(text(sql), batch)`` for each chunk. When a whole
    chunk fails (MySQL aborts a multi-VALUES insert atomically, so nothing from
    the chunk is inserted), the chunk is retried by repeatedly splitting it in
    half instead of falling back to one round trip per row: error-free runs
    insert in bulk, so a chunk with a single bad row costs only O(log n) round
    trips rather than n. Returns ``False`` when a hard error aborted the loop
    (the caller should roll back the transaction).

    Callbacks (all receive the session, plus:):

      on_batch_success(session, batch)   -- after an entire chunk or sub-batch
                                            inserts cleanly (also fired for
                                            single rows that survive a split)
      on_row_duplicate(session, row, err)-- duplicate/unique-constraint failure
      on_row_error(session, row, err)    -- any other row failure
      on_batch_start()                   -- before each chunk is attempted
      on_batch_complete(ok, can_commit)  -- after each chunk; ``can_commit`` is
                                          -- whether the loop still intends to commit

    When ``abort_on_error`` is True (users/devices) a hard error stops the loop;
    when False (external items) the failure is recorded and the next row runs.
    """
    should_commit = True
    for batch in chunks(rows, chunk_size):
        if on_batch_start:
            await on_batch_start()

        batch_ok = True
        try:
            await session.execute(text(sql), batch)
        except Exception as batch_error:
            batch_ok = False
            aborted = await _retry_split(
                session, sql, batch,
                on_batch_success=on_batch_success,
                on_row_duplicate=on_row_duplicate,
                on_row_error=on_row_error,
                abort_on_error=abort_on_error,
            )
            if aborted:
                should_commit = False
            logger.warning("Batch insert fallback triggered: %s", str(batch_error))
        else:
            if on_batch_success:
                await on_batch_success(session, batch)

        if on_batch_complete:
            await on_batch_complete(batch_ok, should_commit)
        await asyncio.sleep(0)

        if not should_commit:
            break
    return should_commit


async def _retry_split(
    session: Any,
    sql: str,
    subrows: List[Dict[str, Any]],
    *,
    on_batch_success,
    on_row_duplicate,
    on_row_error,
    abort_on_error: bool,
) -> bool:
    """Insert ``subrows`` after a batch executemany failed.

    Recursively splits the batch in half on each failure so the rows that
    actually conflict are isolated with O(log n) round trips, while every
    error-free run inserts in bulk. Returns ``True`` when a hard error aborted
    the operation (the caller should roll back); duplicates never abort.
    """
    if len(subrows) == 1:
        row = subrows[0]
        try:
            await session.execute(text(sql), row)
        except Exception as single_error:
            lowered = str(single_error).lower()
            is_duplicate = "duplicate" in lowered or "unique" in lowered
            if is_duplicate and on_row_duplicate:
                await on_row_duplicate(session, row, single_error)
                return False
            if on_row_error:
                await on_row_error(session, row, single_error)
            return abort_on_error and not is_duplicate
        else:
            if on_batch_success:
                await on_batch_success(session, subrows)
            return False

    mid = len(subrows) // 2
    for half in (subrows[:mid], subrows[mid:]):
        try:
            await session.execute(text(sql), half)
        except Exception:
            if await _retry_split(
                session, sql, half,
                on_batch_success=on_batch_success,
                on_row_duplicate=on_row_duplicate,
                on_row_error=on_row_error,
                abort_on_error=abort_on_error,
            ):
                return True
        else:
            if on_batch_success:
                await on_batch_success(session, half)
    return False


def parse_file(contents: bytes, ext: str) -> list:
    rows = []
    if ext == "csv":
        decoded = contents.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded))
        for row in reader:
            rows.append({k.strip().lower(): v.strip() if v else "" for k, v in row.items()})
    elif ext in ("xlsx", "xls"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(contents), read_only=True, data_only=True)
        ws = wb.active
        header_row = None
        for r_idx, row in enumerate(ws.iter_rows(values_only=True)):
            values = [str(v).strip() if v is not None else "" for v in row]
            if r_idx == 0:
                header_row = [str(h).strip().lower() for h in values]
                continue
            if header_row:
                row_dict = {}
                for c_idx, val in enumerate(values):
                    if c_idx < len(header_row):
                        row_dict[header_row[c_idx]] = val
                if any(row_dict.values()):
                    rows.append(row_dict)
        wb.close()
    return rows


def validate_upload_signature(filename_lower: str, content: bytes) -> None:
    if filename_lower.endswith(".xlsx"):
        if not content.startswith(b"PK\x03\x04"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid XLSX file content"
            )
        return

    if filename_lower.endswith(".xls"):
        if not content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid XLS file content"
            )
        return

    if filename_lower.endswith(".csv"):
        if not _is_likely_text(content[:2048]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid CSV file content"
            )


def check_bulk_upload_row_count(rows: list) -> None:
    if len(rows) > MAX_BULK_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many rows. Maximum is {MAX_BULK_ROWS}",
        )


def _is_likely_text(content: bytes) -> bool:
    if not content:
        return True
    return b"\x00" not in content


async def fetch_existing_values(session, table: str, column: str, values: List[str]) -> Set[str]:
    if not values:
        return set()

    existing = set()
    for batch in chunks(values, 500):
        placeholders = ",".join([f":v{i}" for i in range(len(batch))])
        params = {f"v{i}": v for i, v in enumerate(batch)}
        result = await session.execute(
            text(f"SELECT {column} FROM {table} WHERE {column} IN ({placeholders})"),
            params,
        )
        for row in result.scalars().all():
            if row:
                existing.add(str(row).strip().lower())
    return existing


async def fetch_user_parent_map(session, emails: Set[str], role: str) -> Dict[str, int]:
    if not emails:
        return {}
    parent_map = {}
    for batch in chunks(list(emails), 500):
        placeholders = ",".join([f":v{i}" for i in range(len(batch))])
        params = {f"v{i}": v for i, v in enumerate(batch)}
        params["role"] = role
        result = await session.execute(
            text(f"SELECT LOWER(email) as email, id FROM users WHERE LOWER(email) IN ({placeholders}) AND role = :role"),
            params,
        )
        for row in result.mappings().all():
            parent_map[row["email"]] = int(row["id"])
    return parent_map


async def process_bulk_user_upload(
    rows: list,
    current_user: dict,
    target_role: Optional[str] = None,
    parent_id: Optional[int] = None,
) -> dict:
    """Bulk-create users from uploaded rows.

    Emails are normalized to lowercase before insertion, and every uniqueness
    check (duplicate within the file, against existing users, and digital-ID
    ownership) compares lowercase values. The ``users.email`` column is
    backed by a case-insensitive collation in the database, so uniqueness is
    enforced there as well; the service-level normalization keeps the two
    layers consistent and makes the ``LOWER(email)`` lookups exact.
    """
    from app.utils.security import get_password_hash as _hash

    actor_role = normalize_role(current_user.get("role"))
    if actor_role not in {"super_admin", "manager", "sub_distributor", "cluster", "sub_distribution_manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    actor_name = current_user.get("name") or current_user.get("email") or "User"

    if not target_role or target_role not in {"sub_distributor", "cluster", "operator"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid target role '{target_role}'")

    # Permission matrix:
    # - cluster:                       can only upload operators
    # - sub_distributor / sub_distribution_manager: can upload operators AND
    #   clusters created under their own account
    # - manager / super_admin: can upload any role
    if actor_role == "cluster" and target_role != "operator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{actor_role} can only bulk-upload operators"
        )

    # Validate parent for roles that require one.
    if target_role in {"cluster", "operator"}:
        if not parent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A parent is required when bulk-uploading {target_role} users",
            )
        async with async_session_factory() as session:
            parent_row = (
                await session.execute(
                    text("SELECT id, role FROM users WHERE id = :pid"), {"pid": parent_id}
                )
            ).mappings().first()
        if not parent_row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected parent does not exist")
        parent_role = normalize_role(parent_row.get("role"))
        if target_role == "cluster" and parent_role != "sub_distributor":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cluster parent must be a sub distributor",
            )
        if target_role == "cluster" and actor_role in {"sub_distributor", "sub_distribution_manager"} \
                and int(parent_id) != int(current_user.get("id") or 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sub distributors can only create clusters under their own account",
            )
        if target_role == "operator" and parent_role not in {"sub_distributor", "cluster"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Operator parent must be a sub distributor or cluster",
            )
    elif target_role == "sub_distributor" and parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sub distributors cannot be assigned a parent",
        )

    created: List[dict] = []
    errors: List[dict] = []
    skipped: List[dict] = []
    prepared_rows: List[dict] = []
    seen_emails: Set[str] = set()
    seen_digital_keys: Set[str] = set()
    seen_broadband_keys: Set[str] = set()

    for idx, row in enumerate(rows):
        row_num = idx + 2
        email = str(row.get("email") or "").strip().lower()
        password = str(row.get("password") or "")
        name = str(row.get("name") or "").strip()
        phone = str(row.get("phone") or "").strip() or None
        address = str(row.get("address") or "").strip() or None
        pincode = str(row.get("pincode") or "").strip() or None
        network_name = str(row.get("network_name") or "").strip() or None

        # digital_id may contain multiple ids separated by "|" (operators can
        # have several digital ids). The first value is the primary id, the
        # remaining values become additional ids.
        raw_digital = str(row.get("digital_id") or "").strip()
        digital_parts = [d.strip() for d in raw_digital.split("|") if d.strip()] if raw_digital else []
        digital_id = digital_parts[0] if digital_parts else None
        broadband_id = str(row.get("broadband_id") or "").strip() or None
        additional_digital_ids = digital_parts[1:] if len(digital_parts) > 1 else None

        # Backwards-compatible: also read a legacy additional_digital_ids column.
        raw_additional = str(row.get("additional_digital_ids") or "").strip()
        if raw_additional:
            legacy_parts = [d.strip() for d in raw_additional.split("|") if d.strip()]
            if legacy_parts:
                additional_digital_ids = (additional_digital_ids or []) + legacy_parts

        if not email or not password or not name:
            errors.append({"row": row_num, "email": email, "error": "Missing required fields (email, password, name)"})
            continue

        if email in seen_emails:
            skipped.append({"row": row_num, "email": email, "reason": "Duplicate email in file"})
            continue
        seen_emails.add(email)

        all_digital_values = ([digital_id] + (additional_digital_ids or []))
        dup_digital = next((d for d in all_digital_values if d and d.strip().lower() in seen_digital_keys), None)
        if dup_digital:
            skipped.append({"row": row_num, "email": email, "reason": f"Digital ID '{dup_digital}' is duplicated within the file"})
            continue
        for d in all_digital_values:
            if d and d.strip():
                seen_digital_keys.add(d.strip().lower())
        if broadband_id and broadband_id.strip().lower() in seen_broadband_keys:
            skipped.append({"row": row_num, "email": email, "reason": f"Broadband ID '{broadband_id}' is duplicated within the file"})
            continue
        if broadband_id and broadband_id.strip():
            seen_broadband_keys.add(broadband_id.strip().lower())

        prepared_rows.append({
            "row": row_num,
            "email": email,
            "password": password,
            "name": name,
            "digital_id": digital_id,
            "broadband_id": broadband_id,
            "additional_digital_ids": additional_digital_ids,
            "phone": phone,
            "address": address,
            "pincode": pincode,
            "network_name": network_name if target_role == "operator" else None,
        })

    if not prepared_rows:
        return _build_response(0, len(skipped), len(errors), created, skipped, errors)

    loop = asyncio.get_running_loop()
    hashed = await asyncio.gather(
        *(loop.run_in_executor(None, _hash, item["password"]) for item in prepared_rows)
    )
    for item, pw_hash in zip(prepared_rows, hashed):
        item["password_hash"] = pw_hash

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with async_session_factory() as session:
        all_emails = [item["email"] for item in prepared_rows]
        existing_emails = await fetch_existing_values(session, "users", "email", all_emails)

        insertable_rows = []
        for item in prepared_rows:
            if item["email"] in existing_emails:
                skipped.append({"row": item["row"], "email": item["email"], "reason": "Email already exists"})
                continue
            item["parent_id"] = parent_id
            insertable_rows.append(item)

        # Digital / broadband IDs must be unique across all users in the system.
        if insertable_rows:
            all_digital = []
            all_broadband = []
            for item in insertable_rows:
                for d in ([item["digital_id"]] + (item["additional_digital_ids"] or [])):
                    if d and d.strip():
                        all_digital.append(d)
                if item["broadband_id"] and item["broadband_id"].strip():
                    all_broadband.append(item["broadband_id"])
            existing_digital = await fetch_existing_values(session, "digital_identities", "digital_id", all_digital)
            existing_broadband = await fetch_existing_values(session, "digital_identities", "broadband_id", all_broadband)

            filtered_rows = []
            for item in insertable_rows:
                digital_ids = [d.strip() for d in ([item["digital_id"]] + (item["additional_digital_ids"] or [])) if d and d.strip()]
                taken_digital = next((d for d in digital_ids if d.lower() in existing_digital), None)
                if taken_digital:
                    skipped.append({"row": item["row"], "email": item["email"], "reason": f"Digital ID '{taken_digital}' is already assigned to another user"})
                    continue
                if item["broadband_id"] and item["broadband_id"].strip().lower() in existing_broadband:
                    skipped.append({"row": item["row"], "email": item["email"], "reason": f"Broadband ID '{item['broadband_id'].strip()}' is already assigned to another user"})
                    continue
                filtered_rows.append(item)
            insertable_rows = filtered_rows

        if not insertable_rows:
            return _build_response(0, len(skipped), len(errors), created, skipped, errors)

        insert_sql = """INSERT INTO users (email, password_hash, name, role,
            status, phone, designation, address, pincode, network_name, parent_id, created_by, created_at, updated_at)
        VALUES (:email, :password_hash, :name, :role,
            :status, :phone, :designation, :address, :pincode, :network_name, :parent_id, :created_by, :created_at, :updated_at)"""

        creator_id = int(current_user.get("id") or 0)

        payload_rows = []
        for item in insertable_rows:
            payload_rows.append({
                "row": item["row"],
                "email": item["email"],
                "password_hash": item["password_hash"],
                "name": item["name"],
                "role": target_role,
                "status": "active",
                "phone": item["phone"],
                "designation": None,
                "address": item["address"],
                "pincode": item["pincode"],
                "network_name": item["network_name"],
                "parent_id": item.get("parent_id"),
                "created_by": creator_id,
                "created_at": now,
                "updated_at": now,
            })

        async def _user_batch_success(session, batch):
            for item in batch:
                created.append({"row": item["row"], "email": item["email"], "role": target_role, "name": item["name"]})

        async def _user_row_duplicate(session, item, err):
            skipped.append({"row": item["row"], "email": item["email"], "reason": "Email already exists"})

        async def _user_row_error(session, item, err):
            errors.append({"row": item["row"], "email": item["email"], "error": str(err)[:200]})

        should_commit = await chunked_executemany(
            session,
            insert_sql,
            payload_rows,
            on_batch_success=_user_batch_success,
            on_row_duplicate=_user_row_duplicate,
            on_row_error=_user_row_error,
            abort_on_error=True,
        )

        if should_commit and insertable_rows:
            await bump_cache_version(session)

            # Digital / broadband identities for the created users. Resolve the
            # numeric user ids once with a chunked lookup, then batch-insert all
            # identities in the same transaction as the users instead of one
            # transaction + SELECT round trip per user.
            identity_candidates = [
                item for item in insertable_rows
                if item.get("digital_id") or item.get("broadband_id") or item.get("additional_digital_ids")
            ]
            if identity_candidates:
                email_to_id: Dict[str, int] = {}
                for batch in chunks([p["email"] for p in identity_candidates], 500):
                    ph = ",".join([f":e{i}" for i in range(len(batch))])
                    params = {f"e{i}": e for i, e in enumerate(batch)}
                    result = await session.execute(
                        text(f"SELECT id, LOWER(email) AS email FROM users WHERE LOWER(email) IN ({ph})"),
                        params,
                    )
                    for row in result.mappings().all():
                        email_to_id[str(row["email"]).lower()] = int(row["id"])

                identities_payload: List[Dict[str, Any]] = []
                for item in identity_candidates:
                    user_id = email_to_id.get(item["email"])
                    if user_id is None:
                        continue
                    if item.get("digital_id") or item.get("broadband_id"):
                        identities_payload.append({
                            "user_id": user_id,
                            "digital_id": item.get("digital_id"),
                            "broadband_id": item.get("broadband_id"),
                            "is_primary": 1,
                            "created_at": now,
                        })
                    for extra in (item.get("additional_digital_ids") or []):
                        identities_payload.append({
                            "user_id": user_id,
                            "digital_id": extra,
                            "broadband_id": None,
                            "is_primary": 0,
                            "created_at": now,
                        })

                if identities_payload:
                    try:
                        for batch in chunks(identities_payload, 500):
                            await session.execute(text(DIGITAL_IDENTITY_INSERT_SQL), batch)
                    except Exception as e:
                        # MySQL keeps the transaction usable after a failed
                        # statement, so a conflicting identity does not lose the
                        # user rows created above.
                        logger.warning("Failed to insert digital identities: %s", str(e))

            await session.commit()
        elif not insertable_rows:
            pass
        else:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Bulk upload was rolled back due to an unexpected insert error. Please retry."
            )

    await log_business_activity(
        user=current_user,
        path="/activity/users/bulk-upload",
        description=(
            f"{actor_name} used bulk upload for users: "
            f"{len(created)} created, {len(skipped)} skipped, {len(errors)} errors"
        ),
    )

    audit_logger.info(
        "USER_BULK_UPLOAD | actor=%s | total=%d | created=%d | skipped=%d | errors=%d",
        current_user.get("email"), len(prepared_rows), len(created), len(skipped), len(errors),
    )

    return _build_response(len(created), len(skipped), len(errors), created, skipped, errors, total=len(prepared_rows))


def _build_response(
    created_count: int,
    skipped_count: int,
    error_count: int,
    created: list,
    skipped: list,
    errors: list,
    total: Optional[int] = None,
) -> dict:
    result = {
        "success": True,
        "message": f"Bulk upload complete: {created_count} created, {skipped_count} skipped, {error_count} errors",
        "data": build_bulk_result(
            created,
            skipped,
            errors,
            total=total,
            created_count=created_count,
            skipped_count=skipped_count,
            error_count=error_count,
        ),
    }
    return result
