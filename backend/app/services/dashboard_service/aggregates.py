"""Shared aggregate core for the management (admin/manager/md/staff) dashboard.

``/dashboard/stats`` and ``/dashboard/advanced-metrics`` are requested in
parallel on first dashboard load and both independently recompute the same
system-wide aggregates (device / distribution / defect / return / user totals,
replacement counts). Because ETag short-circuits the endpoint only on HTTP
revalidation and provides no deduplication within a single cold page load
(each parallel request independently computes a fresh response), these shared
aggregates were being computed up to twice per page load.

This module computes the shared management aggregates **once**, memoized within
the same 30s window used by the top-level dashboard endpoints, so both
endpoints reuse the result. The keys are the date range only (and the cache is
per-process, matching the existing ``cached``/30s semantics already used across
the dashboard). No API contract or response shape changes.
"""

import asyncio
from typing import Any, Dict, Optional

from sqlalchemy import text

from app.core.cache import cached
from app.database_sqlalchemy import async_session_factory
from app.services import (
    device_service,
    distribution_service,
    defect_service,
    return_service,
    user_service,
)

from .helpers import _build_date_filter

_MANAGEMENT_CORE_TTL = 30


async def get_management_core_metrics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the shared aggregate dict used by /stats and /advanced-metrics.

    Memoized per (start_date, end_date). device_service stats are additionally
    version-keyed and TTL-cached internally, so repeated calls within the TTL
    do not re-query the database.
    """
    cache_key = f"dashboard_management_core:{start_date}:{end_date}"
    return await cached(
        ttl_seconds=_MANAGEMENT_CORE_TTL,
        key=cache_key,
        factory=lambda: _compute_management_core_metrics(start_date, end_date),
    )


async def _compute_management_core_metrics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    total_device_stats, filtered_device_stats, dist_stats, defect_stats, return_stats, user_stats = await asyncio.gather(
        device_service.get_device_stats(),
        device_service.get_device_stats(start_date, end_date),
        distribution_service.get_distribution_stats(start_date, end_date),
        defect_service.get_defect_stats(start_date, end_date),
        return_service.get_return_stats(start_date, end_date),
        user_service.get_user_stats(),
    )

    async with async_session_factory() as session:
        cond, prm = _build_date_filter("1=1", {}, start_date, end_date)

        distributions_filtered = (await session.execute(
            text(f"SELECT COUNT(*) FROM distributions WHERE {cond}"), prm
        )).scalar() or 0

        replacements_in_range = (await session.execute(
            text(f"SELECT COUNT(*) FROM defects WHERE replacement_device_id IS NOT NULL AND {cond}"), prm
        )).scalar() or 0

        replacements_total = (await session.execute(
            text("SELECT COUNT(*) FROM defects WHERE replacement_device_id IS NOT NULL")
        )).scalar() or 0

        replacements_confirmed = (await session.execute(
            text("SELECT COUNT(*) FROM defects WHERE replacement_device_id IS NOT NULL AND replacement_confirmed_at IS NOT NULL")
        )).scalar() or 0

        replacements_pending = (await session.execute(
            text("SELECT COUNT(*) FROM defects WHERE replacement_device_id IS NOT NULL AND replacement_confirmed_at IS NULL")
        )).scalar() or 0

    return {
        "total_device_stats": total_device_stats,
        "device_stats": filtered_device_stats,
        "dist_stats": dist_stats,
        "defect_stats": defect_stats,
        "return_stats": return_stats,
        "user_stats": user_stats,
        "distributions_filtered": distributions_filtered,
        "replacements_in_range": replacements_in_range,
        "replacements_total": replacements_total,
        "replacements_confirmed": replacements_confirmed,
        "replacements_pending": replacements_pending,
    }