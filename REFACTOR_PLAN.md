# DMS Refactoring Plan

## 1. Current State Analysis

### 1.1 Technology Stack

| Layer | Current | Target |
|---|---|---|
| Backend framework | FastAPI | FastAPI (no change) |
| Database driver | aiomysql (raw SQL) | SQLAlchemy 2.0 (async) |
| Migrations | None (auto-DDL in `database.py`) | Alembic |
| Validation | Pydantic v2 | Pydantic v2 (no change) |
| Frontend | React + Vite + Tailwind | React + Vite + Tailwind (no change) |
| Auth | JWT (python-jose) | Same (no change) |
| Monitoring | Prometheus + Grafana | Same (no change) |

### 1.2 Current Database Architecture

**21 tables**, all defined as raw SQL in `backend/app/database.py:240-656` with ~40 inline migration `ALTER TABLE` statements at `database.py:670-830`. No migration history, no rollback capability, no schema versioning.

**Key tables:**

| Table | Purpose | Rows Est. |
|---|---|---|
| `users` | All user types (8 roles) in one table | Core |
| `devices` | Device inventory | Core |
| `distributions` + `distribution_devices` | Device distribution workflow | Core |
| `defects` + `defect_images` + `defect_replacement_devices` | Defect management | Core |
| `returns` | Device returns | Core |
| `approvals` + `approval_role_routing` | Approval workflow | Core |
| `operators` | Standalone operators table (separate from users) | Legacy |
| `notifications` | In-app notifications | Core |
| `change_requests` | User change requests | Core |
| `external_inventory_*` (7 tables) | External inventory management | Module |
| `reassignment_requests` | User deletion reassignment | Core |
| `api_activity_logs` | Audit log | Core |
| `token_blacklist` | Revoked refresh tokens | Auth |
| `refresh_tokens` | Refresh token store | Auth |

### 1.3 Current Pain Points

**Database:**
1. Raw SQL everywhere — no type safety, no IDE autocomplete, no relationship navigation
2. Schema defined in Python string literals — brittle, breaks refactoring tools
3. Inline migrations (`ALTER TABLE` in try/except blocks) — silent failures, no rollback
4. `_translate_sql()` function converts SQLite `?` to MySQL `%s` — legacy from SQLite migration
5. Strings stored as `VARCHAR(64)` for timestamps — no MySQL datetime type usage
6. No foreign key constraints — orphaned data possible, no cascading
7. `operators` table duplicates user data (has its own operator_id, name, phone, email) — separate from the `users` table operator role

**Users table:**
1. Role-specific fields (`digital_id`, `broadband_id`, `cluster_id`, `operator_id`) set to NULL for 60%+ of users
2. `digital_id`/`broadband_id` should be 1:N for operators — currently single column
3. `cluster_id` and `operator_id` are string FKs with no referential integrity
4. `is_verified` is dead — always 0, never enforced
5. `theme`, `compact_mode`, `email_notifications`, `push_notifications` are persisted but only UI preferences
6. `permissions` as JSON string — no schema validation at DB level

**Role/permissions:**
1. Role hierarchy is a hardcoded Python dict (`ROLE_HIERARCHY` in `roles.py`)
2. Permissions matrix is a hardcoded Python dict (`PERMISSIONS` in `permissions.py`)
3. `ALLOWED_CREATE_BY_ROLE` is a hardcoded Python dict in `users.py`
4. `_can_access_user()` is a 50-line nested if/elif block
5. Adding a new role requires code deploy + DB migration

**Frontend:**
1. `roles.js` duplicates backend's string constants and normalization
2. Route-level `allowedRoles` arrays hardcoded in `App.jsx`
3. Repeated role-checking patterns across pages

---

## 2. Target Architecture

### 2.1 Design Principles

1. **Single source of truth** — roles, permissions, and hierarchy come from the database
2. **Normalize only where it matters** — don't split tables for the sake of splitting
3. **Gradual migration** — phase by phase, each phase independently testable
4. **Zero regressions** — every phase preserves existing API responses and behavior
5. **SQLAlchemy 2.0 async** — proper ORM with type safety and relationship navigation

