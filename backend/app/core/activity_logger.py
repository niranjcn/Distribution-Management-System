from datetime import datetime, timezone
import re
from typing import Optional

from app.database import get_db


MEANINGFUL_ACTIVITY_RULES = [
    ("POST", re.compile(r"^/api/auth/logout$"), "User logged out", "logout"),
    ("PUT", re.compile(r"^/api/auth/password$"), "Password updated", "password update"),
    ("POST", re.compile(r"^/api/reports/export$"), "Report exported", "report export"),
    ("GET", re.compile(r"^/api/reports/device-backup$"), "Device backup downloaded", "device backup download"),
    ("GET", re.compile(r"^/api/reports/returns-defects-backup$"), "Returns and defects backup downloaded", "returns/defects backup download"),
    ("POST", re.compile(r"^/api/reports/backup-documents$"), "Backup document uploaded", "backup document upload"),
    ("GET", re.compile(r"^/api/reports/backup-documents/[^/]+$"), "Backup document downloaded", "backup document download"),
    ("POST", re.compile(r"^/api/defects$"), "Defect reported", "defect reporting"),
    ("PATCH", re.compile(r"^/api/defects/[^/]+/status$"), "Defect status updated", "defect status update"),
    ("PATCH", re.compile(r"^/api/defects/[^/]+/resolve$"), "Defect resolved", "defect resolution"),
    ("POST", re.compile(r"^/api/defects/[^/]+/forward-to-management$"), "Defect forwarded to management", "defect forwarding"),
    ("POST", re.compile(r"^/api/returns$"), "Return requested", "return request"),
    ("PATCH", re.compile(r"^/api/returns/[^/]+/status$"), "Return status updated", "return status update"),
    ("POST", re.compile(r"^/api/external-inventory/items$"), "External inventory item created", "external inventory item creation"),
    ("POST", re.compile(r"^/api/external-inventory/items/bulk-upload$"), "External inventory imported", "external inventory import"),
    ("PUT", re.compile(r"^/api/external-inventory/items/[^/]+$"), "External inventory item updated", "external inventory item update"),
    ("POST", re.compile(r"^/api/external-inventory/items/[^/]+/image$"), "External inventory item image uploaded", "item image upload"),
    ("POST", re.compile(r"^/api/external-inventory/adjustments$"), "External inventory adjusted", "stock adjustment"),
    ("POST", re.compile(r"^/api/external-inventory/purchase-orders$"), "Purchase order created", "purchase order creation"),
    ("POST", re.compile(r"^/api/external-inventory/purchase-orders/[^/]+/receive$"), "Purchase order confirmed", "purchase order confirmation"),
    ("POST", re.compile(r"^/api/distributions$"), "Distribution created", "distribution creation"),
    ("POST", re.compile(r"^/api/distributions/bulk-upload$"), "Distribution created from bulk upload", "bulk distribution creation"),
    ("PATCH", re.compile(r"^/api/distributions/[^/]+/status$"), "Distribution status updated", "distribution status update"),
    ("POST", re.compile(r"^/api/distributions/[^/]+/receipt$"), "Distribution receipt confirmed", "distribution receipt confirmation"),
    ("POST", re.compile(r"^/api/users$"), "User account created", "user creation"),
    ("PUT", re.compile(r"^/api/users/[^/]+$"), "User account updated", "user update"),
    ("DELETE", re.compile(r"^/api/users/[^/]+$"), "User account deleted", "user deletion"),
    ("PATCH", re.compile(r"^/api/users/[^/]+/status$"), "User status updated", "user status update"),
    ("PATCH", re.compile(r"^/api/users/[^/]+/credentials$"), "User credentials updated", "user credential update"),
    ("GET", re.compile(r"^/api/distributions/[^/]+/manifest$"), "Distribution manifest downloaded", "distribution manifest download"),
    ("GET", re.compile(r"^/api/distributions/[^/]+/export-mac-nuid$"), "MAC/NUID export downloaded", "MAC/NUID export download"),
]


def build_meaningful_activity_description(method: str, path: str, status_code: int) -> Optional[str]:
    """Return a human-friendly activity description for important business actions only."""
    normalized_method = (method or "").upper().strip()
    normalized_path = (path or "").strip().rstrip("/") or "/"

    for rule_method, rule_pattern, success_description, action_label in MEANINGFUL_ACTIVITY_RULES:
        if normalized_method == rule_method and rule_pattern.fullmatch(normalized_path):
            if 200 <= int(status_code) < 300:
                return success_description
            if 400 <= int(status_code) < 500:
                return f"Attempted {action_label} (rejected: {status_code})"
            return f"Failed {action_label} (status: {status_code})"

    return None


async def log_api_activity(
    method: str,
    path: str,
    status_code: int,
    actor_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    actor_role: Optional[str] = None,
    ip_address: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """Persist API activity log without interrupting request flow."""
    created_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    final_description = description or f"{method} {path} returned {status_code}"

    try:
        async with get_db() as db:
            await db.execute(
                """INSERT INTO api_activity_logs (
                       actor_id, actor_name, actor_role, method, path,
                       status_code, description, ip_address, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    actor_id,
                    actor_name,
                    actor_role,
                    method,
                    path,
                    int(status_code),
                    final_description,
                    ip_address,
                    created_at,
                ),
            )
            await db.commit()
    except Exception:
        # Logging must never block API responses.
        return
