# Distribution Management System (DMS)
## Complete Technical & User Documentation — Part 1

---

## 1. Overview

### 1.1 Introduction

The **Distribution Management System (DMS)** is a full-stack enterprise web application designed to manage the complete lifecycle of hardware device distribution across a multi-tier organizational hierarchy. The system enables PDIC (the central distribution body) to track devices from initial registration through every downstream hand-off — to sub-distributors, cluster managers, and end-point operators — while enforcing structured approvals, defect reporting, replacements, and financial reconciliations.

### 1.2 Objectives & Goals

- Provide **end-to-end traceability** of physical devices (ONUs, ONTs, Routers, Modems, Set-top Boxes, etc.)
- Enforce a **role-gated approval workflow** for all device movements
- Enable **real-time defect reporting** with a structured replacement and payment-due lifecycle
- Maintain a **complete audit trail** of every API action across all users
- Support **bulk data operations** (Excel/CSV import for devices and distributions)
- Allow **hierarchical user management** with strict parent-child access scoping
- Provide **role-specific dashboards** with KPIs and analytics

### 1.3 Problems It Solves

| Problem | Solution |
|---|---|
| No visibility of where devices are at any point | Device tracking with full history per serial/MAC |
| Uncontrolled device handoffs | Structured distribution with receipt confirmation |
| No process for defective devices | Formal defect → replacement → confirmation workflow |
| Manual Excel tracking prone to errors | Database-backed system with bulk import validation |
| No audit of who did what | API activity log on every endpoint action |
| Users accessing things they shouldn't | Role-based access control at route and service level |

### 1.4 High-Level Summary

The DMS is accessed via a browser. Users log in and receive a scoped view based on their role. Admins and managers operate from PDIC headquarters and control the full inventory. Sub-distributors, cluster managers, and operators exist in the field and receive/redistribute devices within their hierarchy. The backend is a FastAPI application backed by MySQL. The frontend is a React SPA bundled by Vite and styled with Tailwind CSS.

---

## 2. System Architecture

### 2.1 Overall Architecture

The system uses a **monolithic client-server architecture** with clear separation between frontend and backend, deployed together via Docker Compose.

```
Browser (React SPA)
      │
      │ HTTPS (Tailscale Serve / reverse proxy)
      ▼
  Frontend Container (Vite/React – port 5173)
      │
      │ REST API calls to /api/*
      ▼
  Backend Container (FastAPI – port 8080)
      │
      │ aiomysql async connection pool
      ▼
  MySQL Container (MySQL 8.4 – port 3306, internal only)
      │
      └── Persistent Docker Volume (mysql_data)
```

### 2.2 Component Breakdown

**Frontend (React 18 + Vite 6 + Tailwind CSS 3)**
- `src/App.jsx` — Root router, protected/public route guards
- `src/context/AuthContext.jsx` — Global auth state, token refresh
- `src/context/NotificationContext.jsx` — Real-time notification polling
- `src/pages/` — ~37 page-level components
- `src/components/layout/` — Sidebar, navbar, layout shell
- `src/services/` — Axios-based API service layer

**Backend (FastAPI + Python)**
- `app/main.py` — App factory, middleware registration, router mounting
- `app/config.py` — Pydantic settings loaded from `.env`
- `app/database.py` — MySQL pool management, table creation, migrations
- `app/routes/` — 15 routers (auth, users, devices, distributions, defects, returns, approvals, operators, notifications, reports, dashboard, change_requests, external_inventory, batches, reports)
- `app/services/` — Business logic layer
- `app/models/` — Pydantic request/response models
- `app/middleware/` — Auth middleware, error handler
- `app/core/` — Rate limiter, audit logger, activity logger

**Database (MySQL 8.4)**
- 17 tables auto-created on first startup
- Lightweight column migrations applied idempotently on every boot

### 2.3 Data Flow

1. User opens browser → React app loads from frontend container
2. Login POST to `/api/auth/login` → backend validates credentials → issues JWT stored in HttpOnly cookies
3. All subsequent requests include the cookie; backend validates JWT on every protected route
4. Service layer executes SQL via `aiomysql` connection pool
5. Response returned as JSON; React state updated; UI re-renders

### 2.4 Third-Party Integrations

| Dependency | Purpose |
|---|---|
| Tailscale | Private network tunneling + HTTPS termination for production |
| Docker / Docker Compose | Container orchestration |
| `slowapi` | Rate limiting on sensitive endpoints |
| `starlette-csrf` | CSRF token protection |
| `openpyxl` / `xlrd` | Excel file parsing for bulk imports |
| `passlib[bcrypt]` | Password hashing |
| `python-jose` | JWT creation and validation |
| `lucide-react` | Icon library |
| `chart.js` / `react-chartjs-2` | Charts and analytics |
| `html5-qrcode` | QR code scanning (device lookup) |
| `jspdf` | PDF export of reports |

---

## 3. User Roles & Access Control

The system defines **8 roles** in a strict hierarchy. Each role has a `parent_id` pointing to its managing user within the tree.

### Role Hierarchy (top → bottom)

```
super_admin
├── md_director          (read-only oversight)
└── manager
    └── pdic_staff
        └── sub_distributor
            └── sub_distribution_manager
                └── cluster
                    └── operator
```

---

### 3.1 super_admin

- **Description:** Full system control. There is exactly one seeded super admin on first boot (`admin@dms.com`), but more can be created.
- **Permissions:** Read + Write on ALL resources
- **Can Create:** Any role including other super admins
- **Restricted:** Cannot delete own account
- **Example use case:** Initial system setup, onboarding managers, overriding device statuses, viewing API activity logs

---

### 3.2 md_director

