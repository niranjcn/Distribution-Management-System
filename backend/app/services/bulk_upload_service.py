import asyncio
import csv
import io
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

from fastapi import HTTPException, status

from app.database_sqlalchemy import async_session_factory
from sqlalchemy import text
from app.core.activity_logger import log_business_activity
from app.core.audit import audit_logger
from app.utils.roles import normalize_role

logger = logging.getLogger(__name__)

MAX_UPLOAD_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_BULK_ROWS = 300000
_MAX_XLSX_UNCOMPRESSED_SIZE = 500 * 1024 * 1024  # 500 MB


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
    from app.utils.security import get_password_hash as _hash

    actor_role = normalize_role(current_user.get("role"))
    if actor_role not in {"super_admin", "manager", "sub_distributor", "cluster", "sub_distribution_manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    actor_name = current_user.get("name") or current_user.get("email") or "User"

    if not target_role or target_role not in {"sub_distributor", "cluster", "operator"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid target role '{target_role}'")

    # Permission matrix:
    # - sub_distributor / cluster / sub_distribution_manager: can only upload operators
    # - manager / super_admin: can upload any role
    if actor_role in {"sub_distributor", "cluster", "sub_distribution_manager"} and target_role != "operator":
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
            status, phone, designation, parent_id, created_at, updated_at)
        VALUES (:email, :password_hash, :name, :role,
            :status, :phone, :designation, :parent_id, :created_at, :updated_at)"""

        should_commit = True
        for batch in chunks(insertable_rows, 500):
            batch_payload = []
            for item in batch:
                batch_payload.append({
                    "email": item["email"],
                    "password_hash": item["password_hash"],
                    "name": item["name"],
                    "role": target_role,
                    "status": "active",
                    "phone": item["phone"],
                    "designation": None,
                    "parent_id": item.get("parent_id"),
                    "created_at": now,
                    "updated_at": now,
                })

            try:
                await session.execute(text(insert_sql), batch_payload)
                for item in batch:
                    created.append({"row": item["row"], "email": item["email"], "role": target_role, "name": item["name"]})
            except Exception as batch_error:
                for item in batch:
                    row_idx = item["row"]
                    email = item["email"]
                    try:
                        await session.execute(
                            text(insert_sql),
                            {
                                "email": email,
                                "password_hash": item["password_hash"],
                                "name": item["name"],
                                "role": target_role,
                                "status": "active",
                                "phone": item["phone"],
                                "designation": None,
                                "parent_id": item.get("parent_id"),
                                "created_at": now,
                                "updated_at": now,
                            },
                        )
                        created.append({"row": row_idx, "email": email, "role": target_role, "name": item["name"]})
                    except Exception as single_error:
                        lowered = str(single_error).lower()
                        if "duplicate" in lowered or "unique" in lowered:
                            skipped.append({"row": row_idx, "email": email, "reason": "Email already exists"})
                        else:
                            errors.append({"row": row_idx, "email": email, "error": str(single_error)[:200]})
                            should_commit = False
                            break

                if not should_commit:
                    break

                logger.warning("Batch insert fallback triggered for users due to: %s", str(batch_error))

            await asyncio.sleep(0)

        if should_commit and insertable_rows:
            await session.commit()
        elif not insertable_rows:
            pass
        else:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Bulk upload was rolled back due to an unexpected insert error. Please retry."
            )

    # Create digital identities for each created user
    from app.services.digital_id_service import create_digital_identities_for_user as _create_identities
    for item in created:
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": item["email"]},
                )
                row = result.mappings().first()
                if row:
                    user_id = int(row["id"])
                    matched = next((p for p in prepared_rows if p["email"] == item["email"]), None)
                    await _create_identities(
                        user_id=user_id,
                        primary_digital_id=matched["digital_id"] if matched else None,
                        primary_broadband_id=matched["broadband_id"] if matched else None,
                        additional_digital_ids=matched.get("additional_digital_ids") if matched else None,
                    )
        except Exception as e:
            logger.warning("Failed to create digital identities for %s: %s", item["email"], e)

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
        "data": {
            "created_count": created_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "created": created,
            "skipped": skipped,
            "errors": errors,
        },
    }
    if total is not None:
        result["data"]["total"] = total
    return result
