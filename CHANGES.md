# Step-by-Step Change Guide

Apply these changes in order to a fresh copy of the repository.

---

## 1. Docker Compose — `docker-compose.yml`

### 1.1 MySQL Healthcheck

**File path:** `docker-compose.yml` lines 31-35

**Change:** Replace the MySQL healthcheck and startup parameters.

```yaml
# BEFORE (lines 31-35)
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h localhost -uroot -p$$MYSQL_ROOT_PASSWORD"]
      interval: 10s
      timeout: 5s
      retries: 15
      start_period: 90s

# AFTER
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "--silent"]
      interval: 10s
      timeout: 5s
      retries: 20
      start_period: 120s
```

### 1.2 MySQL Buffer Pool

**File path:** `docker-compose.yml` line 19

**Change:** Reduce memory allocation.

```yaml
# BEFORE
      - "--innodb_buffer_pool_size=2G"
# AFTER
      - "--innodb_buffer_pool_size=512M"
```

### 1.3 Backend Healthcheck (NEW block)

**File path:** `docker-compose.yml` — insert after the `depends_on` block of the `backend` service (after line 59).

**Change:** Add a healthcheck to the backend service.

```yaml
# INSERT after `condition: service_healthy` under backend depends_on
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]
      interval: 10s
      timeout: 5s
      retries: 15
      start_period: 60s
```

### 1.4 Frontend depends_on

**File path:** `docker-compose.yml` lines 116-118 (inside `frontend` service)

**Change:** Make frontend wait for backend health.

```yaml
# BEFORE
    depends_on:
      - backend

# AFTER
    depends_on:
      backend:
        condition: service_healthy
```

### 1.5 Reverse-Proxy depends_on

**File path:** `docker-compose.yml` lines 141-144 (inside `reverse-proxy` service)

**Change:** Make reverse-proxy wait for backend health + frontend start.

```yaml
# BEFORE
    depends_on:
      - backend
      - frontend

# AFTER
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_started
```

---

## 2. User Schema — `backend/app/database.py`

### 2.1 CREATE TABLE Statement — Remove Old Columns

**File path:** `backend/app/database.py` inside the `users` CREATE TABLE statement (around line 250)

**Change:** Replace the users table columns.

```
# REMOVE these columns from CREATE TABLE:
    digital_id VARCHAR(128),
    broadband_id VARCHAR(128),
    cluster_id VARCHAR(128),        (if present)
    operator_id VARCHAR(128),       (if present)
    department VARCHAR(255),
    location VARCHAR(255),
    theme VARCHAR(32) DEFAULT 'light',
    compact_mode TINYINT(1) DEFAULT 0,
    email_notifications TINYINT(1) DEFAULT 1,
    push_notifications TINYINT(1) DEFAULT 1,
    is_verified TINYINT(1) DEFAULT 0,

# REPLACE with:
    address VARCHAR(255),
    designation VARCHAR(255),
    pincode VARCHAR(64),
```

### 2.2 New Table — `digital_identities`

**File path:** `backend/app/database.py` — add a new entry in the `CREATE_TABLE_STATEMENTS` list.