- **Description:** Managing Director / Director level observer. Read-only across the platform.
- **Permissions:** Read-only on users, devices, distributions, defects, reports
- **Cannot:** Create distributions, modify devices, approve/reject anything, manage users
- **Accessible Pages:** Dashboard, Devices, Distributions, Defects, Reports, Activities, Backup
- **Example use case:** Executive reviewing distribution statistics and defect trends

---

### 3.3 manager

- **Description:** Operational manager at PDIC level. Second highest privilege after super_admin.
- **Can Create:** pdic_staff, sub_distribution_manager, sub_distributor, cluster, operator
- **Permissions:** Approve/reject distributions and returns; manage defects; manage users within branch
- **Accessible Pages:** Dashboard, Devices, Distributions, Create Distribution, Defects, Returns, Approvals, Reports, Users, Backup, Change Requests, Notifications
- **Restricted From:** Creating super_admin or md_director; accessing other managers' branches (if scoped)
- **Example use case:** Approving a pending distribution from staff to sub-distributor

---

### 3.4 pdic_staff

- **Description:** PDIC operations staff. Can register devices and initiate distributions.
- **Permissions:** Register devices (manual + bulk), create distributions, view all devices
- **Cannot:** Approve distributions (only management can), manage users
- **Accessible Pages:** Dashboard, Devices (register), Distributions (create), Defects (view), Notifications
- **Example use case:** Receiving a shipment of ONUs and bulk-importing them into the system

---

### 3.5 sub_distributor

- **Description:** External distributor who holds devices and redistributes to sub_distribution_managers and clusters.
- **Permissions:** View own held devices; create distributions to downstream users; report defects; view own distributions
- **Cannot:** Access admin pages, approve anything, register devices
- **Accessible Pages:** Dashboard, Devices (held), Distributions, Create Distribution, Defects, Returns, Delivery Confirmations, Notifications, External Inventory
- **Example use case:** Receiving a batch of routers from PDIC and distributing them to cluster managers

---

### 3.6 sub_distribution_manager

- **Description:** Internal manager within a sub-distributor's branch.
- **Permissions:** Manage clusters and operators under them; view and distribute held devices
- **Cannot:** Create distributions directly (blocked at route level), access admin reports
- **Example use case:** Managing a group of cluster managers under a specific sub-distributor

---

### 3.7 cluster

- **Description:** Mid-level field user who holds devices and distributes to operators directly below them.
- **Permissions:** View held devices; distribute to operators; report defects; confirm delivery
- **Cannot:** Access user management, reports, approvals
- **Accessible Pages:** Dashboard, Devices, Distributions, Defects, Delivery Confirmations, Replacement Confirmation, Notifications
- **Example use case:** Cluster manager distributing modems to 5 operators in their area

---

### 3.8 operator

- **Description:** End-level field user who holds devices and can report defects.
- **Permissions:** View own held devices; report defects; confirm delivery/replacement; view own defects
- **Cannot:** Create distributions to others outside their cluster (limited), access management pages
- **Accessible Pages:** Dashboard, Devices, Distributions, Defects (create/view own), Delivery Confirmations, Replacement Confirmation, Notifications, Pending Dues
- **Example use case:** Field operator receiving a modem and later reporting it as defective

---

## 4. Complete Workflow

### 4.1 User Journey (Login to Full Usage)

**Step 1 — Login**
- User navigates to `/login`
- Enters email + password
- Backend validates credentials, checks account status (`active`)
- If `force_email_change` or `force_password_change` is set, user is redirected to `/force-update-credentials`
- On success: JWT access token (15 min) + refresh token (7 days) issued as HttpOnly cookies

**Step 2 — Force Credential Update (First Login)**
- New accounts created by admins are flagged with `force_email_change=1` and `force_password_change=1`
- User must set a new email and password before accessing any other page
- On completion, new tokens are issued and flags are cleared

**Step 3 — Dashboard**
- Role-specific dashboard loads automatically after login
- KPIs displayed: total devices, active distributions, open defects, pending approvals

**Step 4 — Core Operations (role-dependent)**
- Admin/Manager: Approve items, manage users, register devices
- Staff: Register devices, create distributions
- Sub-distributor/Cluster/Operator: Accept deliveries, report defects, confirm replacements

**Step 5 — Logout**
- POST `/api/auth/logout` → token blacklisted in DB, cookies cleared

---

### 4.2 Distribution Flow

```
[Creator] → Creates Distribution Request → Status: pending
    │
    ▼
[Recipient] → Confirms/Disputes Receipt
    │
    ├── confirmed → Status: approved → Devices transferred to recipient
    └── disputed  → Status: disputed → Admin/Manager notified
                         │
                         ▼
              [Admin/Manager confirms physical return]
                         │
                         └── Status: returned → Sender regains devices
```

**Detailed Steps:**

1. **Create Distribution** — Initiator selects recipient user and device IDs (or uploads CSV/XLSX). Distribution record created with `status=pending`.
2. **Manifest Generated** — Excel manifest auto-generated listing all included devices with serial numbers and MAC addresses.
3. **Recipient Confirms** — Recipient logs in, goes to "Delivery Confirmations", reviews distribution, clicks Confirm or Dispute.
4. **On Confirm** — `status=approved`, device `current_holder_id` updated to recipient, device history logged.
5. **On Dispute** — `status=disputed`, sender notified, admin/manager notified. Sender cannot redistribute devices.
6. **Admin Resolves Dispute** — Admin reviews physical evidence, calls `POST /distributions/{id}/confirm-return` to reset devices back to sender.

**Bulk Upload:**
- Upload CSV/XLSX with columns `mac_address` and/or `nuid`
- System auto-resolves device IDs from identifiers
- Errors per row reported; valid rows create the distribution

---

### 4.3 Approval Flow

The `approvals` table and `approval_role_routing` table govern which roles can process approvals.

| Approval Type | Who Requests | Who Approves |
|---|---|---|
| distribution | Any role | super_admin, manager, pdic_staff (configurable) |
| return | Any role | super_admin, manager, pdic_staff (configurable) |
| defect | Any role | super_admin, manager, pdic_staff (configurable) |