### 2.2 New Schema Design

#### `users` — cleaned core table

```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    role_id INT NOT NULL,
    status VARCHAR(32) DEFAULT 'active',

    -- Hierarchy
    parent_id INT NULL,
    created_by INT NULL,

    -- Profile
    phone VARCHAR(64),
    department VARCHAR(255),
    location VARCHAR(255),
    address TEXT,           -- NEW
    designation VARCHAR(255), -- NEW

    -- Auth/security
    force_email_change BOOLEAN DEFAULT FALSE,
    force_password_change BOOLEAN DEFAULT FALSE,
    failed_login_attempts INT DEFAULT 0,
    locked_until DATETIME NULL,

    -- Audit
    is_verified BOOLEAN DEFAULT FALSE,
    last_login DATETIME NULL,
    permissions JSON,       -- was LONGTEXT

    -- Timestamps (proper DATETIME types)
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Indexes
    INDEX idx_users_parent_role (parent_id, role_id),
    FOREIGN KEY (parent_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (role_id) REFERENCES roles(id),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Removed columns:** `digital_id`, `broadband_id`, `cluster_id`, `operator_id`, `theme`, `compact_mode`, `email_notifications`, `push_notifications`

#### `digital_identities` — normalized 1:N for Group B roles (NEW)

```sql
CREATE TABLE digital_identities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    digital_id VARCHAR(128) NOT NULL,
    broadband_id VARCHAR(128),
    is_primary BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE INDEX idx_digital_identities_digital_id (digital_id),
    INDEX idx_digital_identities_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### `roles` — database-driven roles (NEW)

```sql
CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) UNIQUE NOT NULL,      -- slug: 'super_admin', 'sub_distributor'
    label VARCHAR(128) NOT NULL,           -- display: 'Super Admin', 'Sub Distributor'
    level INT NOT NULL,                    -- hierarchy level (higher = more power)
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Seed roles
INSERT INTO roles (name, label, level) VALUES
    ('super_admin', 'Super Admin', 80),
    ('md_director', 'MD/Director', 70),
    ('manager', 'Manager', 60),
    ('pdic_staff', 'PDIC Staff', 50),
    ('sub_distribution_manager', 'Sub Distribution MD/Manager', 40),
    ('sub_distributor', 'Sub Distributor', 30),
    ('cluster', 'Cluster', 20),
    ('operator', 'Operator', 10);
```

#### `role_permissions` — database-driven permissions (NEW)

