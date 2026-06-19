from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import json

from app.database import get_db, row_to_dict, rows_to_list
from app.models.user import UserCreate, UserUpdate, UserRole, UserStatus
from app.utils.security import get_password_hash
from app.utils.helpers import get_pagination
from app.utils.roles import normalize_role


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def get_users(
    page: int = 1,
    page_size: int = 20,
    role: Optional[str] = None,
    roles_in: Optional[List[str]] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = None,
    parent_id: Optional[str] = None,
    parent_ids_in: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Get all users with pagination and filters"""
    # Short-circuit: if empty IN list, no results possible
    if parent_ids_in is not None and len(parent_ids_in) == 0:
        return {"data": [], "pagination": get_pagination(page, page_size, 0)}

    async with get_db() as db:
        conditions = []
        params = []
        
        if roles_in is not None:
            normalized_roles = []
            for item in roles_in:
                normalized = normalize_role(item)
                if normalized and normalized not in normalized_roles:
                    normalized_roles.append(normalized)

            if not normalized_roles:
                return {"data": [], "pagination": get_pagination(page, page_size, 0)}

            placeholders = ",".join(["?"] * len(normalized_roles))
            conditions.append(f"role IN ({placeholders})")
            params.extend(normalized_roles)
        elif role:
            conditions.append("role = ?")
            params.append(role)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if search:
            search_escaped = escape_like(search)
            search_like = f"%{search_escaped}%"
            search_field_map = {
                "name": "name",
                "email": "email",
                "role": "role",
                "phone": "phone",
                "department": "department",
                "location": "location",
            }
            normalized_search_by = str(search_by or "all").strip().lower()
            if normalized_search_by and normalized_search_by != "all" and normalized_search_by in search_field_map:
                conditions.append(f"{search_field_map[normalized_search_by]} LIKE ? ESCAPE '\\\\'")
                params.append(search_like)
            else:
                conditions.append("(name LIKE ? ESCAPE '\\\\' OR email LIKE ? ESCAPE '\\\\' OR role LIKE ? ESCAPE '\\\\' OR phone LIKE ? ESCAPE '\\\\' OR department LIKE ? ESCAPE '\\\\' OR location LIKE ? ESCAPE '\\\\')")
                params.extend([search_like, search_like, search_like, search_like, search_like, search_like])
        if parent_ids_in is not None:
            placeholders = ','.join('?' * len(parent_ids_in))
            conditions.append(f"parent_id IN ({placeholders})")
            params.extend(parent_ids_in)
        elif parent_id:
            conditions.append("parent_id = ?")
            params.append(int(parent_id))
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Get total count
        cursor = await db.execute(f"SELECT COUNT(*) as cnt FROM users WHERE {where_clause}", params)
        row = await cursor.fetchone()
        total = row[0] if row else 0
        
        # Get paginated results
        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"SELECT * FROM users WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = await cursor.fetchall()
        
        users = rows_to_list(rows)
        # Remove password hashes and parse permissions
        for user in users:
            user.pop("password_hash", None)
            user["role"] = normalize_role(user.get("role"))
            if user.get("permissions"):
                try:
                    user["permissions"] = json.loads(user["permissions"])
                except (json.JSONDecodeError, TypeError):
                    user["permissions"] = {}
        
        return {
            "data": users,
            "pagination": get_pagination(page, page_size, total)
        }


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (int(user_id),))
        row = await cursor.fetchone()
        if row:
            user = row_to_dict(row)
            user.pop("password_hash", None)
            user["role"] = normalize_role(user.get("role"))
            if user.get("permissions"):
                try:
                    user["permissions"] = json.loads(user["permissions"])
                except (json.JSONDecodeError, TypeError):
                    user["permissions"] = {}
            return user
        return None


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
        row = await cursor.fetchone()
        if row:
            return row_to_dict(row)
        return None


async def create_user(user_data: UserCreate, creator_role: str = "super_admin") -> Dict[str, Any]:
    """Create a new user"""
    async with get_db() as db:
        # Check if email exists
        cursor = await db.execute("SELECT id FROM users WHERE email = ?", (user_data.email.lower(),))
        existing = await cursor.fetchone()
        if existing:
            raise ValueError("Email already exists")

        # Enforce 5000 operator limit per cluster parent
        if user_data.role.value == "operator" and user_data.parent_id:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'operator' AND parent_id = ?",
                (int(user_data.parent_id),)
            )
            count_row = await cursor.fetchone()
            if count_row and count_row[0] >= 5000:
                raise ValueError("Cluster has reached the maximum limit of 5000 operators")
        
        now = datetime.now().replace(tzinfo=None).isoformat()
        permissions_json = json.dumps(user_data.permissions) if user_data.permissions else "{}"
        parent_id = int(user_data.parent_id) if user_data.parent_id else None
        
        cursor = await db.execute(
            """INSERT INTO users (email, password_hash, name, role, digital_id, broadband_id, phone, department, location,
                status, parent_id, permissions, theme, compact_mode, email_notifications,
                push_notifications, is_verified, created_at, updated_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_data.email.lower(),
                get_password_hash(user_data.password),
                user_data.name,
                user_data.role.value,
                user_data.digital_id,
                user_data.broadband_id,
                user_data.phone,
                user_data.department,
                user_data.location,
                UserStatus.ACTIVE.value,
                parent_id,
                permissions_json,
                user_data.theme or "light",
                1 if user_data.compact_mode else 0,
                1 if user_data.email_notifications is not False else 0,
                1 if user_data.push_notifications is not False else 0,
                0,
                now,
                now,
                None
            )
        )
        await db.commit()

        created_id = cursor.lastrowid
        if not created_id:
            cursor_id = await db.execute("SELECT LAST_INSERT_ID() as id")
            id_row = await cursor_id.fetchone()
            if id_row and id_row.get("id"):
                created_id = id_row.get("id")

        created_row = None
        if created_id:
            cursor_user = await db.execute("SELECT * FROM users WHERE id = ?", (int(created_id),))
            created_row = await cursor_user.fetchone()

        if not created_row:
            cursor_user = await db.execute("SELECT * FROM users WHERE email = ?", (user_data.email.lower(),))
            created_row = await cursor_user.fetchone()

        if created_row:
            user = row_to_dict(created_row)
            user.pop("password_hash", None)
            user["role"] = normalize_role(user.get("role"))
            if user.get("permissions"):
                try:
                    user["permissions"] = json.loads(user["permissions"])
                except (json.JSONDecodeError, TypeError):
                    user["permissions"] = {}
            return user

        return {
            "id": str(created_id) if created_id is not None else "",
            "email": user_data.email.lower(),
            "name": user_data.name,
            "role": normalize_role(user_data.role.value),
            "digital_id": user_data.digital_id,
            "broadband_id": user_data.broadband_id,
            "phone": user_data.phone,
            "department": user_data.department,
            "location": user_data.location,
            "status": UserStatus.ACTIVE.value,
            "parent_id": str(parent_id) if parent_id is not None else None,
            "permissions": user_data.permissions or {},
            "theme": user_data.theme or "light",
            "compact_mode": bool(user_data.compact_mode),
            "email_notifications": user_data.email_notifications is not False,
            "push_notifications": user_data.push_notifications is not False,
            "is_verified": False,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        }


