# Security Audit Report

**System:** Distribution Management System (DMS)
**Scope:** Backend (FastAPI), Frontend (React + Vite), MySQL, Docker, Nginx, Monitoring (Prometheus/Grafana)
**Date:** 2026-08-09
**Status:** Informational audit — no code changes made in this pass

---

## Summary

The application has strong security fundamentals:

- JWT tokens in `httpOnly` + `SameSite=strict` cookies with CSRF protection
- Rate-limited authentication endpoints and account lockout
- Fully parameterized SQL (no injection found in application code)
- Upload size caps, zip-bomb guards, and path-traversal protection
- Secrets (`.env`, TLS certs) git-ignored
- Non-root containers with `read_only` root filesystems
- Nginx TLS enforcement, HSTS, CSP, and security headers

The findings below are grouped by severity. Several are already tracked in `PRODUCTION_RISKS.md`; they are cross-referenced where applicable.

---

## Verified Solid (No Action Needed)

| Area | Detail |
|---|---|
| Authentication | JWT in `httpOnly`, `SameSite=strict` cookies; CSRF middleware; token blacklisting on logout; 5-attempt account lockout (15 min); forced credential rotation on seeded admin. |
| Rate limiting | Login 5/min, refresh 10/min, logout 30/min (`backend/app/routes/auth.py`). |
| SQL injection | All queries use parameterized SQLAlchemy/`text()` bind params. Dynamic `{where}` fragments are fixed strings; user values always passed via `params`. No f-string or concatenated interpolation in app code (only in Alembic migrations, dev-time). |
| Uploads | 10 MB cap, xlsx decompression (zip-bomb) guard, path-traversal check on `/api/uploads` (`backend/app/main.py:239-267`). |
| Secrets hygiene | `.env`, `backend/.env`, `nginx/certs/*` are git-ignored. `SECRET_KEY` is 64-char and rejected if < 32 chars (`backend/app/config.py:93-106`). |
| Containers | Backend runs as non-root `app` user, `read_only` rootfs, `tmpfs` for temp; MySQL not port-exposed. |
| Headers | Nginx: HSTS, CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, `server_tokens off`. |
| Error handling | Global handlers strip internal exception details from 5xx responses (`backend/app/middleware/error_handler.py`). |

---

## HIGH

### 1. Hardcoded database password in git-tracked SQL init script

- **Files:** `mysql/init/01-privileges.sql`
- **Issue:** MySQL `IDENTIFIED BY 'k5Tn9Wb2…'` is hardcoded in plaintext in a file committed to the repository. Anyone with repo access obtains the database password.
- **Tracking:** `PRODUCTION_RISKS.md` #12 (verified still broken).
- **Fix:** Use a substitution placeholder (e.g. `IDENTIFIED BY '${MYSQL_PASSWORD}'`) or generate the user at runtime from env; never store the password in a tracked file. Rotate the existing password.

### 2. Excessive database grants for the application user

- **Files:** `mysql/init/01-privileges.sql`
- **Issue:** `dms_user` is granted `DROP, ALTER, CREATE, INDEX, TRIGGER` on all tables. If the application is compromised (e.g. via SQL injection or RCE), the attacker can destroy or alter the schema.
- **Fix:** Restrict to least privilege — `SELECT, INSERT, UPDATE, DELETE` only. Apply migrations with a separate privileged account.

### 3. Grafana default credentials and direct host port exposure

- **Files:** `docker-compose.yml:190-191, 221-222, 214`
- **Issues:**
  - `GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin}` — falls back to `admin` when unset. The root `.env` only defines MySQL variables, so Grafana runs with **admin/admin**.
  - Prometheus (`9090:9090`) and Grafana (`3000:3000`) are bound directly to the host, bypassing nginx TLS, authentication, and rate limiting.
- **Tracking:** `PRODUCTION_RISKS.md` #20, #40, #54.
- **Fix:** Set `GRAFANA_ADMIN_PASSWORD` in env; route Grafana/Prometheus through nginx behind auth (e.g. a `/grafana/` location), or remove host port bindings and access via the internal network only.

---

## MEDIUM

### 4. IDOR on unscoped by-id GET endpoints — **FIXED (2026-08-09)**

