import asyncio
from typing import Dict, Any, Optional

from sqlalchemy import text

from app.database_sqlalchemy import async_session_factory
from app.core.cache import cached
from app.services import device_service, distribution_service, defect_service, return_service, user_service

from .helpers import _build_date_filter, _resolve_scope_root_for_sub_distribution_manager, _get_descendant_user_ids, _get_user_status_split_by_role


async def get_dashboard_stats(user: Dict[str, Any],
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None) -> Dict[str, Any]:
    role = user.get("role")
    user_id = str(user.get("_id", user.get("id", "")))
    scope_root_id = _resolve_scope_root_for_sub_distribution_manager(user, user_id)

    cache_key = f"dashboard_stats:{user_id}:{role}:{scope_root_id}:{start_date}:{end_date}"
    return await cached(ttl_seconds=30, key=cache_key, factory=lambda: _compute_dashboard_stats(user, start_date, end_date))


async def _compute_dashboard_stats(user: Dict[str, Any],
                                   start_date: Optional[str] = None,
                                   end_date: Optional[str] = None) -> Dict[str, Any]:
    role = user.get("role")
    user_id = str(user.get("_id", user.get("id", "")))
    scope_root_id = _resolve_scope_root_for_sub_distribution_manager(user, user_id)

    if role == "sub_distribution_employee" and user.get("parent_id"):
        # Branch-scope employee stats to their parent sub-distributor so the
        # dashboard shows the sub distribution they work in.
        role = "sub_distributor"
        user_id = str(user.get("parent_id"))

    stats = {}

    if role in ["super_admin", "md_director", "manager", "pdic_staff"]:
        if start_date or end_date:
            device_stats, dist_stats, defect_stats, return_stats, user_stats, total_stats = \
                await asyncio.gather(
                    device_service.get_device_stats(start_date, end_date),
                    distribution_service.get_distribution_stats(start_date, end_date),
                    defect_service.get_defect_stats(start_date, end_date),
                    return_service.get_return_stats(start_date, end_date),
                    user_service.get_user_stats(),
                    device_service.get_device_stats(),
                )
            approval_stats = {"total_pending": 0, "approved": 0, "rejected": 0}
        else:
            device_stats, dist_stats, defect_stats, return_stats, user_stats = \
                await asyncio.gather(
                    device_service.get_device_stats(),
                    distribution_service.get_distribution_stats(),
                    defect_service.get_defect_stats(),
                    return_service.get_return_stats(),
                    user_service.get_user_stats(),
                )
            approval_stats = {"total_pending": 0, "approved": 0, "rejected": 0}
            total_stats = device_stats

        async with async_session_factory() as session:
            cond, prm = _build_date_filter("1=1", {}, start_date, end_date)
            distributions_filtered = (await session.execute(
                text(f"SELECT COUNT(*) FROM distributions WHERE {cond}"), prm
            )).scalar() or 0

            replacements_in_range = (await session.execute(
                text(f"SELECT COUNT(*) FROM defects WHERE replacement_device_id IS NOT NULL AND {cond}"), prm
            )).scalar() or 0

            total_replacements = (await session.execute(
                text("SELECT COUNT(*) FROM defects WHERE replacement_device_id IS NOT NULL")
            )).scalar() or 0

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
        async with async_session_factory() as session:
            dc, dp = _build_date_filter("current_holder_id = :uid", {"uid": user_id}, start_date, end_date)
            row = (await session.execute(
                text(f"SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS available FROM devices WHERE {dc}"),
                dp
            )).mappings().first()
            my_devices = int(row["total"])
            available_devices = int(row["available"]) if row["available"] is not None else 0

            sc, sp = _build_date_filter("from_user_id = :uid2", {"uid2": user_id}, start_date, end_date)
            row = (await session.execute(
                text(f"SELECT COUNT(*) AS sent, SUM(CASE WHEN status = 'pending_receipt' THEN 1 ELSE 0 END) AS pending FROM distributions WHERE {sc}"),
                sp
            )).mappings().first()
            sent = int(row["sent"])
            pending = int(row["pending"]) if row["pending"] is not None else 0

            rc, rp = _build_date_filter("to_user_id = :uid3", {"uid3": user_id}, start_date, end_date)
            received = (await session.execute(
                text(f"SELECT COUNT(*) FROM distributions WHERE {rc}"), rp
            )).scalar() or 0

            sub_rows = (await session.execute(
                text("SELECT id FROM users WHERE role = 'sub_distribution_manager' AND parent_id = :pid"),
                {"pid": int(user_id)}
            )).mappings().all()
            sub_dist_manager_ids = [int(r["id"]) for r in sub_rows]
            candidate_cluster_parent_ids = [int(user_id)] + sub_dist_manager_ids

            cluster_ids = []
            if candidate_cluster_parent_ids:
                cph = ",".join([f":cp_{i}" for i in range(len(candidate_cluster_parent_ids))])
                cparams = {f"cp_{i}": cid for i, cid in enumerate(candidate_cluster_parent_ids)}
                cluster_rows = (await session.execute(
                    text(f"SELECT id FROM users WHERE role = 'cluster' AND parent_id IN ({cph})"),
                    cparams
                )).mappings().all()
                cluster_ids = [int(r["id"]) for r in cluster_rows]

            operator_count = 0
            if cluster_ids:
                oph = ",".join([f":oc_{i}" for i in range(len(cluster_ids))])
                oparams = {f"oc_{i}": cid for i, cid in enumerate(cluster_ids)}
                operator_count = (await session.execute(
                    text(f"SELECT COUNT(*) FROM users WHERE role = 'operator' AND parent_id IN ({oph})"),
                    oparams
                )).scalar() or 0

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
        async with async_session_factory() as session:
            scope_ids = sorted({scope_root_id} | await _get_descendant_user_ids(session, scope_root_id))

            if not scope_ids:
                branch_devices = available_devices = sent = received = pending = operator_count = defect_reports = return_requests = 0
            else:
                ph = ",".join([f":s_{i}" for i in range(len(scope_ids))])
                str_ph = ",".join([f":ss_{i}" for i in range(len(scope_ids))])
                sp_map = {f"s_{i}": sid for i, sid in enumerate(scope_ids)}
                str_map = {f"ss_{i}": str(sid) for i, sid in enumerate(scope_ids)}

                date_cond, date_prm = _build_date_filter("1=1", {}, start_date, end_date)

                branch_devices = (await session.execute(
                    text(f"SELECT COUNT(*) FROM devices WHERE current_holder_id IN ({ph}) AND {date_cond}"),
                    {**sp_map, **date_prm}
                )).scalar() or 0

                available_devices = (await session.execute(
                    text(f"SELECT COUNT(*) FROM devices WHERE current_holder_id IN ({ph}) AND status = 'available' AND {date_cond}"),
                    {**sp_map, **date_prm}
                )).scalar() or 0

                sent = (await session.execute(
                    text(f"SELECT COUNT(*) FROM distributions WHERE from_user_id IN ({ph}) AND {date_cond}"),
                    {**sp_map, **date_prm}
                )).scalar() or 0

                received = (await session.execute(
                    text(f"SELECT COUNT(*) FROM distributions WHERE to_user_id IN ({ph}) AND {date_cond}"),
                    {**sp_map, **date_prm}
                )).scalar() or 0

                pending = (await session.execute(
                    text("SELECT COUNT(*) FROM distributions WHERE to_user_id = :uid AND status = 'pending_receipt'"),
                    {"uid": int(user_id)}
                )).scalar() or 0

                operator_count = (await session.execute(
                    text(f"SELECT COUNT(*) FROM users WHERE role = 'operator' AND id IN ({ph})"),
                    sp_map
                )).scalar() or 0

                defect_reports = (await session.execute(
                    text(f"SELECT COUNT(*) FROM defects WHERE reported_by IN ({str_ph}) AND {date_cond}"),
                    {**str_map, **date_prm}
                )).scalar() or 0

                return_requests = (await session.execute(
                    text(f"SELECT COUNT(*) FROM returns r LEFT JOIN defects def ON r.defect_id = CAST(def.id AS CHAR) WHERE def.reported_by IN ({str_ph}) AND {date_cond.replace('created_at', 'r.created_at')}"),
                    {**str_map, **date_prm}
                )).scalar() or 0

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
        async with async_session_factory() as session:
            dc, dp = _build_date_filter("current_holder_id = :uid", {"uid": user_id}, start_date, end_date)
            my_devices = (await session.execute(
                text(f"SELECT COUNT(*) FROM devices WHERE {dc}"), dp
            )).scalar() or 0

            sc, sp = _build_date_filter("from_user_id = :uid2", {"uid2": user_id}, start_date, end_date)
            sent = (await session.execute(
                text(f"SELECT COUNT(*) FROM distributions WHERE {sc}"), sp
            )).scalar() or 0

            rc, rp = _build_date_filter("to_user_id = :uid3", {"uid3": user_id}, start_date, end_date)
            received = (await session.execute(
                text(f"SELECT COUNT(*) FROM distributions WHERE {rc}"), rp
            )).scalar() or 0

            operator_split = await _get_user_status_split_by_role(session, "operator", user_id)
        operator_stats_data = {
            "total": int(operator_split["active"] + operator_split["inactive"]),
            "active": int(operator_split["active"]),
            "inactive": int(operator_split["inactive"]),
        }
        stats = {
            "my_devices": my_devices,
            "operators": operator_stats_data,
            "distributions_sent": sent,
            "distributions_received": received
        }

    elif role == "operator":
        async with async_session_factory() as session:
            uid = user_id
            dc, dp = _build_date_filter("current_holder_id = :uid", {"uid": uid}, start_date, end_date)
            my_devices = (await session.execute(
                text(f"SELECT COUNT(*) FROM devices WHERE {dc}"), dp
            )).scalar() or 0

            dfc, dfp = _build_date_filter("reported_by = :uid2", {"uid2": uid}, start_date, end_date)
            my_defects = (await session.execute(
                text(f"SELECT COUNT(*) FROM defects WHERE {dfc}"), dfp
            )).scalar() or 0

            rc, rp = _build_date_filter("def.reported_by = :uid3", {"uid3": uid}, start_date, end_date)
            my_returns = (await session.execute(
                text(f"SELECT COUNT(*) FROM returns r LEFT JOIN defects def ON r.defect_id = CAST(def.id AS CHAR) WHERE {rc.replace('created_at', 'r.created_at')}"), rp
            )).scalar() or 0

            # Accurate counts independent of any device-list page size. The
            # dashboard reads these keys; without them it falls back to the
            # (page-limited) device rows and shows e.g. 10 instead of the real total.
            ac, ap = _build_date_filter(
                "current_holder_id = :uid5 AND status IN ('available','distributed','in_use')",
                {"uid5": uid}, start_date, end_date
            )
            active_devices = (await session.execute(
                text(f"SELECT COUNT(*) FROM devices WHERE {ac}"), ap
            )).scalar() or 0

            ic, ip = _build_date_filter(
                "current_holder_id = :uid6 AND status = 'in_use'",
                {"uid6": uid}, start_date, end_date
            )
            in_use_devices = (await session.execute(
                text(f"SELECT COUNT(*) FROM devices WHERE {ic}"), ip
            )).scalar() or 0

        stats = {
            "assigned_devices": my_devices,
            "active_devices": active_devices,
            "in_use_devices": in_use_devices,
            "defect_reports": my_defects,
            "my_devices": my_devices,
            "my_defects": my_defects,
            "my_returns": my_returns
        }

    return stats
