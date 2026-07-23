from datetime import datetime
from typing import Optional

from app.database import get_db

from .helpers import _build_date_filter, _month_start, _shift_months


async def get_distribution_chart_data(start_date: Optional[str] = None,
                                      end_date: Optional[str] = None) -> list:
    """Get distribution data for charts"""
    data = []
    now = datetime.now().replace(tzinfo=None)

    async with get_db() as db:
        if start_date or end_date:
            cond, prm = _build_date_filter("status = 'delivered'", (), start_date, end_date)
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM distributions WHERE {cond}", prm
            )
            total = (await cursor.fetchone())[0]
            data.append({
                "month": "Filtered",
                "distributions": total
            })
        else:
            month_start = _month_start(now)
            trend_start = _shift_months(month_start, -11)
            trend_end = _shift_months(month_start, 1)

            cursor = await db.execute(
                "SELECT SUBSTRING(created_at, 1, 7) AS m, COUNT(*) AS total FROM distributions WHERE status = 'delivered' AND created_at >= ? AND created_at < ? GROUP BY SUBSTRING(created_at, 1, 7) ORDER BY m",
                (trend_start.isoformat(), trend_end.isoformat())
            )
            by_month = {str(row["m"]): int(row["total"]) for row in await cursor.fetchall()}

            for i in range(11, -1, -1):
                start = _shift_months(month_start, -i)
                data.append({
                    "month": start.strftime("%b"),
                    "distributions": by_month.get(start.strftime("%Y-%m"), 0),
                })

    return data


async def get_defect_chart_data(start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> list:
    """Get defect data for charts"""
    data = []
    now = datetime.now().replace(tzinfo=None)

    async with get_db() as db:
        if start_date or end_date:
            cond, prm = _build_date_filter("1=1", (), start_date, end_date)
            cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {cond}", prm)
            reported = (await cursor.fetchone())[0]

            resolved_conds = ["status = 'resolved'"]
            resolved_params = []
            if start_date:
                resolved_conds.append("resolved_at >= ?")
                resolved_params.append(start_date)
            if end_date:
                resolved_conds.append("resolved_at <= ?")
                resolved_params.append(end_date)
            resolved_where = " AND ".join(resolved_conds)
            cursor = await db.execute(f"SELECT COUNT(*) FROM defects WHERE {resolved_where}", tuple(resolved_params))
            resolved = (await cursor.fetchone())[0]

            data.append({
                "month": "Filtered",
                "reported": reported,
                "resolved": resolved
            })
        else:
            month_start = _month_start(now)
            trend_start = _shift_months(month_start, -11)
            trend_end = _shift_months(month_start, 1)

            cursor = await db.execute(
                "SELECT SUBSTRING(created_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE created_at >= ? AND created_at < ? GROUP BY SUBSTRING(created_at, 1, 7) ORDER BY m",
                (trend_start.isoformat(), trend_end.isoformat())
            )
            reported_by_month = {str(row["m"]): int(row["total"]) for row in await cursor.fetchall()}

            cursor = await db.execute(
                "SELECT SUBSTRING(resolved_at, 1, 7) AS m, COUNT(*) AS total FROM defects WHERE status = 'resolved' AND resolved_at >= ? AND resolved_at < ? GROUP BY SUBSTRING(resolved_at, 1, 7) ORDER BY m",
                (trend_start.isoformat(), trend_end.isoformat())
            )
            resolved_by_month = {str(row["m"]): int(row["total"]) for row in await cursor.fetchall()}

            for i in range(11, -1, -1):
                start = _shift_months(month_start, -i)
                month_key = start.strftime("%Y-%m")
                data.append({
                    "month": start.strftime("%b"),
                    "reported": reported_by_month.get(month_key, 0),
                    "resolved": resolved_by_month.get(month_key, 0),
                })

    return data
