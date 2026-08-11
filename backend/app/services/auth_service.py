from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
from jose import JWTError, jwt
from fastapi import HTTPException, status

from sqlalchemy import select, and_, or_, delete
from sqlalchemy.exc import IntegrityError

from app.core.cache_version import bump_cache_version
from app.database_sqlalchemy import async_session_factory
from app.db_models.auth import User, TokenBlacklist
from app.models.auth import TokenData
from app.utils.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
)
from app.config import settings
from app.utils.roles import normalize_role


MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def _parse_datetime(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def _strip_user(user_dict: dict) -> dict:
    user_dict["role"] = normalize_role(user_dict.get("role"))
    return user_dict


async def authenticate_user(login: str, password: str) -> Optional[dict]:
    """Authenticate user with email or phone and password"""
    async with async_session_factory() as session:
        q = select(User).where(
            or_(User.email == login.lower(), User.phone == login)
        )
        inst = (await session.execute(q)).scalar_one_or_none()

        if not inst:
            return None

        user = inst.to_dict()
        user["role"] = normalize_role(user.get("role"))

        locked_until_raw = user.get("locked_until")
        if locked_until_raw:
            locked_until = _parse_datetime(locked_until_raw)
            if locked_until and datetime.now().replace(tzinfo=None) < locked_until:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account temporarily locked. Try again later."
                )

        if not verify_password(password, user["password_hash"]):
            attempts = int(user.get("failed_login_attempts") or 0) + 1
            lock_time = None
            if attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                lock_time = (datetime.now().replace(tzinfo=None) + timedelta(minutes=LOCKOUT_DURATION_MINUTES))

            inst.failed_login_attempts = attempts
            inst.locked_until = lock_time
            await bump_cache_version(session)
            await session.commit()
            return None

        inst.failed_login_attempts = 0
        inst.locked_until = None
        inst.last_login = datetime.now().replace(tzinfo=None)
        await bump_cache_version(session)
        await session.commit()
        return user


async def create_user_token(user: dict) -> dict:
    """Create access and refresh tokens for user"""
    role = normalize_role(user.get("role"))
    token_data = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": role,
        "name": user.get("name", ""),
    }

    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(data=token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_expires_in": settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "name": user.get("name", ""),
            "role": role,
            "force_email_change": bool(user.get("force_email_change")),
            "force_password_change": bool(user.get("force_password_change")),
        },
    }


async def refresh_access_token(refresh_token: str) -> Optional[dict]:
    """Validate a refresh token and rotate it.

    On success the presented refresh token is blacklisted and a brand-new
    refresh token is issued alongside a fresh access token. This means a stolen
    refresh token can only be used once: any replay of a previously-used token
    fails the blacklist check below and is rejected.
    """
    if not verify_token_type(refresh_token, "refresh"):
        return None

    if await is_token_blacklisted(refresh_token):
        # Reuse of a token that has already been rotated (or revoked on logout).
        return None

    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    async with async_session_factory() as session:
        inst = await session.get(User, int(user_id))
        if not inst:
            return None

        user = _strip_user(inst.to_dict())

    # Rotate: the presented refresh token can no longer be reused. The atomic
    # blacklist insert is the authoritative single-use guard — if a concurrent
    # request already rotated (and blacklisted) this exact token, we lose the
    # race here and must reject the refresh.
    if not await blacklist_token(refresh_token):
        return None

    token_data = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "name": user.get("name", ""),
    }

    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    new_refresh_token = create_refresh_token(data=token_data)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_expires_in": settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    }


