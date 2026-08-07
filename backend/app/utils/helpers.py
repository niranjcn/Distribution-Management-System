from datetime import datetime
from typing import Any, Dict, List, Optional
import random
import string


def generate_id(prefix: str, length: int = 4) -> str:
    """Generate a unique ID with prefix (e.g., ONU-2026-0001)"""
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


def generate_external_distribution_id() -> str:
    """Generate external inventory distribution ID"""
    return generate_id("EXT")


def get_pagination(page: int, page_size: int, total: int) -> Dict[str, int]:
    """Calculate pagination info"""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
    }


def is_set_top_box_device(device: Optional[dict]) -> bool:
    """Return True if the device is a set-top box (identified by NUID rather than serial)."""
    device_type = str((device or {}).get("device_type") or "").strip().lower().replace("-", " ")
    return device_type in {"set top box", "setup box", "sb", "stb"}
