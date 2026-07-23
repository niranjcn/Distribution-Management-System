from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db

from .helpers import _build_date_filter


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
            for i in range(11, -1, -1):
                month_start = datetime(now.year, now.month, 1) - timedelta(days=i * 30)
                month_end = month_start + timedelta(days=30)

                cursor = await db.execute(
                    "SELECT COUNT(*) FROM distributions WHERE status = 'delivered' AND created_at >= ? AND created_at < ?",
                    (month_start.isoformat(), month_end.isoformat())
                )
                count = (await cursor.fetchone())[0]

                data.append({
                    "month": month_start.strftime("%b"),
                    "distributions": count
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
            for i in range(11, -1, -1):
                month_start = datetime(now.year, now.month, 1) - timedelta(days=i * 30)
                month_end = month_start + timedelta(days=30)

                cursor = await db.execute(
                    "SELECT COUNT(*) FROM defects WHERE created_at >= ? AND created_at < ?",
                    (month_start.isoformat(), month_end.isoformat())
                )
                reported = (await cursor.fetchone())[0]

                cursor = await db.execute(
                    "SELECT COUNT(*) FROM defects WHERE status = 'resolved' AND resolved_at >= ? AND resolved_at < ?",
                    (month_start.isoformat(), month_end.isoformat())
                )
                resolved = (await cursor.fetchone())[0]

                data.append({
                    "month": month_start.strftime("%b"),
                    "reported": reported,
                    "resolved": resolved
                })

    return data
