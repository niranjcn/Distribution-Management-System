import re
import sys

with open("backend/app/services/report_service.py", "r") as f:
    content = f.read()

# 1. Add _build_date_filter function
filter_func = """
def _build_date_filter(base_condition: str, base_params: tuple, start_date: Optional[str], end_date: Optional[str]) -> tuple:
    conds = [base_condition]
    params = list(base_params)
    if start_date:
        conds.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conds.append("created_at <= ?")
        params.append(end_date)
    return " AND ".join(conds), tuple(params)
"""

if "_build_date_filter" not in content:
    content = content.replace(
        "async def get_inventory_report() -> Dict[str, Any]:",
        filter_func + "\nasync def get_inventory_report(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:"
    )

# Replace get_inventory_report
content = re.sub(
    r"async def get_inventory_report\(\) -> Dict\[str, Any\]:",
    r"async def get_inventory_report(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:",
    content
)

content = re.sub(
    r"total = await _count\(db, \"devices\"\)",
    r"cond, prm = _build_date_filter(\"1=1\", (), start_date, end_date)\n        total = await _count(db, \"devices\", cond, prm)",
    content
)

content = re.sub(
    r"by_status\[status\] = await _count\(db, \"devices\", \"status = \?\", \(status,\)\)",
    r"c, p = _build_date_filter(\"status = ?\", (status,), start_date, end_date)\n            by_status[status] = await _count(db, \"devices\", c, p)",
    content
)

content = re.sub(
    r"by_type\[dtype\] = await _count\(db, \"devices\", \"device_type = \?\", \(dtype,\)\)",
    r"c, p = _build_date_filter(\"device_type = ?\", (dtype,), start_date, end_date)\n            by_type[dtype] = await _count(db, \"devices\", c, p)",
    content
)

content = re.sub(
    r"by_location\[htype\] = await _count\(db, \"devices\", \"current_holder_type = \?\", \(htype,\)\)",
    r"c, p = _build_date_filter(\"current_holder_type = ?\", (htype,), start_date, end_date)\n            by_location[htype] = await _count(db, \"devices\", c, p)",
    content
)

# get_distribution_summary
content = re.sub(
    r"async def get_distribution_summary\(\) -> Dict\[str, Any\]:",
    r"async def get_distribution_summary(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:",
    content
)

content = re.sub(
    r"total = await _count\(db, \"distributions\"\)",
    r"cond, prm = _build_date_filter(\"1=1\", (), start_date, end_date)\n        total = await _count(db, \"distributions\", cond, prm)",
    content
)

content = re.sub(
    r"by_status\[status\] = await _count\(db, \"distributions\", \"status = \?\", \(status,\)\)",
    r"c, p = _build_date_filter(\"status = ?\", (status,), start_date, end_date)\n            by_status[status] = await _count(db, \"distributions\", c, p)",
    content
)

content = re.sub(
    r"count = await _count\(db, \"distributions\", \"created_at >= \? AND created_at < \?\",\n                                 \(month_start.isoformat\(\), month_end.isoformat\(\)\)\)",
    r"c, p = _build_date_filter(\"created_at >= ? AND created_at < ?\", (month_start.isoformat(), month_end.isoformat()), start_date, end_date)\n            count = await _count(db, \"distributions\", c, p)",
    content
)

content = re.sub(
    r"cursor = await db\.execute\(\n            \"\"\"SELECT to_user_name, SUM\(device_count\) as total\n            FROM distributions WHERE status = 'delivered'\n            GROUP BY to_user_name ORDER BY total DESC LIMIT 5\"\"\"\n        \)",
    r"c, p = _build_date_filter(\"status = 'delivered'\", (), start_date, end_date)\n        cursor = await db.execute(\n            f\"\"\"SELECT to_user_name, SUM(device_count) as total\n            FROM distributions WHERE {c}\n            GROUP BY to_user_name ORDER BY total DESC LIMIT 5\"\"\", p\n        )",
    content
)

# get_defect_summary
content = re.sub(
    r"async def get_defect_summary\(\) -> Dict\[str, Any\]:",
    r"async def get_defect_summary(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:",
    content
)

content = re.sub(
    r"total = await _count\(db, \"defects\"\)",
    r"cond, prm = _build_date_filter(\"1=1\", (), start_date, end_date)\n        total = await _count(db, \"defects\", cond, prm)",
    content
)

content = re.sub(
    r"by_status\[status\] = await _count\(db, \"defects\", \"status = \?\", \(status,\)\)",
    r"c, p = _build_date_filter(\"status = ?\", (status,), start_date, end_date)\n            by_status[status] = await _count(db, \"defects\", c, p)",
    content
)

content = re.sub(
    r"by_severity\[severity\] = await _count\(db, \"defects\", \"severity = \?\", \(severity,\)\)",
    r"c, p = _build_date_filter(\"severity = ?\", (severity,), start_date, end_date)\n            by_severity[severity] = await _count(db, \"defects\", c, p)",
    content
)

content = re.sub(
    r"by_type\[defect_type\] = await _count\(db, \"defects\", \"defect_type = \?\", \(defect_type,\)\)",
    r"c, p = _build_date_filter(\"defect_type = ?\", (defect_type,), start_date, end_date)\n            by_type[defect_type] = await _count(db, \"defects\", c, p)",
    content
)

content = re.sub(
    r"count = await _count\(db, \"defects\", \"created_at >= \? AND created_at < \?\",\n                                 \(month_start.isoformat\(\), month_end.isoformat\(\)\)\)",
    r"c, p = _build_date_filter(\"created_at >= ? AND created_at < ?\", (month_start.isoformat(), month_end.isoformat()), start_date, end_date)\n            count = await _count(db, \"defects\", c, p)",
    content
)


# get_return_summary
content = re.sub(
    r"async def get_return_summary\(\) -> Dict\[str, Any\]:",
    r"async def get_return_summary(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:",
    content
)

content = re.sub(
    r"total = await _count\(db, \"returns\"\)",
    r"cond, prm = _build_date_filter(\"1=1\", (), start_date, end_date)\n        total = await _count(db, \"returns\", cond, prm)",
    content
)

content = re.sub(
    r"by_status\[status\] = await _count\(db, \"returns\", \"status = \?\", \(status,\)\)",
    r"c, p = _build_date_filter(\"status = ?\", (status,), start_date, end_date)\n            by_status[status] = await _count(db, \"returns\", c, p)",
    content
)

content = re.sub(
    r"by_reason\[reason\] = await _count\(db, \"returns\", \"reason = \?\", \(reason,\)\)",
    r"c, p = _build_date_filter(\"reason = ?\", (reason,), start_date, end_date)\n            by_reason[reason] = await _count(db, \"returns\", c, p)",
    content
)

content = re.sub(
    r"count = await _count\(db, \"returns\", \"created_at >= \? AND created_at < \?\",\n                                 \(month_start.isoformat\(\), month_end.isoformat\(\)\)\)",
    r"c, p = _build_date_filter(\"created_at >= ? AND created_at < ?\", (month_start.isoformat(), month_end.isoformat()), start_date, end_date)\n            count = await _count(db, \"returns\", c, p)",
    content
)

with open("backend/app/services/report_service.py", "w") as f:
    f.write(content)