**Routing Configuration:**
- Super admin can modify `approval_role_routing` to enable/disable approvals per role type
- Staff-level approvals can be toggled on/off per type

**Approval Steps:**
1. Item created → approval record inserted with `status=pending`
2. Assigned approver(s) notified via `notifications` table
3. Approver reviews → `status=approved` or `status=rejected` with optional note
4. Parent entity status updated based on approval decision

---

### 4.4 Defect Reporting Flow

```
Status Lifecycle:
  reported → acknowledged → in_progress → resolved → closed
                                ↓
                          replacement_requested
                                ↓
                          waiting_for_replacement
                                ↓
                          replaced (operator confirms)
```

**Detailed Steps:**

1. **Report Created** — Operator/Cluster/Sub-distributor creates defect report:
   - Selects device, defect type (hardware/software/connectivity/physical_damage/other)
   - Sets severity (critical/high/medium/low)
   - Adds description, symptoms, optional images
   - Sets `report_target`: `manager_admin` (goes to management) or `sub_distributor` (goes to their sub-distributor)

2. **Routing** — If target is `sub_distributor`, sub-distributor reviews and can forward to management via `POST /defects/{id}/forward-to-management`

3. **Acknowledgement** — Manager/Admin changes status to `acknowledged`

4. **In Progress** — Manager changes status to `in_progress`; investigation ongoing

5. **Replacement Requested** (optional path):
   - Admin calls `POST /defects/{id}/replace` with replacement device info
   - `replacement_device_id` stored; defective device status set to `defective`; replacement device dispatched
   - Status → `replacement_requested`

6. **Return Amount Set** — Admin may set `return_amount` (financial charge to user for damaged device)

7. **Waiting** — Admin can mark `POST /defects/{id}/mark-waiting` to indicate replacement is being shipped

8. **Operator Confirms Replacement** — Operator calls `POST /defects/{id}/replacement/confirm`; status → `replaced`

9. **Resolution** — Admin resolves with `PATCH /defects/{id}/resolve`; status → `resolved` → `closed`

---

### 4.5 Replacement & Resolution Flow

**Pre-conditions:**
- A defect report exists in `reported` or `in_progress` state
- A replacement device must exist in system (available/returned status) OR be registered fresh

**Steps:**

1. **Admin selects replacement device** via `POST /defects/{id}/replace`:
   - Option A: Provide `replacement_device_id` (existing device)
   - Option B: Provide `mac_address` or `serial_number` to look up
   - Option C: Provide `register_device` payload to create new device on the fly

2. **System actions on replacement**:
   - Defective device: status → `defective`, removed from operator's holding
   - Replacement device: assigned to operator (`current_holder_id`), history logged
   - Auto-return record created to track the defective device return

3. **Payment Bill** (if `return_amount > 0`):
   - Admin uploads bill via `POST /defects/{id}/payment-bill` (JPG/PNG/PDF ≤ 8MB)
   - User notified of pending payment
   - Admin confirms payment via `POST /defects/{id}/confirm-payment`

4. **Operator Confirms Receipt**:
   - Operator sees alert in Replacement Confirmation page
   - Clicks confirm → `replacement_confirmed_at` set, status → `replaced`

5. **Enquiry** (if replacement not received):
   - Operator sends enquiry via `POST /defects/{id}/enquire` with a message
   - Management users notified

6. **Resend Confirmation** (if operator missed notification):
   - Admin calls `POST /defects/{id}/resend-confirmation` to re-notify operator

---

## 5. Features & Modules (Detailed)

### 5.1 Authentication Module

**Feature:** Login with JWT + HttpOnly Cookies + CSRF Protection

- **Inputs:** `email`, `password`
- **Outputs:** `access_token` (15 min), `refresh_token` (7 days) set as HttpOnly cookies
- **Internal Logic:**
  - Email normalized to lowercase
  - Password verified against bcrypt hash
  - Failed attempts tracked; account locked after repeated failures (`locked_until`)
  - Rate limited: 5 login attempts per minute per IP
  - CSRF token required for state-changing requests (via `starlette-csrf`)
- **Edge Cases:**
  - Inactive/suspended accounts blocked with 403
  - Locked accounts return 401 with no information leak
  - Forced credential update flag checked post-login
- **UI:** Login page at `/login` with email/password fields, error display, loading state

---

### 5.2 Device Registration

**Feature:** Register individual or bulk devices into the PDIC inventory

- **Inputs (single):** `device_type`, `model`, `serial_number`, `mac_address`, `manufacturer`, `band_type` (optional), `nuid` (for Set-top boxes)
- **Inputs (bulk):** Excel/CSV file with SB schema OR regular schema
  - SB schema: `vendor, device_type, model, nuid, box_type`
  - Regular schema: `vendor, device_type, model, mac_address, serial_number, [band_type]`
- **Outputs:** Device record(s) created with `status=available`, `current_holder=PDIC`
- **Validation:**
  - MAC address and serial number must be globally unique
  - File magic bytes validated (PK header for XLSX, D0CF for XLS, no null bytes for CSV)
  - Max file size: 10MB
  - `box_type` must be HD or OTT for Set-top boxes
- **Internal Logic:**
  - Device ID auto-generated (`DEV-{uuid}`)
  - `registered_by_name` stored
  - History entry created: action=`registered`
- **Accessible by:** super_admin, manager, pdic_staff
- **Edge Cases:** Duplicate MAC/serial returns specific error row in bulk; does not abort full upload

---

### 5.3 Device Tracking

**Feature:** Full lifecycle tracking of any device by serial number