async def blacklist_token(token: str) -> bool:
    """Blacklist a JWT token until it expires.

    Returns True if this call newly blacklisted the token, or False if it was
    already blacklisted (e.g. a concurrent rotation or logout). The INSERT
    relies on the ``token_hash`` primary key, so a duplicate is rejected by the
    database instead of a separate check-then-write, closing the refresh-token
    race where two requests could both pass the pre-check.
    """
    now = datetime.now().replace(tzinfo=None)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp")
        if exp is not None:
            if isinstance(exp, (int, float)):
                expires_at = datetime.fromtimestamp(exp)
            elif isinstance(exp, str):
                expires_at = datetime.fromisoformat(exp.replace("Z", "+00:00")).replace(tzinfo=None)
    except (JWTError, ValueError, TypeError):
        pass

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    async with async_session_factory() as session:
        try:
            session.add(TokenBlacklist(
                token_hash=token_hash,
                expires_at=expires_at,
                created_at=now,
            ))
            await session.execute(
                delete(TokenBlacklist).where(TokenBlacklist.expires_at <= now)
            )
            await session.commit()
            return True
        except IntegrityError:
            # Token hash already exists — a concurrent request already
            # blacklisted this token. Expired-row cleanup will run on a
            # future call; nothing to do here.
            await session.rollback()
            return False


async def is_token_blacklisted(token: str) -> bool:
    """Check if a token hash exists in blacklist and is still active."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now().replace(tzinfo=None)

    async with async_session_factory() as session:
        await session.execute(
            delete(TokenBlacklist).where(TokenBlacklist.expires_at <= now)
        )
        stmt = select(TokenBlacklist.token_hash).where(TokenBlacklist.token_hash == token_hash).limit(1)
        row = (await session.execute(stmt)).scalar_one_or_none()
        await session.commit()
        return row is not None


async def get_current_user_from_token(token: str) -> Optional[dict]:
    """Get current user from JWT token"""
    if await is_token_blacklisted(token):
        return None

    token_data = decode_token(token)

    if token_data is None or token_data.user_id is None:
        return None

    async with async_session_factory() as session:
        inst = await session.get(User, int(token_data.user_id))
        if inst is None:
            return None

        user = _strip_user(inst.to_dict())

        if token_data.role and user.get("role") != token_data.role:
            return None

        user.pop("password_hash", None)
        return user


async def complete_forced_credential_update(
    user_id: str,
    current_password: str,
    new_email: str,
    new_phone: str,
    new_password: str,
) -> Optional[dict]:
    """Atomically update email, phone, and password for a force-change user."""
    async with async_session_factory() as session:
        inst = await session.get(User, int(user_id))
        if not inst:
            return None

        user = inst.to_dict()
        if not verify_password(current_password, user["password_hash"]):
            return None

        normalized_email = new_email.lower().strip()
        if normalized_email == user.get("email", "").lower().strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email must be changed from the seeded default",
            )

        existing_q = select(User.id).where(and_(User.email == normalized_email, User.id != int(user_id)))
        existing = (await session.execute(existing_q)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )

        existing_phone_q = select(User.id).where(and_(User.phone == new_phone.strip(), User.id != int(user_id)))
        if (await session.execute(existing_phone_q)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone already in use",
            )

        if verify_password(new_password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password",
            )

        now = datetime.now().replace(tzinfo=None)
        old_email = user.get("email", "")
        old_phone = user.get("phone", "")
        inst.email = normalized_email
        inst.phone = new_phone
        inst.password_hash = get_password_hash(new_password)
        inst.force_email_change = 0
        inst.force_password_change = 0
        inst.updated_at = now
        await bump_cache_version(session)
        await session.commit()

    async with async_session_factory() as session:
        inst = await session.get(User, int(user_id))
        if not inst:
            return None
        updated_user = _strip_user(inst.to_dict())
        updated_user.pop("password_hash", None)
        return updated_user


async def change_user_password(user_id: str, current_password: str, new_password: str) -> bool:
    """Change user password"""
    async with async_session_factory() as session:
        inst = await session.get(User, int(user_id))
        if not inst:
            return False

        user = inst.to_dict()
        if not verify_password(current_password, user["password_hash"]):
            return False

        inst.password_hash = get_password_hash(new_password)
        inst.updated_at = datetime.now().replace(tzinfo=None)
        await bump_cache_version(session)
        await session.commit()
        return True
