import asyncio
from typing import Dict, Any, Optional

from app.database import get_db
from app.services import device_service, distribution_service, defect_service, return_service, user_service, approval_service, operator_service

from .helpers import _build_date_filter, _resolve_scope_root_for_sub_distribution_manager, _get_descendant_user_ids


async def get_dashboard_stats(user: Dict[str, Any],
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get dashboard statistics based on user role"""
    role = user.get("role")
    user_id = str(user.get("_id", user.get("id", "")))
    scope_root_id = _resolve_scope_root_for_sub_distribution_manager(user, user_id)

    stats = {}

    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        if start_date or end_date:
            device_stats, dist_stats, defect_stats, return_stats, user_stats, approval_stats, total_stats = \
                await asyncio.gather(
                    device_service.get_device_stats(start_date, end_date),
                    distribution_service.get_distribution_stats(start_date, end_date),
                    defect_service.get_defect_stats(start_date, end_date),
                    return_service.get_return_stats(start_date, end_date),
                    user_service.get_user_stats(),
                    approval_service.get_approval_stats(),
                    device_service.get_device_stats(),
                )
        else:
            device_stats, dist_stats, defect_stats, return_stats, user_stats, approval_stats = \
                await asyncio.gather(
                    device_service.get_device_stats(),
                    distribution_service.get_distribution_stats(),
                    defect_service.get_defect_stats(),
                    return_service.get_return_stats(),
                    user_service.get_user_stats(),
                    approval_service.get_approval_stats(),
                )
            total_stats = device_stats

        async with get_db() as db:
            cond, prm = _build_date_filter("1=1", (), start_date, end_date)
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM distributions WHERE {cond}", prm
            )
            distributions_filtered = (await cursor.fetchone())[0]

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM defects WHERE replacement_device_id IS NOT NULL AND {cond}", prm
            )
            replacements_in_range = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM defects WHERE replacement_device_id IS NOT NULL"
            )
            total_replacements = (await cursor.fetchone())[0]

        total_active = (
            total_stats.get("available", 0) +
            total_stats.get("distributed", 0) +
            total_stats.get("in_use", 0)
        )
        total_distributed = total_stats.get("distributed", 0) + total_stats.get("in_use", 0)
        total_inactive = max(0, total_stats.get("total", 0) - total_active)

        filtered_total = device_stats.get("total", 0)
        filtered_active = (
            device_stats.get("available", 0) +
            device_stats.get("distributed", 0) +
            device_stats.get("in_use", 0)
        )

        stats = {
            "total_devices": total_stats.get("total", 0),
            "total_active_devices": total_active,
            "total_distributed_devices": total_distributed,
            "total_inactive_devices": total_inactive,
            "total_defective_devices": total_stats.get("defective", 0),
            "total_replaced_devices": total_replacements,
            "registered_in_range": filtered_total,
            "distributed_in_range": device_stats.get("distributed", 0) + device_stats.get("in_use", 0),
            "inactive_in_range": max(0, filtered_total - filtered_active),
            "defective_in_range": device_stats.get("defective", 0),
            "replacements_in_range": replacements_in_range,
            "available_devices": device_stats.get("available", 0),
            "in_use_devices": device_stats.get("in_use", 0),
            "defective_devices": device_stats.get("defective", 0),
            "returned_devices": device_stats.get("returned", 0),
            "active_devices": filtered_active,
            "distributed_devices": device_stats.get("distributed", 0) + device_stats.get("in_use", 0),
            "total_distributions": dist_stats.get("total", 0),
            "pending_distributions": dist_stats.get("pending", 0),
            "approved_distributions": dist_stats.get("approved", 0),
            "delivered_distributions": dist_stats.get("delivered", 0),
            "rejected_distributions": dist_stats.get("rejected", 0),
            "distribution_this_month": distributions_filtered,
            "total_defects": defect_stats.get("total", 0),
            "defect_reports": defect_stats.get("total", 0),
            "reported_defects": defect_stats.get("by_status", {}).get("reported", 0),
            "under_review_defects": defect_stats.get("by_status", {}).get("under_review", 0),
            "resolved_defects": defect_stats.get("by_status", {}).get("resolved", 0),
            "total_returns": return_stats.get("total", 0),
            "return_requests": return_stats.get("total", 0),
            "pending_returns": return_stats.get("by_status", {}).get("pending", 0),
            "approved_returns": return_stats.get("by_status", {}).get("approved", 0),
            "received_returns": return_stats.get("by_status", {}).get("received", 0),
            "rejected_returns": return_stats.get("by_status", {}).get("rejected", 0),
            "total_users": user_stats.get("total", 0),
            "active_users": user_stats.get("active", 0),
            "pending_approvals": approval_stats.get("total_pending", 0),
            "pending_receipts": dist_stats.get("pending_receipt", 0),
            "total_approved": approval_stats.get("approved", 0),
            "total_rejected": approval_stats.get("rejected", 0),
            "devices": device_stats,
            "distributions": dist_stats,
            "defects": defect_stats,
            "returns": return_stats,
            "users": user_stats,
            "approvals": approval_stats
        }

    elif role == "sub_distributor":
        async with get_db() as db:
            dc, dp = _build_date_filter("current_holder_id = ?", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM devices WHERE {dc}", dp)
            my_devices = (await cursor.fetchone())[0]

            ac, ap = _build_date_filter("current_holder_id = ? AND status = 'available'", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM devices WHERE {ac}", ap)
            available_devices = (await cursor.fetchone())[0]

            sc, sp = _build_date_filter("from_user_id = ?", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {sc}", sp)
            sent = (await cursor.fetchone())[0]

            rc, rp = _build_date_filter("to_user_id = ?", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {rc}", rp)
            received = (await cursor.fetchone())[0]

            pc, pp = _build_date_filter("from_user_id = ? AND status = 'pending'", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {pc}", pp)
            pending = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT id FROM users WHERE role = 'sub_distribution_manager' AND parent_id = ?", (int(user_id),))
            sub_dist_manager_ids = [row[0] for row in await cursor.fetchall()]
            candidate_cluster_parent_ids = [int(user_id)] + sub_dist_manager_ids
            if candidate_cluster_parent_ids:
                placeholders = ",".join("?" * len(candidate_cluster_parent_ids))
                cursor = await db.execute(
                    f"SELECT id FROM users WHERE role = 'cluster' AND parent_id IN ({placeholders})",
                    tuple(candidate_cluster_parent_ids)
                )
                cluster_ids = [row[0] for row in await cursor.fetchall()]
            else:
                cluster_ids = []

            if cluster_ids:
                placeholders = ",".join("?" * len(cluster_ids))
                cursor = await db.execute(
                    f"SELECT COUNT(*) FROM users WHERE role = 'operator' AND parent_id IN ({placeholders})",
                    tuple(cluster_ids)
                )
                operator_count = (await cursor.fetchone())[0]
            else:
                operator_count = 0

        stats = {
            "my_devices": my_devices,
            "received_devices": my_devices,
            "available_devices": available_devices,
            "distributions_sent": sent,
            "distributions_received": received,
            "pending_distributions": pending,
            "operator_count": operator_count,
        }

    elif role == "sub_distribution_manager":
        async with get_db() as db:
            scope_ids = sorted({scope_root_id} | await _get_descendant_user_ids(db, scope_root_id))
            placeholders = ",".join(["?"] * len(scope_ids)) if scope_ids else "?"

            dc, dp = _build_date_filter(f"current_holder_id IN ({placeholders})", tuple(scope_ids), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM devices WHERE {dc}", dp)
            branch_devices = (await cursor.fetchone())[0]

            ac, ap = _build_date_filter(f"current_holder_id IN ({placeholders}) AND status = 'available'", tuple(scope_ids), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM devices WHERE {ac}", ap)
            available_devices = (await cursor.fetchone())[0]

            sc, sp = _build_date_filter(f"from_user_id IN ({placeholders})", tuple(scope_ids), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {sc}", sp)
            sent = (await cursor.fetchone())[0]

            rc, rp = _build_date_filter(f"to_user_id IN ({placeholders})", tuple(scope_ids), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {rc}", rp)
            received = (await cursor.fetchone())[0]

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM distributions WHERE to_user_id = ? AND status = 'pending_receipt'",
                (user_id,)
            )
            pending = (await cursor.fetchone())[0]

            cursor = await db.execute(
                f"SELECT COUNT(*) FROM users WHERE role = 'operator' AND id IN ({placeholders})",
                tuple(scope_ids)
            )
            operator_count = (await cursor.fetchone())[0]

            dec, dep = _build_date_filter(f"CAST(reported_by AS TEXT) IN ({placeholders})", tuple(scope_ids), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {dec}", dep)
            defect_reports = (await cursor.fetchone())[0]

            rec, rep = _build_date_filter(f"CAST(requested_by AS TEXT) IN ({placeholders})", tuple(scope_ids), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM returns WHERE {rec}", rep)
            return_requests = (await cursor.fetchone())[0]

        stats = {
            "my_devices": branch_devices,
            "received_devices": branch_devices,
            "available_devices": available_devices,
            "distributions_sent": sent,
            "distributions_received": received,
            "pending_distributions": pending,
            "operator_count": operator_count,
            "defect_reports": defect_reports,
            "return_requests": return_requests,
            "assigned_to_operators": sent,
        }

    elif role == "cluster":
        async with get_db() as db:
            dc, dp = _build_date_filter("current_holder_id = ?", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM devices WHERE {dc}", dp)
            my_devices = (await cursor.fetchone())[0]

            sc, sp = _build_date_filter("from_user_id = ?", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {sc}", sp)
            sent = (await cursor.fetchone())[0]

            rc, rp = _build_date_filter("to_user_id = ?", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM distributions WHERE {rc}", rp)
            received = (await cursor.fetchone())[0]
        operator_stats_data = await operator_service.get_operator_stats(user_id)
        stats = {
            "my_devices": my_devices,
            "operators": operator_stats_data,
            "distributions_sent": sent,
            "distributions_received": received
        }

    elif role == "operator":
        async with get_db() as db:
            dc, dp = _build_date_filter("current_holder_id = ?", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM devices WHERE {dc}", dp)
            my_devices = (await cursor.fetchone())[0]

            dfc, dfp = _build_date_filter("reported_by = ?", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {dfc}", dfp)
            my_defects = (await cursor.fetchone())[0]

            rc, rp = _build_date_filter("requested_by = ?", (user_id,), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM returns WHERE {rc}", rp)
            my_returns = (await cursor.fetchone())[0]
        stats = {
            "my_devices": my_devices,
            "my_defects": my_defects,
            "my_returns": my_returns
        }

    return stats
