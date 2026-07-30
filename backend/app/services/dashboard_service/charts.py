from datetime import datetime
from typing import Optional

from sqlalchemy import text

from app.database_sqlalchemy import async_session_factory

from .helpers import _build_date_filter, _month_start, _shift_months


async def get_distribution_chart_data(start_date: Optional[str] = None,
                                      end_date: Optional[str] = None) -> list:
    data = []
    now = datetime.now().replace(tzinfo=None)

    async with async_session_factory() as session:
        if start_date or end_date:
            cond, prm = _build_date_filter("status = 'delivered'", {}, start_date, end_date)
            total = (await session.execute(
                text(f"SELECT COUNT(*) FROM distributions WHERE {cond}"), prm
            )).scalar() or 0
            data.append({"month": "Filtered", "distributions": total})
        else:
            month_start = _month_start(now)
            trend_start = _shift_months(month_start, -11)
            trend_end = _shift_months(month_start, 1)

            rows = (await session.execute(
                text("SELECT SUBSTRING(created_at, 1, 7) AS m, COUNT(*) AS total FROM distributions WHERE status = 'delivered' AND created_at >= :ts AND created_at < :te GROUP BY SUBSTRING(created_at, 1, 7) ORDER BY m"),
                {"ts": trend_start.isoformat(), "te": trend_end.isoformat()}
            )).mappings().all()
            by_month = {str(r["m"]): int(r["total"]) for r in rows}

            for i in range(11, -1, -1):
                start = _shift_months(month_start, -i)
                data.append({
                    "month": start.strftime("%b"),
                    "distributions": by_month.get(start.strftime("%Y-%m"), 0),
                })

    return data


async def get_defect_chart_data(start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> list:
    data = []
    now = datetime.now().replace(tzinfo=None)

    async with async_session_factory() as session:
        if start_date or end_date:
            cond, prm = _build_date_filter("1=1", {}, start_date, end_date)
            reported = (await session.execute(
                text(f"SELECT COUNT(*) FROM defects WHERE {cond}"), prm
            )).scalar() or 0

            resolved_conds = ["status = 'resolved'"]
            resolved_params = {}
            if start_date:
                resolved_conds.append("resolved_at >= :rstart")
                resolved_params["rstart"] = start_date
            if end_date:
                resolved_conds.append("resolved_at <= :rend")
                resolved_params["rend"] = end_date
            resolved_where = " AND ".join(resolved_conds)
            resolved = (await session.execute(
                text(f"SELECT COUNT(*) FROM defects WHERE {resolved_where}"), resolved_params
            )).scalar() or 0

            data.append({"month": "Filtered", "reported": reported, "resolved": resolved})
        else:
            month_start = _month_start(now)
            trend_start = _shift_months(month_start, -11)
            trend_end = _shift_months(month_start, 1)

            rows = (await session.execute(
                text("SELECT SUBSTRING(created_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE created_at >= :ts AND created_at < :te GROUP BY SUBSTRING(created_at, 1, 7) ORDER BY m"),
                {"ts": trend_start.isoformat(), "te": trend_end.isoformat()}
            )).mappings().all()
            reported_by_month = {str(r["m"]): int(r["total"]) for r in rows}

            rows = (await session.execute(
                text("SELECT SUBSTRING(resolved_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE status = 'resolved' AND resolved_at >= :ts AND resolved_at < :te GROUP BY SUBSTRING(resolved_at, 1, 7) ORDER BY m"),
                {"ts": trend_start.isoformat(), "te": trend_end.isoformat()}
            )).mappings().all()
            resolved_by_month = {str(r["m"]): int(r["total"]) for r in rows}

            for i in range(11, -1, -1):
                start = _shift_months(month_start, -i)
                month_key = start.strftime("%Y-%m")
                data.append({
                    "month": start.strftime("%b"),
                    "reported": reported_by_month.get(month_key, 0),
                    "resolved": resolved_by_month.get(month_key, 0),
                })

    return data
