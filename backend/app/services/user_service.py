from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import select, func, and_, or_

from app.database_sqlalchemy import async_session_factory
from app.db_models.auth import User
from app.db_models.digital_id import DigitalIdentity
from app.models.user import UserCreate, UserUpdate, UserRole, UserStatus
from app.services.digital_id_service import (
    create_digital_identities_for_user as create_digital_identities,
    get_digital_identities_by_user,
    delete_digital_identities_by_user,
)
from app.utils.security import get_password_hash
from app.utils.helpers import get_pagination
from app.utils.roles import normalize_role


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _strip_user(user_dict: Dict[str, Any]) -> Dict[str, Any]:
    user_dict.pop("password_hash", None)
    user_dict["role"] = normalize_role(user_dict.get("role"))
    return user_dict


async def _attach_digital_ids_bulk(session, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach the full digital_identities list to each user record (single query)."""
    if not users:
        return users
    user_ids = [u["id"] for u in users]
    q = (
        select(DigitalIdentity)
        .where(DigitalIdentity.user_id.in_(user_ids))
        .order_by(DigitalIdentity.user_id, DigitalIdentity.is_primary.desc(), DigitalIdentity.created_at.desc())
    )
    rows = (await session.execute(q)).scalars().all()
    by_user: Dict[str, List[Dict[str, Any]]] = {}
    for entry in rows:
        key = str(entry.user_id)
        by_user.setdefault(key, []).append({
            "id": entry.id,
            "user_id": entry.user_id,
            "digital_id": entry.digital_id,
            "broadband_id": entry.broadband_id,
            "is_primary": bool(entry.is_primary),
            "created_at": entry.created_at.isoformat() if hasattr(entry.created_at, "isoformat") else str(entry.created_at),
        })
    for u in users:
        u["digital_ids"] = by_user.get(str(u["id"]), [])
    return users


async def _attach_creator_info_bulk(session, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach created_by_name / created_by_email to each user record (single query)."""
    if not users:
        return users
    creator_ids = {u["created_by"] for u in users if u.get("created_by")}
    by_id: Dict[str, Dict[str, Any]] = {}
    if creator_ids:
        rows = (await session.execute(
            select(User).where(User.id.in_(list(creator_ids)))
        )).scalars().all()
        for entry in rows:
            by_id[str(entry.id)] = {
                "name": entry.name,
                "email": entry.email,
                "role": normalize_role(entry.role),
            }
    for u in users:
        creator = by_id.get(str(u.get("created_by") or ""))
        if creator:
            u["created_by_name"] = creator["name"]
            u["created_by_email"] = creator["email"]
            u["created_by_role"] = creator["role"]
        else:
            u["created_by_name"] = None
            u["created_by_email"] = None
            u["created_by_role"] = None
    return users


async def get_users(
    page: int = 1,
    page_size: int = 20,
    role: Optional[str] = None,
    roles_in: Optional[List[str]] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    parent_id: Optional[str] = None,
    parent_ids_in: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Get all users with pagination and filters"""
    if parent_ids_in is not None and len(parent_ids_in) == 0:
        return {"data": [], "pagination": get_pagination(page, page_size, 0)}

    async with async_session_factory() as session:
        conditions = []

        if roles_in is not None:
            normalized_roles = []
            for item in roles_in:
                normalized = normalize_role(item)
                if normalized and normalized not in normalized_roles:
                    normalized_roles.append(normalized)
            if not normalized_roles:
                return {"data": [], "pagination": get_pagination(page, page_size, 0)}
            conditions.append(User.role.in_(normalized_roles))
        elif role:
            conditions.append(User.role == role)
        if search:
            search_escaped = escape_like(search)
            search_like = f"%{search_escaped}%"
            search_field_map = {
                "name": User.name, "email": User.email, "role": User.role,
                "phone": User.phone, "address": User.address, "designation": User.designation,
                "pincode": User.pincode,
            }
            identity_conditions = {
                "digital_id": User.id.in_(
                    select(DigitalIdentity.user_id).where(
                        DigitalIdentity.digital_id.like(search_like, escape="\\")
                    )
                ),
                "broadband_id": User.id.in_(
                    select(DigitalIdentity.user_id).where(
                        DigitalIdentity.broadband_id.like(search_like, escape="\\")
                    )
                ),
            }
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                conditions.append(search_field_map[normalized_search_by].like(search_like, escape="\\"))
            elif normalized_search_by in identity_conditions:
                conditions.append(identity_conditions[normalized_search_by])
            else:
                conditions.append(or_(
                    User.name.like(search_like, escape="\\"),
                    User.email.like(search_like, escape="\\"),
                    User.role.like(search_like, escape="\\"),
                    User.phone.like(search_like, escape="\\"),
                    User.address.like(search_like, escape="\\"),
                    User.designation.like(search_like, escape="\\"),
                    User.pincode.like(search_like, escape="\\"),
                    identity_conditions["digital_id"],
                    identity_conditions["broadband_id"],
                ))
        if parent_ids_in is not None:
            conditions.append(User.parent_id.in_(parent_ids_in))
        elif parent_id:
            conditions.append(User.parent_id == int(parent_id))

        where = and_(*conditions) if conditions else True

        count_q = select(func.count()).select_from(User).where(where)
        total = (await session.execute(count_q)).scalar()

        offset = (page - 1) * page_size
        q = (
            select(User)
            .where(where)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await session.execute(q)).scalars().all()

        users = [_strip_user(r.to_dict()) for r in rows]
        await _attach_digital_ids_bulk(session, users)
        await _attach_creator_info_bulk(session, users)

        return {
            "data": users,
            "pagination": get_pagination(page, page_size, total),
        }


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    async with async_session_factory() as session:
        inst = await session.get(User, int(user_id))
        if not inst:
            return None
        user = _strip_user(inst.to_dict())
    user["digital_ids"] = await get_digital_identities_by_user(int(user_id))
    async with async_session_factory() as session:
        await _attach_creator_info_bulk(session, [user])
    return user


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email"""
    async with async_session_factory() as session:
        q = select(User).where(User.email == email.lower())
        inst = (await session.execute(q)).scalar_one_or_none()
        if not inst:
            return None
        return inst.to_dict()


async def create_user(user_data: UserCreate, creator_id: Optional[int] = None) -> Dict[str, Any]:
    """Create a new user"""
    async with async_session_factory() as session:
        existing = (
            await session.execute(select(User.id).where(User.email == user_data.email.lower()))
        ).scalar_one_or_none()
        if existing:
            raise ValueError("Email already exists")

        if user_data.role.value == "operator" and user_data.parent_id:
            count_q = select(func.count()).select_from(User).where(
                and_(User.role == "operator", User.parent_id == int(user_data.parent_id))
            )
            count = (await session.execute(count_q)).scalar()
            if count >= 5000:
                raise ValueError("Cluster has reached the maximum limit of 5000 operators")

        # Digital / broadband IDs must be unique across all users.
        additional_ids = (
            [d.strip() for d in user_data.additional_digital_ids.split("|") if d.strip()]
            if user_data.additional_digital_ids
            else None
        )
        digital_values = ([user_data.digital_id] if user_data.digital_id else []) + (additional_ids or [])
        digital_values = [v for v in digital_values if v and v.strip()]
        broadband_values = [user_data.broadband_id] if user_data.broadband_id and user_data.broadband_id.strip() else []
        if digital_values or broadband_values:
            from app.services.digital_id_service import check_identity_conflicts, _identity_conflict_error
            conflicts = await check_identity_conflicts(session, digital_values, broadband_values)
            if conflicts["digital"] or conflicts["broadband"]:
                raise ValueError(_identity_conflict_error(conflicts))

        now = datetime.now().replace(tzinfo=None)
        parent_id = int(user_data.parent_id) if user_data.parent_id else None

        u = User(
            email=user_data.email.lower(),
            name=user_data.name,
            password_hash=get_password_hash(user_data.password),
            role=user_data.role.value,
            status=user_data.status.value if isinstance(user_data.status, UserStatus) else "active",
            phone=user_data.phone,
            designation=user_data.designation,
            address=user_data.address,
            pincode=user_data.pincode,
            parent_id=parent_id,
            created_by=creator_id,
            created_at=now,
            updated_at=now,
            last_login=None,
        )
        session.add(u)
        await session.flush()
        await session.commit()

        created_id = u.id

        # Store digital identities
        await create_digital_identities(
            user_id=u.id,
            primary_digital_id=user_data.digital_id,
            primary_broadband_id=user_data.broadband_id,
            additional_digital_ids=additional_ids,
        )

        if created_id:
            inst = await session.get(User, int(created_id))
            if inst:
                return await _attach_digital_ids(created_id, _strip_user(inst.to_dict()))

        result = {
            "id": str(created_id) if created_id is not None else "",
            "email": user_data.email.lower(),
            "name": user_data.name,
            "role": normalize_role(user_data.role.value),
            "status": "active",
            "phone": user_data.phone,
            "designation": user_data.designation,
            "address": user_data.address,
            "pincode": user_data.pincode,
            "parent_id": str(parent_id) if parent_id is not None else None,
            "created_by": creator_id,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        }
        result["digital_ids"] = await get_digital_identities_by_user(int(created_id or 0))
        return result


async def _attach_digital_ids(user_id: int, user_dict: Dict[str, Any]) -> Dict[str, Any]:
    user_dict["digital_ids"] = await get_digital_identities_by_user(user_id)
    return user_dict


async def update_user(user_id: str, user_data: UserUpdate) -> Optional[Dict[str, Any]]:
    """Update user"""
    async with async_session_factory() as session:
        inst = await session.get(User, int(user_id))
        if not inst:
            return None

        data = user_data.model_dump(exclude_unset=True)
        changed = False

        field_mapping = {
            "name": "name", "phone": "phone",
            "designation": "designation", "address": "address", "pincode": "pincode",
            "status": "status",
        }

        for py_field, db_attr in field_mapping.items():
            if py_field in data and data[py_field] is not None:
                setattr(inst, db_attr, data[py_field])
                changed = True

        if not changed:
            return await _attach_digital_ids(int(user_id), _strip_user(inst.to_dict()))

        inst.updated_at = datetime.now().replace(tzinfo=None)
        await session.commit()
        return await _attach_digital_ids(int(user_id), _strip_user(inst.to_dict()))


async def delete_user(user_id: str) -> bool:
    """Delete user and associated digital identities"""
    async with async_session_factory() as session:
        inst = await session.get(User, int(user_id))
        if not inst:
            return False
        await session.delete(inst)
        await session.commit()
    await delete_digital_identities_by_user(int(user_id))
    return True


async def get_users_by_role(role: str) -> List[Dict[str, Any]]:
    """Get all users by role"""
    async with async_session_factory() as session:
        q = (
            select(User)
            .where(User.role == normalize_role(role))
            .limit(5000)
        )
        rows = (await session.execute(q)).scalars().all()
        return [_strip_user(r.to_dict()) for r in rows]


async def get_user_stats() -> Dict[str, int]:
    """Get user statistics"""
    async with async_session_factory() as session:
        q = select(User.role, func.count().label("cnt"))
        q = q.group_by(User.role)
        rows = (await session.execute(q)).all()

        total = 0
        by_role: Dict[str, int] = {}
        for row in rows:
            role = str(row.role)
            count = int(row.cnt)
            total += count
            by_role[role] = by_role.get(role, 0) + count

        return {"total": total, "by_role": by_role}


async def reassign_user(
    user_id: str,
    target_user: Dict[str, Any],
    new_parent_id: str,
    new_parent: Dict[str, Any],
    performed_by: Dict[str, Any],
) -> Dict[str, Any]:
    """Reassign a user to a new parent"""
    now = datetime.now().replace(tzinfo=None)
    async with async_session_factory() as session:
        inst = await session.get(User, int(user_id))
        if inst:
            inst.parent_id = int(new_parent_id)
            inst.updated_at = now
            await session.commit()

    target_role = normalize_role(target_user.get("role"))
    return {
        "message": f"{target_role.title()} {target_user.get('name') or target_user.get('email')} reassigned to {new_parent.get('name') or new_parent.get('email')}",
        "data": {
            "user_id": user_id,
            "user_name": target_user.get("name") or target_user.get("email"),
            "user_role": target_role,
            "old_parent_id": str(target_user.get("parent_id", "")),
            "new_parent_id": new_parent_id,
            "new_parent_name": new_parent.get("name") or new_parent.get("email"),
        },
    }


async def get_children_users(parent_id: str) -> List[Dict[str, Any]]:
    """Get all users that are children of a given parent"""
    async with async_session_factory() as session:
        q = select(User).where(User.parent_id == int(parent_id)).order_by(User.created_at.desc())
        rows = (await session.execute(q)).scalars().all()
        return [_strip_user(r.to_dict()) for r in rows]
