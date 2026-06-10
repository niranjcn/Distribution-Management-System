from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import json
from jose import JWTError, jwt
from fastapi import HTTPException, status

from app.database import get_db, row_to_dict
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


async def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate user with email and password"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower(),)
        )
        row = await cursor.fetchone()
        
        if not row:
            return None
        
        user = row_to_dict(row)
        user["role"] = normalize_role(user.get("role"))

        locked_until_raw = user.get("locked_until")
        if locked_until_raw:
            locked_until = _parse_datetime(locked_until_raw)
            if locked_until and datetime.now(timezone.utc).replace(tzinfo=None) < locked_until:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account temporarily locked. Try again later."
                )

            await db.execute(
                "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
                (int(user["id"]),)
            )
            await db.commit()
            user["failed_login_attempts"] = 0
            user["locked_until"] = None
        
        if not verify_password(password, user["password_hash"]):
            attempts = int(user.get("failed_login_attempts") or 0) + 1
            lock_time = None
            if attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                lock_time = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)).isoformat()

            await db.execute(
                "UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE id = ?",
                (attempts, lock_time, int(user["id"]))
            )
            await db.commit()
            return None

        await db.execute(
            "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
            (int(user["id"]),)
        )
        
        # Update last login
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        await db.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (now, int(user["id"]))
        )
        await db.commit()
        
        return user


async def create_user_token(user: dict) -> dict:
    """Create access and refresh tokens for user"""
    role = normalize_role(user.get("role"))
    token_data = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": role,
        "name": user["name"]
    }
    
    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
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
            "name": user["name"],
            "role": role,
            "force_email_change": bool(user.get("force_email_change")),
            "force_password_change": bool(user.get("force_password_change")),
        }
    }


async def refresh_access_token(refresh_token: str) -> Optional[dict]:
    """Validate refresh token and issue a new access token."""
    if not verify_token_type(refresh_token, "refresh"):
        return None

    if await is_token_blacklisted(refresh_token):
        return None

    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE id = ?",
            (int(user_id),)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        user = row_to_dict(row)
        user["role"] = normalize_role(user.get("role"))
        if user.get("status") != "active":
            return None

    token_data = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "name": user["name"],
    }

    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def blacklist_token(token: str) -> None:
    """Blacklist a JWT token until it expires."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp")
        if exp is not None:
            # jose can return exp as epoch seconds; support datetime-like values defensively.
            if isinstance(exp, (int, float)):
                expires_at = datetime.utcfromtimestamp(exp)
            elif isinstance(exp, str):
                expires_at = datetime.fromisoformat(exp.replace("Z", "+00:00")).replace(tzinfo=None)
    except (JWTError, ValueError, TypeError):
        # If token decode fails during logout, keep conservative TTL fallback.
        pass

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    async with get_db() as db:
        await db.execute(
            """INSERT OR IGNORE INTO token_blacklist (token_hash, expires_at, created_at)
               VALUES (?, ?, ?)""",
            (token_hash, expires_at.isoformat(), now.isoformat())
        )
        await db.execute(
            "DELETE FROM token_blacklist WHERE expires_at <= ?",
            (now.isoformat(),)
        )
        await db.commit()


async def is_token_blacklisted(token: str) -> bool:
    """Check if a token hash exists in blacklist and is still active."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    async with get_db() as db:
        await db.execute(
            "DELETE FROM token_blacklist WHERE expires_at <= ?",
            (now_iso,)
        )
        cursor = await db.execute(
            "SELECT 1 FROM token_blacklist WHERE token_hash = ? LIMIT 1",
            (token_hash,)
        )
        row = await cursor.fetchone()
        await db.commit()
        return row is not None


async def get_current_user_from_token(token: str) -> Optional[dict]:
    """Get current user from JWT token"""
    if await is_token_blacklisted(token):
        return None

    token_data = decode_token(token)
    
    if token_data is None or token_data.user_id is None:
        return None
    
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE id = ?",
            (int(token_data.user_id),)
        )
        row = await cursor.fetchone()
        
        if row is None:
            return None
        
        user = row_to_dict(row)
        user["role"] = normalize_role(user.get("role"))

        if token_data.role and user.get("role") != token_data.role:
            return None
        
        # Parse permissions JSON
        if user.get("permissions"):
            try:
                user["permissions"] = json.loads(user["permissions"])
            except (json.JSONDecodeError, TypeError):
                user["permissions"] = {}
        else:
            user["permissions"] = {}
        
        # Don't return password hash
        user.pop("password_hash", None)
        
        return user


async def complete_forced_credential_update(
    user_id: str,
    current_password: str,
    new_email: str,
    new_password: str,
) -> Optional[dict]:
    """Atomically update email and password for a force-change user."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE id = ?",
            (int(user_id),),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        user = row_to_dict(row)
        if not verify_password(current_password, user["password_hash"]):
            return None

        normalized_email = new_email.lower().strip()
        if normalized_email == user.get("email", "").lower().strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email must be changed from the seeded default",
            )

        email_cursor = await db.execute(
            "SELECT id FROM users WHERE email = ? AND id != ?",
            (normalized_email, int(user_id)),
        )
        existing = await email_cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )

        if verify_password(new_password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password",
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        await db.execute(
            """UPDATE users
            SET email = ?, password_hash = ?, force_email_change = 0, force_password_change = 0, updated_at = ?
            WHERE id = ?""",
            (normalized_email, get_password_hash(new_password), now, int(user_id)),
        )
        await db.commit()

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (int(user_id),))
        updated_row = await cursor.fetchone()
        if not updated_row:
            return None
        updated_user = row_to_dict(updated_row)
        updated_user["role"] = normalize_role(updated_user.get("role"))
        updated_user.pop("password_hash", None)
        return updated_user


async def change_user_password(user_id: str, current_password: str, new_password: str) -> bool:
    """Change user password"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE id = ?",
            (int(user_id),)
        )
        row = await cursor.fetchone()
        
        if not row:
            return False
        
        user = row_to_dict(row)
        
        if not verify_password(current_password, user["password_hash"]):
            return False
        
        new_hash = get_password_hash(new_password)
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        
        await db.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (new_hash, now, int(user_id))
        )
        await db.commit()
        
        return True