- **Inputs:** `serial_number` path param
- **Outputs:** Device details + complete `device_history` entries (date, action, from/to user, status before/after, notes)
- **Page:** `/devices/track` with search field + QR scanner using `html5-qrcode`
- **History Actions:** `registered`, `distributed`, `returned`, `defective`, `replaced`, `status_change`, `holder_updated`

---

### 5.4 Distribution Management

**Feature:** Create, track, and confirm device distributions across the hierarchy

- **Inputs:** `device_ids[]`, `to_user_id`, optional `notes`
- **Statuses:** `pending → approved / disputed → returned`
- **Manifest:** Auto-generated Excel file per distribution, downloadable
- **Export:** MAC/NUID export as CSV or XLSX per distribution
- **Access scoping:** Sub-level users only see distributions where they are sender or recipient
- **Bulk upload:** CSV/XLSX with `mac_address`/`nuid` columns to create distribution

---

### 5.5 Defect Reports

**Feature:** Structured defect lifecycle from report to resolution

- **Inputs:** `device_id`, `defect_type`, `severity`, `description`, `symptoms`, `images[]`, `report_target`
- **Image upload:** JPG/PNG/WEBP/PDF files, multiple allowed, stored in `/uploads/`
- **Payment bill:** Separate upload endpoint for proof-of-payment documents
- **Filters:** Status, severity, defect type, search by device/reporter
- **Scoping:**
  - Operators: see their own reported defects or defects on devices they hold
  - Cluster: see defects on their held devices + hierarchy
  - Sub-distributor: see defects in their full branch
  - Management: see all defects

---

### 5.6 Returns Management

**Feature:** Device return requests with approval workflow

- **Reasons:** defective, excess_stock, wrong_device, end_of_contract, other
- **Statuses:** pending → approved → received
- **Linked Defects:** Returns can be linked to a defect report via `defect_id`
- **Accessible by:** sub_distributor, cluster, operator, manager, pdic_staff, super_admin

---

### 5.7 User Management

**Feature:** Create and manage users with hierarchy enforcement

- **Inputs:** `email`, `name`, `role`, `password`, `parent_id`, `phone`, `department`, `location`
- **Force flags:** `force_email_change`, `force_password_change` — set by admin, cleared after first login
- **Status management:** active / inactive / suspended
- **Hierarchy enforcement:**
  - sub_distributor → sub_distribution_manager requires valid parent
  - sub_distribution_manager → cluster requires valid parent
  - cluster → operator assignment validated
- **Credentials admin endpoint:** Super admin can reset any user's email/password via `PATCH /users/{id}/credentials`
- **Hierarchy view:** `/users/hierarchy` shows tree visualization

---

### 5.8 External Inventory

**Feature:** Track non-system items (spare parts, accessories) outside the main device lifecycle

- **Entities:** `external_inventory_items`, `inventory_purchase_orders`, `inventory_po_lines`, `inventory_receipts`, `inventory_receipt_lines`, `inventory_stock_movements`
- **Operations:** Add items, create POs, receive against POs, track stock movements
- **Accessible by:** All roles except super_admin-only features

---

### 5.9 Reports & Analytics

**Feature:** Generate reports across distributions, devices, defects

- **Report types:** Distribution reports, Device inventory reports, Defect reports
- **Export:** PDF via jsPDF, printable views
- **Filters:** Date range, status, device type, user
- **Accessible by:** super_admin, md_director, manager, pdic_staff

---

### 5.10 Notifications

**Feature:** In-app notification system per user

- **Triggers:** Distribution created/confirmed/disputed, defect created/resolved, replacement, approval actions
- **Storage:** `notifications` table with `user_id`, `title`, `message`, `type`, `category`, `is_read`
- **UI:** Bell icon with unread count badge, notification dropdown showing latest 5, full page at `/notifications`
- **Operations:** Mark read, mark all read

---

### 5.11 Change Requests

**Feature:** Users request credential changes; admins review

- **Types:** email change, password change, device status change
- **Flow:** User submits → admin reviews via `/change-requests` → approve/reject with note
- **Security:** Passwords stored hashed immediately upon request (migration applied on boot for legacy plaintext)
- **Accessible by:** super_admin, manager (review); any authenticated user (submit)

---

### 5.12 Activity Log (Audit Trail)

**Feature:** Every API action logged to `api_activity_logs`

- **Captured:** actor_id, actor_name, actor_role, method, path, status_code, ip_address, description, timestamp
- **Excluded:** OPTIONS preflight, non-API paths, low-significance GETs
- **Page:** `/activities` — paginated timeline of all system actions
- **Accessible by:** super_admin, md_director only

---

### 5.13 Backup

**Feature:** Manual and scheduled database backups

- **Manual:** Download backup via `/backup` page (admin/manager/md_director)
- **Scheduled:** Monthly backup scheduler runs as background task on startup (`backup_scheduler_loop`)
- **Storage:** `backend/monthly_backups/` directory (mounted as Docker volume)

---

### 5.14 Delivery Confirmations

**Feature:** Dedicated page for recipients to confirm/dispute incoming distributions

- **Page:** `/delivery-confirmations`
- **Shows:** All pending distributions where the current user is the recipient
- **Actions:** Confirm Receipt, Dispute Receipt (with notes)
- **Accessible by:** sub_distributor, cluster, operator

---

### 5.15 Pending Dues

**Feature:** Track financial obligations when devices are returned as defective with a charge

- **`/pending-dues`:** Operator/cluster/sub-distributor see their own pending dues
- **`/defects/pending-dues/users`:** Management sees all users with pending dues
- **Resolved when:** Admin uploads payment bill and confirms payment

---

## 6. Database Design

### Tables Overview

