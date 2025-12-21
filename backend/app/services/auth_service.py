from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId

from app.database import get_database
from app.models.user import UserInDB, UserRole
from app.models.auth import TokenData
from app.utils.security import verify_password, get_password_hash, create_access_token, decode_token
from app.config import settings


async def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate user with email and password"""
    db = get_database()
    user = await db.users.find_one({"email": email.lower()})
    
    if not user:
        return None
    
    if not verify_password(password, user["password_hash"]):
        return None
    
    # Update last login
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    return user


async def create_user_token(user: dict) -> dict:
    """Create access token for user"""
    token_data = {
        "sub": str(user["_id"]),
        "email": user["email"],
        "role": user["role"],
        "name": user["name"]
    }
    
    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": str(user["_id"]),
            "email": user["email"],
            "name": user["name"],
            "role": user["role"]
        }
    }


async def get_current_user_from_token(token: str) -> Optional[dict]:
    """Get current user from JWT token"""
    token_data = decode_token(token)
    
    if token_data is None or token_data.user_id is None:
        return None
    
    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(token_data.user_id)})
    
    if user is None:
        return None
    
    # Don't return password hash
    user["id"] = str(user["_id"])
    del user["password_hash"]
    
    return user


async def change_user_password(user_id: str, current_password: str, new_password: str) -> bool:
    """Change user password"""
    db = get_database()
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return False
    
    if not verify_password(current_password, user["password_hash"]):
        return False
    
    new_hash = get_password_hash(new_password)
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "password_hash": new_hash,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return result.modified_count > 0
