from __future__ import annotations

from typing import Iterable

SUPER_ADMIN = "super_admin"
MD_DIRECTOR = "md_director"
MANAGER = "manager"
PDIC_STAFF = "pdic_staff"
SUB_DISTRIBUTION_MANAGER = "sub_distribution_manager"
SUB_DISTRIBUTOR = "sub_distributor"
CLUSTER = "cluster"
OPERATOR = "operator"

ROLE_ORDER = [
    SUPER_ADMIN,
    MD_DIRECTOR,
    MANAGER,
    PDIC_STAFF,
    SUB_DISTRIBUTION_MANAGER,
    SUB_DISTRIBUTOR,
    CLUSTER,
    OPERATOR,
]

ROLE_HIERARCHY = {role: (len(ROLE_ORDER) - index) for index, role in enumerate(ROLE_ORDER)}

LEGACY_ROLE_MAP = {
    "super_admin": SUPER_ADMIN,
    "pdic_staff": PDIC_STAFF,
    "staff": PDIC_STAFF,
}


def normalize_role(role: str | None) -> str:
    if not role:
        return ""
    role_value = str(role).strip().lower()
    return LEGACY_ROLE_MAP.get(role_value, role_value)


def is_valid_role(role: str | None) -> bool:
    return normalize_role(role) in ROLE_HIERARCHY


def role_level(role: str | None) -> int:
    return ROLE_HIERARCHY.get(normalize_role(role), 0)


def is_higher_role(actor_role: str | None, target_role: str | None) -> bool:
    return role_level(actor_role) > role_level(target_role)


def is_same_role(actor_role: str | None, target_role: str | None) -> bool:
    return normalize_role(actor_role) == normalize_role(target_role)


def has_any_role(role: str | None, allowed_roles: Iterable[str]) -> bool:
    normalized = normalize_role(role)
    return normalized in {normalize_role(r) for r in allowed_roles}


def can_mutate_super_admin(actor_id: str | None, actor_role: str | None, target_id: str | None, target_role: str | None) -> bool:
    actor_normalized = normalize_role(actor_role)
    target_normalized = normalize_role(target_role)
    if target_normalized != SUPER_ADMIN:
        return True
    if actor_normalized != SUPER_ADMIN:
        return False
    return str(actor_id or "") == str(target_id or "")


def can_manage_user(actor_role: str | None, target_role: str | None) -> bool:
    actor_normalized = normalize_role(actor_role)
    target_normalized = normalize_role(target_role)

    if not actor_normalized or not target_normalized:
        return False

    if actor_normalized == MD_DIRECTOR:
        return False
    if actor_normalized in {MANAGER, SUB_DISTRIBUTION_MANAGER}:
        if target_normalized in {SUPER_ADMIN, MD_DIRECTOR}:
            return False
        return is_higher_role(actor_normalized, target_normalized)
    return is_higher_role(actor_normalized, target_normalized)