async def update_user(user_id: str, user_data: UserUpdate) -> Optional[Dict[str, Any]]:
    """Update user"""
    async with get_db() as db:
        update_fields = []
        params = []
        
        data = user_data.model_dump(exclude_unset=True)
        
        field_mapping = {
            "name": "name",
            "digital_id": "digital_id",
            "broadband_id": "broadband_id",
            "phone": "phone",
            "department": "department",
            "location": "location",
            "theme": "theme",
        }
        
        for py_field, db_field in field_mapping.items():
            if py_field in data and data[py_field] is not None:
                update_fields.append(f"{db_field} = ?")
                params.append(data[py_field])
        
        if "status" in data and data["status"] is not None:
            update_fields.append("status = ?")
            params.append(data["status"].value if hasattr(data["status"], "value") else data["status"])
        
        for bool_field in ["compact_mode", "email_notifications", "push_notifications"]:
            if bool_field in data and data[bool_field] is not None:
                update_fields.append(f"{bool_field} = ?")
                params.append(1 if data[bool_field] else 0)
        
        if "permissions" in data and data["permissions"] is not None:
            update_fields.append("permissions = ?")
            params.append(json.dumps(data["permissions"]))
        
        if not update_fields:
            return await get_user_by_id(user_id)
        
        update_fields.append("updated_at = ?")
        params.append(datetime.now().replace(tzinfo=None).isoformat())
        params.append(int(user_id))
        
        await db.execute(
            f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?",
            params
        )
        await db.commit()
        
        return await get_user_by_id(user_id)


