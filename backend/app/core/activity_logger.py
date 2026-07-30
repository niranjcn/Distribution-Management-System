from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, Iterable, Optional, Tuple

from app.database_sqlalchemy import async_session_factory
from sqlalchemy import text


MEANINGFUL_ACTIVITY_RULES = [
    ("POST", re.compile(r"^/api/auth/logout$"), "User logged out", "logout"),
    ("PUT", re.compile(r"^/api/auth/password$"), "Password updated", "password update"),
    ("POST", re.compile(r"^/api/reports/export$"), "Report exported", "report export"),
    ("GET", re.compile(r"^/api/reports/backup-documents/[^/]+$"), "Backup document downloaded", "backup document download"),
    ("PATCH", re.compile(r"^/api/defects/[^/]+/resolve$"), "Defect resolved", "defect resolution"),
    ("POST", re.compile(r"^/api/defects/[^/]+/forward-to-management$"), "Defect forwarded to management", "defect forwarding"),
    ("POST", re.compile(r"^/api/returns$"), "Return requested", "return request"),
    ("POST", re.compile(r"^/api/external-inventory/items/[^/]+/image$"), "External inventory item image uploaded", "item image upload"),
    ("POST", re.compile(r"^/api/external-inventory/adjustments$"), "External inventory adjusted", "stock adjustment"),
    ("POST", re.compile(r"^/api/distributions/[^/]+/receipt$"), "Distribution receipt confirmed", "distribution receipt confirmation"),
    ("PATCH", re.compile(r"^/api/users/[^/]+/credentials$"), "User credentials updated", "user credential update"),
    ("GET", re.compile(r"^/api/distributions/[^/]+/manifest$"), "Distribution manifest downloaded", "distribution manifest download"),
    ("GET", re.compile(r"^/api/distributions/[^/]+/export-mac-nuid$"), "MAC/NUID export downloaded", "MAC/NUID export download"),
]


def extract_actor_details(user: Optional[Dict[str, Any]]) -> Tuple[str, str, str]:
    """Safely normalize auth payload variants to actor id/name/role strings."""
    if not isinstance(user, dict):
        return "", "Unknown", ""

    actor_id = str(user.get("id") or user.get("_id") or user.get("user_id") or user.get("sub") or "")
    actor_name = str(user.get("name") or user.get("email") or "Unknown")
    actor_role = str(user.get("role") or "")
    return actor_id, actor_name, actor_role


def _stringify_change_value(value: Any, max_len: int = 80) -> str:
    if value is None:
        text = "null"
    elif isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (dict, list, tuple)):
        try:
            text = json.dumps(value, ensure_ascii=True, sort_keys=True)
        except Exception:
            text = str(value)
    else:
        text = str(value)

    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 3]}..."


def build_field_change_summary(
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
    fields: Optional[Iterable[str]] = None,
    *,
    exclude_fields: Optional[Iterable[str]] = None,
    max_fields: int = 5,
) -> str:
    """Build a concise old->new summary for changed fields."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return "no field changes captured"

    exclude = {str(item) for item in (exclude_fields or [])}
    candidate_fields = list(fields) if fields else sorted(set(before.keys()) | set(after.keys()))

    changed_fields = []
    for field in candidate_fields:
        key = str(field)
        if key in exclude:
            continue

        old_value = before.get(key)
        new_value = after.get(key)
        old_text = _stringify_change_value(old_value)
        new_text = _stringify_change_value(new_value)

        if old_text == new_text:
            continue

        changed_fields.append(f"{key}: {old_text} -> {new_text}")

    if not changed_fields:
        return "no field value changes"

    if len(changed_fields) > max_fields:
        remaining = len(changed_fields) - max_fields
        return f"{'; '.join(changed_fields[:max_fields])}; +{remaining} more"

    return "; ".join(changed_fields)


async def log_business_activity(
    user: Optional[Dict[str, Any]],
    description: str,
    path: str,
    method: str = "BUSINESS",
    status_code: int = 200,
    ip_address: Optional[str] = None,
) -> None:
    """Persist a structured business activity event for the admin activity stream."""
    actor_id, actor_name, actor_role = extract_actor_details(user)
    await log_api_activity(
        method=method,
        path=path,
        status_code=status_code,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        ip_address=ip_address,
        description=description,
    )


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
    created_at = datetime.now().replace(tzinfo=None)
    final_description = description or f"{method} {path} returned {status_code}"

    try:
        async with async_session_factory() as session:
            await session.execute(
                text("""INSERT INTO api_activity_logs (
                       actor_id, actor_name, actor_role, method, path,
                       status_code, description, ip_address, created_at
                   ) VALUES (:actor_id, :actor_name, :actor_role, :method, :path,
                             :status_code, :description, :ip_address, :created_at)"""),
                {
                    "actor_id": actor_id,
                    "actor_name": actor_name,
                    "actor_role": actor_role,
                    "method": method,
                    "path": path,
                    "status_code": int(status_code),
                    "description": final_description,
                    "ip_address": ip_address,
                    "created_at": created_at,
                },
            )
            await session.commit()
    except Exception:
        # Logging must never block API responses.
        return