- **Files:** `backend/app/routes/distributions.py`, `backend/app/routes/defects.py`, `backend/app/routes/returns.py`, `backend/app/routes/devices.py`
- **Issue:** List endpoints are hierarchy-scoped (recursive CTE), but single-record lookups were not. Any authenticated user could enumerate records (`/distributions/{id}`, `/defects/{id}`, `/returns/{id}`, `/devices/{id}`, `/devices/{id}/history`) outside their sub-distributor scope.
- **Fix (applied):** Each by-id GET now calls a new `user_can_view_*` helper that mirrors the corresponding list's scope semantics (management/PDIC see all; everyone else is limited to their branch scope):
  - `distribution_service.user_can_view_distribution` — `from_user_id`/`to_user_id` within scope.
  - `defect_service.user_can_view_defect` — `reported_by` within scope.
  - `return_service.user_can_view_return` — `requested_by` within scope.
  - `device_service.user_can_view_device` — current holder within scope, or defective device reported within scope, or device belonging to a distribution to/from someone in scope (so a recipient can inspect a delivery's devices while they await receipt confirmation, when the sender still holds them).
  - Out-of-scope requests return `403 "Insufficient permissions"`, matching the existing `GET /users/{user_id}` pattern.
- **Verification:** `16 failed, 434 passed` both before and after the change (identical pre-existing failures); no new failures introduced.

### 5. Digital ID endpoints lack ownership/scope checks — **FIXED (2026-08-09)**

- **Files:** `backend/app/routes/digital_ids.py`
- **Issue:** Any authenticated user could create/read/update/delete digital identities for **any** `user_id` (IDOR + data integrity).
- **Fix (applied):** Each `/digital-ids` endpoint now resolves the target user and reuses `users._can_access_user` via a `_target_user_or_403` helper (write for create/update/delete, read for the GET). Self and in-branch management remain allowed; everything else gets `403`. Also relaxed `_can_access_user` so sub-distribution roles and clusters can edit users within their scope.

### 6. `backend/dms.db` (SQLite) is tracked in git

- **Files:** `backend/dms.db` (331 KB, ~100k rows across users/devices/distributions/notifications)
- **Issue:** Contains real seed users, password hashes, phones, devices, distributions, and notifications. Tracked in the repository.
- **Fix:** `git rm --cached backend/dms.db`, add to `.gitignore`/`.dockerignore` (already in `.dockerignore`), and purge from git history if the repo is public.

### 7. Refresh tokens never rotate — **FIXED (2026-08-09)**

- **Files:** `backend/app/services/auth_service.py`
- **Issue:** The same refresh token remained valid until expiry (blacklist only on logout). A stolen refresh token was replayable for the full 7-day lifetime.
- **Fix (applied):** `refresh_access_token` now rotates the refresh token on every use — the presented token is blacklisted and a brand-new refresh token is issued alongside the new access token (the `/auth/refresh` route already sets the new refresh cookie when one is returned). Reuse of an already-rotated token fails the blacklist check and is rejected with `401`.

### 8. Admin credential update bypasses password strength policy

- **Files:** `backend/app/models/user.py:129`
- **Issue:** `AdminCredentialUpdate.password` only enforces `min_length=8`, while self-service password changes enforce full complexity.
- **Tracking:** `PRODUCTION_RISKS.md` #22.
- **Fix:** Apply the shared `validate_password_strength` validator to admin-set passwords as well.

---

## LOW

### 9. User enumeration via distinct login errors

- **Files:** `backend/app/routes/auth.py:41-44, 63-65`
- **Issue:** Bad credentials return `401 "Invalid email/phone or password"`, but inactive accounts return `403 "Account is not active"`, letting attackers distinguish active accounts.
- **Fix:** Return a generic 401 for both cases (or delay the inactive response).

### 10. DB password in child-process environment

- **Files:** `backend/app/services/db_backup_scheduler.py:229`
- **Issue:** `env["MYSQL_PWD"] = settings.DB_PASSWORD` exposes the database password in the `mysqldump` subprocess environment.
- **Tracking:** `PRODUCTION_RISKS.md` #9.
- **Fix:** Pass credentials via a restricted mechanism or dedicated backup user; avoid environment leakage where feasible.

### 11. Unauthenticated `/metrics` endpoint

- **Files:** `backend/app/main.py:233-236`
- **Issue:** Prometheus metrics are served without authentication; any network client can read request rates and endpoint paths.
- **Tracking:** `PRODUCTION_RISKS.md` #50.
- **Fix:** Restrict to the internal network or require authentication.

### 12. Weak seed admin password fallback

- **Files:** `backend/app/services/seed_service.py:66`
- **Issue:** `os.getenv("ADMIN_INITIAL_PASSWORD") or "Admin@123"` — a weak hardcoded fallback. Mitigated by forced credential rotation (`force_email_change=1`, `force_password_change=1`), but the fallback exists in code and docs.
- **Tracking:** `PRODUCTION_RISKS.md` #48.
- **Fix:** Fail startup if `ADMIN_INITIAL_PASSWORD` is unset in production; remove the weak default.

### 13. No rate limits on non-auth mutations

- **Issue:** Defects, returns, digital IDs, and notifications endpoints have no rate limiting, enabling abuse/spam.
- **Fix:** Apply `slowapi` limits to high-volume mutation endpoints.

### 14. Sample/bulk CSVs with password columns tracked in git

- **Files:** `clusters.csv`, `operators.csv`, `sub_distributors.csv`, `users_bulk_upload_sample.csv`
- **Issue:** Committed CSV fixtures contain `password` columns (`Pass@123`). They use `@example.com` addresses (test data), so risk is low, but the files are public.
- **Fix:** Replace with placeholder values or move to `test/` fixtures and keep them clearly marked as fake.

---

## Recommended Next Steps

1. Fix the three HIGH items (init-script password, DB grants, Grafana/Prometheus exposure).
2. Scope remaining by-id lookups (e.g. `track_device_by_serial`) and any future record creation using the existing `_can_access_user` pattern.
3. Remove `backend/dms.db` from the repository.
4. Enable refresh-token rotation and enforce password strength on admin-set credentials.
5. Address LOW items opportunistically (login error uniformity, rate limits, seed fallback).

---

## Files Referenced

| File | Notes |
|---|---|
| `backend/app/main.py` | Middleware ordering, uploads, `/metrics`, `/reset-and-seed` |
| `backend/app/routes/auth.py` | Login/logout/refresh, forced update |
| `backend/app/services/auth_service.py` | Lockout, blacklist, refresh |
| `backend/app/middleware/auth_middleware.py` | Role/permission checkers |
| `backend/app/config.py` | Settings, SECRET_KEY validation |
| `backend/app/services/seed_service.py` | Admin seeding, `Admin@123` fallback |
| `backend/app/services/bulk_upload_service.py` | Upload/file validation |
| `docker-compose.yml` | Grafana/Prometheus exposure, container hardening |
| `nginx/conf.d/dms.conf` | TLS, CSP, HSTS, rate limiting |
| `mysql/init/01-privileges.sql` | Hardcoded DB password, broad grants |
| `PRODUCTION_RISKS.md` | Existing risk tracker (cross-referenced) |