async def delete_user(user_id: str) -> bool:
    """Delete user"""
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM users WHERE id = ?", (int(user_id),))
        await db.commit()
        return cursor.rowcount > 0


async def update_user_status(user_id: str, status: str) -> Optional[Dict[str, Any]]:
    """Update user status"""
    async with get_db() as db:
        now = datetime.now().replace(tzinfo=None).isoformat()
        await db.execute(
            "UPDATE users SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, int(user_id))
        )
        await db.commit()
        return await get_user_by_id(user_id)


async def get_users_by_role(role: str) -> List[Dict[str, Any]]:
    """Get all users by role"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE role = ? AND status = 'active'",
            (normalize_role(role),)
        )
        rows = await cursor.fetchall()
        users = rows_to_list(rows)
        for user in users:
            user.pop("password_hash", None)
            user["role"] = normalize_role(user.get("role"))
        return users


async def get_user_stats() -> Dict[str, int]:
    """Get user statistics"""
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
        active = (await cursor.fetchone())[0]
        
        by_role = {}
        for role in UserRole:
            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE role = ?", (role.value,))
            by_role[role.value] = (await cursor.fetchone())[0]
        
        return {
            "total": total,
            "active": active,
            "by_role": by_role
        }


async def update_user_permissions(user_id: str, permissions: dict) -> Optional[Dict[str, Any]]:
    """Update user's custom permissions (admin only)"""
    async with get_db() as db:
        now = datetime.now().replace(tzinfo=None).isoformat()
        await db.execute(
            "UPDATE users SET permissions = ?, updated_at = ? WHERE id = ?",
            (json.dumps(permissions), now, int(user_id))
        )
        await db.commit()
        return await get_user_by_id(user_id)


async def reassign_user(
    user_id: str,
    target_user: Dict[str, Any],
    new_parent_id: str,
    new_parent: Dict[str, Any],
    performed_by: Dict[str, Any],
) -> Dict[str, Any]:
    target_role = normalize_role(target_user.get("role"))
    now = datetime.now().replace(tzinfo=None).isoformat()

    async with get_db() as db:
        await db.execute(
            "UPDATE users SET parent_id = ?, updated_at = ? WHERE id = ?",
            (int(new_parent_id), now, int(user_id))
        )
        await db.commit()

    result = {
        "message": f"{target_role.title()} {target_user.get('name')} reassigned to {new_parent.get('name')}",
        "data": {
            "user_id": user_id,
            "user_name": target_user.get("name"),
            "user_role": target_role,
            "old_parent_id": str(target_user.get("parent_id", "")),
            "new_parent_id": new_parent_id,
            "new_parent_name": new_parent.get("name"),
        }
    }

    return result


async def get_children_users(parent_id: str) -> List[Dict[str, Any]]:
    """Get all users that are children of a given parent"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE parent_id = ? ORDER BY created_at DESC",
            (int(parent_id),)
        )
        rows = await cursor.fetchall()
        users = rows_to_list(rows)
        for user in users:
            user.pop("password_hash", None)
            user["role"] = normalize_role(user.get("role"))
        return users
