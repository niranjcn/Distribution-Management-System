from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.services import device_service, distribution_service, defect_service, return_service, user_service
from app.utils.helpers import serialize_docs


async def get_inventory_report() -> Dict[str, Any]:
    """Generate device inventory report"""
    db = get_database()
    
    # Total devices
    total = await db.devices.count_documents({})
    
    # By status
    by_status = {}
    for status in ["available", "distributed", "in_use", "defective", "returned", "maintenance"]:
        count = await db.devices.count_documents({"status": status})
        by_status[status] = count
    
    # By type
    by_type = {}
    device_types = await db.devices.distinct("device_type")
    for dtype in device_types:
        count = await db.devices.count_documents({"device_type": dtype})
        by_type[dtype] = count
    
    # By holder type
    by_location = {}
    holder_types = await db.devices.distinct("current_holder_type")
    for htype in holder_types:
        if htype:
            count = await db.devices.count_documents({"current_holder_type": htype})
            by_location[htype] = count
    
    return {
        "total_devices": total,
        "by_status": by_status,
        "by_type": by_type,
        "by_location": by_location,
        "generated_at": datetime.utcnow().isoformat()
    }


async def get_distribution_summary() -> Dict[str, Any]:
    """Generate distribution summary report"""
    db = get_database()
    
    # Total distributions
    total = await db.distributions.count_documents({})
    
    # By status
    by_status = {}
    for status in ["pending", "approved", "in_transit", "delivered", "rejected", "cancelled"]:
        count = await db.distributions.count_documents({"status": status})
        by_status[status] = count
    
    # By month (last 6 months)
    by_month = []
    now = datetime.utcnow()
    for i in range(5, -1, -1):
        month_start = datetime(now.year, now.month, 1) - timedelta(days=i*30)
        month_end = month_start + timedelta(days=30)
        count = await db.distributions.count_documents({
            "created_at": {"$gte": month_start, "$lt": month_end}
        })
        by_month.append({
            "month": month_start.strftime("%B %Y"),
            "count": count
        })
    
    # Top distributors
    pipeline = [
        {"$match": {"status": "delivered"}},
        {"$group": {"_id": "$to_user_name", "count": {"$sum": "$device_count"}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    top_distributors = await db.distributions.aggregate(pipeline).to_list(length=5)
    
    return {
        "total": total,
        "by_status": by_status,
        "by_month": by_month,
        "top_distributors": [{"name": d["_id"], "devices": d["count"]} for d in top_distributors],
        "generated_at": datetime.utcnow().isoformat()
    }


async def get_defect_summary() -> Dict[str, Any]:
    """Generate defect summary report"""
    db = get_database()
    
    # Total defects
    total = await db.defects.count_documents({})
    
    # By status
    by_status = {}
    for status in ["reported", "under_review", "approved", "rejected", "resolved"]:
        count = await db.defects.count_documents({"status": status})
        by_status[status] = count
    
    # By severity
    by_severity = {}
    for severity in ["critical", "high", "medium", "low"]:
        count = await db.defects.count_documents({"severity": severity})
        by_severity[severity] = count
    
    # By type
    by_type = {}
    for defect_type in ["hardware", "software", "physical_damage", "performance", "connectivity", "other"]:
        count = await db.defects.count_documents({"defect_type": defect_type})
        by_type[defect_type] = count
    
    # By month (last 6 months)
    by_month = []
    now = datetime.utcnow()
    for i in range(5, -1, -1):
        month_start = datetime(now.year, now.month, 1) - timedelta(days=i*30)
        month_end = month_start + timedelta(days=30)
        count = await db.defects.count_documents({
            "created_at": {"$gte": month_start, "$lt": month_end}
        })
        by_month.append({
            "month": month_start.strftime("%B %Y"),
            "count": count
        })
    
    return {
        "total": total,
        "by_status": by_status,
        "by_severity": by_severity,
        "by_type": by_type,
        "by_month": by_month,
        "generated_at": datetime.utcnow().isoformat()
    }


async def get_return_summary() -> Dict[str, Any]:
    """Generate return summary report"""
    db = get_database()
    
    # Total returns
    total = await db.returns.count_documents({})
    
    # By status
    by_status = {}
    for status in ["pending", "approved", "in_transit", "received", "rejected", "cancelled"]:
        count = await db.returns.count_documents({"status": status})
        by_status[status] = count
    
    # By reason
    by_reason = {}
    for reason in ["defective", "unused", "end_of_contract", "upgrade", "other"]:
        count = await db.returns.count_documents({"reason": reason})
        by_reason[reason] = count
    
    # By month (last 6 months)
    by_month = []
    now = datetime.utcnow()
    for i in range(5, -1, -1):
        month_start = datetime(now.year, now.month, 1) - timedelta(days=i*30)
        month_end = month_start + timedelta(days=30)
        count = await db.returns.count_documents({
            "created_at": {"$gte": month_start, "$lt": month_end}
        })
        by_month.append({
            "month": month_start.strftime("%B %Y"),
            "count": count
        })
    
    return {
        "total": total,
        "by_status": by_status,
        "by_reason": by_reason,
        "by_month": by_month,
        "generated_at": datetime.utcnow().isoformat()
    }


async def get_user_activity_report() -> Dict[str, Any]:
    """Generate user activity report"""
    db = get_database()
    
    # Users by role
    by_role = {}
    for role in ["admin", "manager", "distributor", "sub_distributor", "operator"]:
        count = await db.users.count_documents({"role": role})
        by_role[role] = count
    
    # Active users (logged in within last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_users = await db.users.count_documents({
        "last_login": {"$gte": thirty_days_ago}
    })
    
    # Total users
    total_users = await db.users.count_documents({})
    
    # Recent activities (device history)
    cursor = db.device_history.find({}).sort("timestamp", -1).limit(50)
    recent_activities = await cursor.to_list(length=50)
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "by_role": by_role,
        "recent_activities": serialize_docs(recent_activities),
        "generated_at": datetime.utcnow().isoformat()
    }


async def get_device_utilization_report() -> Dict[str, Any]:
    """Generate device utilization report"""
    db = get_database()
    
    total_devices = await db.devices.count_documents({})
    in_use = await db.devices.count_documents({"status": {"$in": ["distributed", "in_use"]}})
    available = await db.devices.count_documents({"status": "available"})
    defective = await db.devices.count_documents({"status": "defective"})
    
    utilization_rate = (in_use / total_devices * 100) if total_devices > 0 else 0
    
    # Average time to distribute (from creation to first distribution)
    # This would require more complex aggregation
    
    return {
        "total_devices": total_devices,
        "in_use": in_use,
        "available": available,
        "defective": defective,
        "utilization_rate": round(utilization_rate, 2),
        "generated_at": datetime.utcnow().isoformat()
    }
