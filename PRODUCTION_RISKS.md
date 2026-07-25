# Production Risks — Critical & High

## 🚨 Critical — Will crash

### 1. No CPU/memory limits on any container
**File:** `docker-compose.yml` (all services)
**Why:** Docker has no resource caps. A single memory-leaking container or traffic spike can exhaust host memory/CPU, crashing the entire server and all containers.
**Fix:** Add `deploy.resources.limits` (e.g., backend: 512M memory, 1.0 CPU) to every service.

### 2. No connection pool recycle timeout
**File:** `backend/app/database.py:187-196`
**Why:** MySQL kills idle connections after `wait_timeout` (default 8 hours). The pool never recycles, so after overnight idle, the first query on a stale connection crashes with `MySQL server has gone away (2006)`.
**Fix:** Add `pool_recycle=3600` to `aiomysql.create_pool()`.

### 3. `init_db()` transaction leak
**File:** `backend/app/database.py:633-806`
**Why:** `init_db()` manually acquires a pool connection but never rolls back on error. If a migration fails mid-way, the connection is returned to the pool with an open, uncommitted transaction. The next acquirer sees dirty state or deadlocks.
**Fix:** Add `await conn.rollback()` in the `finally` block before `pool.release(conn)`.

---

## 🔴 High — Will degrade or break under load

### 4. N+1 queries in distribution creation
**File:** `backend/app/services/distribution_service.py:614-651`
**Why:** Each device in a distribution triggers its own `SELECT * FROM devices WHERE id = ?`. Distributing 100 devices = 101 queries. Under concurrent load, the connection pool (max 10) exhausts rapidly, causing timeouts.
**Fix:** Batch with `SELECT * FROM devices WHERE id IN (?, ?, ...)`.

### 5. N+1 notifications in loops
**Files:** `backend/app/services/defect_service.py:454,550,1157,1274,1328,1385,1447`, `backend/app/services/return_service.py:194,344,516`, `backend/app/routes/users.py:586`, `backend/app/routes/change_requests.py:223`
**Why:** Every notification opens its own `get_db()` connection. 20 notifications = 20 pool acquires. Same pool exhaustion risk as #4.
**Fix:** Batch INSERT with `executemany()` or a single multi-row INSERT.

### 6. No LIMIT on report queries
**Files:**
- `backend/app/services/report_service.py:352` — `SELECT * FROM devices ORDER BY id ASC`
- `backend/app/services/report_service.py:355` — `SELECT * FROM device_history ORDER BY timestamp ASC`
- `backend/app/services/device_service.py:503,532,543,563` — device listing queries
- `backend/app/services/distribution_service.py:1100,1140` — distribution listing queries
- `backend/app/services/user_service.py:327,407` — user listing queries
**Why:** These fetch ALL rows into memory with no LIMIT. At scale (50K devices, 500K history records), these will OOM the backend container.
**Fix:** Add `LIMIT ?` with pagination or streaming.

### 7. Backend missing Docker health check
**Files:** `docker-compose.yml:33-79`, `backend/app/main.py:191` (`/health` endpoint exists)
**Why:** Frontend and reverse-proxy depend on backend but don't wait for `service_healthy`. If backend starts slowly, they get 502 errors on first requests.
**Fix:** Add `healthcheck` block to backend service and `condition: service_healthy` to frontend/reverse-proxy depends_on.

### 8. Prometheus + Grafana exposed directly to host
**Files:** `docker-compose.yml:152-153` (prometheus port 9090), `docker-compose.yml:178-179` (grafana port 3000)
**Why:** Both monitoring services bypass the reverse proxy — no HSTS, no rate limiting, no CSP. Grafana defaults to `admin:admin` if env var not set.
**Fix:** Remove `ports` mapping and route through reverse proxy, or bind to `127.0.0.1` only.

### 9. Defect photo upload: no file validation
**File:** `backend/app/routes/defects.py:55-83`
**Why:** No file size limit, no MIME type check, no magic byte validation, no extension allowlist. Attacker can upload arbitrarily large files (memory exhaustion) or malicious executables.
**Fix:** Add all four checks (size, MIME, magic bytes, extension allowlist).

### 10. `AdminCredentialUpdate.password` bypasses strength policy
**File:** `backend/app/models/user.py:140-143`
**Why:** Super admin can set any user's password to `password123` (only `min_length=8` enforced, no uppercase/lowercase/digit/special char requirement). Bypasses the normal password policy.
**Fix:** Add same `@field_validator("password")` with complexity check used in other models.

### 11. Rclone config mounted writable
**File:** `docker-compose.yml:73`
**Why:** `${HOME}/.config/rclone/rclone.conf` contains cloud storage credentials but is mounted without `:ro`. Any process in the backend container can overwrite it.
**Fix:** Add `:ro` suffix to the bind mount.

### 12. No Python-level rate limiting on 30+ endpoints
**Files:** All route files except `backend/app/routes/auth.py`
**Why:** Rate limiting only exists at nginx level. An attacker who reaches the backend directly (internal network, misconfigured firewall, port 8080) can flood every endpoint without restriction.
**Fix:** Add `@limiter.limit(...)` decorator to all endpoints, or add a global middleware rate limit.
