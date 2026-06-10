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


def generate_operator_id() -> str:
    """Generate operator ID"""
    return generate_id("OP")


def generate_inventory_item_id() -> str:
    """Generate external inventory item ID"""
    return generate_id("INV")


def generate_purchase_order_id() -> str:
    """Generate external inventory purchase order ID"""
    return generate_id("EPO")


def generate_inventory_receipt_id() -> str:
    """Generate external inventory receipt ID"""
    return generate_id("ERC")


def generate_inventory_movement_id() -> str:
    """Generate external inventory stock movement ID"""
    return generate_id("EIM")


def get_pagination(page: int, page_size: int, total: int) -> Dict[str, int]:
    """Calculate pagination info"""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages
    }
