from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
import random
import string


def generate_id(prefix: str, length: int = 4) -> str:
    """Generate a unique ID with prefix (e.g., ONU-2024-0001)"""
    year = datetime.now().year
    random_num = ''.join(random.choices(string.digits, k=length))
    return f"{prefix}-{year}-{random_num}"


def generate_device_id(device_type: str) -> str:
    """Generate device ID based on type"""
    prefix_map = {
        "ONU": "ONU",
        "ONT": "ONT",
        "Router": "RTR",
        "Switch": "SWT",
        "Modem": "MDM",
        "Access Point": "AP",
        "Other": "DEV"
    }
    prefix = prefix_map.get(device_type, "DEV")
    return generate_id(prefix)


def generate_distribution_id() -> str:
    """Generate distribution ID"""
    return generate_id("DIST")


def generate_defect_id() -> str:
    """Generate defect report ID"""
    return generate_id("DEF")


def generate_return_id() -> str:
    """Generate return request ID"""
    return generate_id("RET")


def generate_operator_id() -> str:
    """Generate operator ID"""
    return generate_id("OP")


def serialize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Convert MongoDB document to serializable format"""
    if doc is None:
        return None
    
    doc = dict(doc)
    
    # Convert ObjectId to string
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        doc["_id"] = str(doc["_id"])
    
    # Convert other ObjectId fields
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
        elif isinstance(value, list):
            doc[key] = [str(v) if isinstance(v, ObjectId) else v for v in value]
    
    return doc


def serialize_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert list of MongoDB documents to serializable format"""
    return [serialize_doc(doc) for doc in docs if doc is not None]


def get_pagination(page: int, page_size: int, total: int) -> Dict[str, int]:
    """Calculate pagination info"""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages
    }


def validate_object_id(id_str: str) -> bool:
    """Check if string is valid ObjectId"""
    try:
        ObjectId(id_str)
        return True
    except:
        return False


def to_object_id(id_str: str) -> Optional[ObjectId]:
    """Convert string to ObjectId safely"""
    try:
        return ObjectId(id_str)
    except:
        return None
