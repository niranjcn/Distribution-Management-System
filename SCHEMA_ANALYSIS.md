# DMS Schema Analysis & Redesign Report

## 1. Business Domain Overview

```
                    ┌──────────────────┐
                    │  Super Admin     │
                    │  MD/Director     │
                    │  Manager         │
                    │  PDIC Staff      │
                    └───────┬──────────┘
                            │ manages
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                   ▼
  ┌───────────────┐ ┌──────────────┐ ┌──────────────────┐
  │Sub Distributor│ │Sub Dist MD   │ │ Change Requests  │
  │ MD/Manager    │ │              │ │ Approvals         │
  └───────┬───────┘ └──────────────┘ └──────────────────┘
          │ owns/distributes to
          ▼
  ┌───────────────┐
  │   Cluster     │
  └───────┬───────┘
          │ manages
          ▼
  ┌───────────────┐
  │   Operator    │
  └───────────────┘
```

**Core workflows:**

1. **User Management** — create/manage users across 8 roles, hierarchical visibility
2. **Device Management** — register, track, transfer devices between users
3. **Distribution** — distribute devices from admin down to operators, with receipt confirmation and disputes
4. **Defect Management** — report defects, escalate, replace devices, process payments
5. **Return Management** — return devices up the chain
6. **Approval Workflow** — approvals for distributions, returns, defects with role-based routing
7. **Notifications** — in-app event notifications
8. **External Inventory** — track non-DMS inventory (POs, receipts, stock movements)
9. **Reports & Dashboard** — aggregated stats, KPIs, charts
10. **Backup** — automated MySQL + document backup to rclone

---

## 2. Current Schema Problems (All Tables)

### 2.1 Systemic Issues

| Issue | Impact | Tables Affected |
|---|---|---|
| **Timestamps as VARCHAR(64)** | No DB-side sorting, no range queries, no timezone handling | ALL tables |
| **No foreign key constraints** | Orphaned references, no cascading deletes, data integrity relies entirely on application code | ALL tables |
| **No ENUM types** | Role/status constraints at application layer only, possible invalid data | ALL tables |
| **No CHECK constraints** | Business rules not enforced at database level | ALL tables |
| **JSON stored as LONGTEXT** | No JSON validation, no JSON path queries | `users.permissions`, `defects.images`, `distributions.device_ids` |
| **Mixed naming conventions** | Some `snake_case`, some inconsistent prefixes | `inventory_*` vs `external_*` naming mismatch |
| **No column comments** | Schema intent is invisible | ALL tables |
| **Schema defined in Python strings** | No migration history, no rollback, no versioning | ALL tables (in `database.py`) |
| **ID as VARCHAR in some FKs** | `user_id VARCHAR(64)` instead of `INT` — type mismatch with `users.id INT` | `defects`, `returns`, `distributions`, `notifications` |

---

## 3. Table-by-Table Analysis

### 3.1 `users`

**Purpose:** All 8 user roles in one table. The hierarchical backbone of the entire application.

**Current schema issues:**
- `digital_id`, `broadband_id`, `cluster_id`, `operator_id` — role-specific, NULL for 60%+ of users
- `theme`, `compact_mode`, `email_notifications`, `push_notifications` — UI preferences in business table
- `is_verified` — never enforced, always 0
- `permissions` as LONGTEXT — should be JSON
- `created_at`/`updated_at`/`last_login`/`locked_until` as VARCHAR(64) — should be DATETIME
- No FK on `parent_id` — possible orphaned references
- `role` as string — should be FK to `roles` table

**Referenced as FK by (implicitly, no actual constraints):**
- `devices.held_by`, `devices.current_holder_id`
- `distributions.from_user_id`, `distributions.to_user_id`
- `defects.reported_by`, `defects.assigned_to`, `defects.resolved_by`, etc.
- `returns.requested_by`, `returns.approved_by`
- `notifications.user_id`
- `change_requests.requested_by`
- `api_activity_logs.actor_id`
- `operators.assigned_to`

**Redesign:**

```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    role_id INT NOT NULL,
    status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',

    -- Hierarchy
    parent_id INT NULL,
    created_by INT NULL,

    -- Profile
    phone VARCHAR(64),
    department VARCHAR(255),
    location VARCHAR(255),
    address TEXT,
    designation VARCHAR(255),

    -- Security
    force_email_change BOOLEAN DEFAULT FALSE,
    force_password_change BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    failed_login_attempts INT DEFAULT 0,
    locked_until DATETIME NULL,
    last_login DATETIME NULL,

    -- Permissions (role overrides)
    permissions JSON,

    -- Timestamps
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_users_parent_id (parent_id),
    INDEX idx_users_role_id (role_id),
    INDEX idx_users_status (status),
    INDEX idx_users_email (email),
    CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles(id),
    CONSTRAINT fk_users_parent FOREIGN KEY (parent_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_users_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Removed columns:** `digital_id`, `broadband_id`, `cluster_id`, `operator_id`, `theme`, `compact_mode`, `email_notifications`, `push_notifications`

**Note on `is_verified`:** Kept because it might be used in future, but currently dead. If you're sure it will never be used, remove it.

---

### 3.2 `digital_identities` (NEW)

**Purpose:** Replace single `digital_id`/`broadband_id` on `users` with 1:N support (operators need multiple digital IDs).

**Relationships:** N:1 with `users`

```sql
CREATE TABLE digital_identities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    digital_id VARCHAR(128) NOT NULL,
    broadband_id VARCHAR(128),
    is_primary BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE INDEX idx_di_digital_id (digital_id),
    INDEX idx_di_user_id (user_id),
    CONSTRAINT fk_di_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.3 `roles` (NEW)

