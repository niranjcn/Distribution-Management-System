import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select

from app.database_sqlalchemy import async_session_factory
from app.db_models.digital_id import DigitalId
from app.models.digital_id import DigitalIdCreate, DigitalIdUpdate

logger = logging.getLogger(__name__)


def compute_user_id_hash(email: str, phone: Optional[str]) -> str:
    raw = f"{email.strip().lower()}{phone or ''}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def create_digital_id(data: DigitalIdCreate) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        from app.db_models.auth import User
        user_q = select(User).where(User.id == int(data.user_id))
        user_inst = (await session.execute(user_q)).scalar_one_or_none()
        if not user_inst:
            return None
        user = user_inst.to_dict()

    user_id_hash = compute_user_id_hash(user["email"], user.get("phone"))
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with async_session_factory() as session:
        entry = DigitalId(
            user_id=int(data.user_id),
            user_id_hash=user_id_hash,
            digital_id=data.digital_id,
            broadband_id=data.broadband_id,
            created_at=now,
            updated_at=now,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return _entry_to_dict(entry)


async def get_digital_ids_by_user(user_id: str) -> List[Dict[str, Any]]:
    async with async_session_factory() as session:
        q = select(DigitalId).where(DigitalId.user_id == int(user_id)).order_by(DigitalId.created_at.desc())
        rows = (await session.execute(q)).scalars().all()
        return [_entry_to_dict(r) for r in rows]


async def get_digital_id_by_id(entry_id: str) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        inst = await session.get(DigitalId, int(entry_id))
        if not inst:
            return None
        return _entry_to_dict(inst)


async def create_digital_id_for_user(
    user_id: str, email: str, phone: Optional[str],
    digital_id: Optional[str] = None, broadband_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    user_id_hash = compute_user_id_hash(email, phone)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session_factory() as session:
        entry = DigitalId(
            user_id=int(user_id),
            user_id_hash=user_id_hash,
            digital_id=digital_id,
            broadband_id=broadband_id,
            created_at=now,
            updated_at=now,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return _entry_to_dict(entry)


async def recompute_hashes_for_user(user_id: str, email: str, phone: Optional[str]) -> None:
    """Recompute user_id_hash for all digital ID entries of a user when email or phone changes."""
    new_hash = compute_user_id_hash(email, phone)
    async with async_session_factory() as session:
        q = select(DigitalId).where(DigitalId.user_id == int(user_id))
        rows = (await session.execute(q)).scalars().all()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for entry in rows:
            entry.user_id_hash = new_hash
            entry.updated_at = now
        await session.commit()


async def delete_digital_ids_by_user(user_id: str) -> None:
    async with async_session_factory() as session:
        from sqlalchemy import delete as sa_delete
        await session.execute(sa_delete(DigitalId).where(DigitalId.user_id == int(user_id)))
        await session.commit()


async def update_digital_id(entry_id: str, data: DigitalIdUpdate) -> Optional[Dict[str, Any]]:
    async with async_session_factory() as session:
        inst = await session.get(DigitalId, int(entry_id))
        if not inst:
            return None
        if data.digital_id is not None:
            inst.digital_id = data.digital_id
        if data.broadband_id is not None:
            inst.broadband_id = data.broadband_id
        inst.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()
        await session.refresh(inst)
        return _entry_to_dict(inst)


async def delete_digital_id(entry_id: str) -> bool:
    async with async_session_factory() as session:
        inst = await session.get(DigitalId, int(entry_id))
        if not inst:
            return False
        await session.delete(inst)
        await session.commit()
        return True


def _entry_to_dict(entry: DigitalId) -> Dict[str, Any]:
    return {
        "id": str(entry.id),
        "user_id": str(entry.user_id),
        "user_id_hash": entry.user_id_hash,
        "digital_id": entry.digital_id,
        "broadband_id": entry.broadband_id,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }
