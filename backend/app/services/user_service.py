from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.models.user import UserCreate, UserUpdate, UserRole, UserStatus
from app.utils.security import get_password_hash
from app.utils.helpers import serialize_doc, serialize_docs, get_pagination


async def get_users(
    page: int = 1,
    page_size: int = 20,
    role: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Get all users with pagination and filters"""
    db = get_database()
    
    # Build query
    query = {}
    if role:
        query["role"] = role
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.users.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = db.users.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    users = await cursor.to_list(length=page_size)
    
    # Remove password hashes and serialize
    for user in users:
        user.pop("password_hash", None)
    
    return {
        "data": serialize_docs(users),
        "pagination": get_pagination(page, page_size, total)
    }


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    db = get_database()
    
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            user.pop("password_hash", None)
            return serialize_doc(user)
        return None
    except:
        return None


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email"""
    db = get_database()
    user = await db.users.find_one({"email": email.lower()})
    if user:
        return serialize_doc(user)
    return None


async def create_user(user_data: UserCreate) -> Dict[str, Any]:
    """Create a new user"""
    db = get_database()
    
    # Check if email exists
    existing = await db.users.find_one({"email": user_data.email.lower()})
    if existing:
        raise ValueError("Email already exists")
    
    now = datetime.utcnow()
    user_doc = {
        "email": user_data.email.lower(),
        "password_hash": get_password_hash(user_data.password),
        "name": user_data.name,
        "role": user_data.role.value,
        "phone": user_data.phone,
        "department": user_data.department,
        "location": user_data.location,
        "status": UserStatus.ACTIVE.value,
        "is_verified": False,
        "created_at": now,
        "updated_at": now,
        "last_login": None
    }
    
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    user_doc.pop("password_hash")
    
    return serialize_doc(user_doc)


async def update_user(user_id: str, user_data: UserUpdate) -> Optional[Dict[str, Any]]:
    """Update user"""
    db = get_database()
    
    update_dict = {k: v for k, v in user_data.model_dump().items() if v is not None}
    
    if not update_dict:
        return await get_user_by_id(user_id)
    
    # Convert enum to value if present
    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value
    
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    if result.modified_count > 0 or result.matched_count > 0:
        return await get_user_by_id(user_id)
    return None


async def delete_user(user_id: str) -> bool:
    """Delete user"""
    db = get_database()
    
    result = await db.users.delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count > 0


async def update_user_status(user_id: str, status: str) -> Optional[Dict[str, Any]]:
    """Update user status"""
    db = get_database()
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "status": status,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count > 0:
        return await get_user_by_id(user_id)
    return None


async def get_users_by_role(role: str) -> List[Dict[str, Any]]:
    """Get all users by role"""
    db = get_database()
    
    cursor = db.users.find({"role": role, "status": "active"})
    users = await cursor.to_list(length=100)
    
    for user in users:
        user.pop("password_hash", None)
    
    return serialize_docs(users)


async def get_user_stats() -> Dict[str, int]:
    """Get user statistics"""
    db = get_database()
    
    total = await db.users.count_documents({})
    active = await db.users.count_documents({"status": "active"})
    
    # Count by role
    by_role = {}
    for role in UserRole:
        count = await db.users.count_documents({"role": role.value})
        by_role[role.value] = count
    
    return {
        "total": total,
        "active": active,
        "by_role": by_role
    }
