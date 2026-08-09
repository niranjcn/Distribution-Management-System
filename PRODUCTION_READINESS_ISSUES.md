# Production Readiness Issues — DMS

This document explains every issue found during the production-readiness audit, in plain language.

**How to read it:** Each issue has:
- **What's wrong** — what the code actually does
- **Why it matters** — what happens in the real world if you don't fix it (the 3 AM scenario)
- **Where it lives** — exact file:line evidence
- **What to do** — the required fix
- **How to verify** — how to confirm the fix worked

Severity: 🔴 Critical (must fix before production) · 🟠 High · 🟡 Medium · 🔵 Low

---

## Table of Contents

1. [🔴 Live database password is committed to git](#1-live-database-password-is-committed-to-git)
2. [🔴 Two people can be given the same device (double allocation)](#2-two-people-can-be-given-the-same-device-double-allocation)
3. [🔴 Stock can go negative (overselling)](#3-stock-can-go-negative-overselling)
4. [🔴 Refresh tokens work as login tokens](#4-refresh-tokens-work-as-login-tokens)
5. [🔴 Alerts are configured but nobody receives them](#5-alerts-are-configured-but-nobody-receives-them)
6. [🔴 No backup restore procedure — data loss is irreversible](#6-no-backup-restore-procedure--data-loss-is-irreversible)
7. [🔴 Database migrations run on app start with a super-powered user](#7-database-migrations-run-on-app-start-with-a-super-powered-user)
8. [🔴 No protection against duplicate submissions](#8-no-protection-against-duplicate-submissions)
9. [🔴 The app is hard-wired to "localhost"](#9-the-app-is-hard-wired-to-localhost)
10. [🔴 Audit log and device history tables grow forever](#10-audit-log-and-device-history-tables-grow-forever)
11. [🟠 No CI/CD pipeline — every deploy is manual and unverifiable](#11-no-cicd-pipeline--every-deploy-is-manual-and-unverifiable)
12. [🟠 Grafana default password admin/admin, exposed on the host](#12-grafana-default-password-adminadmin-exposed-on-the-host)
13. [🟠 No request timeouts on the frontend — hung screens](#13-no-request-timeouts-on-the-frontend--hung-screens)
14. [🟠 No foreign keys — orphaned data is possible](#14-no-foreign-keys--orphaned-data-is-possible)
15. [🟠 Full-table scans on the two biggest tables](#15-full-table-scans-on-the-two-biggest-tables)
16. [🟠 No structured logs or request IDs](#16-no-structured-logs-or-request-ids)
17. [🟠 In-memory caching breaks the moment you run a second worker](#17-in-memory-caching-breaks-the-moment-you-run-a-second-worker)
18. [🟠 Account enumeration via login error messages and timing](#18-account-enumeration-via-login-error-messages-and-timing)
19. [🟠 App-level rate limiting is effectively broken behind the proxy](#19-app-level-rate-limiting-is-effectively-broken-behind-the-proxy)
20. [🟠 Single uvicorn worker — one slow request stalls everything](#20-single-uvicorn-worker--one-slow-request-stalls-everything)
21. [🟠 No health check on the actual dependencies](#21-no-health-check-on-the-actual-dependencies)
22. [🟠 Weak default passwords in code](#22-weak-default-passwords-in-code)
23. [🟡 Main JavaScript bundle is 2 MB](#23-main-javascript-bundle-is-2-mb)
24. [🟡 No test coverage for the approval workflow](#24-no-test-coverage-for-the-approval-workflow)
25. [🟡 Tests never run against a real database](#25-tests-never-run-against-a-real-database)
26. [🟡 No automated SSL certificate renewal](#26-no-automated-ssl-certificate-renewal)
27. [🟡 All times stored in server-local time, not UTC](#27-all-times-stored-in-server-local-time-not-utc)
28. [🟡 Frontend accessibility gaps](#28-frontend-accessibility-gaps)
29. [🟡 The approvals workflow tables were deleted](#29-the-approvals-workflow-tables-were-deleted)
30. [🔵 Stale documentation and dead files in the repo](#30-stale-documentation-and-dead-files-in-the-repo)
31. [🔵 No gzip compression and no browser-level security on static files](#31-no-gzip-compression-and-no-browser-level-security-on-static-files)

---

## 1. 🔴 Live database password is committed to git

**What's wrong:** The MySQL application password is written in plain text in a file that is tracked by git:

```sql
-- mysql/init/01-privileges.sql:4
CREATE USER IF NOT EXISTS 'dms_user'@'%' IDENTIFIED BY 'k5Tn9Wb2Qv7Mx4Lc8Ya1Jp6Zr3Hd0Gs9Vu2Ef5Bn8Ct';
```

That same password also appears in the root `.env` file (`MYSQL_PASSWORD`). The repository is hosted on GitHub (`github.com/niranjcn/Distribution-Management-System`), so anyone who can view the repository — and everyone who ever gets a copy of it — now knows your production database password.

**Why it matters (the 3 AM scenario):** The database password is the key to every device record, every user account (including password hashes), every distribution, every return. Anyone with this password can log into your database directly, read all customer data, delete tables, or lock you out. Because the grant in the same file includes `DROP, ALTER, CREATE, TRIGGER` on the whole schema, they can destroy the entire database. You would not even know they were there until something is already gone.

**Where it lives:** `mysql/init/01-privileges.sql:4-7` (and it is now baked into git history).

**What to do:**
1. Generate a new random MySQL password.
2. Remove the hardcoded password from the SQL file — use an environment-variable placeholder instead (e.g. run a small entrypoint script that substitutes `${MYSQL_PASSWORD}`), or generate the user at container start from env.
3. Rotate the live database password immediately.
4. Purge the old password from git history (`git filter-repo` / BFG) if the repo is or may become public.
5. Add secret scanning (pre-commit hook or CI step) so this never happens again.

**How to verify:** `git log -S 'k5Tn9Wb2Qv7Mx4Lc8Ya1Jp6Zr3Hd0Gs9Vu2Ef5Bn8Ct'` returns nothing; a fresh `docker compose up` creates the user from the new password; the old password no longer works.

---

## 2. 🔴 Two people can be given the same device (double allocation)

**What's wrong:** When a distribution is created, the code first *reads* which devices are available, then later *writes* their new holder:

```python
# distribution_service.py:217-220
rows = (await session.execute(
    text(f"SELECT id, status FROM devices WHERE id IN ({ph})"),
    params
)).mappings().all()
# ... later ...
await session.execute(text(stock_update_sql.format(ph=eph)), update_params)  # line 258
```

There is no lock (`FOR UPDATE`) on that SELECT, and the database uses MySQL's default REPEATABLE READ isolation. Nothing at the database level stops two people — or two approvals, or two browser tabs — from checking "is this device available?" at the same time, seeing "yes", and both assigning it. `devices.current_distribution_id` is not a unique column, so the database happily records the same device in two active distributions.

**Why it matters (the 3 AM scenario):** You approve two distributions on Friday afternoon. Both contain device serial `ABC123`. On Monday, two field operators report that they each received the same physical phone. Someone has to manually find and reverse one of the distributions, and the `device_history` now shows the same device being "delivered" twice. If you don't notice, that device silently exists in two places and your inventory reconciliation never matches.

**Where it lives:** `distribution_service.py:217-260` (availability SELECT without `FOR UPDATE`, followed by holder UPDATE in the same transaction). The same pattern affects `create_distribution` at `distribution_service.py:1214`.

**What to do:** Lock the rows inside the transaction: `SELECT id, status FROM devices WHERE id IN (...) FOR UPDATE` and re-check availability while holding the lock, OR add a database-level unique constraint on `(current_distribution_id)` where not null. Do both for defense in depth. Ship the fix with a concurrency test.

**How to verify:** Write a test that fires two `create_distribution` calls for the same device concurrently — exactly one succeeds, the other returns a clean error, and the device appears in only one distribution.

---

## 3. 🔴 Stock can go negative (overselling)

**What's wrong:** The single-item external-inventory distribution does a read, a check, then an update:

```python
# inventory_service.py:440-480
current_qty = int(item.get("quantity") or 0)
if payload.quantity > current_qty:
    raise ...  # "Cannot distribute more than the available quantity"
# ...
await session.execute(
    text("UPDATE external_inventory_items SET quantity = :quantity, ..."),
    {"quantity": remaining, ...}
)
```

Between the `SELECT` (line 441) and the `UPDATE` (line 478), nothing locks the row and nothing makes the write conditional. Two concurrent requests for the same item both read `quantity = 10`, both pass the check, and both subtract — leaving the item at `-2` on the shelf.

**Why it matters (the 3 AM scenario):** Two operators on two phones request the last 6 units of a popular item at the same moment. Both get confirmation emails. Your stock shows negative. One of them will not actually receive goods, and you find out when they call support angry that you confirmed something you don't have.

**Where it lives:** `inventory_service.py:436-480` (`distribute_item`). Note the bulk path *does* use `FOR UPDATE` (`inventory_service.py:569,787`) — only this single-item path is missing it, which makes this an easy fix that matches an existing pattern.

**What to do:** Make the decrement atomic and conditional:

```sql
UPDATE external_inventory_items
SET quantity = quantity - :qty
WHERE id = :id AND quantity >= :qty
```

then check the number of affected rows — if zero, reject the request. (Or `SELECT ... FOR UPDATE` first, matching the bulk path.)

**How to verify:** Concurrent-distribution test on the same item: final quantity is never negative and no request that should have failed succeeds.

---

## 4. 🔴 Refresh tokens work as login tokens — **FIXED (2026-08-09)**

**Fix (applied):** `decode_token` (in `backend/app/utils/security.py`) now requires the JWT `type` claim to be `"access"` and returns `None` for any refresh token. Because `decode_token` is the only decoder used by `get_current_user_from_token` (the auth gate behind `get_current_user`/`get_current_user_optional`), a refresh token presented in the `Authorization` header or the `access_token` cookie no longer authenticates. `refresh_access_token` is unaffected — it still decodes the refresh token directly via `jwt.decode`.

**Tests added:** `TestTokenTypeSeparation` in `backend/tests/services/test_auth_service.py` (access token decodes; refresh token rejected; `get_current_user_from_token` rejects a refresh token before any DB lookup; access token accepted) and route tests in `backend/tests/routes/test_auth_routes.py` asserting a refresh token returns `401` on `GET /api/auth/me` when sent as the `access_token` cookie or as a `Bearer` credential.

**What's wrong:** The function that decodes tokens for authentication never checks *what kind* of token it is:

```python
# security.py:59-73
def decode_token(token: str) -> Optional[TokenData]:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    ...
    if user_id is None:
        return None
    return TokenData(user_id=user_id, email=email, role=role, name=name)
```

Access tokens live for ~16.7 hours (`ACCESS_TOKEN_EXPIRE_MINUTES=1000` in `.env`). Refresh tokens live for **7 days**. Because `decode_token` never looks at the `type` claim (which says `"access"` vs `"refresh"`), presenting a refresh token in the `Authorization` header (or the access-token cookie) authenticates you to *every* protected endpoint.

**Why it matters (the 3 AM scenario):** A laptop with an open session is stolen. The attacker extracts the refresh cookie. Even though that refresh token would normally only be useful to mint a new session, here it is a direct 7-day login. Logout and token rotation become far less effective — the "short-lived" access token concept is moot because the long-lived token IS a login.

**Where it lives:** `security.py:59-73` (`decode_token`), used by `auth_service.py:225-246` (`get_current_user_from_token`). The type check exists (`verify_token_type`, `security.py:76-82`) but is only called in the refresh path.

**What to do:** Reject tokens whose `type != "access"` inside `decode_token` (or inside `get_current_user_from_token`). Add a unit test asserting that a refresh token gets a `401` on `/api/auth/me`.

**How to verify:** `POST /api/auth/login` → take the refresh cookie → call `GET /api/auth/me` with it → must return `401`, not `200`.

---

## 5. 🔴 Alerts are configured but nobody receives them

**What's wrong:** There are 7 Prometheus alert rules (backend down, high error rate, high latency, slow queries, etc.) but the alerting destination is empty:

```yaml
# monitoring/prometheus/prometheus.yml:6-7
alerting:
  alertmanagers: []
```

There is no Alertmanager container, no email, Slack, PagerDuty, or webhook configured anywhere.

**Why it matters (the 3 AM scenario):** The backend crashes at 2 AM. `BackendDown` fires — and disappears into the void. Users start complaining in the morning. You find out when a manager calls at 9 AM asking why the system is down. The alert you carefully wrote did its job; nobody was listening.

**Where it lives:** `monitoring/prometheus/prometheus.yml:6-7`; `monitoring/prometheus/alert.rules.yml` (the 7 rules); `docker-compose.yml` (no alertmanager service).

**What to do:**
1. Add an Alertmanager service to `docker-compose.yml`.
2. Configure a notification route (email, Slack, PagerDuty, or webhook).
3. Point Prometheus at it: `alerting: alertmanagers: [- url: http://alertmanager:9093]`.
4. Add the alerts you're missing: backup failure, backup age, certificate expiry, disk space, MySQL connection exhaustion.

**How to verify:** Trigger a test alert (stop the backend) and confirm a notification is actually received within the expected window.

---

## 6. 🔴 No backup restore procedure — data loss is irreversible

**What's wrong:** The app takes a daily `mysqldump` at 02:00 and uploads it via rclone to a Google Drive remote. But:
- There is **no restore runbook** anywhere in the repo.
- The rclone config mounted on this machine is a **1-byte placeholder** — the backups are currently not being uploaded at all.
- Backups are **not encrypted** and have **no retention policy** (they accumulate forever, or never exist).
- Restore has **never been tested**.

**Why it matters (the 3 AM scenario):** The server's disk dies — or worse, someone deletes data. You reach for the backups. The restore procedure does not exist. You have to reverse-engineer the dump format and the import steps while the business is down. You cannot confirm the backups were even uploaded, because the credentials are a placeholder and nobody ever tested it. Data loss is not hypothetical — it is the expected outcome.

**Where it lives:** `db_backup_scheduler.py:316-333` (dump+upload), `docker-compose.yml:93` (host rclone mount), `PRODUCTION_RISKS.md` risk #41 (restore procedure "not documented").

**What to do:**
1. Complete a working rclone config for a real, checked destination.
2. Write a step-by-step restore runbook (dump → fresh MySQL → verify row counts → smoke test login).
3. Encrypt backups at rest and add retention (e.g. keep 30 daily + 12 monthly).
4. **Run a restore drill** before launch and quarterly after.
5. Define RPO (recommend ≤ 24h, matching the daily dump) and RTO (recommend ≤ 4h).
6. Alert if a backup fails or is older than expected.

**How to verify:** Restore from an actual backup into a fresh MySQL container; confirm key tables and a login work. Schedule this as a recurring drill.

---

## 7. 🔴 Database migrations run on app start with a super-powered user

**What's wrong:** Every time the backend container starts, it runs `alembic upgrade head` automatically:

```python
# database_sqlalchemy.py:114-127  (invoked from main.py:91 via init_db())
# run_alembic_migrations() -> command.upgrade(alembic_cfg, "head")
```

And the database user the app connects as has schema-changing privileges:

```sql
-- mysql/init/01-privileges.sql:6-7
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, TRIGGER ...
```

**Why it matters (the 3 AM scenario):** You deploy version X, which includes a migration that renames a column. The migration runs *as part of the app starting*. If it fails halfway, or if two instances start at once and both try to run DDL, you get a half-migrated schema and a boot-looping app. Worse: the application user — the same account an attacker would get through the leaked password (Issue #1) — can `DROP` or `ALTER` any table at will. And there is no rollback: many migrations have no-op or lossy `downgrade()` bodies, so "undo the deploy" is not actually possible.

**Where it lives:** `database_sqlalchemy.py:114-127`, `main.py:91`, `mysql/init/01-privileges.sql:6-7`, and the lossy downgrades in migrations `0017/0018/0028/0030`.

**What to do:**
1. Move migrations out of app startup — run them as an explicit, separate deployment step.
2. Use a dedicated migration user (or the root init user) for migrations, and strip `CREATE/ALTER/DROP/INDEX/TRIGGER` from the runtime app user (leave `SELECT, INSERT, UPDATE, DELETE`).
3. Test that every migration's `downgrade` works, or remove migration-based rollback and use a "restore from backup" rollback strategy instead.
4. Add a migration test to CI.

**How to verify:** With migrations split out, `docker compose up` performs **no DDL**; the runtime user cannot run `DROP TABLE`; and a failed-migration drill has a documented, tested recovery path.

---

## 8. 🔴 No protection against duplicate submissions

**What's wrong:** Create endpoints (distributions, defects, returns, bulk uploads) have **no idempotency keys**. Worse, the frontend re-sends the *same* request after a token refresh:

```js
// frontend/src/services/api/client.js:165-168
if (refreshed) {
  return apiRequest(endpoint, options);   // re-sends the identical POST
}
```

If the server processed the first POST but the response was lost (or the refresh interrupted it), the retry creates a **second** record. The user-facing double-click guards are client-side only and not universal.

**Why it matters (the 3 AM scenario):** A distributor's Wi-Fi drops right as they click "Create distribution". They click again. Two identical distributions now exist, both allocating the same devices. A bulk import that partially succeeded and was retried now has a duplicated batch. Every duplicate is a manual reconciliation job.

**Where it lives:** `client.js:165-168` (re-POST after refresh), create routes in `routes/distributions.py`, `routes/defects.py`, `routes/returns.py` (no idempotency handling), `bulk_upload_service.py`.

**What to do:**
1. Generate an idempotency key on the client per business action (a UUID) and send it as a header.
2. On the server, store the key against the created record; if a request with the same key arrives again, return the original result instead of creating a duplicate.
3. For bulk uploads, make resubmission of the same file/batch idempotent (e.g. fingerprint the file).

**How to verify:** Double-submit the same create request (with the same key) → exactly one record created.

---

## 9. 🔴 The app is hard-wired to "localhost"

**What's wrong:** The frontend is built with the API URL baked in as `https://localhost/api`:

```yaml
# docker-compose.yml:106
args:
  VITE_API_URL: https://localhost/api
```

And the TLS certificate is self-signed for `CN=localhost` (10-year validity, `nginx/certs/`). There is no `/api` proxy on the frontend container's own nginx (`frontend/nginx.conf` only serves static files) — API calls go from the *browser* to whatever `VITE_API_URL` says.

**Why it matters (the 3 AM scenario):** You deploy to a LAN server at `https://10.0.0.5`. Your operators open `https://10.0.0.5`. The page loads, but every API call goes to `https://localhost/api` — which in *their* browser means their own machine. Nothing works. The system works perfectly only if you open it on the server itself as `https://localhost`. For any real deployment with remote users, this is broken out of the box.

**Where it lives:** `docker-compose.yml:106`, `frontend/Dockerfile:5` (default `http://backend:8080/api`), `client.js:3` (fallback `http://localhost:8080/api`), `nginx/certs/` (CN=localhost).

**What to do:**
1. Parameterize the API URL per environment (build the frontend with the actual hostname operators will use).
2. Issue a certificate for the real hostname (internal CA or Let's Encrypt), with the correct SAN entries.
3. Consider using same-origin relative URLs (`/api`) so the API follows whatever host the page was served from.

**How to verify:** From a second machine, load the app by its real hostname and confirm login works (API reachable).

---

## 10. 🔴 Audit log and device history tables grow forever

**What's wrong:** The three biggest tables have no retention policy and lost key indexes:
- `api_activity_logs` — every request is logged here (write-heavy) with an index only on `created_at`.
- `device_history` — one row per device movement, with the per-user indexes **dropped in migration 0039** to save ~242 MB.
- `notifications` — created for every distribution/defect/return event; indexes lead with `user_id`, so the bulk delete by `created_at` scans.

Meanwhile the dashboard's "recent activities" query filters by the acting user's id (`dashboard_service/activities.py:31`) — which now has **no index** → a full table scan on the second-largest table on every dashboard load.

**Why it matters (the 3 AM scenario):** Six months in, `api_activity_logs` is 10 GB and `device_history` is 2 GB on the same disk as the data you care about. The dashboard gets slower every week because of scans. The disk fills up — MySQL stops writing — the whole system goes read-only or down. Nobody predicted it because nothing watched growth.

**Where it lives:** `activity_log_cleanup.py` (scheduler exists — verify thresholds), migrations `0036-0040` (dropped indexes), `dashboard_service/activities.py:31`, `notification_service.py:203`.

**What to do:**
1. Enforce retention: archive/delete `api_activity_logs` and old notifications on a schedule (the cleanup scheduler exists — make it provably work and monitored).
2. Reintroduce the per-user indexes needed by the dashboard, or change the query so it can use an existing index.
3. Add disk-space and table-growth alerts.
4. Partition the biggest tables by date if they stay large.

**How to verify:** Run the cleanup and confirm size drop; `EXPLAIN` the dashboard activity query and confirm it uses an index.

---

## 11. 🟠 No CI/CD pipeline — every deploy is manual and unverifiable

**What's wrong:** There is no `.github/`, `.gitlab-ci.yml`, `Jenkinsfile`, or any automation. The 502 backend tests and 24 frontend tests exist but are **never run by any machine**. Deploys are manual `git pull` + `docker compose build` + `docker compose up -d` on the server itself, and images are built directly on the production host.

**Why it matters (the 3 AM scenario):** A teammate merges a change that breaks imports. Because nothing built or tested it, the break ships to the server. `docker compose up -d` fails, or worse, starts with a broken feature. There is no artifact to roll back to — rollback means "rebuild from git" while the system is down.

**Where it lives:** repo-wide (absence), `PRODUCTION_RISKS.md` risks #45/#46.

**What to do:**
1. Add a GitHub Actions pipeline: lint → backend tests → frontend tests → frontend build → secret scan → (later) dependency & container scan.
2. Build Docker images in CI, tag them with the commit/version, and push to a registry.
3. Deploy by pulling a tagged image, not by building on the host.

**How to verify:** A pull request that breaks a test or build is blocked; every deploy uses a versioned artifact.

---

## 12. 🟠 Grafana default password admin/admin, exposed on the host

**What's wrong:**

```yaml
# docker-compose.yml:214
GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin}
```

The root `.env` only defines the two MySQL variables — so `GRAFANA_ADMIN_PASSWORD` is unset and Grafana runs with **admin/admin**. Both Grafana (`3000:3000`) and Prometheus (`9090:9090`) are published directly to the host, bypassing nginx TLS, rate limiting, and security headers entirely.

**Why it matters (the 3 AM scenario):** Anyone on the network can open `http://server:3000`, log in as `admin/admin`, and see every backend metric — or modify dashboards and alerts. On a semi-public network, attackers also probe `9090` and read endpoint-level request data from Prometheus.

**Where it lives:** `docker-compose.yml:190-191,214,221-222`.

**What to do:**
1. Force a strong `GRAFANA_ADMIN_PASSWORD` in env (and fail fast if unset in production).
2. Stop publishing Prometheus/Grafana on the host — route them through nginx behind authentication, or keep them internal-only.

**How to verify:** `admin/admin` no longer logs in; `9090`/`3000` are not reachable from the host port.

---

## 13. 🟠 No request timeouts on the frontend — hung screens

**What's wrong:** The API client does not use `AbortController` or any timeout (grep for `AbortController|signal:` finds zero uses in `client.js` and the app).

**Why it matters (the 3 AM scenario):** The backend hangs on a slow query (or the network blips mid-request). The spinner spins forever. Buttons stay disabled. The user cannot do anything — not even cancel — because the request never settles. They close the tab and retry, which (with Issue #8) can duplicate the action.

**Where it lives:** `frontend/src/services/api/client.js:96-200` and all consumers.

**What to do:** Add a timeout + `AbortController` to the fetch wrapper (e.g. 30s default, longer for uploads), and on timeout, surface a clear "request timed out, please retry" state.

**How to verify:** Simulate a hanging endpoint; the UI recovers with a timeout message within the configured window.

---

## 14. 🟠 No foreign keys — orphaned data is possible

**What's wrong:** Across all 16 tables and 40 migrations there is not a single `FOREIGN KEY`. Some "relationship" columns are also the wrong type — `defects.device_id` is `VARCHAR(64)` while `devices.id` is `INT`, forcing `CAST()`-based joins. Referential integrity is enforced 100% in application code.

**Why it matters (the 3 AM scenario):** A bug in any write path (or a future feature) leaves a `device_history` row pointing at a deleted device, or a distribution pointing at a deleted user. Because the database doesn't know, nothing errors — the orphan just sits there, silently corrupting reports ("distribution by a user who no longer exists") and reconciliation. Every integrity rule lives in code that can drift, get bypassed by a new path, or be skipped by bulk `executemany`.

**Where it lives:** `db_models/*` (no `ForeignKey`), `alembic/versions/*` (no `REFERENCES`), `device_service.py:995,1032,1088,1120` (CAST joins), `dashboard_service/stats.py:230,300`.

**What to do:**
1. Add real foreign keys in a migration, with defined `ON DELETE` behavior (matching what the app already does, e.g. `SET NULL` or `RESTRICT`).
2. Fix the type mismatches so joins use indexes instead of `CAST()`.
3. Add a reconciliation query/report that flags orphans.

**How to verify:** `SHOW CREATE TABLE` shows FKs; a script inserting an orphaned child row is rejected; report joins use the index (no `CAST`).

---

## 15. 🟠 Full-table scans on the two biggest tables

**What's wrong:** Several hot queries cannot use indexes:
- Dashboard "recent activities" per user — the needed indexes were **dropped** in migration 0039 → full scan of `device_history`.
- Every search box uses leading-wildcard `LIKE '%…%'` on devices, users, defects, distributions, and digital IDs → index can't help.
- `devices.device_type` / `manufacturer` / `current_holder_type` filters and `GROUP BY` have no index (dropped in 0036).
- Type-mismatched FK joins (Issue #14) can't use `idx_defects_device_status` or `idx_returns_defect_id`.

**Why it matters (the 3 AM scenario):** A manager opens the dashboard and the "recent activity" panel takes 8 seconds because it scanned a million-row table. Report screens time out. Every search box gets slower as data grows. The latency alert (Issue #5) fires constantly, but you can't act because the queries are unindexable by design.

**Where it lives:** `dashboard_service/activities.py:31`, `user_service.py:177-187`, `device_service.py:1263-1300`, `defect_service.py:309-313`, `distribution_service.py:565`, migrations `0036-0039`.

**What to do:**
1. Restore the specific indexes the dashboard actually needs.
2. For searches, consider full-text indexes or at least prefix-friendly matching; set a small `LIMIT` and show "narrow your search" when truncated.
3. Fix the `CAST()` join columns.

**How to verify:** `EXPLAIN` on each hot query shows an index (no `type: ALL`).

---

## 16. 🟠 No structured logs or request IDs

**What's wrong:** Logs are plain text (`%(asctime)s | %(levelname)s | %(name)s | %(message)s`, `main.py:57`), rotated to a local file. There is **no request ID**, no JSON structure, no centralized aggregation (no Loki/ELK/vector), and logs are lost when the container is recreated (Docker json-file, 3×10 MB).

**Why it matters (the 3 AM scenario):** A distributor reports "my approval failed at 14:05". You cannot answer *which request*, *which API call*, or *what the request ID was*, because nothing ties log lines to a specific request. You search a plain-text log by timestamp and cross your fingers. Meanwhile the docker logs you actually needed have rotated away. Every incident is a forensic excavation instead of a lookup.

**Where it lives:** `main.py:38-81`, `docker-compose.yml` logging blocks (json-file, 10m×3).

**What to do:**
1. Add a middleware that generates a request ID per call, logs it, and echoes it in the response header.
2. Switch to structured (JSON) logging.
3. Add a lightweight log aggregation (Loki via compose is easy) so logs survive container restarts and are searchable.

**How to verify:** Every log line contains a request ID you can correlate to a specific failed call.

---

## 17. 🟠 In-memory caching breaks the moment you run a second worker

**What's wrong:** Three caching layers store state **in the process memory**:
- `core/cache.py` — a TTL dict (max 100 entries, clears the whole cache on overflow).
- `core/cache_version_manager.py` — the ETag version that drives `304` responses, kept in memory and only re-read from MySQL every 60s.
- `device_service._ttl_async_cache` — per-process TTL cache.

The code itself documents the assumption: this is correct **only with a single uvicorn worker** (`cache_version_manager.py:6-18`, `main.py:93-96`). The dashboard TTL cache is also not keyed on `cache_version`, so it can serve data up to 30s stale after a write.

**Why it matters (the 3 AM scenario):** Someone "just scales" the backend by running `--workers 4` (or two containers). Now four processes each hold their own ETag version. Worker A sees a change, worker B still serves the old `304` for hours (until the 60s failsafe re-sync). Users on different workers see different data. The dashboard shows stale counts that disagree with the list pages. Data "disappears" and "reappears" depending on which worker answered.

**Where it lives:** `core/cache.py`, `core/cache_version_manager.py:6-18`, `database_sqlalchemy.py:90-97`, `device_service.py:1362-1365,1467-1470`, `dashboard_service/stats.py:19-20`.

**What to do:**
1. Move the ETag/cache version to a shared store (MySQL row — already partially does this — or Redis), and read it per-request instead of relying on in-memory sync.
2. Either remove the 30s dashboard cache or key it on `cache_version`.
3. Document and enforce the single-worker assumption until this is fixed (add a startup warning).

**How to verify:** Run two workers/containers against the same DB; a write is reflected immediately (or within the defined TTL) on both.

---

## 18. 🟠 Account enumeration via login error messages and timing

**What's wrong:**
- Unknown email → generic `401`.
- Known email but wrong password → `401` **after running bcrypt**.
- Locked account → `423`.
- Inactive account → `403 "Account is not active"`.
- Unknown email skips bcrypt entirely (`auth_service.py:52-53` returns immediately), while existing accounts pay the bcrypt cost → measurable timing difference.

**Why it matters (the 3 AM scenario):** An attacker enumerates all real operator/distributor accounts in minutes by mapping which emails return `423`/`403` vs `401`, and confirms them by timing. Targeted phishing or credential-stuffing campaigns then hit exactly the right accounts — including admin.

**Where it lives:** `auth.py:41-66`, `auth_service.py:44-65`.

**What to do:**
1. Return the same generic `401 "Invalid email/phone or password"` for unknown, wrong-password, inactive, and locked accounts.
2. Run a dummy bcrypt verification for unknown emails to equalize timing.

**How to verify:** A script probing unknown vs known accounts cannot distinguish them by status code or response time.

---

## 19. 🟠 App-level rate limiting is effectively broken behind the proxy

**What's wrong:** The in-app slowapi limiter keys on `request.client.host`:

```python
# core/rate_limiter.py:1-6
limiter = Limiter(key_func=get_remote_address)
```

Behind the nginx proxy, uvicorn does not trust `X-Forwarded-For` from the proxy container (no `--proxy-headers`/trust config), so *every client shares one bucket* keyed to the nginx container's IP. The limit store is also in-memory (per process). The nginx per-IP limits (`dms.conf`) are the only effective per-client limiter.

**Why it matters (the 3 AM scenario):** The app-level `5/minute` login limit is effectively **global**. One user refreshing aggressively (or a bot) can exhaust the bucket for *everyone* — the whole company is locked out of login until the minute resets, and there is no way to tell why from the client side.

**Where it lives:** `rate_limiter.py:1-6`, `auth.py:20,127,168`, `backend/Dockerfile:26` (uvicorn without proxy trust).

**What to do:**
1. Configure uvicorn to trust the proxy (`--proxy-headers --forwarded-allow-ips=172.20.0.5`) or use a middleware that keys on `X-Forwarded-For`.
2. Move the limiter store to a shared backend (Redis) if you ever run multiple workers.

**How to verify:** Two different client IPs through the proxy get independent buckets (each can log in 5×/min without affecting the other).

---

## 20. 🟠 Single uvicorn worker — one slow request stalls everything

**What's wrong:** The backend runs one uvicorn worker (`backend/Dockerfile:26`, no `--workers`, no `--limit-concurrency`). FastAPI is async, but CPU-heavy work (XLSX parsing for bulk uploads, report aggregation, big dashboard queries) blocks the single event loop. Bulk uploads are allowed up to **600s** at nginx (`dms.conf:73`).

**Why it matters (the 3 AM scenario):** A manager uploads a 50,000-row Excel file at 9:30 AM. For the next minute, *every* request — including login and the health check — waits behind it. Operators across the company see a frozen system during peak hours, and the health check timing out causes orchestrators to think the service is dead.

**Where it lives:** `backend/Dockerfile:26`, `nginx/conf.d/dms.conf:71-83`, `bulk_upload_service.py`.

**What to do:**
1. Run bulk uploads/report generation in a background task or worker process (return a job ID immediately).
2. Or run multiple uvicorn workers (after fixing Issue #17's cache assumption and #19's limiter).
3. Add `--limit-concurrency` to bound event-loop pressure.

**How to verify:** While a bulk upload runs, login/health and light API calls remain responsive.

---

## 21. 🟠 No health check on the actual dependencies

**What's wrong:** `/health` returns `{"status": "healthy"}` unconditionally (`main.py:227-230`) — it never checks the database. There are no healthchecks for the frontend, reverse-proxy, or Prometheus containers (`docker-compose.yml`), and the reverse-proxy only waits for `service_started` on the frontend, not healthy.

**Why it matters (the 3 AM scenario):** MySQL dies. `/health` still says healthy, the backend healthcheck keeps passing, and nothing restarts anything. The dashboard container has no healthcheck, so a broken frontend build silently serves errors. Monitoring "the system is up" while the database is down is worse than no monitoring.

**Where it lives:** `main.py:227-230`, `docker-compose.yml:119-121,149-153` (no healthchecks / started-only waits).

**What to do:**
1. Make `/health` actually verify DB connectivity (and report dependency status in the body).
2. Add healthchecks to frontend, reverse-proxy, and Prometheus.
3. Use `condition: service_healthy` consistently in `depends_on`.

**How to verify:** With MySQL stopped, `/health` returns `503`/degraded and the container is marked unhealthy.

---

## 22. 🟠 Weak default passwords in code

**What's wrong:**
- Seeded super admin password falls back to the publicly-documented `Admin@123` if the env var is unset (`seed_service.py:66`), and `.env` sets it explicitly.
- DB password defaults to `dms_password` if missing (`config.py:26`) — no fail-fast.
- Grafana defaults to `admin/admin` (Issue #12).
- `change_requests` password-reset path only enforces `min_length=6` (`change_requests.py:128-129`) while the rest of the app requires full complexity.

**Why it matters (the 3 AM scenario):** The seed admin is created with a password that's printed in the README. If the forced-credential-rotation on first login is skipped or the account was created by a script that didn't honor it, you have a super-admin account with a public password. A reset-request path that accepts `abcdef` means password-reset tickets can set weak passwords, and `dms_password` as a DB default means a misconfigured server runs with credentials an attacker will try first.

**Where it lives:** `seed_service.py:66`, `config.py:25-26`, `change_requests.py:128-129`, `docker-compose.yml:214`.

**What to do:**
1. Fail startup if `ADMIN_INITIAL_PASSWORD` is unset in production; remove the `Admin@123` fallback.
2. Fail-fast (or warn loudly) if DB credentials are the known defaults.
3. Apply the same `validate_password_strength` validator to admin-set and reset passwords.

**How to verify:** With the env var unset, startup refuses to run; a password-reset attempt with `abcdef` is rejected.

---

## 23. 🟡 Main JavaScript bundle is 2 MB

**What's wrong:** `vite.config.js` has no `build` section — no `manualChunks`, no route-level lazy loading. `App.jsx` eagerly imports all ~40 pages, pulling `xlsx` (~900 KB) and `jspdf` into the initial download. The main chunk is **2,168 KB** (uncompressed ~4 MB before transfer).

**Why it matters (the 3 AM scenario):** A field operator on a 3G/4G connection waits 10+ seconds for the app shell on every cold load (first login of the day, after the service worker updates). On a bad connection the page times out or half-loads. Slow onboarding to your own system = lost field time every single day.

**Where it lives:** `frontend/vite.config.js:5-11`, `frontend/src/App.jsx:7-50`, `package.json:26` (`xlsx`), `dist/assets/index-*.js`.

**What to do:**
1. Add `manualChunks` to split vendors (react, chart, xlsx/jspdf) from app code.
2. Lazy-load route pages with `React.lazy`/dynamic import.
3. Enable gzip/brotli at nginx (see Issue #31).

**How to verify:** Rebuild and inspect `dist/assets` — initial JS is split and the first paint bundle is meaningfully smaller.

---

## 24. 🟡 No test coverage for the approval workflow

**What's wrong:** There are no test files for approvals/approval-requests — the source test files were **deleted** (only stale `.pyc` files remain in `__pycache__`). Approve/reject/role-routing has zero automated coverage.

**Why it matters (the 3 AM scenario:** The approval flow is the heart of the business — a rejected request that goes through as approved, or an approver who can approve their own request, is a process-integrity failure. With no tests, the next refactor ships a regression and nobody catches it until a real approval is wrong.

**Where it lives:** `backend/tests/routes/__pycache__/test_approvals_routes.*.pyc` (source gone).

**What to do:** Rewrite tests for the approval workflow: approve/reject, role routing, self-approval rejection, permission matrix, idempotency.

**How to verify:** CI runs the approval suite; a self-approval test fails before the fix and passes after.

---

## 25. 🟡 Tests never run against a real database

**What's wrong:** Every backend test mocks the services and database (`tests/routes/conftest.py:94-265`) or uses fake in-memory sessions. Nothing ever runs against a real MySQL. There are no concurrency tests, no migration tests, no deadlock/connection-exhaustion tests, and no DB-outage tests.

**Why it matters (the 3 AM scenario):** The double-allocation race (Issue #2) and oversell race (Issue #3) pass all 502 tests — because tests can't run two real transactions against a real database. A migration that breaks a constraint (Issue #7) ships green. "All tests pass" gives false confidence precisely where the production risk is highest.

**Where it lives:** `backend/tests/routes/conftest.py:94-265`, absence of integration test infra.

**What to do:**
1. Add a test stage that runs the suite against a real MySQL (e.g. a testcontainers or a compose-based MySQL for tests).
2. Add the concurrency tests from Issues #2/#3.
3. Add a migration smoke test (upgrade to head on a scratch DB).

**How to verify:** CI runs tests against real MySQL; the new concurrency tests actually fail on the current code.

---

## 26. 🟡 No automated SSL certificate renewal

**What's wrong:** The deployed cert is **self-signed for `CN=localhost`, valid until 2036** — and there is no automated rotation. The only documented renewal path is a **manual cron script** that stops the reverse-proxy, renews, and restarts (`DEPLOYMENT.md:427-450`). There is also no cert-expiry alert.

**Why it matters (the 3 AM scenario):** If you switch to a real Let's Encrypt cert (you should), it expires in 90 days. The manual cron runs late one month, or the operator forgets, and suddenly every browser shows "Your connection is not private" with no way to click through for all users. Field staff can't log in; support is flooded; you find out when someone calls.

**Where it lives:** `nginx/certs/` (self-signed, 10yr), `DEPLOYMENT.md:427-450` (manual cron), no cert-expiry alert in `alert.rules.yml`.

**What to do:** Automate renewal (certbot with a webroot/nginx plugin, or an internal CA with automated issuance), and add a Prometheus/Blackbox cert-expiry alert.

**How to verify:** A cert-expiry alert exists and renewal runs unattended; test by shortening a cert's validity in a staging environment.

---

## 27. 🟡 All times stored in server-local time, not UTC

**What's wrong:** Timestamps are generated as naive local time (`datetime.now().replace(tzinfo=None)` across services), and MySQL runs with `TZ=Asia/Kolkata` / `--default-time-zone=+05:30` (`docker-compose.yml:16-18`). Everything is stored as server-local, not UTC.

**Why it matters (the 3 AM scenario):** Today, one timezone, it works. The moment anyone changes the server's clock, or you add users in another zone, or you migrate hosts across regions, every report date, every audit trail, and every "when did this happen" answer is silently wrong by hours. DST boundaries double-book reports. The data is ambiguous and unfixable retroactively without rewriting history.

**Where it lives:** `auth_service.py` / `distribution_service.py` / all services (`datetime.now().replace(tzinfo=None)`), `docker-compose.yml:16-18`.

**What to do:** Store UTC everywhere (use `datetime.now(timezone.utc)`), convert to the business zone only for display. Add a migration to normalize existing data or document the cutover.

**How to verify:** A record created at 14:30 IST is stored as 09:00 UTC; reports render it back as 14:30 IST.

---

## 28. 🟡 Frontend accessibility gaps

**What's wrong:** The shared `Modal` has no focus trap, no `role="dialog"`/`aria-modal`, no Escape-to-close, and its close button is icon-only without an accessible name (`components/ui/Modal.jsx:14-51`). Several icon-only buttons lack labels (table pagination chevrons, navbar hamburger), the camera overlay in RegisterDevice is a raw `div`, and the "Remember me" checkbox on Login is inert (`Login.jsx:183-186`).

**Why it matters:** Keyboard users (including many with motor disabilities) cannot operate the app — focus escapes into the page behind the modal, there's no Escape, and screen readers announce nothing. It's also a legal/compliance risk in many regions for a business tool. The inert "Remember me" checkbox actively lies to users about what the system will do.

**Where it lives:** `Modal.jsx:14-51`, `DataTable.jsx:383-444`, `Navbar.jsx:99-104`, `RegisterDevice.jsx:234-274`, `Login.jsx:183-186`.

**What to do:** Add a focus trap + Escape handling + `aria-modal` to Modal; add `aria-label`s to icon buttons; either implement or remove "Remember me".

**How to verify:** Tab through a modal with keyboard only — focus stays inside, Escape closes, screen reader announces it as a dialog.

---

## 29. 🟡 The approvals workflow tables were deleted

**What's wrong:** The dedicated approval tables (`approvals`, `approval_requests`, `approval_role_routing`) were **dropped** in migrations `0003` and `0027`, and `approval_requests` again in `0027`. Approval logic now lives only as status transitions on distributions/defects/returns. Yet the README, the route router (`main.py:214` includes `approvals.router`), and user-facing docs still describe a centralized approval workflow.

**Why it matters (the 3 AM scenario):** You get a call that an approval "disappeared" — because there is no approval record to point at; the state change is buried in a distribution row. Auditors ask "who approved what, when, and why?" and the answer requires reconstructing it from history tables. The gap between what the docs/business believe exists and what the schema actually stores is exactly the kind of thing that bites during an audit or a compliance review.

**Where it lives:** migrations `0003`, `0027` (drops), `main.py:214` (router still mounted), README §7.

**What to do:** Either (a) re-introduce a proper approval entity with an audit trail, or (b) confirm the status-transition model is the intended design, update all docs/UI to match, and remove the dead approvals router.

**How to verify:** Approval actions are provably auditable (who/when/why) and no dead route/docs contradict the implemented model.

---

## 30. 🔵 Stale documentation and dead files in the repo

**What's wrong:** The repo contains references and files that no longer match reality:
- README §3 sequence diagram and §17 troubleshooting reference **MongoDB** — the system runs on MySQL.
- `backend/README.md` describes MongoDB/Cloud Atlas setup (stale).
- `backend/dms.db` — a 331 KB **SQLite database** with ~100k rows of real seed data, password hashes, phones, and distributions — is **tracked in git**.
- `.backup` files committed in the frontend: `Devices.jsx.backup`, `Distributions.jsx.backup2`, `RegisterDevice.jsx.backup`.
- Root `clusters.csv`, `operators.csv`, `sub_distributors.csv`, `users_bulk_upload_sample.csv` contain `password` columns (`Pass@123`).

**Why it matters (the 3 AM scenario):** A new engineer follows the README's MongoDB instructions and wastes an hour, or worse, "fixes" the wrong thing. More seriously, `dms.db` contains real password hashes and PII sitting in the repository that anyone with repo access can pull — the same exposure class as Issue #1. Dead `.backup` files suggest unstable work-in-progress shipped into a "production" tree.

**Where it lives:** `README.md` (MongoDB refs), `backend/README.md`, `backend/dms.db`, `frontend/src/pages/*.backup*`, root `*.csv`.

**What to do:**
1. Remove `dms.db` from git (`git rm --cached`), add to `.gitignore`, purge from history if the repo is public.
2. Delete the `.backup` files.
3. Replace CSV sample `password` values with placeholders or move them under `test/` clearly marked as fake.
4. Fix the MongoDB references in docs.

**How to verify:** `git ls-files` shows none of the above; a fresh clone contains no PII-bearing database and no dead files.

---

## 31. 🔵 No gzip compression and no browser-level security on static files

**What's wrong:** nginx has **no `gzip` directive anywhere** (`grep gzip` over `nginx/` → none). The frontend container's nginx (`frontend/nginx.conf`) also omits security headers and only sets cache headers on a few file types; it serves the `dist` directory with no `X-Content-Type-Options`, no `X-Frame-Options`, etc. (the reverse-proxy adds headers for requests that flow through it, but the static server itself doesn't).

**Why it matters:** The 2 MB JS bundle (Issue #23) is transferred uncompressed — roughly 3× the size it could be on every load. And any path that reaches the static server directly is missing the same security headers the rest of the stack applies, which weakens the defense-in-depth posture the app otherwise has.

**Where it lives:** `nginx/nginx.conf`, `frontend/nginx.conf`.

**What to do:** Enable gzip (or brotli) for text/JS/CSS/JSON in both nginx configs; add the standard security headers to the frontend static server.

**How to verify:** `curl -H "Accept-Encoding: gzip" -I` on the bundle shows `Content-Encoding: gzip`; response headers include the security headers.

---

## Summary

| Severity | Count | Fix-before-launch? |
|---|---|---|
| 🔴 Critical | 10 | Yes — data integrity, secrets, DR, alert delivery |
| 🟠 High | 12 | Yes, ideally before; at minimum the first 30 days |
| 🟡 Medium | 7 | After launch, but plan for them |
| 🔵 Low | 2 | Opportunistically |

The ten critical issues are the difference between "this system will lose or leak data in production" and "this system is safe to run." Everything else hardens it for the long term.