```sql
CREATE TABLE role_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role_id INT NOT NULL,
    permission_key VARCHAR(128) NOT NULL,  -- 'users:read', 'devices:create', etc.
    is_granted BOOLEAN DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE INDEX idx_role_permissions_unique (role_id, permission_key),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### `user_preferences` — optional, only if multi-device persistence needed (NEW)

```sql
CREATE TABLE user_preferences (
    user_id INT PRIMARY KEY,
    theme VARCHAR(32) DEFAULT 'light',
    compact_mode BOOLEAN DEFAULT FALSE,
    email_notifications BOOLEAN DEFAULT TRUE,
    push_notifications BOOLEAN DEFAULT TRUE,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

> If multi-device persistence is not needed, drop this table and keep preferences in `localStorage`.

### 2.3 SQLAlchemy Models

```python
# models/base.py
import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


class Base(DeclarativeBase, TimestampMixin):
    pass
```

```python
# models/user.py
from sqlalchemy import String, Boolean, Integer, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
import enum

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    status: Mapped[str] = mapped_column(String(32), default="active")

    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    phone: Mapped[Optional[str]] = mapped_column(String(64))
    department: Mapped[Optional[str]] = mapped_column(String(255))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(Text)
    designation: Mapped[Optional[str]] = mapped_column(String(255))

    force_email_change: Mapped[bool] = mapped_column(Boolean, default=False)
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime.datetime]]

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[Optional[datetime.datetime]]

    permissions: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    role: Mapped["Role"] = relationship()
    parent: Mapped[Optional["User"]] = relationship(
        "User", remote_sidebar="User.id", backref="children"
    )
    digital_identities: Mapped[List["DigitalIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class DigitalIdentity(Base):
    __tablename__ = "digital_identities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    digital_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    broadband_id: Mapped[Optional[str]] = mapped_column(String(128))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="digital_identities")
```

```python
# models/role.py
from sqlalchemy import String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional

from .base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    permissions: Mapped[List["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    permission_key: Mapped[str] = mapped_column(String(128), nullable=False)
    is_granted: Mapped[bool] = mapped_column(Boolean, default=True)

    role: Mapped["Role"] = relationship(back_populates="permissions")
```

---

## 3. Migration Phases

### Phase 0 — Infrastructure Setup (1-2 days)

**Goal:** Alembic running, SQLAlchemy connected, nothing changes yet.

1. Add dependencies:
   ```
   sqlalchemy>=2.0
   alembic>=1.13
   aiomysql  (keep for now — dual-write during migration)
   ```

2. Initialize Alembic:
   ```bash
   alembic init alembic
   ```
3. Configure `alembic.ini` with MySQL connection string
4. Create `backend/app/db/` package with `engine.py`, `session.py`, `base.py`
5. Create SQLAlchemy `engine` and `async_sessionmaker`
6. Verify connection works with a health-check query

**Verification:** Server starts, `/health` returns 200.

---

### Phase 1 — Roles & Permissions Table (2-3 days)

**Goal:** Move role/permission definitions from Python to database. No user table changes yet.

**Backend changes:**

1. Create `Role` and `RolePermission` SQLAlchemy models
2. Create Alembic migration for `roles` and `role_permissions` tables
3. Seed roles data from existing `ROLE_HIERARCHY` dict
4. Seed permissions data from existing `PERMISSIONS` dict
5. Create a `RoleService` that replaces:
   - `normalize_role()` → reads from `roles` table (with in-memory cache)
   - `role_level()` → reads from `roles.level`
   - `check_permission()` → reads from `role_permissions`
   - `can_manage_user()` → compares role levels
   - `get_viewable_roles()` → queried from DB
6. Add a `/api/roles` and `/api/roles/permissions` admin endpoint (read-only for now)
7. Update `auth_middleware.py` to use `RoleService` instead of hardcoded constants

**Frontend changes:**

1. Update `utils/roles.js` to fetch roles from `/api/roles` instead of hardcoding
2. Update `ROLE_LABELS` to be fetched from API
3. Update `normalizeRole` to work with role IDs instead of strings

**Verification:**
- All existing permission checks still pass
- Login works for all roles
- All 24 existing test files pass

---

### Phase 2 — Users Table Cleanup (3-4 days)

**Goal:** Remove deprecated columns, add new columns, migrate data.

**Schema changes (Alembic migration):**

Step 2a — Add new columns:
```sql
ALTER TABLE users ADD COLUMN address TEXT;
ALTER TABLE users ADD COLUMN designation VARCHAR(255);
ALTER TABLE users ADD COLUMN role_id INT;
```

Step 2b — Migrate role data:
```python
# In the migration script
connection.execute(
    """UPDATE users u JOIN roles r ON u.role = r.name
       SET u.role_id = r.id"""
)
```

Step 2c — Drop deprecated columns:
```sql
ALTER TABLE users DROP COLUMN digital_id;
ALTER TABLE users DROP COLUMN broadband_id;
ALTER TABLE users DROP COLUMN cluster_id;
ALTER TABLE users DROP COLUMN operator_id;
ALTER TABLE users DROP COLUMN theme;
ALTER TABLE users DROP COLUMN compact_mode;
ALTER TABLE users DROP COLUMN email_notifications;
ALTER TABLE users DROP COLUMN push_notifications;
```

Step 2d — Convert timestamp columns to DATETIME:
```sql
ALTER TABLE users MODIFY created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE users MODIFY updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE users MODIFY last_login DATETIME;
ALTER TABLE users MODIFY locked_until DATETIME;
```

Step 2e — Add foreign keys:
```sql
ALTER TABLE users ADD FOREIGN KEY (role_id) REFERENCES roles(id);
ALTER TABLE users ADD FOREIGN KEY (parent_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE users ADD FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE users MODIFY permissions JSON;
ALTER TABLE users MODIFY is_verified BOOLEAN DEFAULT FALSE;
```

Step 2f — Make `role` column nullable first, then drop after data verified.

**SQLAlchemy model changes:**
- Update `User` model to match new schema
- Remove `digital_id`, `broadband_id`, `cluster_id`, `operator_id`, `theme`, `compact_mode`, `email_notifications`, `push_notifications`
- Add `address`, `designation`, `role_id`, relationship to `Role`

**Service layer changes:**

1. Update `UserService` to use SQLAlchemy instead of raw SQL
   - `get_users()` — use `select()` with filters
   - `get_user_by_id()` — use `session.get(User, id)`
   - `create_user()` — use `session.add()`
   - `update_user()` — use merge/set operations
2. Keep raw SQL in services that are NOT yet migrated (Phase 3+)
3. Response format must remain identical:
   - `id` as string (current convention)
   - `role` as string slug (not `role_id`)
   - Remove now-deprecated fields from response (`theme`, `compact_mode`, etc.)
   - Add `address`, `designation` to response

**Verification:**
- `GET /api/users` returns same shape
- `GET /api/users/{id}` returns same shape (minus removed fields)
- Create, update, delete users all work
- All user-related tests pass

---

### Phase 3 — Digital Identities Table (2 days)

**Goal:** Support multiple digital IDs per operator.

**Schema changes (Alembic migration):**

```sql
CREATE TABLE digital_identities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    digital_id VARCHAR(128) NOT NULL,
    broadband_id VARCHAR(128),
    is_primary BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_digital_identities_digital_id (digital_id),
    INDEX idx_digital_identities_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

**Data migration:**
```python
# For each user with a non-null digital_id, create one digital_identities row
connection.execute("""
    INSERT INTO digital_identities (user_id, digital_id, broadband_id, is_primary)
    SELECT id, digital_id, broadband_id, TRUE
    FROM users
    WHERE digital_id IS NOT NULL
""")
```

**SQLAlchemy model:**
- Add `DigitalIdentity` model
- Add `digital_identities` relationship on `User`

**Service/API changes:**
- Add `GET /api/users/{id}/digital-identities` and `POST /api/users/{id}/digital-identities`
- Update `UserResponse` — `digital_id`/`broadband_id` now populated from primary identity
- Update bulk upload to handle multiple digital IDs
- Update frontend `Users.jsx` to show digital identities list (not single field)
- Update `UserHierarchy.jsx` similarly

**Verification:**
- Sub_distributor users see their digital IDs from the new table
- Operator users can add/remove multiple digital IDs
- Backward compatibility: `digital_id` in response still populated (from primary)

---

### Phase 4 — Service Layer Migration (5-7 days, parallel)

**Goal:** Convert each service from raw SQL to SQLAlchemy, one at a time.

**Strategy:**
- Keep the `get_db()` raw SQL context manager for non-migrated services
- New services use `async with AsyncSession(engine) as session`
- Migrate in dependency order:

```
Phase 4a: auth_service.py  (no other services depend on it being migrated first)
Phase 4b: user_service.py  (already started in Phase 2)
Phase 4c: device_service.py + operator_service.py
Phase 4d: distribution_service.py
Phase 4e: defect_service.py + return_service.py
Phase 4f: approval_service.py + notification_service.py
Phase 4g: report_service.py + inventory_service.py
Phase 4h: dashboard_service/* (all submodules)
Phase 4i: bulk_upload_service.py + reassignment_request_service.py
Phase 4j: backup_scheduler.py + activity_log_cleanup.py
```

**Per service checklist:**
- [ ] Create SQLAlchemy model if not exists
- [ ] Create Alembic migration if schema changes needed
- [ ] Rewrite service functions using `select()` / `insert()` / `update()` / `delete()`
- [ ] Add type hints to all functions
- [ ] Preserve exact same return dict format
- [ ] Remove `row_to_dict()` / `rows_to_list()` usage
- [ ] Remove `_translate_sql()` dependency
- [ ] Run existing tests — they must pass without changes
- [ ] Run the service's route tests

---

### Phase 5 — Remove Raw SQL Infrastructure (1 day)

**Goal:** Delete unused raw SQL code.

1. Delete `backend/app/database.py` (all CREATE TABLE, _translate_sql, row_to_dict, get_db)
2. Remove `aiomysql` from `requirements.txt`
3. Remove `pymysql` from `requirements.txt`
4. Clean up `main.py` — remove `init_db()`, `close_pool()` calls
5. Remove `_looks_like_bcrypt_hash()` if unused
6. Clean up `MySQLDB`, `CursorWrapper`, `CompatRow` classes

**Verification:**
- Full test suite passes
- Server starts cleanly
- All 144 endpoints return expected responses

---

### Phase 6 — Remaining Table Conversions (3-4 days)

**Goal:** Convert all remaining raw CREATE TABLE statements to SQLAlchemy models.

Schema changes needed for other tables:

| Table | Changes |
|---|---|
| `devices` | Convert timestamps to DATETIME, add FK for `current_holder_id` → `users.id` |
| `distributions` | Convert timestamps to DATETIME, add FKs for `from_user_id`, `to_user_id` |
| `defects` | Convert timestamps to DATETIME, add FKs |
| `returns` | Convert timestamps to DATETIME, add FKs |
| `notifications` | Add FK `user_id` → `users.id`, convert timestamps |
| `api_activity_logs` | Convert timestamp to DATETIME |
| `change_requests` | Add FKs |
| All external_inventory tables | Add proper FKs |

**Strategy per table:**
1. Create SQLAlchemy model
2. Create Alembic migration (schema changes only)
3. Add foreign key constraints
4. Run data verification queries

---

### Phase 7 — Frontend Cleanup (2-3 days, parallel with Phase 4-6)

**Goal:** Remove duplicated role/permission logic, drive from API.

1. **Roles API integration:**
   - Fetch roles from `GET /api/roles` on app init
   - Store in React context or cache
   - Drive role-based routing from API data

2. **Remove `utils/roles.js` duplication:**
   - Delete `normalizeRole()` — use role ID from user object
   - Delete `ROLES` constant — fetch from API
   - Delete `ROLE_LABELS` — fetch from API
   - Keep `isForcedCredentialUpdateRequired()` — it reads user fields, not role

3. **Update `App.jsx`:**
   - `allowedRoles` accepts role slugs or IDs
   - Route guards use context roles

4. **Digital identities UI:**
   - Add/remove digital IDs on user edit form
   - Show in user detail modal
   - Bulk upload updated to support multiple IDs

5. **Remove preference fields from UI:**
   - Settings page uses localStorage instead of API for theme/preferences
   - Or keep `user_preferences` table if multi-device needed

6. **Remove `is_verified` from user detail display**

---

### Phase 8 — Test Audit & Cleanup (2 days)

1. Run full test suite — all 24 backend test files + 3 frontend component tests
2. Fix any regressions
3. Add integration tests for new models:
   - Digital identities CRUD
   - Role/permission API
4. Verify all 14 route handlers still return matching response shapes
5. Compare API response diffs before/after migration
6. Manual QA walkthrough of all major flows:
   - Login, logout, refresh
   - Create/edit user (all roles)
   - Device CRUD
   - Distribution workflow
   - Defect workflow
   - Reports and dashboard

---

## 4. Service Layer Migration Patterns

### 4.1 Before (raw SQL)

```python
async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
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
```

### 4.2 After (SQLAlchemy)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(User).where(User.id == int(user_id))
        )
        user = result.scalar_one_or_none()
        if not user:
            return None
        return _user_to_dict(user)


def _user_to_dict(user: User) -> Dict[str, Any]:
    """Convert User model to API response dict (preserves existing format)."""
    primary_di = next(
        (di for di in user.digital_identities if di.is_primary), None
    ) if user.digital_identities else None

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role.name,  # slug from roles table
        "digital_id": primary_di.digital_id if primary_di else None,
        "broadband_id": primary_di.broadband_id if primary_di else None,
        "phone": user.phone,
        "department": user.department,
        "location": user.location,
        "address": user.address,
        "designation": user.designation,
        "parent_id": str(user.parent_id) if user.parent_id else None,
        "status": user.status,
        "is_verified": user.is_verified,
        "permissions": user.permissions or {},
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        # Note: theme, compact_mode, email_notifications, push_notifications removed
    }
```

### 4.3 Paginated List Query Pattern

```python
async def get_users(
    page: int = 1,
    page_size: int = 20,
    role_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    parent_id: Optional[int] = None,
) -> Dict[str, Any]:
    async with AsyncSession(engine) as session:
        query = select(User)

        if role_id:
            query = query.where(User.role_id == role_id)
        if status:
            query = query.where(User.status == status)
        if parent_id:
            query = query.where(User.parent_id == parent_id)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                User.name.like(pattern) | User.email.like(pattern)
            )

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar()

        # Paginated results
        offset = (page - 1) * page_size
        query = query.order_by(User.created_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await session.execute(query)
        users = result.scalars().all()

        return {
            "data": [_user_to_dict(u) for u in users],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }
```

---

## 5. Raw SQL vs SQLAlchemy — Coexistence Strategy

During migration (Phases 2-6), both systems will coexist:

```python
# Option A: Keep both connected (simpler)
# database.py (raw SQL) + SQLAlchemy engine
# Services choose which to use based on migration status

# Option B: Raw SQL wraps SQLAlchemy (cleaner eventual migration)
# Rewrite get_db() to use SQLAlchemy session internally
# But this adds complexity for diminishing returns
```

**Recommendation:** Option A. Both systems connect to the same MySQL instance. A service either uses raw SQL OR SQLAlchemy, never both in the same function. This avoids dual-write complexity.

---

## 6. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| API response shape changes | Medium | High | `_user_to_dict()` explicitly maps to match existing format; compare diffs before/after |
| Foreign key constraints fail on existing data | High | Medium | Run data validation queries before adding FKs; fix orphans first |
| Performance regression from ORM | Low | Low | SQLAlchemy 2.0 generates efficient SQL; profile if needed |
| Migration script takes too long on large dataset | Medium | Medium | Run migrations in batches; test on production clone first |
| Bug in service migration causes data corruption | Low | Critical | Each service change is tested; dual systems allow rollback |
| Frontend breaks due to removed response fields | Medium | High | Frontend reads `digital_id` from API — need to populate from `digital_identities`; verify all 34 pages |

---

## 7. Rollback Plan

Each phase has a rollback:

| Phase | Rollback |
|---|---|
| Phase 0 | Revert Alembic init, remove SQLAlchemy deps |
| Phase 1 | Drop `roles`/`role_permissions` tables, restore hardcoded dicts |
| Phase 2 | Restore dropped columns from migration backup, drop new columns |
| Phase 3 | Drop `digital_identities` table, restore data to users table |
| Phase 4 | Revert to raw SQL in the affected service file |
| Phase 5 | Restore `database.py` from git, reinstall aiomysql |
| Phase 6 | Drop FKs if they cause issues, revert to schema-less design |

**General rule:** Never merge a phase until the previous phase is verified stable in production (or staging).

---

## 8. Summary Timeline

| Phase | Duration | Dependencies |
|---|---|---|
| Phase 0: Infrastructure | 1-2 days | None |
| Phase 1: Roles & Permissions | 2-3 days | Phase 0 |
| Phase 2: Users Table Cleanup | 3-4 days | Phase 1 |
| Phase 3: Digital Identities | 2 days | Phase 2 |
| Phase 4: Service Migration | 5-7 days | Phase 2 |
| Phase 5: Remove Raw SQL | 1 day | Phase 4 |
| Phase 6: Remaining Tables | 3-4 days | Phase 5 |
| Phase 7: Frontend Cleanup | 2-3 days | Phase 1-3 (parallel) |
| Phase 8: Test & Verify | 2 days | All phases |

**Total: ~21-26 days** depending on parallel work opportunities (Phases 4 and 7 can run in parallel with different team members).
