import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, delete as sa_delete, text

from app.core.cache_version import bump_cache_version
from app.database_sqlalchemy import async_session_factory
from app.db_models.digital_id import DigitalIdentity
from app.models.digital_id import DigitalIdentityCreate

logger = logging.getLogger(__name__)


def _normalize(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _identity_conflict_error(conflicts: Dict[str, List[str]]) -> str:
    parts = []
    if conflicts.get("digital"):
        parts.append("Digital ID(s) already assigned to another user: " + ", ".join(conflicts["digital"]))
    if conflicts.get("broadband"):
        parts.append("Broadband ID(s) already assigned to another user: " + ", ".join(conflicts["broadband"]))
    return "; ".join(parts)


async def check_identity_conflicts(
    session,
    digital_ids: List[Optional[str]],
    broadband_ids: List[Optional[str]],
    exclude_identity_id: Optional[int] = None,
) -> Dict[str, List[str]]:
    """Return {'digital': [...], 'broadband': [...]} values that are already taken.

    Matching is case-insensitive to stay consistent with the MySQL unique index
    (case-insensitive collation). Empty/blank values are ignored.
    """
    digital_values = sorted({d.strip() for d in (digital_ids or []) if d and d.strip()})
    broadband_values = sorted({b.strip() for b in (broadband_ids or []) if b and b.strip()})

    result: Dict[str, List[str]] = {"digital": [], "broadband": []}
    if not digital_values and not broadband_values:
        return result

    conditions = []
    params = {}
    if digital_values:
        conditions.append("LOWER(digital_id) IN ({})".format(",".join(f":di_{i}" for i in range(len(digital_values)))))
        for i, v in enumerate(digital_values):
            params[f"di_{i}"] = v.lower()
    if broadband_values:
        conditions.append("LOWER(broadband_id) IN ({})".format(",".join(f":bb_{i}" for i in range(len(broadband_values)))))
        for i, v in enumerate(broadband_values):
            params[f"bb_{i}"] = v.lower()

    where_sql = " OR ".join(conditions)
    if exclude_identity_id is not None:
        where_sql = f"( {where_sql} ) AND id != :excl_id"
        params["excl_id"] = exclude_identity_id

    rows = (await session.execute(
        text(f"SELECT id, digital_id, broadband_id FROM digital_identities WHERE {where_sql}"),
        params,
    )).mappings().all()

    digital_lookup = {v.lower(): v for v in digital_values}
    broadband_lookup = {v.lower(): v for v in broadband_values}
    for row in rows:
        if row["digital_id"]:
            original = digital_lookup.get(str(row["digital_id"]).strip().lower())
            if original and original not in result["digital"]:
                result["digital"].append(original)
        if row["broadband_id"]:
            original = broadband_lookup.get(str(row["broadband_id"]).strip().lower())
            if original and original not in result["broadband"]:
                result["broadband"].append(original)

    return result


async def create_digital_identity(data: DigitalIdentityCreate) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    digital_id = _normalize(data.digital_id)
    broadband_id = _normalize(data.broadband_id)
    async with async_session_factory() as session:
        conflicts = await check_identity_conflicts(session, [digital_id], [broadband_id])
        if conflicts["digital"] or conflicts["broadband"]:
            raise ValueError(_identity_conflict_error(conflicts))
        entry = DigitalIdentity(
            user_id=data.user_id,
            digital_id=digital_id,
            broadband_id=broadband_id,
            is_primary=data.is_primary,
            created_at=now,
        )
        session.add(entry)
        await bump_cache_version(session)
        await session.commit()
        await session.refresh(entry)
        return _identity_to_dict(entry)


async def create_digital_identities_for_user(
    user_id: int,
    primary_digital_id: Optional[str] = None,
    primary_broadband_id: Optional[str] = None,
    additional_digital_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    created = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    primary_digital_id = _normalize(primary_digital_id)
    primary_broadband_id = _normalize(primary_broadband_id)
    additional_digital_ids = [_normalize(d) for d in (additional_digital_ids or [])]
    additional_digital_ids = [d for d in additional_digital_ids if d]

    digital_values = ([primary_digital_id] if primary_digital_id else []) + additional_digital_ids
    broadband_values = [primary_broadband_id] if primary_broadband_id else []

    async with async_session_factory() as session:
        conflicts = await check_identity_conflicts(session, digital_values, broadband_values)
        if conflicts["digital"] or conflicts["broadband"]:
            raise ValueError(_identity_conflict_error(conflicts))

        entries = []
        if primary_digital_id or primary_broadband_id:
            entry = DigitalIdentity(
                user_id=user_id,
                digital_id=primary_digital_id,
                broadband_id=primary_broadband_id,
                is_primary=True,
                created_at=now,
            )
            session.add(entry)
            entries.append(entry)

        for did in additional_digital_ids:
            entry = DigitalIdentity(
                user_id=user_id,
                digital_id=did,
                broadband_id=None,
                is_primary=False,
                created_at=now,
            )
            session.add(entry)
            entries.append(entry)

        await bump_cache_version(session)
        await session.commit()
        for entry in entries:
            await session.refresh(entry)

        return [_identity_to_dict(e) for e in entries]


async def get_digital_identities_by_user(user_id: int) -> List[Dict[str, Any]]:
    async with async_session_factory() as session:
        q = (
            select(DigitalIdentity)
            .where(DigitalIdentity.user_id == user_id)
            .order_by(DigitalIdentity.is_primary.desc(), DigitalIdentity.created_at.desc())
        )
        rows = (await session.execute(q)).scalars().all()
        return [_identity_to_dict(r) for r in rows]


async def delete_digital_identities_by_user(user_id: int) -> None:
    async with async_session_factory() as session:
        await session.execute(sa_delete(DigitalIdentity).where(DigitalIdentity.user_id == user_id))
        await bump_cache_version(session)
        await session.commit()


def _identity_to_dict(entry: DigitalIdentity) -> Dict[str, Any]:
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "digital_id": entry.digital_id,
        "broadband_id": entry.broadband_id,
        "is_primary": bool(entry.is_primary),
        "created_at": entry.created_at.isoformat() if hasattr(entry.created_at, 'isoformat') else str(entry.created_at),
    }