| Table | Purpose |
|---|---|
| `users` | All system users with role, hierarchy, auth state |
| `devices` | Hardware devices with lifecycle status |
| `device_history` | Immutable audit log of every device action |
| `distributions` | Distribution requests and their lifecycle |
| `defects` | Defect reports with full replacement/payment lifecycle |
| `returns` | Return requests for devices |
| `approvals` | Generic approval records for distributions/returns/defects |
| `operators` | External operator contact directory |
| `notifications` | Per-user notification messages |
| `change_requests` | User-submitted credential/status change requests |
| `external_inventory_items` | Non-system inventory items |
| `inventory_purchase_orders` | POs for external inventory |
| `inventory_po_lines` | Line items on POs |
| `inventory_receipts` | Receipts against POs |
| `inventory_receipt_lines` | Line items on receipts |
| `inventory_stock_movements` | Stock in/out movements |
| `api_activity_logs` | Full API audit trail |
| `approval_role_routing` | Configures which roles handle which approval types |
| `token_blacklist` | Revoked JWT tokens (logout/rotation) |

### Key Relationships

- `users.parent_id → users.id` (self-referential hierarchy)
- `distributions.from_user_id` and `to_user_id` reference user IDs (as VARCHAR, not FK)
- `defects.device_id → devices.device_id`
- `returns.defect_id → defects.report_id`
- `notifications.user_id → users.id`
- `device_history.device_id → devices.device_id`

### Key Fields Explained

**users:**
- `role` — one of 8 role values
- `parent_id` — points to managing user
- `force_email_change`, `force_password_change` — first-login flags
- `failed_login_attempts`, `locked_until` — brute-force protection
- `permissions` — JSON blob for custom overrides

**devices:**
- `device_id` — system-generated unique ID (`DEV-*`)
- `status` — available / distributed / defective / returned / replaced
- `current_holder_id` — ID of the user currently holding the device
- `metadata` — JSON for type-specific extra fields (e.g., `box_type` for Set-top boxes)

**defects:**
- `report_id` — system-generated unique ID
- `report_target` — `manager_admin` or `sub_distributor`
- `replacement_device_id` — assigned replacement
- `return_amount` — financial charge
- `payment_bill_url` — uploaded bill path
- `payment_confirmed` — boolean

---

## 7. Security & Authentication

### 7.1 Authentication

- **Method:** JWT (HS256) via `python-jose`
- **Storage:** HttpOnly cookies (`access_token`, `refresh_token`) — not in localStorage
- **Expiry:** Access token: 15 minutes; Refresh token: 7 days
- **Rotation:** `POST /api/auth/refresh` — new access token issued from refresh token
- **Revocation:** Logout blacklists the token hash in `token_blacklist`; expired entries are pruned

### 7.2 Authorization

- Every protected route uses `Depends(get_current_user)` middleware
- Role checks performed at both route level (`_ensure_not_md_director`, etc.) and service level
- Hierarchy access validated via recursive `_branch_contains_user()` tree traversal
- `md_director` is always read-only regardless of endpoint

### 7.3 Security Hardening

| Control | Implementation |
|---|---|
| Rate Limiting | `slowapi`: 5/min on login, 10/min on token refresh, 30/min on logout |
| CSRF Protection | `starlette-csrf` middleware; login endpoint explicitly exempted |
| Security Headers | `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy` |
| HTTPS Enforcement | `ENFORCE_HTTPS=true` triggers 307 redirect; HSTS header set in production |
| Password Hashing | bcrypt via `passlib` — never stored plaintext |
| SQL Injection | Parameterized queries throughout (`?` placeholders translated to `%s`) |
| File Upload Validation | Magic byte check for XLSX/XLS; null-byte check for CSV; extension allowlist; size cap (10MB/8MB) |
| Path Traversal | Uploads served via `serve_upload` with `resolve()` containment check |
| Sensitive Data | `password_hash` stripped from all API responses |
| Account Lockout | `failed_login_attempts` tracked; `locked_until` set on threshold breach |
| Audit Logging | All API actions (actor, method, path, status, IP) written to DB |

### 7.4 Secret Key Validation

`SECRET_KEY` is validated at startup:
- Must be at least 32 characters
- Must not contain the string `dms` (prevents use of weak defaults)
- If invalid, application refuses to start

---

## 8. API Design

### Base URL

```
http(s)://<host>:8080/api
```

### Standard Response Format

**Success:**
```json
{
  "success": true,
  "message": "Human-readable message",
  "data": { ... },
  "pagination": { "page": 1, "page_size": 20, "total": 100, "total_pages": 5 }
}
```

**Error:**
```json
{
  "detail": "Error description (never exposes internals)"
}
```

### Authentication Endpoints

| Method | Path | Description | Auth Required |
|---|---|---|---|
| POST | `/api/auth/login` | Login | No |
| POST | `/api/auth/logout` | Logout + blacklist token | Yes |
| POST | `/api/auth/refresh` | Refresh access token | No (cookie) |
| GET | `/api/auth/me` | Get current user | Yes |
| PUT | `/api/auth/password` | Change own password | Yes |
| POST | `/api/auth/complete-forced-update` | First-login credential update | Yes |

### Device Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/devices` | List devices (scoped by role) |
| POST | `/api/devices` | Register device |
| GET | `/api/devices/{id}` | Get device by ID |
| PUT | `/api/devices/{id}` | Update device |
| DELETE | `/api/devices/{id}` | Delete device |
| PATCH | `/api/devices/{id}/status` | Update status |
| GET | `/api/devices/{id}/history` | Device history |
| GET | `/api/devices/track/{serial}` | Track by serial |
| GET | `/api/devices/available` | Devices available to distribute |
| GET | `/api/devices/for-replacement` | Replacement-eligible devices |
| GET | `/api/devices/my-overview` | Dashboard-level device stats |
| POST | `/api/devices/bulk-upload` | Bulk register from Excel/CSV |
| POST | `/api/devices/{id}/request-edit` | Staff request device edit |
| POST | `/api/devices/{id}/repair-holder` | Admin repair holder from history |

