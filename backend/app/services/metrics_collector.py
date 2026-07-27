import asyncio
import logging

from app.database import get_db

logger = logging.getLogger(__name__)

UPDATE_INTERVAL_SECONDS = 300

_last_new_users = 0
_last_dist_created = 0
_last_dist_completed = 0
_last_dist_failed = 0
_last_success_logins = 0
_last_failed_logins = 0
_last_device_distributions = {}

LOW_STOCK_THRESHOLD = 10

# Single consolidated query grouping all aggregate counts
_CONSOLIDATED_QUERY = """
SELECT
  (SELECT COUNT(*) FROM users) AS total_users,
  (SELECT COUNT(*) FROM users WHERE status = 'active') AS active_users,
  (SELECT COUNT(*) FROM users WHERE role = 'operator') AS total_operators,
  (SELECT COUNT(*) FROM users WHERE role = 'operator' AND status = 'active') AS active_operators,
  (SELECT COUNT(*) FROM users WHERE role = 'cluster') AS total_clusters,
  (SELECT COUNT(*) FROM users WHERE role = 'cluster' AND status = 'active') AS active_clusters,
  (SELECT COUNT(*) FROM users WHERE role = 'sub_distributor') AS total_sub_distributors,
  (SELECT COUNT(*) FROM users WHERE role = 'sub_distributor' AND status = 'active') AS active_sub_distributors,
  (SELECT COUNT(*) FROM devices) AS total_devices,
  (SELECT COUNT(*) FROM devices WHERE status = 'available') AS available_devices,
  (SELECT COUNT(*) FROM distributions) AS total_distributions,
  (SELECT COUNT(*) FROM distributions WHERE status = 'delivered') AS completed_distributions,
  (SELECT COUNT(*) FROM distributions WHERE status = 'rejected') AS failed_distributions,
  (SELECT COUNT(*) FROM api_activity_logs WHERE path = '/api/auth/login' AND status_code = 200) AS success_logins,
  (SELECT COUNT(*) FROM api_activity_logs WHERE path = '/api/auth/login' AND status_code >= 400) AS failed_logins
"""


async def _update_all_metrics():
    from app.core.metrics import (
        total_users, active_users,
        total_operators, active_operators,
        total_clusters, active_clusters,
        total_sub_distributors, active_sub_distributors,
        new_users_created_total,
        inventory_items_total, low_stock_items_total,
        distributions_created_total,
        distributions_completed_total,
        distributions_failed_total,
        device_distributions_total,
        successful_logins_total, failed_logins_total,
    )

    global _last_new_users, _last_dist_created, _last_dist_completed, _last_dist_failed
    global _last_device_distributions, _last_success_logins, _last_failed_logins

    try:
        async with get_db() as db:
            cursor = await db.execute(_CONSOLIDATED_QUERY)
            row = await cursor.fetchone()

            total_users_n = row[0]
            active_users_n = row[1]
            total_operators_n = row[2]
            active_operators_n = row[3]
            total_clusters_n = row[4]
            active_clusters_n = row[5]
            total_sub_distributors_n = row[6]
            active_sub_distributors_n = row[7]
            total_devices_n = row[8]
            available_devices_n = row[9]
            total_distributions_n = row[10]
            completed_distributions_n = row[11]
            failed_distributions_n = row[12]
            success_logins_n = row[13]
            failed_logins_n = row[14]

            cursor2 = await db.execute(
                "SELECT status, COUNT(*) AS total FROM distributions GROUP BY status"
            )
            by_status = {str(r[0]): int(r[1]) for r in await cursor2.fetchall()}

        # User gauges
        total_users.set(total_users_n)
        active_users.set(active_users_n)
        total_operators.set(total_operators_n)
        active_operators.set(active_operators_n)
        total_clusters.set(total_clusters_n)
        active_clusters.set(active_clusters_n)
        total_sub_distributors.set(total_sub_distributors_n)
        active_sub_distributors.set(active_sub_distributors_n)

        diff_users = total_users_n - _last_new_users
        if diff_users > 0:
            new_users_created_total.inc(diff_users)
        _last_new_users = total_users_n

        # Device gauges
        inventory_items_total.set(total_devices_n)
        low_stock_items_total.set(max(0, LOW_STOCK_THRESHOLD - available_devices_n))

        # Distribution gauges + counters
        for status, count in by_status.items():
            prev = _last_device_distributions.get(status, 0)
            diff = count - prev
            if diff > 0:
                device_distributions_total.labels(status=status).inc(diff)
        _last_device_distributions = by_status

        diff_created = total_distributions_n - _last_dist_created
        if diff_created > 0:
            distributions_created_total.inc(diff_created)
        _last_dist_created = total_distributions_n

        diff_completed = completed_distributions_n - _last_dist_completed
        if diff_completed > 0:
            distributions_completed_total.inc(diff_completed)
        _last_dist_completed = completed_distributions_n

        diff_failed = failed_distributions_n - _last_dist_failed
        if diff_failed > 0:
            distributions_failed_total.inc(diff_failed)
        _last_dist_failed = failed_distributions_n

        # Login counters
        diff_success = success_logins_n - _last_success_logins
        if diff_success > 0:
            successful_logins_total.inc(diff_success)
        _last_success_logins = success_logins_n

        diff_fail = failed_logins_n - _last_failed_logins
        if diff_fail > 0:
            failed_logins_total.inc(diff_fail)
        _last_failed_logins = failed_logins_n

    except Exception as exc:
        logger.exception("Failed to update Prometheus metrics: %s", exc)


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
