import asyncio
import logging

from app.database import get_db

logger = logging.getLogger(__name__)

UPDATE_INTERVAL_SECONDS = 60

_last_new_users = 0
_last_dist_created = 0
_last_dist_completed = 0
_last_dist_failed = 0
_last_success_logins = 0
_last_failed_logins = 0
_last_device_distributions = {}

LOW_STOCK_THRESHOLD = 10


async def _sync_gauge_from_db(gauge, query, params=None):
    async with get_db() as db:
        cursor = await db.execute(query, params or ())
        row = await cursor.fetchone()
        gauge.set(row[0] if row else 0)


async def _update_user_metrics():
    from app.core.metrics import (
        total_users, active_users,
        total_operators, active_operators,
        total_clusters, active_clusters,
        total_sub_distributors, active_sub_distributors,
        new_users_created_total,
    )

    global _last_new_users

    try:
        async with get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total = (await cursor.fetchone())[0]
            total_users.set(total)

            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
            active_users.set((await cursor.fetchone())[0])

            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE role = 'operator'")
            total_operators.set((await cursor.fetchone())[0])

            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'operator' AND status = 'active'"
            )
            active_operators.set((await cursor.fetchone())[0])

            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE role = 'cluster'")
            total_clusters.set((await cursor.fetchone())[0])

            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'cluster' AND status = 'active'"
            )
            active_clusters.set((await cursor.fetchone())[0])

            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE role = 'sub_distributor'")
            total_sub_distributors.set((await cursor.fetchone())[0])

            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'sub_distributor' AND status = 'active'"
            )
            active_sub_distributors.set((await cursor.fetchone())[0])

        diff = total - _last_new_users
        if diff > 0:
            new_users_created_total.inc(diff)
        _last_new_users = total
    except Exception as exc:
        logger.exception("Failed to update user Prometheus metrics: %s", exc)


async def _update_device_metrics():
    from app.core.metrics import inventory_items_total, low_stock_items_total

    try:
        async with get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM devices")
            inventory_items_total.set((await cursor.fetchone())[0])

            cursor = await db.execute(
                "SELECT COUNT(*) FROM devices WHERE status = 'available'"
            )
            available = (await cursor.fetchone())[0]
            low_stock_items_total.set(max(0, LOW_STOCK_THRESHOLD - available))
    except Exception as exc:
        logger.exception("Failed to update device Prometheus metrics: %s", exc)


async def _update_distribution_metrics():
    from app.core.metrics import (
        distributions_created_total,
        distributions_completed_total,
        distributions_failed_total,
        device_distributions_total,
    )

    global _last_dist_created, _last_dist_completed, _last_dist_failed, _last_device_distributions

    try:
        async with get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM distributions")
            total = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM distributions WHERE status = 'delivered'"
            )
            completed = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM distributions WHERE status = 'rejected'"
            )
            failed = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT status, COUNT(*) AS total FROM distributions GROUP BY status"
            )
            rows = await cursor.fetchall()
            by_status = {}
            for row in rows:
                by_status[str(row[0])] = int(row[1])

        for status, count in by_status.items():
            prev = _last_device_distributions.get(status, 0)
            diff = count - prev
            if diff > 0:
                device_distributions_total.labels(status=status).inc(diff)
        _last_device_distributions = by_status

        diff = total - _last_dist_created
        if diff > 0:
            distributions_created_total.inc(diff)
        _last_dist_created = total

        diff = completed - _last_dist_completed
        if diff > 0:
            distributions_completed_total.inc(diff)
        _last_dist_completed = completed

        diff = failed - _last_dist_failed
        if diff > 0:
            distributions_failed_total.inc(diff)
        _last_dist_failed = failed
    except Exception as exc:
        logger.exception("Failed to update distribution Prometheus metrics: %s", exc)


async def _update_login_metrics():
    from app.core.metrics import successful_logins_total, failed_logins_total

    global _last_success_logins, _last_failed_logins

    try:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM api_activity_logs WHERE path = '/api/auth/login' AND status_code = 200"
            )
            success_count = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM api_activity_logs WHERE path = '/api/auth/login' AND status_code >= 400"
            )
            fail_count = (await cursor.fetchone())[0]

        diff = success_count - _last_success_logins
        if diff > 0:
            successful_logins_total.inc(diff)
        _last_success_logins = success_count

        diff = fail_count - _last_failed_logins
        if diff > 0:
            failed_logins_total.inc(diff)
        _last_failed_logins = fail_count
    except Exception as exc:
        logger.exception("Failed to update login Prometheus metrics: %s", exc)


async def _update_all_metrics():
    await _update_user_metrics()
    await _update_device_metrics()
    await _update_distribution_metrics()
    await _update_login_metrics()


async def metrics_collector_loop():
    """Background loop that periodically syncs DB state to Prometheus metrics."""
    logger.info("Metrics collector started (interval=%ds)", UPDATE_INTERVAL_SECONDS)
    while True:
        try:
            await _update_all_metrics()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Metrics collector error: %s", exc)
        await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