**Purpose:** Database-driven role definitions — replace the hardcoded `ROLE_HIERARCHY` dict.

**Relationships:** 1:N with `users`, 1:N with `role_permissions`

```sql
CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) UNIQUE NOT NULL,      -- 'super_admin', 'sub_distributor', etc.
    label VARCHAR(128) NOT NULL,           -- 'Super Admin', 'Sub Distributor'
    level INT NOT NULL,                    -- 80 = super_admin, 10 = operator
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.4 `role_permissions` (NEW)

**Purpose:** Database-driven permission matrix — replace the hardcoded `PERMISSIONS` dict.

**Relationships:** N:1 with `roles`

```sql
CREATE TABLE role_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role_id INT NOT NULL,
    permission_key VARCHAR(128) NOT NULL,  -- 'users:read', 'devices:create', etc.
    is_granted BOOLEAN DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE INDEX idx_rp_role_perm (role_id, permission_key),
    CONSTRAINT fk_rp_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Seed data:**

```sql
INSERT INTO roles (name, label, level) VALUES
    ('super_admin', 'Super Admin', 80),
    ('md_director', 'MD/Director', 70),
    ('manager', 'Manager', 60),
    ('pdic_staff', 'PDIC Staff', 50),
    ('sub_distribution_manager', 'Sub Distribution MD/Manager', 40),
    ('sub_distributor', 'Sub Distributor', 30),
    ('cluster', 'Cluster', 20),
    ('operator', 'Operator', 10);

-- 55 permission rows matching backend/app/utils/permissions.py:16-55
INSERT INTO role_permissions (role_id, permission_key) VALUES
    -- users:read
    (1, 'users:read'), (2, 'users:read'), (3, 'users:read'),
    (5, 'users:read'), (6, 'users:read'), (7, 'users:read'),
    -- users:create
    (1, 'users:create'), (3, 'users:create'), (6, 'users:create'), (7, 'users:create'),
    -- ... (all 55 permissions from PERMISSIONS dict)
```

---

### 3.5 `devices`

**Purpose:** Core device inventory — tracks every device's status, location, holder.

**Current schema issues:**
- `current_holder_id VARCHAR(64)` — should be INT FK to `users.id`
- `held_by` appears unused alongside `current_holder_id` — potential duplication
- `metadata LONGTEXT` — should be JSON
- All timestamps as VARCHAR(64)
- No FK on `current_holder_id` → `users.id`
- `nuid`, `serial_number`, `mac_address` are unique but nullable — MySQL allows multiple NULLs

**Relationships:**
- `current_holder_id` → `users.id` (N:1)
- Referenced by: `distributions` (via `distribution_devices`), `defects`, `returns`, `device_history`

**Redesign:**