### Distribution Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/distributions` | List distributions |
| POST | `/api/distributions` | Create distribution |
| GET | `/api/distributions/{id}` | Get distribution |
| PATCH | `/api/distributions/{id}/status` | Update status |
| DELETE | `/api/distributions/{id}` | Cancel distribution |
| POST | `/api/distributions/{id}/receipt` | Confirm/dispute receipt |
| POST | `/api/distributions/{id}/confirm-return` | Confirm disputed return |
| GET | `/api/distributions/{id}/manifest` | Download Excel manifest |
| GET | `/api/distributions/{id}/export-mac-nuid` | Export MAC/NUID |
| POST | `/api/distributions/bulk-upload` | Create distribution from file |
| GET | `/api/distributions/pending` | Get pending approvals |
| POST | `/api/distributions/sync-devices` | Admin device sync |

### Defect Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/defects` | List defects (scoped) |
| POST | `/api/defects` | Create defect report |
| GET | `/api/defects/{id}` | Get defect |
| PUT | `/api/defects/{id}` | Update defect |
| DELETE | `/api/defects/{id}` | Delete defect |
| PATCH | `/api/defects/{id}/status` | Update status |
| PATCH | `/api/defects/{id}/resolve` | Resolve defect |
| POST | `/api/defects/{id}/replace` | Assign replacement device |
| POST | `/api/defects/{id}/replacement/confirm` | Operator confirms receipt |
| POST | `/api/defects/{id}/enquire` | Send replacement enquiry |
| POST | `/api/defects/{id}/resend-confirmation` | Resend confirmation to operator |
| POST | `/api/defects/{id}/mark-waiting` | Mark as waiting for shipment |
| POST | `/api/defects/{id}/forward-to-management` | Forward to management |
| POST | `/api/defects/{id}/payment-bill` | Upload payment bill |
| POST | `/api/defects/{id}/confirm-payment` | Confirm payment received |
| GET | `/api/defects/replacements` | All replacement mappings |
| GET | `/api/defects/replacements/pending` | Pending replacements |
| GET | `/api/defects/pending-dues/users` | Users with pending dues |
| GET | `/api/defects/pending-dues/users/{id}` | Dues for specific user |
| GET | `/api/defects/pending-dues/me` | My pending dues |

### Other Endpoint Groups

| Prefix | Routes Include |
|---|---|
| `/api/users` | CRUD users, status, credentials, role-filter, hierarchy |
| `/api/returns` | Create/list/approve returns |
| `/api/approvals` | List/approve/reject approvals, routing config |
| `/api/operators` | CRUD external operators |
| `/api/notifications` | List/read notifications |
| `/api/reports` | Generate/export reports |
| `/api/dashboard` | Dashboard stats |
| `/api/change-requests` | CRUD change requests |
| `/api/external-inventory` | Inventory items, POs, receipts |
| `/health` | Health check |

### Sample Request: Create Distribution

```http
POST /api/distributions
Content-Type: application/json
Cookie: access_token=<jwt>

{
  "device_ids": ["DEV-abc123", "DEV-def456"],
  "to_user_id": "42",
  "notes": "Batch Q1 2026 deployment"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Distribution created successfully",
  "data": {
    "distribution_id": "DIST-xyz789",
    "status": "pending",
    "device_count": 2,
    "from_user_name": "PDIC Staff",
    "to_user_name": "Operator A",
    "request_date": "2026-04-07T15:00:00"
  }
}
```

### Error Handling (API)

| HTTP Code | Meaning |
|---|---|
| 400 | Bad request / validation failure |
| 401 | Not authenticated |
| 403 | Authenticated but lacks permission |
| 404 | Resource not found |
| 409 | Conflict (e.g., duplicate MAC) |
| 413 | File too large |
| 422 | Request body schema validation failure |
| 429 | Rate limit exceeded |
| 500 | Internal server error (sanitized message, never stack trace) |

All 500 errors log the full exception via `logger.exception()` server-side but return only `"An internal error occurred. Please try again later."` to the client.

---

## 9. UI/UX Structure

### 9.1 Layout

- **Sidebar** — Role-specific navigation links, collapsible
- **Top Navbar** — User avatar, role badge, notification bell with unread count, logout
- **Main Content Area** — Page-level content with breadcrumbs
- **Modals** — Used for create/edit/view actions without page navigation
- **Theme** — Light / Dark / System — stored per user, applied via CSS class on root

### 9.2 Page Breakdown

| Route | Page | Key UI Elements |
|---|---|---|
| `/` | Dashboard | KPI cards, charts, recent activity |
| `/devices` | Devices | Filterable table, view modal, register button |
| `/devices/register` | Register Device | Form for single-device registration |
| `/devices/bulk-import` | Bulk Import | File drop zone, validation results table |
| `/devices/track` | Track Device | Serial number search, QR scanner, history timeline |
| `/distributions` | Distributions | Filterable table, KPI breakdown cards |
| `/distributions/create` | Create Distribution | Device selector, recipient picker, notes |
| `/distributions/bulk-upload` | Bulk Distribution | File upload, recipient picker |
| `/defects` | Defect Reports | Tabbed by status, filter panel |
| `/defects/create` | Create Defect Report | Device search, severity/type selectors, image upload |
| `/replacements` | Replacements | List of active replacement mappings |
| `/replacements/pending` | Pending Replacements | Defects awaiting replacement assignment |
| `/pending-dues` | Pending Dues | Financial obligations summary |
| `/returns` | Returns | Return requests and status |
| `/delivery-confirmations` | Delivery Confirmations | Incoming distributions for recipient |
| `/replacement-confirmation` | Replacement Confirmation | Confirm replacement device received |
| `/users` | Users | User management table with CRUD |
| `/users/hierarchy` | User Hierarchy | Visual tree of organizational structure |
| `/approvals` | Approvals | Pending approvals with approve/reject actions |
| `/reports` | Reports | Report generation with filters + PDF export |
| `/backup` | Backup | Download backup, scheduler status |
| `/activities` | Activity Log | Paginated API action timeline |
| `/notifications` | Notifications | Full notification list |
| `/external-inventory` | External Inventory | Item list, PO management |
| `/change-requests` | Change Requests | Pending credential/status change requests |
| `/profile` | Profile | View/edit own profile |
| `/settings` | Settings | Theme, compact mode, notification preferences |

