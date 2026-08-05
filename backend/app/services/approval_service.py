import logging
import time
from typing import Any, Dict, Optional

from app.services import distribution_service, return_service, defect_service
from app.utils.helpers import get_pagination

logger = logging.getLogger(__name__)

# A single page window never materializes more than this many rows per source.
MAX_SOURCE_ROWS = 10000
COUNTS_TTL_SECONDS = 60

# Per-user cache of the tab-badge counts: user_id -> (expires_at, counts).
_counts_cache: Dict[str, tuple] = {}


def _get_item_id(row: Dict[str, Any]) -> Any:
    return row.get("_id") or row.get("id")


async def _fetch_counts(current_user: Dict[str, Any]) -> Dict[str, int]:
    """Exact per-type pending totals from indexed COUNT(*) queries.

    Returns the badge counts without materializing any rows. Called once per
    user per TTL window and reused across pagination clicks.
    """
    dist_result = await distribution_service.get_distributions(
        page=1,
        page_size=1,
        status="pending",
        current_user=current_user,
        include_device_ids=False,
    )
    ret_pending = await return_service.get_returns(
        page=1, page_size=1, status="pending", current_user=current_user
    )
    ret_approved = await return_service.get_returns(
        page=1, page_size=1, status="approved", current_user=current_user
    )
    defect_result = await defect_service.get_defects(
        page=1,
        page_size=1,
        status="reported",
        visibility_user=current_user,
    )

    distribution = int(dist_result.get("pagination", {}).get("total") or 0)
    return_confirmation = (
        int(ret_pending.get("pagination", {}).get("total") or 0)
        + int(ret_approved.get("pagination", {}).get("total") or 0)
    )
    defect = int(defect_result.get("pagination", {}).get("total") or 0)

    return {
        "distribution": distribution,
        "return_confirmation": return_confirmation,
        "defect": defect,
        "all": distribution + return_confirmation + defect,
    }


async def _get_cached_counts(current_user: Dict[str, Any]) -> Dict[str, int]:
    cache_key = str(current_user.get("id") or current_user.get("_id") or "anonymous")
    now = time.time()
    cached = _counts_cache.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]
    counts = await _fetch_counts(current_user)
    _counts_cache[cache_key] = (now + COUNTS_TTL_SECONDS, counts)
    return counts


async def get_pending_approvals(
    current_user: Dict[str, Any],
    page: int = 1,
    page_size: int = 100,
    item_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a unified pending-approvals feed across distributions, returns, and defects.

    Scoping is delegated to each underlying service (they apply the same role/hierarchy
    visibility rules already used by the individual list pages). Page rows are fetched
    with a bounded per-source limit (page * page_size) and merged in Python; badge
    counts come from cached exact SQL totals so pagination never re-scans the full set.
    """
    counts = await _get_cached_counts(current_user)

    need = min(page * page_size, MAX_SOURCE_ROWS)
    dist_result = await distribution_service.get_distributions(
        page=1,
        page_size=need,
        status="pending",
        current_user=current_user,
        include_device_ids=True,
    )
    ret_pending = await return_service.get_returns(
        page=1, page_size=need, status="pending", current_user=current_user
    )
    ret_approved = await return_service.get_returns(
        page=1, page_size=need, status="approved", current_user=current_user
    )
    defect_result = await defect_service.get_defects(
        page=1,
        page_size=need,
        status="reported",
        visibility_user=current_user,
    )

    items = []

    for d in dist_result.get("data") or []:
        device_count = d.get("device_count") or len(d.get("device_ids") or []) or 0
        items.append({
            **d,
            "type": "distribution",
            "id": _get_item_id(d),
            "title": f"Distribution to {d.get('to_user_name') or 'Unknown'}",
            "requestedBy": d.get("from_user_name") or "Unknown",
            "requestDate": d.get("created_at"),
            "status": d.get("status"),
            "recipient": d.get("to_user_name") or "Unknown",
            "deviceCount": device_count,
        })

    for r in (ret_pending.get("data") or []) + (ret_approved.get("data") or []):
        device = r.get("device_name") or r.get("device_type") or "Unknown Device"
        items.append({
            **r,
            "type": "return_confirmation",
            "id": _get_item_id(r),
            "title": f"Confirm Return Receipt - {device}",
            "requestedBy": r.get("initiated_by_name") or r.get("requested_by_name") or "Unknown",
            "requestDate": r.get("created_at"),
            "status": r.get("status"),
            "device": device,
            "reason": r.get("reason") or "-",
        })

    for d in defect_result.get("data") or []:
        device = d.get("device_name") or d.get("device_type") or "Unknown Device"
        items.append({
            **d,
            "type": "defect",
            "id": _get_item_id(d),
            "title": f"Defect Report - {device}",
            "requestedBy": d.get("reported_by_name") or "Unknown",
            "requestDate": d.get("created_at"),
            "status": d.get("status"),
            "device": device,
            "defectType": d.get("defect_type") or "-",
            "severity": d.get("severity") or "-",
        })

    # Newest first
    items.sort(key=lambda i: str(i.get("requestDate") or ""), reverse=True)

    # Dedupe by type:id (a single entity may surface through more than one source)
    seen = set()
    unique = []
    for item in items:
        key = f"{item.get('type')}:{item.get('id')}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    if item_type and item_type != "all":
        filtered = [i for i in unique if i.get("type") == item_type]
        total = counts.get(item_type, 0)
    else:
        filtered = unique
        total = counts["all"]

    offset = (page - 1) * page_size
    page_items = filtered[offset:offset + page_size]

    return {
        "data": page_items,
        "pagination": get_pagination(page, page_size, total),
        "counts": counts,
    }