```sql
CREATE TABLE devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(128) UNIQUE NOT NULL,
    device_type VARCHAR(128) NOT NULL,
    model VARCHAR(255) NOT NULL,
    manufacturer VARCHAR(255) NOT NULL,
    serial_number VARCHAR(255) UNIQUE,
    mac_address VARCHAR(255) UNIQUE,
    nuid VARCHAR(255) UNIQUE,
    band_type VARCHAR(64),

    status VARCHAR(64) DEFAULT 'available',
    current_location VARCHAR(255),
    current_holder_id INT,
    current_holder_name VARCHAR(255),
    current_holder_type VARCHAR(64),
    registered_by_name VARCHAR(255),

    purchase_date DATE,
    warranty_expiry DATE,
    metadata JSON,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_devices_status (status),
    INDEX idx_devices_holder (current_holder_id),
    INDEX idx_devices_device_type (device_type),
    CONSTRAINT fk_devices_holder FOREIGN KEY (current_holder_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Changes from current:**
- `current_holder_id` → INT with FK to `users.id`
- `metadata` → JSON type
- `purchase_date`/`warranty_expiry` → DATE type
- `created_at`/`updated_at` → DATETIME

---

### 3.6 `device_history`

**Purpose:** Audit trail for device movements (distributions, holder changes, etc.).

**Current schema issues:**
- `performed_by VARCHAR(64)` — should be INT FK to `users.id`
- `from_user_id`/`to_user_id` as VARCHAR(64) — should be INT FK
- `timestamp` as VARCHAR(64) — should be DATETIME
- High write volume — needs proper indexing

**Redesign:**

```sql
CREATE TABLE device_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    action VARCHAR(128) NOT NULL,

    from_user_id INT,
    from_user_name VARCHAR(255),
    to_user_id INT,
    to_user_name VARCHAR(255),

    status_before VARCHAR(64),
    status_after VARCHAR(64),
    location VARCHAR(255),
    notes JSON,

    performed_by INT,
    performed_by_name VARCHAR(255),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_dh_device_id (device_id),
    INDEX idx_dh_created_at (created_at DESC),
    INDEX idx_dh_performed_by (performed_by),
    INDEX idx_dh_from_user (from_user_id),
    INDEX idx_dh_to_user (to_user_id),
    CONSTRAINT fk_dh_performed_by FOREIGN KEY (performed_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_dh_from_user FOREIGN KEY (from_user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_dh_to_user FOREIGN KEY (to_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.7 `distributions`

**Purpose:** Device distribution workflow — track devices moving from one user to another.

**Current schema issues:**
- `device_ids LONGTEXT` — duplicate of `distribution_devices` data! This is denormalized.
- `from_user_id`/`to_user_id` as VARCHAR(64) — should be INT FK
- `approved_by` as VARCHAR(64) — should be INT FK
- `created_by` as VARCHAR(64) — should be INT FK
- All timestamps as VARCHAR(64)
- `date_of_distribution` as VARCHAR(64) — should be DATE
- `status` as VARCHAR(64) — should be ENUM or reference to status table

**Relationships:**
- `distribution_devices` (1:N)
- `from_user_id` → `users.id`
- `to_user_id` → `users.id`

**Redesign:**

```sql
CREATE TABLE distributions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    distribution_id VARCHAR(128) UNIQUE NOT NULL,

    device_count INT DEFAULT 0,

    from_user_id INT NOT NULL,
    from_user_name VARCHAR(255),
    from_user_type VARCHAR(64),

    to_user_id INT NOT NULL,
    to_user_name VARCHAR(255),
    to_user_type VARCHAR(64),

    status VARCHAR(64) DEFAULT 'pending',  -- pending, approved, in_transit, delivered, disputed, cancelled
    request_date DATETIME NOT NULL,
    date_of_distribution DATE,
    approval_date DATETIME,
    delivery_date DATETIME,

    notes TEXT,
    manifest_file VARCHAR(255),

    approved_by INT,
    approved_by_name VARCHAR(255),
    created_by INT NOT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_dist_status (status),
    INDEX idx_dist_from_user (from_user_id),
    INDEX idx_dist_to_user (to_user_id),
    INDEX idx_dist_created_at (created_at),

    CONSTRAINT fk_dist_from_user FOREIGN KEY (from_user_id) REFERENCES users(id),
    CONSTRAINT fk_dist_to_user FOREIGN KEY (to_user_id) REFERENCES users(id),
    CONSTRAINT fk_dist_approved_by FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_dist_created_by FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Note:** `device_ids` LONGTEXT should be **removed** — it's redundant with `distribution_devices`. But check if any service code reads it directly (it does in `distribution_service.py` line ~708 and other places). Migration must populate `distribution_devices` from existing `device_ids` JSON strings first.

---

### 3.8 `distribution_devices`

**Purpose:** Junction table linking distributions to devices.

**Current schema issues:**
- `distribution_id VARCHAR(128)` — should be INT FK (but distribution table uses distribution_id as VARCHAR)
- `device_id INT` — should be INT FK to `devices.id`
- No unique constraint on `(distribution_id, device_id)` — duplicate entries possible

**Redesign:**

```sql
CREATE TABLE distribution_devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    distribution_id VARCHAR(128) NOT NULL,
    device_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE INDEX idx_dd_unique (distribution_id, device_id),
    INDEX idx_dd_distribution (distribution_id),
    INDEX idx_dd_device (device_id),
    CONSTRAINT fk_dd_distribution FOREIGN KEY (distribution_id)
        REFERENCES distributions(distribution_id) ON DELETE CASCADE,
    CONSTRAINT fk_dd_device FOREIGN KEY (device_id)
        REFERENCES devices(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.9 `defects`

**Purpose:** Defect reporting and resolution workflow — from report through replacement to payment.

**Current schema issues:**
- **Massive table** — 35+ columns mixing defect data with payment data with replacement data
- `device_id VARCHAR(64)` — should be INT FK to `devices.id`
- `reported_by`/`resolved_by`/`forwarded_to_management_by`/`payment_confirmed_by`/etc. as VARCHAR(64) — should be INT FK
- `operator_id`/`sub_distributor_id` as VARCHAR(64) — should be INT FK to `users.id`
- `images LONGTEXT` — JSON array of image URLs, should be proper JSON
- All timestamps as VARCHAR(64)
- **Payment fields mixed in** (return_amount, service_charge, payment_bill_url, payment_confirmed) — should be separate `defect_payments` table
- **Replacement fields mixed in** (replacement_device_id, replacement_requested_at, etc.) — some reference `defect_replacement_devices` concept but stored inline

**Current columns (35):**
`id`, `report_id`, `device_id`, `device_serial`, `device_type`, `reported_by`, `reported_by_name`, `defect_type`, `severity`, `description`, `symptoms`, `report_target`, `forwarded_to_management`, `forwarded_to_management_at`, `forwarded_to_management_by`, `forwarded_to_management_by_name`, `operator_id`, `sub_distributor_id`, `status`, `resolution`, `resolved_by`, `resolved_by_name`, `resolved_at`, `replacement_device_id`, `replacement_requested_at`, `replacement_confirmed_at`, `replacement_confirmed_by`, `replacement_confirmed_by_name`, `return_amount`, `service_charge`, `payment_bill_url`, `payment_confirmed`, `payment_confirmed_at`, `payment_confirmed_by`, `payment_confirmed_by_name`, `payment_due_user_id`, `payment_due_user_name`, `images`, `auto_return_id`, `created_at`, `updated_at`

**Redesign — split into 3 tables:**

```sql
-- Core defect record
CREATE TABLE defects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    report_id VARCHAR(128) UNIQUE NOT NULL,

    device_id INT NOT NULL,
    device_serial VARCHAR(255),
    device_type VARCHAR(128),

    reported_by INT NOT NULL,
    reported_by_name VARCHAR(255),
    operator_id INT,
    sub_distributor_id INT,

    defect_type VARCHAR(64) NOT NULL,
    severity ENUM('low', 'medium', 'high', 'critical') NOT NULL,
    status VARCHAR(64) DEFAULT 'reported',
    description TEXT NOT NULL,
    symptoms TEXT,
    resolution TEXT,

    report_target VARCHAR(64) DEFAULT 'manager_admin',
    forwarded_to_management BOOLEAN DEFAULT FALSE,
    forwarded_to_management_at DATETIME,
    forwarded_to_management_by INT,
    forwarded_to_management_by_name VARCHAR(255),

    resolved_by INT,
    resolved_by_name VARCHAR(255),
    resolved_at DATETIME,

    images JSON,  -- array of image URLs

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_defects_status (status),
    INDEX idx_defects_device (device_id),
    INDEX idx_defects_reported_by (reported_by),
    INDEX idx_defects_severity (severity),
    CONSTRAINT fk_def_device FOREIGN KEY (device_id) REFERENCES devices(id),
    CONSTRAINT fk_def_reported_by FOREIGN KEY (reported_by) REFERENCES users(id),
    CONSTRAINT fk_def_operator FOREIGN KEY (operator_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_def_sub_distributor FOREIGN KEY (sub_distributor_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_def_resolved_by FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_def_forwarded_by FOREIGN KEY (forwarded_to_management_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Replacement tracking (extracted from defects)
CREATE TABLE defect_replacements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    defect_id INT NOT NULL UNIQUE,
    replacement_device_id INT,
    requested_at DATETIME,
    confirmed_at DATETIME,
    confirmed_by INT,
    confirmed_by_name VARCHAR(255),

    CONSTRAINT fk_dr_defect FOREIGN KEY (defect_id) REFERENCES defects(id) ON DELETE CASCADE,
    CONSTRAINT fk_dr_device FOREIGN KEY (replacement_device_id) REFERENCES devices(id) ON DELETE SET NULL,
    CONSTRAINT fk_dr_confirmed_by FOREIGN KEY (confirmed_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Payment tracking (extracted from defects)
CREATE TABLE defect_payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    defect_id INT NOT NULL UNIQUE,
    return_amount DECIMAL(10, 2) DEFAULT 0,
    service_charge DECIMAL(10, 2) DEFAULT 0,
    bill_url VARCHAR(255),
    is_confirmed BOOLEAN DEFAULT FALSE,
    confirmed_at DATETIME,
    confirmed_by INT,
    confirmed_by_name VARCHAR(255),
    due_user_id INT,
    due_user_name VARCHAR(255),

    CONSTRAINT fk_dpay_defect FOREIGN KEY (defect_id) REFERENCES defects(id) ON DELETE CASCADE,
    CONSTRAINT fk_dpay_confirmed_by FOREIGN KEY (confirmed_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_dpay_due_user FOREIGN KEY (due_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.10 `defect_images`

**Current:** Not a separate table — JSON array in `defects.images` LONGTEXT column.

The images are stored in rclone cloud storage (defect_photos/), and the URLs are serialized as JSON. This is fine — no need for a separate table. Just change `images` column type to `JSON`.

---

### 3.11 `returns`

**Purpose:** Device return workflow — devices returned up the chain.

**Current schema issues:**
- `device_id VARCHAR(64)` — should be INT FK
- `requested_by`/`approved_by` as VARCHAR(64) — should be INT FK
- All timestamps as VARCHAR(64)
- `request_date`/`approval_date`/`received_date` — should be DATETIME

**Redesign:**

```sql
CREATE TABLE returns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    return_id VARCHAR(128) UNIQUE NOT NULL,

    device_id INT NOT NULL,
    device_serial VARCHAR(255),
    device_type VARCHAR(128),
    defect_id INT,

    requested_by INT NOT NULL,
    requested_by_name VARCHAR(255),
    return_to INT,
    return_to_name VARCHAR(255),

    reason VARCHAR(64) NOT NULL,
    description TEXT,
    mac_address VARCHAR(255),

    status VARCHAR(64) DEFAULT 'pending',
    request_date DATETIME NOT NULL,
    approval_date DATETIME,
    received_date DATETIME,

    approved_by INT,
    approved_by_name VARCHAR(255),

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_returns_status (status),
    INDEX idx_returns_device (device_id),
    INDEX idx_returns_requested_by (requested_by),
    CONSTRAINT fk_ret_device FOREIGN KEY (device_id) REFERENCES devices(id),
    CONSTRAINT fk_ret_requested_by FOREIGN KEY (requested_by) REFERENCES users(id),
    CONSTRAINT fk_ret_return_to FOREIGN KEY (return_to) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_ret_approved_by FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_ret_defect FOREIGN KEY (defect_id) REFERENCES defects(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.12 `approvals`

**Purpose:** Generic approval workflow for distributions, returns, defects.

**Current schema issues:**
- `requested_by`/`approved_by` as VARCHAR(64) — should be INT FK
- All timestamps as VARCHAR(64)
- `entity_id`/`entity_type` as generic pair — no FK constraint (polymorphic pattern)

**Redesign:**

```sql
CREATE TABLE approvals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    approval_type VARCHAR(64) NOT NULL,     -- 'distribution', 'return', 'defect'
    entity_id VARCHAR(64) NOT NULL,          -- polymorphic: could be distribution_id, return_id, etc.
    entity_type VARCHAR(64) NOT NULL,        -- 'distribution', 'return', 'defect'

    requested_by INT NOT NULL,
    requested_by_name VARCHAR(255),

    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    priority ENUM('low', 'medium', 'high', 'urgent') DEFAULT 'medium',

    request_date DATETIME NOT NULL,
    approved_by INT,
    approved_by_name VARCHAR(255),
    approval_date DATETIME,
    rejection_reason TEXT,
    notes TEXT,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_app_status_type (status, approval_type),
    INDEX idx_app_entity (entity_id, entity_type),
    INDEX idx_app_requested_by (requested_by),
    CONSTRAINT fk_app_requested_by FOREIGN KEY (requested_by) REFERENCES users(id),
    CONSTRAINT fk_app_approved_by FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.13 `approval_role_routing`

**Purpose:** Configuration for which roles can approve which approval types.

**Current state:** Only 3 approval types (distribution, return, defect), each with 3 role toggles (admin, manager, staff). This is simple enough that it can stay as-is with minor type fixes.

**Redesign:**

```sql
CREATE TABLE approval_role_routing (
    id INT AUTO_INCREMENT PRIMARY KEY,
    approval_type VARCHAR(64) UNIQUE NOT NULL,
    admin_enabled BOOLEAN DEFAULT TRUE,
    manager_enabled BOOLEAN DEFAULT TRUE,
    staff_enabled BOOLEAN DEFAULT TRUE,
    updated_by INT,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_arr_updated_by FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.14 `operators`

**Purpose:** Standalone operator records, separate from `users` table. This is a **legacy design** — operators also exist in the `users` table with `role = 'operator'`.

**Current schema issues:**
- **DUPLICATES user data** — `operators.operator_id` = `users.operator_id`, `operators.name` = `users.name`, etc.
- `assigned_to` as VARCHAR(64) — should be INT FK to `users.id`
- When a user with role=operator is created, data must also be inserted HERE — dual-write risk
- When an operator is assigned, both tables must be updated — sync risk

**Business question:** Do operators need to exist in BOTH places? If yes, this is a 1:1 relationship. If no, operators should ONLY be in the `users` table.

**If keeping (1:1 with users):**

```sql
CREATE TABLE operator_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    address VARCHAR(255),
    area VARCHAR(255),
    city VARCHAR(255),
    connection_type VARCHAR(64),
    device_count INT DEFAULT 0,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_op_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**If removing:** Migrate any operator-specific data (address, area, city, connection_type) to `users` table (as nullable columns) or to `digital_identities`. The `device_count` can be a computed value from queries.

**Recommendation: MERGE into users.** The `operators` table adds dual-write complexity with almost no benefit. All operator-specific fields can be:
- `address` → added to `users` (Phase 2)
- `area`/`city` → added to `users` or dropped
- `connection_type` → added to `users`
- `device_count` → computed from devices query
- `assigned_to` → `users.parent_id` (already serves this purpose)

---

### 3.15 `notifications`

**Purpose:** In-app notifications for events (distributions, defects, approvals, etc.).

**Current schema issues:**
- `user_id VARCHAR(64)` — should be INT FK
- `metadata LONGTEXT` — should be JSON
- `created_at` as VARCHAR(64) — should be DATETIME
- `is_read` TINYINT(1) — should be BOOLEAN

**Redesign:**

```sql
CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(64) DEFAULT 'info',
    category VARCHAR(64) NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    link VARCHAR(255),
    metadata JSON,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_notif_user_read (user_id, is_read),
    INDEX idx_notif_user_created (user_id, created_at DESC),
    INDEX idx_notif_created_at (created_at),
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Cleanup note:** Old notifications should be purged regularly. The `activity_log_cleanup.py` service already does this. Add `created_at` index to support efficient range deletion.

---

### 3.16 `change_requests`

**Purpose:** User-initiated change requests (change email, password, device status).

**Current schema issues:**
- `requested_by`/`reviewed_by` as INT — already correct! But no FK constraint
- `new_password` stores hashed passwords — **security concern** even if hashed; should not persist
- All timestamps as VARCHAR(64)
- `request_type` as VARCHAR(128) — could be ENUM
- `settings JSON` column mentioned in Pydantic model but not in CREATE TABLE — check if it exists

**Redesign:**

```sql
CREATE TABLE change_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id VARCHAR(128) UNIQUE NOT NULL,

    request_type VARCHAR(128) NOT NULL,   -- 'email_change', 'password_reset', 'device_status'
    requested_by INT NOT NULL,
    requested_by_name VARCHAR(255) NOT NULL,
    requested_by_role VARCHAR(64) NOT NULL,

    target_user_id INT,
    device_id VARCHAR(64),

    new_email VARCHAR(255),
    new_password_hash VARCHAR(255),       -- consider removing; ephemeral use only
    requested_status VARCHAR(64),
    reason TEXT,

    status VARCHAR(32) DEFAULT 'pending',
    reviewed_by INT,
    reviewed_by_name VARCHAR(255),
    review_note TEXT,
    -- settings: maybe separate table for request type configs

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_cr_status (status),
    INDEX idx_cr_requested_by (requested_by),
    INDEX idx_cr_type_status (request_type, status),
    CONSTRAINT fk_cr_requested_by FOREIGN KEY (requested_by) REFERENCES users(id),
    CONSTRAINT fk_cr_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_cr_target_user FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Security note:** The `new_password` column stores hashed passwords even after the change request is processed. Add a cleanup routine to nullify `new_password_hash` after the request is completed.

---

### 3.17 `external_inventory_items`

**Purpose:** Track non-DMS inventory items (purchased equipment, supplies).

**Note:** This table has been heavily modified via inline migrations — it has more columns now than the original CREATE TABLE. The migration at `database.py:704-778` adds item_id, serial_number, mac_id, identifier_type, identifier, device_type, price, image_url.

**Current schema issues:**
- `created_by VARCHAR(64)` — should be INT FK to `users.id`
- All timestamps as VARCHAR(64)
- `price`, `unit_cost`, `quantity_on_hand` — could use DECIMAL for price
- `sku`, `category` may overlap with `item_id`/`device_type`

**Redesign:**

```sql
CREATE TABLE external_inventory_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    inventory_id VARCHAR(128) UNIQUE NOT NULL,  -- system-generated
    item_id VARCHAR(128) NOT NULL,               -- user-facing ID/SKU

    name VARCHAR(255) NOT NULL,
    serial_number VARCHAR(255),
    mac_id VARCHAR(255),
    identifier_type VARCHAR(128),
    identifier VARCHAR(255),
    device_type VARCHAR(128) NOT NULL,
    custom_device_type VARCHAR(255),

    price DECIMAL(12, 2) DEFAULT 0,
    unit_cost DECIMAL(12, 2) DEFAULT 0,
    unit VARCHAR(32) DEFAULT 'pcs',
    quantity_on_hand INT DEFAULT 0,
    reorder_level INT DEFAULT 0,

    supplier_name VARCHAR(255),
    category VARCHAR(128),
    sku VARCHAR(128),
    location VARCHAR(255),
    status VARCHAR(32) DEFAULT 'active',
    notes TEXT,
    image_url VARCHAR(255),

    created_by INT,
    created_by_name VARCHAR(255),

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_ei_item_id (item_id),
    INDEX idx_ei_serial (serial_number),
    INDEX idx_ei_mac (mac_id),
    INDEX idx_ei_device_type (device_type),
    INDEX idx_ei_status (status),
    INDEX idx_ei_sku (sku),
    CONSTRAINT fk_ei_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.18-3.21 `inventory_purchase_orders`, `inventory_po_lines`, `inventory_receipts`, `inventory_receipt_lines`, `inventory_stock_movements`

**Purpose:** PO management, goods receipt, stock movement tracking for external inventory.

**These 5 tables form a mini-ERP module.** They're relatively well-designed for what they do. Main issues are:
- `created_by`/`ordered_by`/`received_by`/`performed_by` as VARCHAR(64) — should be INT FK
- All timestamps as VARCHAR(64)
- No FK constraints

**Redesign pattern (apply to all):** Same as other tables — convert VARCHAR FKs to INT, convert timestamps to DATETIME, add proper FK constraints.

**Example — purchase_orders:**

```sql
CREATE TABLE purchase_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    po_id VARCHAR(128) UNIQUE NOT NULL,
    supplier_name VARCHAR(255) NOT NULL,
    status VARCHAR(32) DEFAULT 'draft',
    expected_date DATE,
    ordered_by INT NOT NULL,
    ordered_by_name VARCHAR(255),
    total_amount DECIMAL(12, 2) DEFAULT 0,
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_po_ordered_by FOREIGN KEY (ordered_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.22 `api_activity_logs`

**Purpose:** Audit log for meaningful API activity.

**Current schema issues:**
- `actor_id VARCHAR(64)` — should be INT FK
- `created_at` as VARCHAR(64) — should be DATETIME
- High write volume — needs partition strategy

**Redesign:**

```sql
CREATE TABLE api_activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    actor_id INT,
    actor_name VARCHAR(255),
    actor_role VARCHAR(64),
    method VARCHAR(16) NOT NULL,
    path VARCHAR(255) NOT NULL,
    status_code INT,
    description TEXT,
    ip_address VARCHAR(64),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_aal_created_at (created_at),
    INDEX idx_aal_actor (actor_name),
    INDEX idx_aal_path (path),
    INDEX idx_aal_path_status (path, status_code),
    CONSTRAINT fk_aal_actor FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Partitioning consideration:** For high-volume deployments, consider `PARTITION BY RANGE (TO_DAYS(created_at))` to allow efficient old-data purging.

---

### 3.23 `reassignment_requests`

**Purpose:** When a user is deleted, their children (cluster/operators) need reassignment.

**Current schema issues:**
- `deleted_user_id INT` — correct! But no FK (user is being deleted, so FK would fail)
- `reassigned_to_id INT` — should be FK
- `children_json LONGTEXT` — should be JSON
- All timestamps as VARCHAR(64)

**Redesign:**

```sql
CREATE TABLE reassignment_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id VARCHAR(128) UNIQUE NOT NULL,

    deleted_user_id INT NOT NULL,
    deleted_user_name VARCHAR(255),
    deleted_user_role VARCHAR(64) NOT NULL,

    status VARCHAR(32) DEFAULT 'pending',
    reassigned_to_id INT,
    reassigned_to_name VARCHAR(255),
    reassigned_to_role VARCHAR(64),

    children_json JSON,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_rr_status (status),
    CONSTRAINT fk_rr_reassigned_to FOREIGN KEY (reassigned_to_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.24 `token_blacklist`

**Purpose:** Revoked refresh tokens.

**Current schema:**
```sql
CREATE TABLE token_blacklist (
    token_hash VARCHAR(255) PRIMARY KEY,
    expires_at VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    INDEX idx_token_blacklist_expires_at(expires_at)
);
```

**Redesign:** Minimal changes — just fix timestamps.

```sql
CREATE TABLE token_blacklist (
    token_hash VARCHAR(255) PRIMARY KEY,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tb_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

### 3.25 `backup_schedules`

**Current name:** `backup_schedules` (not `db_backup_schedule` as user thought)

**Purpose:** DB backup schedule configuration — effectively a singleton table (one row).

**Redesign:**

```sql
CREATE TABLE backup_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    frequency ENUM('daily', 'weekly', 'monthly') DEFAULT 'daily',
    time_of_day TIME DEFAULT '02:00:00',
    day_of_week VARCHAR(16),    -- 'MON', 'TUE', etc.
    day_of_month INT,
    retention_days INT DEFAULT 30,
    updated_by INT,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_bs_updated_by FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 4. Entity Relationship Diagram (Summary)

```
roles ──── role_permissions
  │
  └──── users ────────────────────────────── digital_identities
           │
           ├── parent_id (self-ref)
           ├── created_by (self-ref)
           ├──┄ devices (current_holder_id)
           ├──┄ device_history (performed_by, from_user_id, to_user_id)
           ├──┄ distributions (from_user_id, to_user_id, approved_by, created_by)
           ├──┄ defects (reported_by, resolved_by, operator_id, sub_distributor_id)
           ├──┄ defect_replacements (confirmed_by)
           ├──┄ defect_payments (confirmed_by, due_user_id)
           ├──┄ returns (requested_by, return_to, approved_by)
           ├──┄ approvals (requested_by, approved_by)
           ├──┄ approval_role_routing (updated_by)
           ├──┄ notifications (user_id)
           ├──┄ change_requests (requested_by, reviewed_by, target_user_id)
           ├──┄ external_inventory_items (created_by)
           ├──┄ purchase_orders (ordered_by)
           ├──┄ receipts (received_by)
           ├──┄ stock_movements (performed_by)
           ├──┄ api_activity_logs (actor_id)
           ├──┄ reassignment_requests (reassigned_to_id)
           ├──┄ backup_schedules (updated_by)
           └──┄ operator_profiles (user_id) -- if keeping

devices ──── distribution_devices
  │              │
  │              └──┄ distributions
  │
  ├──┄ defects
  ├──┄ defect_replacements
  └──┄ returns

defects ──── defect_replacements
  │
  ├──┄ defect_payments
  └──┄ returns (defect_id)

external_inventory_items ──── purchase_orders ──── po_lines
  │                               │
  │                               └──┄ receipts ──── receipt_lines
  │
  └──┄ stock_movements
```

---

## 5. Migration Strategy Summary

### 5.1 Phase Order

| Phase | Tables | Key Changes | Dependency |
|---|---|---|---|
| 0 | Infra | Alembic + SQLAlchemy setup | None |
| 1a | `roles`, `role_permissions` | New tables, seed data | Phase 0 |
| 1b | `users` | Add `role_id`, `address`, `designation`; drop `digital_id`, `broadband_id`, `cluster_id`, `operator_id`, `theme`, `compact_mode`, `email_notifications`, `push_notifications`, `is_verified`; fix timestamps, add FKs | Phase 1a |
| 2 | `digital_identities` | New table, migrate existing data from `users` | Phase 1b |
| 3 | `devices`, `device_history` | Fix timestamps, add FKs, JSON | Phase 1b |
| 4 | `distributions`, `distribution_devices` | Remove `device_ids`, fix FKs, add unique constraint | Phase 3 |
| 5 | `defects` → split into `defects` + `defect_replacements` + `defect_payments` | 3-table split, the biggest migration | Phase 3 |
| 6 | `returns` | Fix timestamps, add FKs | Phase 3 |
| 7 | `approvals`, `approval_role_routing` | Fix timestamps, add FKs | Phase 1b |
| 8 | `operators` → merge OR `operator_profiles` | Depends on decision | Phase 1b |
| 9 | `notifications` | Fix timestamps, add FK, JSON | Phase 1b |
| 10 | `change_requests` | Fix timestamps, add FKs | Phase 1b |
| 11 | External inventory (7 tables) | Fix timestamps, add FKs | Phase 1b |
| 12 | `api_activity_logs` | Fix timestamps, add FK | Phase 1b |
| 13 | `reassignment_requests` | Fix timestamps, JSON | Phase 1b |
| 14 | `token_blacklist` | Fix timestamps | Phase 0 |
| 15 | `backup_schedules` | Fix types | Phase 0 |

### 5.2 Critical Decisions Before Starting

| # | Decision | Options | Recommended |
|---|---|---|---|
| 1 | Merge `operators` table? | Merge into users / keep as 1:1 | **Merge** — dual-write is a bug farm |
| 2 | Split `defects` into 3 tables? | Keep wide / split payments + replacements | **Split** — the payment/replacement columns are independent sub-entities |
| 3 | Drop `is_verified`? | Drop / keep dead / build verification flow | **Drop** — dead column, no business logic depends on it |
| 4 | Drop `device_ids` from distributions? | Keep denormalized / remove (rely on distribution_devices) | **Remove** — it's a duplicate of distribution_devices |
| 5 | UI preferences in DB or localStorage? | Keep `user_preferences` table / localStorage only | **localStorage** — unless multi-device sync is required |
| 6 | ENUM or reference table for statuses? | ENUM (rigid) / reference table (flexible) | **ENUM** for simple, unchanging statuses; reference table if statuses are user-configurable |

### 5.3 Data Migration Pattern

Every column type change follows this pattern:

```python
"""Alembic migration example: convert created_at VARCHAR(64) to DATETIME"""

# Step 1: Add temporary column
op.add_column("users", sa.Column("created_at_new", sa.DateTime(), nullable=True))

# Step 2: Migrate data with STR_TO_DATE
op.execute("UPDATE users SET created_at_new = STR_TO_DATE(created_at, '%Y-%m-%dT%H:%i:%s') WHERE created_at IS NOT NULL")

# Step 3: Drop old column
op.drop_column("users", "created_at")

# Step 4: Rename new column
op.alter_column("users", "created_at_new", new_column_name="created_at")

# Step 5: Make NOT NULL
op.alter_column("users", "created_at", existing_type=sa.DateTime(), nullable=False)
```

### 5.4 Rollback Strategy

Each Alembic migration must have a `downgrade()`:

```python
def downgrade():
    # Reverse: add back VARCHAR column, convert DATETIME back to string
    op.add_column("users", sa.Column("created_at_old", sa.String(64), nullable=True))
    op.execute("UPDATE users SET created_at_old = DATE_FORMAT(created_at, '%Y-%m-%dT%H:%i:%s')")
    op.drop_column("users", "created_at")
    op.alter_column("users", "created_at_old", new_column_name="created_at")
```

For destructive changes (column drops), the downgrade script must preserve data in a backup table first.

---

## 6. Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| `operators` table merge breaks frontend pages that query it | High | Create a VIEW that mirrors old schema; update gradually |
| `defects` table split changes API response shape | High | SQLAlchemy models can reconstruct the old shape via relationships; frontend never needs to know |
| VARCHAR→INT FK migration fails on orphaned references | Medium | Run orphan detection queries before migration; fix or delete orphans |
| VARCHAR→DATETIME migration loses data on malformed strings | Medium | Validate all string dates before migration; use STR_TO_DATE with fallback |
| `device_ids` removal from distributions breaks existing code | High | Search all references first; populate distribution_devices from JSON before dropping |
| Foreign keys on high-traffic tables (api_activity_logs) slow inserts | Low | FK overhead is negligible; measure if concerned |

---

## 7. Recommendation Summary

1. **Do all 21 tables** — not just users. The systemic issues (timestamps, FKs, JSON types) affect every table equally.
2. **Phase by feature domain**, not by table. Each phase should leave one business feature fully migrated and testable.
3. **Start with roles/permissions** (Phase 1a) — it's the foundation everything depends on.
4. **Defects split is the highest-risk, highest-reward** migration. Do it mid-project after gaining confidence.
5. **Operators merge is optional but highly recommended.** The dual-table design adds complexity with no benefit.
6. **Keep API responses backwards-compatible** throughout — the frontend should never break mid-migration.