### 9.3 Navigation Flow

1. Unauthenticated user → `/login`
2. First-login forced update → `/force-update-credentials`
3. Normal user → `/` (Dashboard)
4. Sidebar links render based on role (ProtectedRoute guards at route level + conditional rendering in sidebar)
5. Unauthorized access → `/unauthorized`
6. Unknown route → `/not-found`

### 9.4 Key UI Interactions

- **Role-gated sidebar links** — Rendered conditionally per role
- **Modals** — Distribution detail, device detail, defect detail — opened inline without nav change
- **Pagination** — Server-side pagination with page controls
- **Search** — Client-side search input → debounced API call with `search` param
- **Status badges** — Color-coded chips per status value
- **Confirmation dialogs** — Before destructive actions (cancel, delete)
- **Toast notifications** — Success/error feedback on API actions
- **Compact mode** — Tighter padding/font sizes, toggled via settings

---

## 10. Error Handling & Edge Cases

### 10.1 System-Level Errors

| Scenario | Handling |
|---|---|
| DB connection failure | Connection pool raises; response: 500 with generic message |
| MySQL pool exhausted | aiomysql raises; 500 returned |
| File disk write failure | Try/except in upload handler; 500 with generic message |
| Backup scheduler crash | Background task cancelled gracefully on shutdown |
| Token blacklist not found | Token validated by signature only; blacklist check is additional |

### 10.2 User-Level Errors

| Scenario | Response |
|---|---|
| Wrong credentials | 401 "Invalid email or password" |
| Inactive account | 403 "Account is not active" |
| Duplicate MAC/serial | 400 with field-specific message |
| Distributing device not in your possession | 400 from service validation |
| Approving already-approved distribution | 400 "Distribution is not in pending state" |
| Confirming receipt not addressed to you | 400 "You are not the recipient" |
| Uploading invalid file type | 400 with extension allowlist message |
| File magic bytes mismatch | 400 "Invalid XLSX/XLS file content" |
| Bulk upload with partial errors | 200 returned with per-row error list; valid rows still processed |

### 10.3 Fail-Safe Mechanisms

- **Idempotent migrations** — All `ALTER TABLE` in migrations wrapped in `try/except`; already-existing columns silently ignored
- **Transaction rollback** — `db.rollback()` on unhandled exceptions in service layer
- **Token expiry** — Frontend intercepts 401 → attempts refresh → re-queues original request → if refresh fails, redirects to login
- **Disputed distribution lock** — Sender cannot redistribute devices while distribution is in `disputed` state

---

## 11. Deployment & Infrastructure

### 11.1 Local Development Setup (Windows)

**Prerequisites:**
- Python 3.11+
- Node.js 18+
- Docker Desktop (for MySQL)
- Git

**Step 1 — Clone repository:**
```bash
git clone <repo-url> distribution-management-system
cd distribution-management-system
```

**Step 2 — Start MySQL via Docker:**
```bash
docker compose up mysql -d
```

**Step 3 — Backend setup:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

**Step 4 — Backend environment:**

Create `backend/.env`:
```dotenv
DEBUG=true
ENVIRONMENT=development
DB_HOST=localhost
DB_PORT=3306
DB_USER=dms_user
DB_PASSWORD=dms_password
DB_NAME=distribution_management_system
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(64))">
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
CSRF_COOKIE_SECURE=false
ENFORCE_HTTPS=false
CORS_ORIGINS=http://localhost:5173
```

**Step 5 — Start backend:**
```bash
python -m uvicorn app.main:app --reload --port 8080
```

Backend available at: `http://localhost:8080`
Swagger docs at: `http://localhost:8080/docs`

**Step 6 — Frontend setup:**
```bash
cd frontend
npm install
```

Create `frontend/.env`:
```dotenv
VITE_API_URL=http://localhost:8080/api
```

**Step 7 — Start frontend:**
```bash
npm run dev
```

Frontend available at: `http://localhost:5173`

**Or use PowerShell convenience scripts:**
```powershell
.\start.ps1    # starts backend + frontend
.\stop.ps1     # stops both
```

---

### 11.2 Docker Compose (Full Stack)

```bash
# Start all services (MySQL + Backend + Frontend)
docker compose up -d --build

# View logs
docker compose logs -f backend

# Stop services
docker compose down
```

Services:
- `dms-mysql` on port `3306` (internal only in production)
- `dms-backend` on port `8080`
- `dms-frontend` on port `5173`

Persistent volumes:
- `mysql_data` — database files
- `./backend/distribution_manifests` — Excel manifests
- `./backend/monthly_backups` — scheduled backups
- `./backend/uploads` — uploaded files (images, bills)

---

### 11.3 Production Deployment (Headless Server + Tailscale)

**Architecture:**
- Ubuntu 22.04/24.04 Linux server (no GUI)
- Docker Compose stack
- Tailscale for private network access
- Tailscale Serve for HTTPS termination

**Step 1 — Server preparation:**
```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install ca-certificates curl gnupg git ufw jq
sudo ufw default deny incoming
sudo ufw allow 22/tcp
sudo ufw enable
```

**Step 2 — Install Docker:**
```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo apt update
sudo apt -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```
Log out and back in for group membership to apply.