**Change:** Add a new CREATE TABLE string to the list (order doesn't matter, but place it logically near the users table entry).

```python
"""
CREATE TABLE IF NOT EXISTS digital_identities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    digital_id VARCHAR(128),
    broadband_id VARCHAR(128),
    is_primary TINYINT(1) DEFAULT 0,
    created_at VARCHAR(64) NOT NULL,
    INDEX idx_digital_identities_user_id(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
```

### 2.3 Migration Statements in `init_db()`

**File path:** `backend/app/database.py` inside the `init_db()` function (around line 720)

**Change:** Replace the migration ALTER TABLE statements block.

```
# REMOVE these lines:
"ALTER TABLE users ADD COLUMN force_password_change TINYINT(1) DEFAULT 0",
"ALTER TABLE users ADD COLUMN digital_id VARCHAR(128)",
"ALTER TABLE users ADD COLUMN broadband_id VARCHAR(128)",
"ALTER TABLE users ADD COLUMN cluster_id VARCHAR(128)",
"ALTER TABLE users ADD COLUMN operator_id VARCHAR(128)",
"CREATE UNIQUE INDEX idx_users_cluster_id ON users (cluster_id)",
"CREATE UNIQUE INDEX idx_users_operator_id ON users (operator_id)",

# REPLACE WITH:
"DROP INDEX IF EXISTS idx_users_cluster_id ON users",
"DROP INDEX IF EXISTS idx_users_operator_id ON users",
"ALTER TABLE users DROP COLUMN IF EXISTS cluster_id",
"ALTER TABLE users DROP COLUMN IF EXISTS operator_id",
"ALTER TABLE users ADD COLUMN address VARCHAR(255)",
"ALTER TABLE users ADD COLUMN designation VARCHAR(255)",
"ALTER TABLE users ADD COLUMN pincode VARCHAR(64)",
"ALTER TABLE users DROP COLUMN IF EXISTS digital_id",
"ALTER TABLE users DROP COLUMN IF EXISTS broadband_id",
"ALTER TABLE users DROP COLUMN IF EXISTS department",
"ALTER TABLE users DROP COLUMN IF EXISTS location",
"ALTER TABLE users DROP COLUMN IF EXISTS theme",
"ALTER TABLE users DROP COLUMN IF EXISTS compact_mode",
"ALTER TABLE users DROP COLUMN IF EXISTS email_notifications",
"ALTER TABLE users DROP COLUMN IF EXISTS push_notifications",
"ALTER TABLE users DROP COLUMN IF EXISTS is_verified",
"CREATE TABLE IF NOT EXISTS digital_identities (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, digital_id VARCHAR(128), broadband_id VARCHAR(128), is_primary TINYINT(1) DEFAULT 0, created_at VARCHAR(64) NOT NULL, INDEX idx_digital_identities_user_id(user_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
"CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications (user_id, created_at DESC)",
```

### 2.4 `row_to_dict()` — Remove Boolean Coercion

**File path:** `backend/app/database.py` in the `row_to_dict()` function (around line 883)

**Change:** Remove these keys from the boolean coercion loop.

```python
# REMOVE from the key list:
"compact_mode",
"email_notifications",
"push_notifications",
"is_verified",
```

---

## 3. User Models — `backend/app/models/user.py`

### 3.1 `UserBase` Class

**File path:** `backend/app/models/user.py` lines 26-38

**Change:** Replace the entire field set.

```python
# REMOVE these fields:
    digital_id: Optional[str] = Field(default=None, max_length=128)
    broadband_id: Optional[str] = Field(default=None, max_length=128)
    cluster_id: Optional[str] = Field(default=None, max_length=128)
    operator_id: Optional[str] = Field(default=None, max_length=128)
    phone: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    parent_id: Optional[str] = None
    theme: Optional[str] = "light"
    compact_mode: Optional[bool] = False
    email_notifications: Optional[bool] = True
    push_notifications: Optional[bool] = True

# REPLACE WITH:
    address: Optional[str] = None
    designation: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    parent_id: Optional[str] = None
```

### 3.2 `UserCreate` Class

**File path:** `backend/app/models/user.py` — after `UserBase` fields, inside `UserCreate`.

**Change:** Add these extra fields to the `UserCreate` class (not in `UserBase`).

```python
# ADD after password field:
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None
    additional_digital_ids: Optional[str] = None  # pipe-separated for operators
```

### 3.3 `UserUpdate` Class

**File path:** `backend/app/models/user.py` lines 60-78

**Change:** Replace the field set.

```python
# REMOVE these fields:
    digital_id: Optional[str] = Field(default=None, max_length=128)
    broadband_id: Optional[str] = Field(default=None, max_length=128)
    cluster_id: Optional[str] = Field(default=None, max_length=128)
    operator_id: Optional[str] = Field(default=None, max_length=128)
    phone: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    status: Optional[UserStatus] = None
    theme: Optional[str] = None
    compact_mode: Optional[bool] = None
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    permissions: Optional[Dict[str, bool]] = None

# REPLACE WITH:
    address: Optional[str] = None
    designation: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[UserStatus] = None
    permissions: Optional[Dict[str, bool]] = None
```

### 3.4 `UserResponse` Class

**File path:** `backend/app/models/user.py`

**Change:** Replace the field set and add `digital_identities` field.

```python
# REMOVE these fields:
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None
    cluster_id: Optional[str] = None
    operator_id: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    parent_id: Optional[str] = None
    status: UserStatus
    is_verified: bool
    permissions: Optional[Dict[str, bool]] = None
    created_at: str
    updated_at: str

# REPLACE WITH:
    address: Optional[str] = None
    designation: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    parent_id: Optional[str] = None
    status: UserStatus
    permissions: Optional[Dict[str, bool]] = None
    created_at: str
    updated_at: str
    digital_identities: Optional[List[Dict[str, Any]]] = None
```

---

## 4. User Service — `backend/app/services/user_service.py`

### 4.1 Add Logger Import

**File path:** top of `user_service.py`

```python
# ADD after existing imports:
import logging
logger = logging.getLogger(__name__)
```

### 4.2 `get_users()` Function — Search Fields

Find the `search_field_map` dictionary and remove `department` and `location` entries. Also update the fallback search condition.

```python
# In search_field_map, REMOVE:
"department": "department",
"location": "location",

# In the fallback else clause, change:
# BEFORE:
conditions.append("(name LIKE ? ESCAPE '\\\\' OR email LIKE ? ESCAPE '\\\\' OR role LIKE ? ESCAPE '\\\\' OR phone LIKE ? ESCAPE '\\\\' OR department LIKE ? ESCAPE '\\\\' OR location LIKE ? ESCAPE '\\\\')")
params.extend([search_like, search_like, search_like, search_like, search_like, search_like])

# AFTER:
conditions.append("(name LIKE ? ESCAPE '\\\\' OR email LIKE ? ESCAPE '\\\\' OR role LIKE ? ESCAPE '\\\\' OR phone LIKE ? ESCAPE '\\\\')")
params.extend([search_like, search_like, search_like, search_like])
```

### 4.3 `create_user()` Function

**File path:** inside `create_user()` — the INSERT statement and the response dict.

**Step 1 — INSERT statement (around line 165):**

```python
# BEFORE:
cursor = await db.execute(
    """INSERT INTO users (email, password_hash, name, role, digital_id, broadband_id, cluster_id, operator_id, phone, department, location,
        status, parent_id, permissions, theme, compact_mode, email_notifications,
        push_notifications, is_verified, created_at, updated_at, last_login)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (
        user_data.email.lower(),
        get_password_hash(user_data.password),
        user_data.name,
        user_data.role.value,
        user_data.digital_id,
        user_data.broadband_id,
        user_data.cluster_id,
        user_data.operator_id,
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
    ),
)

# AFTER:
cursor = await db.execute(
    """INSERT INTO users (email, password_hash, name, role, address, designation, pincode, phone,
        status, parent_id, permissions, created_at, updated_at, last_login)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (
        user_data.email.lower(),
        get_password_hash(user_data.password),
        user_data.name,
        user_data.role.value,
        user_data.address,
        user_data.designation,
        user_data.pincode,
        user_data.phone,
        UserStatus.ACTIVE.value,
        parent_id,
        permissions_json,
        now,
        now,
        None
    ),
)
```

**Step 2 — Update imports (top of file):**

```python
# ADD to imports:
from app.models.digital_id import DigitalIdentityCreate
from app.services.digital_id_service import create_digital_identities_for_user as create_digital_identities
```

**Step 3 — Replace the old `digital_id` insertion block:**

```python
# FIND this code (old digital_id_service call):
        # Store digital_id / broadband_id if provided
        if user_data.digital_id or user_data.broadband_id:
            await digital_id_service.create_digital_id_for_user(
                user_id=u.id,
                email=user_data.email.lower(),
                phone=user_data.phone,
                digital_id=user_data.digital_id,
                broadband_id=user_data.broadband_id,
            )

# REPLACE WITH:
        # Store digital identities
        additional_ids = (
            [d.strip() for d in user_data.additional_digital_ids.split("|") if d.strip()]
            if user_data.additional_digital_ids
            else None
        )
        await create_digital_identities(
            user_id=u.id,
            primary_digital_id=user_data.digital_id,
            primary_broadband_id=user_data.broadband_id,
            additional_digital_ids=additional_ids,
        )
```

**Step 3 — Update the `return` dict (around line 220):**

```python
# Change the fallback return to use user_id_val and new fields:
        return {
            "id": str(user_id_val) if user_id_val is not None else "",
            "email": user_data.email.lower(),
            "name": user_data.name,
            "role": normalize_role(user_data.role.value),
            "address": user_data.address,
            "designation": user_data.designation,
            "pincode": user_data.pincode,
            "phone": user_data.phone,
            "status": UserStatus.ACTIVE.value,
            "parent_id": str(parent_id) if parent_id is not None else None,
            "permissions": user_data.permissions or {},
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        }
```

### 4.4 `update_user()` Function

**File path:** inside `update_user()` — the field mapping and SET clause.

```python
# Change field_mapping:
# BEFORE:
field_mapping = {
    "name": "name",
    "digital_id": "digital_id",
    "broadband_id": "broadband_id",
    "cluster_id": "cluster_id",
    "operator_id": "operator_id",
    "phone": "phone",
    "department": "department",
    "location": "location",
    "theme": "theme",
}

# AFTER:
field_mapping = {
    "name": "name",
    "address": "address",
    "designation": "designation",
    "pincode": "pincode",
    "phone": "phone",
}
```

**Remove the boolean field update block (for `compact_mode`, `email_notifications`, `push_notifications`):**

```python
# DELETE this entire block:
        for bool_field in ["compact_mode", "email_notifications", "push_notifications"]:
            if bool_field in data and data[bool_field] is not None:
                update_fields.append(f"{bool_field} = ?")
                params.append(1 if data[bool_field] else 0)
```

---

## 5. Digital Identity Models & Service

### 5.1 Pydantic Models — `backend/app/models/digital_id.py`

**Change:** Add `DigitalIdentityCreate` and `DigitalIdentityResponse` models for the new `digital_identities` table.

```python
# ADD after the existing DigitalIdResponse class:

class DigitalIdentityCreate(BaseModel):
    user_id: int
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None
    is_primary: bool = False


class DigitalIdentityResponse(BaseModel):
    id: int
    user_id: int
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None
    is_primary: bool = False
    created_at: str
```

### 5.2 SQLAlchemy Model — `backend/app/db_models/digital_id.py`

**Change:** Add the `DigitalIdentity` SQLAlchemy model for the new table.

```python
# ADD after the existing DigitalId class:

class DigitalIdentity(Base):
    __tablename__ = "digital_identities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    digital_id = Column(String(128), nullable=True)
    broadband_id = Column(String(128), nullable=True)
    is_primary = Column(SqlBool, default=False)
    created_at = Column(DateTime, nullable=False)
```

### 5.3 Service Functions — `backend/app/services/digital_id_service.py`

**Change:** Add new functions for the `digital_identities` table (keep existing `digital_ids` functions for backward compatibility).

```python
# ADD after the existing legacy functions:

# ─── New digital_identities table ───

async def create_digital_identity(data: DigitalIdentityCreate) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session_factory() as session:
        entry = DigitalIdentity(
            user_id=data.user_id,
            digital_id=data.digital_id,
            broadband_id=data.broadband_id,
            is_primary=data.is_primary,
            created_at=now,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return _identity_to_dict(entry)


async def create_digital_identities_for_user(
    user_id: int,
    primary_digital_id: Optional[str] = None,
    primary_broadband_id: Optional[str] = None,
    additional_digital_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Create primary + additional digital identities for a user.
    
    - `primary_digital_id` / `primary_broadband_id` → is_primary=True
    - `additional_digital_ids` list → each gets is_primary=False
    """
    created = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with async_session_factory() as session:
        if primary_digital_id or primary_broadband_id:
            entry = DigitalIdentity(
                user_id=user_id,
                digital_id=primary_digital_id,
                broadband_id=primary_broadband_id,
                is_primary=True,
                created_at=now,
            )
            session.add(entry)
            created.append(_identity_to_dict(entry))

        for did in (additional_digital_ids or []):
            entry = DigitalIdentity(
                user_id=user_id,
                digital_id=did,
                broadband_id=None,
                is_primary=False,
                created_at=now,
            )
            session.add(entry)
            created.append(_identity_to_dict(entry))

        await session.commit()
        for entry in created:
            session.refresh(entry)

    return created


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
```

### 5.4 Import Update — `backend/app/services/user_service.py`

**Change:** Update imports to use the new functions.

```python
# BEFORE:
from app.services import digital_id_service

# AFTER:
from app.models.digital_id import DigitalIdentityCreate
from app.services import digital_id_service
from app.services.digital_id_service import create_digital_identities_for_user as create_digital_identities
```


## 6. Seed Service (minor) — `backend/app/services/seed_service.py`

### File path: `seed_service.py` around line 65

**Change:** Update the INSERT statement to use the new column set.

```python
# BEFORE:
insert_cursor = await db.execute(
    """INSERT OR IGNORE INTO users (email, password_hash, name, role, force_email_change, force_password_change, phone, department, location,
        status, permissions, theme, compact_mode, email_notifications,
        push_notifications, is_verified, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (
        "admin@dms.com",
        get_password_hash(admin_password),
        "Super Admin",
        "super_admin",
        1,
        1,
        "",
        "IT",
        "Head Office",
        "active",
        "{}",
        "light",
        0,
        1,
        1,
        1,
        now,
        now
    ),
)

# AFTER:
insert_cursor = await db.execute(
    """INSERT OR IGNORE INTO users (email, password_hash, name, role, force_email_change, force_password_change, phone,
        status, permissions, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (
        "admin@dms.com",
        get_password_hash(admin_password),
        "Super Admin",
        "super_admin",
        1,
        1,
        "",
        "active",
        "{}",
        now,
        now
    ),
)
```

---

## 7. User Routes — `backend/app/routes/users.py`

### 7.1 `POST /users` (create_user) — Remove Role Restrictions

**File path:** around line 287

```python
# DELETE these ~10 lines:
    if target_role != SUB_DISTRIBUTOR:
        user_data = user_data.model_copy(update={"digital_id": None, "broadband_id": None})

    if target_role != CLUSTER:
        user_data = user_data.model_copy(update={"cluster_id": None})
    if target_role != OPERATOR:
        user_data = user_data.model_copy(update={"operator_id": None})
```

### 7.2 Operator Parent Validation

**File path:** around line 335

```python
# BEFORE — cluster-only parent validation:
    if target_role == OPERATOR:
        if not user_data.parent_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must select a cluster parent for operator")
        cluster = await user_service.get_user_by_id(user_data.parent_id)
        if not cluster or normalize_role(cluster.get("role")) != CLUSTER:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cluster selected")

# AFTER — cluster OR subdistributor parent:
    if target_role == OPERATOR:
        if not user_data.parent_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must select a cluster or subdistributor parent for operator")
        parent = await user_service.get_user_by_id(user_data.parent_id)
        if not parent or normalize_role(parent.get("role")) not in {CLUSTER, SUB_DISTRIBUTOR}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Operator parent must be a cluster or subdistributor")
```

### 7.3 Actor Branch Check (Subdistributor creating operator)

```python
# BEFORE:
    if actor_role == SUB_DISTRIBUTOR:
        if target_role == OPERATOR:
            cluster = await user_service.get_user_by_id(user_data.parent_id)
            if not cluster or not await _branch_contains_user(current_user.get("id"), cluster.get("id")):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected cluster is outside your branch")

# AFTER:
    if actor_role == SUB_DISTRIBUTOR and target_role == OPERATOR:
        parent = await user_service.get_user_by_id(user_data.parent_id)
        if not parent or not await _branch_contains_user(current_user.get("id"), parent.get("id")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected parent is outside your branch")
```

### 7.4 Actor Branch Check (Sub Distribution Manager creating operator)

```python
# BEFORE:
    if actor_role == SUB_DISTRIBUTION_MANAGER and target_role == OPERATOR:
        cluster = await user_service.get_user_by_id(user_data.parent_id)
        if not cluster or not await _branch_contains_user(current_user.get("id"), cluster.get("id")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected cluster is outside your branch")

# AFTER:
    if actor_role == SUB_DISTRIBUTION_MANAGER and target_role == OPERATOR:
        parent = await user_service.get_user_by_id(user_data.parent_id)
        if not parent or not await _branch_contains_user(current_user.get("id"), parent.get("id")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected parent is outside your branch")
```

### 7.5 `PATCH /users/{id}` (update_user) — Self-Service

**File path:** around line 380

**Change:** Replace the entire update_user permission logic.

```python
# BEFORE:
async def update_user(user_id: str, user_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    try:
        actor_role = normalize_role(current_user.get("role"))
        if actor_role in {MD_DIRECTOR, SUB_DISTRIBUTION_MANAGER}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This role has read-only access to users",
            )

        target_user = await user_service.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if not await _can_access_user(current_user, target_user, write=True):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        if actor_role in {MD_DIRECTOR, PDIC_STAFF} and str(current_user.get("id")) != str(user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

# AFTER:
async def update_user(user_id: str, user_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    try:
        actor_role = normalize_role(current_user.get("role"))
        is_self = str(current_user.get("id")) == str(user_id)

        target_user = await user_service.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Self-service: any user can update their own basic profile
        if is_self:
            restricted_fields = {"status", "permissions", "role"}
            edited = set(user_data.model_dump(exclude_unset=True).keys())
            if edited & restricted_fields:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot change status, permissions, or role")
        else:
            # Admin editing others – enforce write permission
            if actor_role in {MD_DIRECTOR, SUB_DISTRIBUTION_MANAGER}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This role has read-only access to users",
                )
            if not await _can_access_user(current_user, target_user, write=True):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
            if actor_role in {MD_DIRECTOR, PDIC_STAFF} and not is_self:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
```

### 7.6 `POST /users/bulk-upload` — New Query Parameters

**File path:** around line 830

**Change:** Add `role` and `parent_id` query parameters and pass them to the service.

```python
# BEFORE:
async def bulk_upload_users(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    ...
    return await bulk_upload_service.process_bulk_user_upload(rows, current_user)

# AFTER:
async def bulk_upload_users(
    request: Request,
    file: UploadFile = File(...),
    role: str = Query(..., description="Target role: sub_distributor, cluster, or operator"),
    parent_id: Optional[str] = Query(None, description="Parent user ID for cluster/operator"),
    current_user: dict = Depends(get_current_user),
):
    ...
    target_role = normalize_role(role)
    if not target_role or target_role not in {"sub_distributor", "cluster", "operator"}:
        raise HTTPException(status_code=400, detail=f"Invalid target role '{role}'")

    parent_id_int = None
    if parent_id:
        try:
            parent_id_int = int(parent_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid parent_id")

    return await bulk_upload_service.process_bulk_user_upload(rows, current_user, target_role, parent_id_int)
```

---

## 8. Bulk Upload Service — Full Rewrite

### File: `backend/app/services/bulk_upload_service.py`

Replace the entire `process_bulk_user_upload` function. Key changes:

### 8.1 Function Signature

```python
async def process_bulk_user_upload(
    rows: list,
    current_user: dict,
    target_role: str,
    parent_id: Optional[int] = None,
) -> dict:
```

### 8.2 Validation Logic

```python
    actor_role = normalize_role(current_user.get("role"))
    normalized_target_role = normalize_role(target_role)
    if not normalized_target_role or normalized_target_role not in {"sub_distributor", "cluster", "operator"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid target role '{target_role}'")

    if actor_role not in {"super_admin", "manager", "sub_distributor", "cluster"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if actor_role in {"sub_distributor", "cluster"} and normalized_target_role != "operator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"You can only bulk upload operators, not '{normalized_target_role}'")
```

### 8.3 Row Parsing

```python
    for idx, row in enumerate(rows):
        row_num = idx + 2
        email = str(row.get("email") or "").strip().lower()
        password = str(row.get("password") or "")
        name = str(row.get("name") or "").strip()
        phone = str(row.get("phone") or "").strip() or None
        raw_digi = str(row.get("digital_id") or "").strip()
        raw_bb = str(row.get("broadband_id") or "").strip()

        if not email or not password or not name:
            errors.append({"row": row_num, "email": email, "error": "Missing required fields (email, password, name)"})
            continue

        if email in seen_emails:
            skipped.append({"row": row_num, "email": email, "reason": "Duplicate email in file"})
            continue
        seen_emails.add(email)

        # For operators, pipe-separated digital_id means multiple IDs
        digi_parts = [d.strip() for d in raw_digi.split("|") if d.strip()] if raw_digi else []
        primary_digi = digi_parts[0] if digi_parts else None
        extra_digi_ids = digi_parts[1:] if len(digi_parts) > 1 else []

        prepared_rows.append({
            "row": row_num,
            "email": email,
            "password": password,
            "name": name,
            "phone": phone,
            "digital_id": primary_digi,
            "broadband_id": raw_bb or None,
            "additional_digital_ids": extra_digi_ids,
        })
```

### 8.4 Database Insert

```python
    insert_sql = """INSERT INTO users (email, password_hash, name, role, phone,
        status, parent_id, permissions, created_at, updated_at, last_login)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
```

### 8.5 Digital Identities Insert (at end, after successful inserts)

```python
        # Insert digital identities into digital_identities table
        digi_candidates = [
            item for item in insertable_rows
            if should_commit and (item.get("digital_id") or item.get("broadband_id") or item.get("additional_digital_ids"))
        ]
        if digi_candidates:
            digi_emails = [item["email"] for item in digi_candidates]
            placeholders = ",".join(["?"] * len(digi_emails))
            cursor = await db.execute(
                f"SELECT id, email FROM users WHERE LOWER(email) IN ({placeholders})",
                digi_emails,
            )
            email_to_id = {str(row["email"]).lower(): int(row["id"]) for row in await cursor.fetchall()}
            digi_payload = []
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            for item in digi_candidates:
                user_id = email_to_id.get(item["email"])
                if user_id is None:
                    continue
                if item.get("digital_id") or item.get("broadband_id"):
                    digi_payload.append((user_id, item["digital_id"], item["broadband_id"], 1, now))
                for digi_id in (item.get("additional_digital_ids") or []):
                    digi_payload.append((user_id, digi_id, None, 0, now))
            if digi_payload:
                try:
                    await db.executemany(
                        "INSERT INTO digital_identities (user_id, digital_id, broadband_id, is_primary, created_at) VALUES (?, ?, ?, ?, ?)",
                        digi_payload,
                    )
                    await db.commit()
                except Exception as e:
                    logger.warning("Failed to insert digital identities: %s", str(e))
```

### 8.6 Logging Update

```python
    # Change log messages to include target role
    await log_business_activity(
        ...
        description=(
            f"{actor_name} used bulk upload for {normalized_target_role}s: "
            f"{len(created)} created, {len(skipped)} skipped, {len(errors)} errors"
        ),
    )

    audit_logger.info(
        "USER_BULK_UPLOAD | actor=%s | role=%s | total=%d | created=%d | skipped=%d | errors=%d",
        current_user.get("email"), normalized_target_role, len(prepared_rows), len(created), len(skipped), len(errors),
    )
```

---

## 9. View-As Dashboard Service — `backend/app/services/dashboard_service/view_as.py`

### File path: around line 32

**Change:** Remove `location` from the SELECT query.

```python
# BEFORE:
"SELECT id, name, email, role, status, phone, location FROM users WHERE role = 'operator' ..."

# AFTER:
"SELECT id, name, email, role, status, phone FROM users WHERE role = 'operator' ..."
```

---

## 10. Frontend API Service — `frontend/src/services/api/users.js`

### File path: `users.js`

**Change:** Update `bulkUpload()` method to accept and pass `role` and `parentId`.

```javascript
// BEFORE:
  bulkUpload: async (file) => {
    const formData = new FormData();
    const fileBuffer = await file.arrayBuffer();
    const fileSnapshot = new Blob([fileBuffer], { type: file.type || 'application/octet-stream' });
    formData.append('file', fileSnapshot, file.name || 'bulk-upload.csv');
    const url = `${API_BASE_URL}/users/bulk-upload`;
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      ...

// AFTER:
  bulkUpload: async (file, role, parentId) => {
    const formData = new FormData();
    const fileBuffer = await file.arrayBuffer();
    const fileSnapshot = new Blob([fileBuffer], { type: file.type || 'application/octet-stream' });
    formData.append('file', fileSnapshot, file.name || 'bulk-upload.csv');
    const params = new URLSearchParams({ role });
    if (parentId) params.set('parent_id', parentId);
    const url = `${API_BASE_URL}/users/bulk-upload?${params}`;
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
```

---

## 11. Sidebar — `frontend/src/components/layout/Sidebar.jsx`

### Change: Group defect-related links into a "Defect" dropdown

For each of the 8 role menu arrays in `getMenuItems()`, replace the individual link items:

```javascript
// INSTEAD OF these individual links:
{ path: '/defects', icon: AlertTriangle, label: 'Defect Reports' },
{ path: '/replacements', icon: ArrowLeftRight, label: 'Replacements' },
{ path: '/replacements/pending', icon: AlertTriangle, label: 'Pending Replacements' },
{ path: '/pending-dues', icon: DollarSign, label: 'Pending Dues' },
{ path: '/returns', icon: RotateCcw, label: 'Returns' },
{ path: '/approvals', icon: CheckSquare, label: 'Approvals' },

// ADD a dropdown group:
{
  key: 'defect',
  icon: AlertTriangle,
  label: 'Defect',
  children: [
    { path: '/defects', label: 'Defect Reports' },
    { path: '/replacements', label: 'Replacements' },
    { path: '/replacements/pending', label: 'Pending Replacements' },
    { path: '/pending-dues', label: 'Pending Dues' },
    { path: '/returns', label: 'Returns' },
    { path: '/approvals', label: 'Approvals' },
  ]
},
```

**Role-specific variations to apply:**

| Role | Children |
|------|----------|
| **SUPER_ADMIN**, **MANAGER**, **PDIC_STAFF** | All 6 items (Defect Reports, Replacements, Pending Replacements, Pending Dues, Returns, Approvals) |
| **MD_DIRECTOR** | 5 items (no Approvals) |
| **SUB_DISTRIBUTION_MANAGER** | Defect Reports, Replacements\*, Pending Replacements\*, Pending Payments |
| **SUB_DISTRIBUTOR**, **CLUSTER** | Defect Reports, Replacements\*, Pending Replacements\*, Pending Payments, Return Requests |
| **OPERATOR** | Report Defect, My Defect Reports, Replacements\*, Pending Replacements\*, Pending Payments, My Returns |

*\*Conditionally shown based on `canShowReplacementOptions` — wrap in: `...(canShowReplacementOptions ? [{ path: ... }, { path: ... }] : [])`*

**Keep remaining items** (Reports, Backup, External Inventory, etc.) as top-level links after the dropdown.

---

## 12. Bulk Upload Page — Full Rewrite `frontend/src/pages/BulkUploadUsers.jsx`

### File path: `BulkUploadUsers.jsx`

Replace the entire file content. Key components to build:

### 12.1 Imports

```javascript
import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, Download, FileSpreadsheet, AlertCircle, ArrowLeft, Loader2, ChevronRight, Users, Building2, UserCog } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import FilePreview from '../components/ui/FilePreview';
import { usersAPI, dashboardAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
```

### 12.2 Constants

```javascript
const ALLOWED_EXTENSIONS = ['.csv', '.xlsx', '.xls'];
const CSV_HEADERS = ['email', 'password', 'name', 'digital_id', 'broadband_id', 'phone'];
const CSV_SAMPLE = 'op1@example.com,Pass@123,Operator One,DIG001,BB001,+911234567890';

const ROLE_BUTTONS = [
  { key: 'sub_distributor', label: 'Subdistributor', icon: Users, description: 'Bulk upload subdistributor accounts' },
  { key: 'cluster', label: 'Cluster', icon: Building2, description: 'Bulk upload cluster accounts under a subdistributor' },
  { key: 'operator', label: 'Operator', icon: UserCog, description: 'Bulk upload operator accounts' },
];
```

### 12.3 Component State

```javascript
const BulkUploadUsers = () => {
  const navigate = useNavigate();
  const { user: currentUser, hasRole } = useAuth();
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [selectedRole, setSelectedRole] = useState(null);
  const [operatorMode, setOperatorMode] = useState(null);
  const [sdList, setSdList] = useState([]);
  const [clusterList, setClusterList] = useState([]);
  const [selectedSdId, setSelectedSdId] = useState('');
  const [selectedClusterId, setSelectedClusterId] = useState('');
  const [loadingParents, setLoadingParents] = useState(false);

  const actorRole = currentUser?.role;
  const isMgmt = actorRole === 'super_admin' || actorRole === 'manager';
```

### 12.4 Template Download

```javascript
  const downloadTemplate = useCallback(() => {
    const label = selectedRole === 'operator' && selectedRole
      ? `Operator (${operatorMode === 'cluster' ? 'via Cluster' : 'via Subdistributor'})`
      : selectedRole ? selectedRole : 'Users';
    try {
      dashboardAPI.trackActivity({
        action: 'template_export',
        description: `Exported ${label} bulk upload template`,
        context: 'users_bulk_upload_template',
      }).catch(() => {});
    } catch {}
    const bom = '\uFEFF';
    const blob = new Blob([bom + CSV_HEADERS.join(',') + '\n' + CSV_SAMPLE], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `user-template-${selectedRole || 'users'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [selectedRole, operatorMode]);
```

### 12.5 Parent Data Loaders

```javascript
  useEffect(() => {
    if (selectedRole === 'cluster' || (selectedRole === 'operator' && operatorMode)) {
      setSelectedSdId('');
      setSelectedClusterId('');
      setClusterList([]);
      if (selectedRole === 'cluster' || operatorMode) {
        loadSdList();
      }
    }
  }, [selectedRole, operatorMode]);

  useEffect(() => {
    if (selectedSdId) {
      if (selectedRole === 'cluster' || operatorMode === 'cluster') {
        loadClusterList(selectedSdId);
      }
    }
  }, [selectedSdId]);

  const loadSdList = async () => {
    setLoadingParents(true);
    try {
      const res = await usersAPI.getUsers({ role: 'sub_distributor', page_size: 10000 });
      setSdList(res.data || []);
    } catch (err) {
      console.error('Failed to load subdistributors:', err);
    } finally {
      setLoadingParents(false);
    }
  };

  const loadClusterList = async (sdId) => {
    setLoadingParents(true);
    try {
      const res = await usersAPI.getUsers({ role: 'cluster', parent_id: sdId, page_size: 10000 });
      setClusterList(res.data || []);
    } catch (err) {
      console.error('Failed to load clusters:', err);
    } finally {
      setLoadingParents(false);
    }
  };
```

### 12.6 File Handlers

```javascript
  const handleFileChange = (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    const ext = '.' + selected.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      alert('Please upload a CSV or Excel file');
      return;
    }
    setFile(selected);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (!dropped) return;
    const ext = '.' + dropped.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      alert('Please upload a CSV or Excel file');
      return;
    }
    setFile(dropped);
  };

  const handleUpload = async () => {
    if (!file || !selectedRole) return;
    let parentId = null;
    if (selectedRole === 'cluster') {
      parentId = selectedSdId || null;
    } else if (selectedRole === 'operator') {
      if (operatorMode === 'cluster') {
        parentId = selectedClusterId || null;
      } else if (operatorMode === 'sd') {
        if (isMgmt) {
          parentId = selectedSdId || null;
        } else {
          parentId = currentUser?.id || null;
        }
      }
    }
    try {
      setUploading(true);
      setResult(null);
      const res = await usersAPI.bulkUpload(file, selectedRole, parentId);
      setResult(res.data);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      console.error('Upload error:', err);
      const msg = err?.response?.data?.detail || err?.message || 'Upload failed';
      setResult({ success: false, error: msg, message: msg });
    } finally {
      setUploading(false);
    }
  };

  const handleClear = () => {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const resetFlow = () => {
    setSelectedRole(null);
    setOperatorMode(null);
    setFile(null);
    setResult(null);
    setSelectedSdId('');
    setSelectedClusterId('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };
```

### 12.7 Render Helpers

```javascript
  const renderRoleButtons = () => {
    let buttons;
    if (isMgmt) {
      buttons = ROLE_BUTTONS;
    } else if (actorRole === 'sub_distributor') {
      buttons = [{ key: 'operator', label: 'Operator', icon: UserCog, description: 'Bulk upload operators' }];
    } else if (actorRole === 'cluster') {
      buttons = [{ key: 'operator', label: 'Operator', icon: UserCog, description: 'Bulk upload operators under you' }];
    } else {
      buttons = [];
    }
    return (
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {buttons.map((btn) => (
          <button key={btn.key} onClick={() => { setSelectedRole(btn.key); setOperatorMode(null); setFile(null); setResult(null); }}
            className={`p-6 rounded-xl border-2 text-left transition-all ${selectedRole === btn.key ? 'border-blue-500 bg-blue-50 shadow-md' : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'}`}>
            <btn.icon className="w-8 h-8 text-blue-600 mb-2" />
            <p className="font-semibold text-gray-800">{btn.label}</p>
            <p className="text-xs text-gray-500 mt-1">{btn.description}</p>
          </button>
        ))}
      </div>
    );
  };
```

### 12.8 JSX Layout Structure

```jsx
return (
  <div className="space-y-6">
    {/* Header with back button */}
    <div className="flex items-center gap-4">
      <button onClick={() => navigate('/users')} className="p-2 hover:bg-gray-100 rounded-lg">
        <ArrowLeft className="w-5 h-5" />
      </button>
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Bulk Upload Users</h1>
        <p className="text-sm text-gray-500">Upload subdistributors, clusters, and operators via CSV or Excel</p>
      </div>
    </div>

    {/* Step 1: Select User Type */}
    <Card title="Select User Type" icon={Users}>
      {isMgmt && selectedRole && (
        <button onClick={resetFlow} className="text-sm text-blue-600 hover:underline mb-3 inline-block">
          &larr; Change role
        </button>
      )}
      {renderRoleButtons()}
    </Card>

    {/* Step 2: Operator Assignment Mode */}
    {selectedRole === 'operator' && (
      <Card title="Operator Assignment" icon={UserCog}>
        {/* operator mode buttons */}
      </Card>
    )}

    {/* Step 3: Parent Selectors */}
    {(selectedRole === 'cluster' || ...) && (
      <Card title="Select Parent" icon={Building2}>
        {/* subdistributor dropdown + cluster dropdown */}
      </Card>
    )}

    {/* Step 4: Template + Upload */}
    {selectedRole && (selectedRole !== 'operator' || operatorMode) && (
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <Card title="Template" icon={FileSpreadsheet} className="lg:col-span-1">
          {/* CSV column info + download button */}
        </Card>
        <Card title="Upload File" icon={Upload} className="lg:col-span-2">
          {/* drag-drop zone + file preview + upload button */}
        </Card>
      </div>
    )}

    {/* File Preview */}
    {file && <FilePreview file={file} />}

    {/* Result display (success/error) */}
    {result && (...)}
  </div>
);
```

---

## 13. Users Page — `frontend/src/pages/Users.jsx`

### 13.1 Search Options

```javascript
// Replace the USER_SEARCH_BY_OPTIONS array:
// BEFORE:
{ value: 'department', label: 'Department' },
{ value: 'location', label: 'Location' },
{ value: 'digital_id', label: 'Digital ID' },
{ value: 'broadband_id', label: 'Broadband ID' },
{ value: 'cluster_id', label: 'Cluster ID' },
{ value: 'operator_id', label: 'Operator ID' },

// AFTER:
{ value: 'address', label: 'Address' },
{ value: 'designation', label: 'Designation' },
{ value: 'pincode', label: 'Pincode' },
```

### 13.2 Form State (emptyForm)

```javascript
// Replace:
const emptyForm = { name, email, password, role, ..., digitalId, broadbandId, clusterId, operatorId,
                    phone, department, location, parentId };

// With:
const emptyForm = { name, email, password, role, phone, address, designation, pincode,
                    parentId, digital_id, broadband_id, additional_digital_ids: [] };
```

### 13.3 Create User Payload Construction

```javascript
// Replace the payload building in handleSubmit:
// BEFORE:
if (formData.role === 'sub_distributor') {
    payload.digital_id = formData.digitalId || null;
    payload.broadband_id = formData.broadbandId || null;
}
if (formData.role === 'cluster') {
    payload.cluster_id = formData.clusterId || null;
}
if (formData.role === 'operator') {
    payload.operator_id = formData.operatorId || null;
}
if (formData.phone)      payload.phone = formData.phone;
if (formData.department) payload.department = formData.department;
if (formData.location)   payload.location = formData.location;
if (formData.parentId)   payload.parent_id = formData.parentId;

// AFTER:
if (formData.phone)      payload.phone = formData.phone;
if (formData.address)    payload.address = formData.address;
if (formData.designation) payload.designation = formData.designation;
if (formData.pincode)    payload.pincode = formData.pincode;
if (formData.parentId)   payload.parent_id = formData.parentId;
if (formData.digital_id) payload.digital_id = formData.digital_id;
if (formData.broadband_id) payload.broadband_id = formData.broadband_id;
if (formData.additional_digital_ids?.length > 0) payload.additional_digital_ids = formData.additional_digital_ids.join('|');
```

### 13.4 Update User Payload

```javascript
// BEFORE:
const payload = {};
if (formData.name)       payload.name = formData.name;
if (formData.phone)      payload.phone = formData.phone;
if (formData.department) payload.department = formData.department;
if (formData.location)   payload.location = formData.location;

// AFTER:
const payload = {};
if (formData.name)        payload.name = formData.name;
if (formData.phone)       payload.phone = formData.phone;
if (formData.address)     payload.address = formData.address;
if (formData.designation) payload.designation = formData.designation;
if (formData.pincode)     payload.pincode = formData.pincode;
```

### 13.5 Operator Parent Options (useMemo)

```javascript
// ADD this new useMemo:
const operatorParentOptions = useMemo(() => {
    if (formData.role !== 'operator') return [];
    const sds = subDistributorOptions.map((sd) => ({ ...sd, groupLabel: 'Subdistributor' }));
    const cls = parentOptions.map((cl) => ({ ...cl, groupLabel: 'Cluster' }));
    return [...sds, ...cls];
}, [formData.role, subDistributorOptions, parentOptions]);
```

### 13.6 Parent Selector in Create Form

**Replace the two-step subdistributor → cluster cascade with a single dropdown:**

```jsx
{/* BEFORE: */}
{isAdminOrManager && formData.role === 'operator' ? (
  <div className="space-y-3">
    <div>
      <label>Select Sub Distribution *</label>
      <select value={selectedOperatorSubDistId} onChange={...}>
        <option value="">Select Sub Distribution...</option>
        {subDistributorOptions.map(sd => ...)}
      </select>
    </div>
    <div>
      <label>Assign to Cluster *</label>
      <select value={formData.parentId} onChange={...} disabled={!selectedOperatorSubDistId}>
        ...
      </select>
    </div>
  </div>
) : (...)}

{/* AFTER: */}
{formData.role === 'operator' ? (
  <div>
    <label>Assign to Cluster or Subdistributor *</label>
    <select value={formData.parentId} onChange={(e) => setFormData((prev) => ({ ...prev, parentId: e.target.value }))} required>
      <option value="">Select Cluster or Subdistributor...</option>
      {operatorParentOptions.map((p) => (
        <option key={p.id} value={p.id}>
          {p.groupLabel ? `[${p.groupLabel}] ${p.name}` : p.name}
        </option>
      ))}
    </select>
  </div>
) : (...)}
```

### 13.7 Form Fields (Optional Section)

**Change from 2-column to 3-column grid with new fields:**

```jsx
{/* BEFORE: */}
<div className="grid grid-cols-2 gap-4">
  <div><label>Phone</label><input ... /></div>
  <div><label>Department</label><input ... /></div>
  <div className="col-span-2"><label>Location</label><input ... /></div>
</div>

{/* AFTER: */}
<div className="grid grid-cols-3 gap-4">
  <div><label>Phone</label><input ... /></div>
  <div><label>Address</label><input ... /></div>
  <div><label>Designation</label><input ... /></div>
  <div><label>Pincode</label><input ... /></div>
  <div><label>Digital ID</label><input ... /></div>
  <div><label>Broadband ID</label><input ... /></div>
  {formData.role === 'operator' && (
    <div>
      <label>Additional Digital IDs</label>
      <div className="space-y-2">
        {formData.additional_digital_ids.map((id, idx) => (
          <div key={idx} className="flex gap-2 items-center">
            <input value={id} onChange={...} placeholder="e.g., DIG002" />
            <button onClick={() => { ... }}>✕</button>
          </div>
        ))}
        <button onClick={() => setFormData({ ...formData, additional_digital_ids: [...formData.additional_digital_ids, ''] })}>
          + Add Digital ID
        </button>
      </div>
    </div>
  )}
</div>
```

### 13.8 Detail View (Selected User Panel)

```jsx
{/* Remove these blocks from the detail view: */}
{/* Email Verified */}
{/* Digital ID */}
{/* Broadband ID */}
{/* Cluster ID (if cluster) */}
{/* Operator ID (if operator) */}
{/* Email Notifications */}
{/* Push Notifications */}
{/* Theme */}
{/* Compact Mode */}

{/* Replace Department → Address, Location → Designation and add Pincode: */}
<div className="flex items-center gap-3">
  <MapPin className="w-5 h-5 text-gray-400" />
  <div>
    <p className="text-sm text-gray-500">Address</p>
    <p className="font-medium text-gray-800">{selectedUser.address || 'Not provided'}</p>
  </div>
</div>
<div className="flex items-center gap-3">
  <MapPin className="w-5 h-5 text-gray-400" />
  <div>
    <p className="text-sm text-gray-500">Designation</p>
    <p className="font-medium text-gray-800">{selectedUser.designation || 'Not provided'}</p>
  </div>
</div>
<div className="flex items-center gap-3">
  <MapPin className="w-5 h-5 text-gray-400" />
  <div>
    <p className="text-sm text-gray-500">Pincode</p>
    <p className="font-medium text-gray-800">{selectedUser.pincode || 'Not provided'}</p>
  </div>
</div>
```

### 13.9 Inline Edit Modal

**Replace department/location fields with address/designation/pincode in the edit form:**

```jsx
{/* In the exportable columns list: */}
{/* BEFORE: */}
{ key: 'department', label: 'Department' },
{ key: 'location', label: 'Location' },

{/* AFTER: */}
{ key: 'address', label: 'Address' },
{ key: 'designation', label: 'Designation' },
{ key: 'pincode', label: 'Pincode' },
```

**Remove `digital_id`, `broadband_id`, `cluster_id`, `operator_id` from detailForm and the update payload building:**

```javascript
// In the save handler, remove:
if (detailUser.role === 'sub_distributor') {
    updatePayload.digital_id = detailForm.digital_id || null;
    updatePayload.broadband_id = detailForm.broadband_id || null;
}
if (detailUser.role === 'cluster') {
    updatePayload.cluster_id = detailForm.cluster_id || null;
}
if (detailUser.role === 'operator') {
    updatePayload.operator_id = detailForm.operator_id || null;
}
```

---

## 14. User Hierarchy Page — `frontend/src/pages/UserHierarchy.jsx`

### 14.1 Form State

```javascript
// BEFORE:
const emptyForm = { name, email, password, role, phone, department, location,
                    parentId, digitalId, broadbandId, clusterId, operatorId };

// AFTER:
const emptyForm = { name, email, password, role, phone, address, designation,
                    pincode, parentId, digital_id, broadband_id, additional_digital_ids: [] };
```

### 14.2 Filter/Search

```javascript
// Add to the filter condition:
u.address?.toLowerCase().includes(query) ||
u.designation?.toLowerCase().includes(query) ||
u.pincode?.toLowerCase().includes(query),

// Remove:
u.digital_id?.toLowerCase().includes(query) ||
u.broadband_id?.toLowerCase().includes(query) ||
u.cluster_id?.toLowerCase().includes(query) ||
u.operator_id?.toLowerCase().includes(query),
```

### 14.3 Parent Options (operator creation)

```javascript
// In the useEffect that loads parent options:

// For sub_distributor actor:
// BEFORE:
setParentOptions(visibleUsers.filter(u => u.role === 'cluster').map(u => ({ ...u, groupLabel: 'Cluster' })));

// AFTER:
const me = { id: String(currentUser.id), name: currentUser.name, groupLabel: 'You (Subdistributor)' };
const clusters = visibleUsers.filter(u => u.role === 'cluster').map(u => ({ ...u, groupLabel: 'Cluster' }));
setParentOptions([me, ...clusters]);

// For admin/manager actor:
// BEFORE:
const r = await usersAPI.getUsers({ role: 'cluster', page_size: HIERARCHY_PAGE_SIZE });
setParentOptions((r.data || []).map(u => ({ ...u, groupLabel: 'Cluster' })));

// AFTER:
const [sdRes, clRes] = await Promise.all([
    usersAPI.getUsers({ role: 'sub_distributor', page_size: HIERARCHY_PAGE_SIZE }),
    usersAPI.getUsers({ role: 'cluster', page_size: HIERARCHY_PAGE_SIZE }),
]);
const sds = (sdRes.data || []).map(u => ({ ...u, groupLabel: 'Subdistributor' }));
const cls = (clRes.data || []).map(u => ({ ...u, groupLabel: 'Cluster' }));
setParentOptions([...sds, ...cls]);
```

### 14.4 Create User Payload

```javascript
// BEFORE:
if (formData.phone) payload.phone = formData.phone;
if (formData.department) payload.department = formData.department;
if (formData.location) payload.location = formData.location;
if (formData.parentId) payload.parent_id = formData.parentId;
if (formData.role === 'sub_distributor') {
    payload.digital_id = formData.digitalId || null;
    payload.broadband_id = formData.broadbandId || null;
}
if (formData.role === 'cluster') {
    payload.cluster_id = formData.clusterId || null;
}
if (formData.role === 'operator') {
    payload.operator_id = formData.operatorId || null;
}

// AFTER:
if (formData.phone) payload.phone = formData.phone;
if (formData.address) payload.address = formData.address;
if (formData.designation) payload.designation = formData.designation;
if (formData.pincode) payload.pincode = formData.pincode;
if (formData.parentId) payload.parent_id = formData.parentId;
if (formData.digital_id) payload.digital_id = formData.digital_id;
if (formData.broadband_id) payload.broadband_id = formData.broadband_id;
if (formData.additional_digital_ids?.length > 0) payload.additional_digital_ids = formData.additional_digital_ids.join('|');
```

### 14.5 Detail View Rows

```jsx
{/* BEFORE: */}
<Row label="Department" value={selectedUser.department} />
<Row label="Location" value={selectedUser.location} />

{/* AFTER: */}
<Row label="Address" value={selectedUser.address} />
<Row label="Designation" value={selectedUser.designation} />
<Row label="Pincode" value={selectedUser.pincode} />
```

**Remove these rows:**
```jsx
{selectedUser.digital_id && <Row label="Digital ID" value={selectedUser.digital_id} />}
{selectedUser.broadband_id && <Row label="Broadband ID" value={selectedUser.broadband_id} />}
{selectedUser.cluster_id && <Row label="Cluster ID" value={selectedUser.cluster_id} />}
{selectedUser.operator_id && <Row label="Operator ID" value={selectedUser.operator_id} />}
```

### 14.6 Form Fields

```jsx
{/* Change from 2-col to 3-col grid with new fields: */}
{/* BEFORE: */}
<div className="grid grid-cols-2 gap-4">
  <Field label="Phone">...</Field>
  <Field label="Department">...</Field>
  <div className="col-span-2"><Field label="Location">...</Field></div>
</div>

{formData.role === 'sub_distributor' && (
  <div className="grid grid-cols-2 gap-4">
    <Field label="Digital ID">...</Field>
    <Field label="Broadband ID">...</Field>
  </div>
)}

{formData.role === 'cluster' && (
  <Field label="Cluster ID">...</Field>
)}

{formData.role === 'operator' && (
  <Field label="Operator ID">...</Field>
)}

{/* AFTER: */}
<p className="text-xs text-gray-400">Optional — user can fill in later</p>
<div className="grid grid-cols-3 gap-4">
  <Field label="Phone">...</Field>
  <Field label="Address">...</Field>
  <Field label="Designation">...</Field>
  <Field label="Pincode">...</Field>
  <Field label="Digital ID">...</Field>
  <Field label="Broadband ID">...</Field>
  {formData.role === 'operator' && (
    <Field label="Additional Digital IDs">
      <div className="space-y-2">
        {formData.additional_digital_ids.map((id, idx) => (
          <div key={idx} className="flex gap-2 items-center">
            <input value={id} onChange={...} />
            <button onClick={() => { ... }}>✕</button>
          </div>
        ))}
        <button onClick={() => setFormData(p => ({ ...p, additional_digital_ids: [...p.additional_digital_ids, ''] }))}>
          + Add Digital ID
        </button>
      </div>
    </Field>
  )}
</div>
```

### 14.7 Parent Label Update

```jsx
{/* In the parent assignment Field: */}
{/* BEFORE: */}
label={formData.role === 'operator' ? 'Assign to Cluster' : ...}

{/* AFTER: */}
label={formData.role === 'operator' ? 'Assign to Cluster or Subdistributor' : ...}
```

---

## 15. Profile Page — `frontend/src/pages/Profile.jsx`

### 15.1 Form State

```javascript
// BEFORE:
const [profileData, setProfileData] = useState({
    name: user?.name || '',
    phone: user?.phone || '',
    department: user?.department || '',
    location: user?.location || '',
});

// AFTER:
const [profileData, setProfileData] = useState({
    name: user?.name || '',
    phone: user?.phone || '',
    address: user?.address || '',
    designation: user?.designation || '',
    pincode: user?.pincode || '',
});
```

### 15.2 API Payload

```javascript
// BEFORE:
const payload = {
    name: profileData.name,
    phone: profileData.phone,
    department: profileData.department,
    location: profileData.location,
};

// AFTER:
const payload = {
    name: profileData.name,
    phone: profileData.phone,
    address: profileData.address,
    designation: profileData.designation,
    pincode: profileData.pincode,
};
```

### 15.3 Form Fields

```jsx
{/* Replace: */}
<div>
  <label><Building className="w-4 h-4 inline mr-2" />Department</label>
  <input value={profileData.department} onChange={...} placeholder="Enter department" />
</div>

<div className="md:col-span-2">
  <label><MapPin className="w-4 h-4 inline mr-2" />Location</label>
  <input value={profileData.location} onChange={...} placeholder="Enter location" />
</div>

{/* With: */}
<div>
  <label><MapPin className="w-4 h-4 inline mr-2" />Address</label>
  <input value={profileData.address} onChange={...} placeholder="Enter address" />
</div>

<div>
  <label><User className="w-4 h-4 inline mr-2" />Designation</label>
  <input value={profileData.designation} onChange={...} placeholder="Enter designation" />
</div>

<div>
  <label><MapPin className="w-4 h-4 inline mr-2" />Pincode</label>
  <input value={profileData.pincode} onChange={...} placeholder="Enter pincode" />
</div>
```

---

## 16. Settings Page — `frontend/src/pages/Settings.jsx`

### File path: `Settings.jsx`

Replace the entire file content with a simplified version.

**Remove:**
- `Appearance` settings card (Compact Mode, Animations, Theme)
- `Privacy` settings card (Show Online Status, Share Activity Data)
- Most content of the `System Settings (Admin Only)` card (Maintenance Mode, Debug Mode, Auto Backup, Backup Frequency)

**Keep:**
- `Regional Settings` card (Language, Timezone, Date Format, Time Format) — unchanged
- The outer layout (header + cards)

**Imports required:**
```javascript
import Card from '../components/ui/Card';
import { useAuth } from '../context/AuthContext';
import { Settings as SettingsIcon, Globe, Lock } from 'lucide-react';
```

**JSX structure:**
```jsx
<div className="space-y-6">
  <div>
    <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Settings</h1>
    <p className="text-gray-500 mt-1">System settings</p>
  </div>

  {hasRole(['super_admin']) && (
    <Card title="System Settings (Admin Only)" icon={SettingsIcon}>
      <p className="text-sm text-gray-500">System administration options.</p>
    </Card>
  )}

  <Card title="Regional Settings" icon={Globe}>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
        <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
          <option value="en">English</option>
          <option value="es">Spanish</option>
          <option value="fr">French</option>
          <option value="de">German</option>
          <option value="ar">Arabic</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Timezone</label>
        <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
          <option value="UTC">UTC</option>
          <option value="America/New_York">Eastern Time (US)</option>
          <option value="America/Los_Angeles">Pacific Time (US)</option>
          <option value="Europe/London">London</option>
          <option value="Asia/Dubai">Dubai</option>
          <option value="Asia/Tokyo">Tokyo</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Date Format</label>
        <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
          <option value="MM/DD/YYYY">MM/DD/YYYY</option>
          <option value="DD/MM/YYYY">DD/MM/YYYY</option>
          <option value="YYYY-MM-DD">YYYY-MM-DD</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Time Format</label>
        <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
          <option value="12h">12 Hour (AM/PM)</option>
          <option value="24h">24 Hour</option>
        </select>
      </div>
    </div>
  </Card>
</div>
```

---

## 17. View-As Dashboard — `frontend/src/pages/ViewAsDashboard.jsx`

### File path: `ViewAsDashboard.jsx` around line 193

**Change:** Remove the `location` column from the user table.

```jsx
{/* Remove the <td> for location: */}
{/* BEFORE: */}
<td className="px-5 py-3 text-gray-600">{u.location || '-'}</td>

{/* AFTER: (just delete this line) */}
```