**Step 3 — Install Tailscale:**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```
Approve the server in your Tailscale admin console.

**Step 4 — Deploy application:**
```bash
sudo mkdir -p /opt/dms
cd /opt/dms
git clone <repo-url> distribution-management-system
cd distribution-management-system
```

**Step 5 — Production environment files:**

`backend/.env`:
```dotenv
APP_NAME=Distribution Management System
APP_VERSION=1.0.0
DEBUG=False
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8080
DB_HOST=mysql
DB_PORT=3306
DB_USER=dms_user
DB_PASSWORD=<strong-random-password>
DB_NAME=distribution_management_system
SECRET_KEY=<64-byte-urlsafe-secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
CSRF_COOKIE_SECURE=true
ENFORCE_HTTPS=false
CORS_ORIGINS=https://<server-hostname>.<tailnet>.ts.net
ADMIN_INITIAL_PASSWORD=<strong-temp-password>
```

`frontend/.env.production`:
```dotenv
VITE_API_URL=https://<server-hostname>.<tailnet>.ts.net/api
```

**Step 6 — Start production stack:**
```bash
docker compose up -d --build
```

**Step 7 — Enable HTTPS via Tailscale Serve:**
```bash
sudo tailscale serve --https=443 / http://127.0.0.1:5173
sudo systemctl enable --now tailscaled
```

Users access the app at: `https://<server-hostname>.<tailnet>.ts.net`

**Step 8 — Validate:**
```bash
curl -sS http://127.0.0.1:8080/health
docker compose ps
tailscale serve status
```

---

### 11.4 Initial Data Seeding

On first backend startup, `seed_initial_data()` is called automatically:
- Creates super admin: `admin@dms.com`
- Password: value in `ADMIN_INITIAL_PASSWORD` env var, or a fallback default
- `force_email_change=1` and `force_password_change=1` are set

**Development seed (full data):**
```bash
# POST to reset-and-seed (development only)
curl -X POST http://localhost:8080/reset-and-seed
```
Creates: 39 users, 200 devices, 50 distributions, 30 defects, 25 returns, 300+ notifications.

**Default test credentials:**
- Admin: `admin@dms.com` / `Admin@123`
- Manager: `manager1@dms.com` / `Manager@123`
- Operator: `operator1@dms.com` / `Oper@123`

---

## 12. Logging & Monitoring

### 12.1 Application Logging

**Audit Logger (`app.core.audit`):**
- Dedicated logger for sensitive security events
- Events: `LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOGOUT_SUCCESS`, `TOKEN_REFRESH_*`, `PASSWORD_CHANGE_*`, `FORCED_CREDENTIAL_ROTATION_COMPLETE`, `USER_DELETE`, `USER_STATUS_UPDATE`, `USER_CREDENTIALS_UPDATE`, `DB_RESET`
- Written to server stdout + application log file

**API Activity Logger (`app.core.activity_logger`):**
- Every significant API call logged to `api_activity_logs` table in DB
- Captures: actor_id, actor_name, actor_role, method, path, status_code, ip_address, timestamp
- Insignificant paths (health checks, OPTIONS) silently ignored
- Viewable in `/activities` page by super_admin and md_director

**Application Logger:**
- Standard Python `logging` module used in all route handlers
- `logger.exception()` called on every unhandled exception to capture full stack trace server-side
- Clients never receive stack traces

### 12.2 Backend Logs (Docker)

```bash
# Tail backend logs
docker compose logs -f backend

# View MySQL logs
docker compose logs -f mysql

# View last 100 lines
docker compose logs backend --tail=100
```

### 12.3 Health Check

```
GET /health
→ { "status": "healthy" }
```

Used by Docker and load balancers to verify service availability.

### 12.4 Monitoring Recommendations

- **Uptime:** Configure a cron job or external tool (Uptime Kuma, etc.) to poll `/health` every 60 seconds
- **Log aggregation:** Ship Docker logs to a centralized tool (Grafana Loki, ELK, or similar)
- **DB backup validation:** Monthly restore test from `monthly_backups/`
- **Disk space:** Monitor `backend/uploads` and `backend/monthly_backups` directories

---

## 13. Future Improvements

### 13.1 Scalability

- **Horizontal scaling:** Replace single MySQL container with managed RDS; use a shared session store for tokens
- **Message queue:** Add Redis/Celery for async notifications instead of synchronous DB writes
- **CDN for uploads:** Move uploaded files (images, bills) to object storage (S3-compatible)
- **WebSocket notifications:** Replace polling notification pattern with WebSocket push

### 13.2 Feature Enhancements

- **Mobile app:** Expose API to React Native or Flutter app for field operators
- **QR code generation:** Generate QR labels for each device at registration
- **Geo-tracking:** Integrate GPS coordinates for operator location at time of defect report
- **Email notifications:** Send email alerts on approval actions (SMTP integration)
- **Advanced analytics:** Time-series defect trends, MTTR tracking, distribution velocity
- **Multi-tenancy:** Support multiple independent organizations on one deployment
- **SSO:** OAuth2/SAML integration for enterprise identity providers
- **SLA management:** Set SLA timers on defect statuses with automatic escalation
- **Inventory forecasting:** Reorder alerts when stock drops below `reorder_level`

### 13.3 Operational Improvements

- **CI/CD pipeline:** GitHub Actions → build Docker images → push to registry → deploy to server
- **Database migrations:** Migrate from inline `ALTER TABLE` to a proper migration tool (Alembic)
- **Automated backups to cloud:** Schedule upload of `monthly_backups` to S3 or cloud storage
- **Two-factor authentication:** TOTP-based 2FA for admin and manager accounts
- **Secrets management:** Replace `.env` file secrets with a secrets manager (Vault, AWS Secrets Manager)

---

*End of Documentation*

**Document Metadata:**
- System: Distribution Management System v1.0.0
- Backend: FastAPI + Python + MySQL
- Frontend: React 18 + Vite 6 + Tailwind CSS 3
- Deployment: Docker Compose + Tailscale
- Generated: 2026-04-07
