from typing import List

from app.utils.roles import (
    ROLE_HIERARCHY,
    SUPER_ADMIN,
    MD_DIRECTOR,
    MANAGER,
    PDIC_STAFF,
    SUB_DISTRIBUTION_MANAGER,
    SUB_DISTRIBUTOR,
    CLUSTER,
    OPERATOR,
    SUB_DISTRIBUTION_EMPLOYEE,
    normalize_role,
)

PERMISSIONS = {
    "users:read": [SUPER_ADMIN, MD_DIRECTOR, MANAGER, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER],
    "users:create": [SUPER_ADMIN, MANAGER, SUB_DISTRIBUTOR, CLUSTER],
    "users:update": [SUPER_ADMIN, MANAGER],
    "users:delete": [SUPER_ADMIN],
    "users:set_permissions": [SUPER_ADMIN],

    "devices:read": [SUPER_ADMIN, MD_DIRECTOR, MANAGER, PDIC_STAFF, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER, OPERATOR],
    "devices:create": [SUPER_ADMIN, MANAGER, PDIC_STAFF],
    "devices:update": [SUPER_ADMIN, MANAGER],
    "devices:delete": [SUPER_ADMIN],

    "distributions:read": [SUPER_ADMIN, MD_DIRECTOR, MANAGER, PDIC_STAFF, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER, OPERATOR, SUB_DISTRIBUTION_EMPLOYEE],
    "distributions:create": [SUPER_ADMIN, MANAGER, PDIC_STAFF, SUB_DISTRIBUTOR, CLUSTER, OPERATOR],
    "distributions:update": [SUPER_ADMIN, MANAGER],
    "distributions:delete": [SUPER_ADMIN],
    "distributions:approve": [SUPER_ADMIN, MANAGER, PDIC_STAFF],

    "defects:read": [SUPER_ADMIN, MD_DIRECTOR, MANAGER, PDIC_STAFF, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER, OPERATOR, SUB_DISTRIBUTION_EMPLOYEE],
    "defects:create": [SUPER_ADMIN, MANAGER, PDIC_STAFF, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER, OPERATOR],
    "defects:update": [SUPER_ADMIN, MANAGER, SUB_DISTRIBUTION_MANAGER],
    "defects:delete": [SUPER_ADMIN],
    "defects:resolve": [SUPER_ADMIN, MANAGER, PDIC_STAFF],

    "returns:read": [SUPER_ADMIN, MD_DIRECTOR, MANAGER, PDIC_STAFF, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER, OPERATOR],
    "returns:create": [SUPER_ADMIN, MANAGER, PDIC_STAFF, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER, OPERATOR],
    "returns:update": [SUPER_ADMIN, MANAGER, SUB_DISTRIBUTION_MANAGER],
    "returns:delete": [SUPER_ADMIN],
    "returns:approve": [SUPER_ADMIN, MANAGER, PDIC_STAFF],

    "reports:read": [SUPER_ADMIN, MD_DIRECTOR, MANAGER, PDIC_STAFF],
    "reports:export": [SUPER_ADMIN, MD_DIRECTOR, MANAGER, PDIC_STAFF],

    "dashboard:read": [SUPER_ADMIN, MD_DIRECTOR, MANAGER, PDIC_STAFF, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER, OPERATOR, SUB_DISTRIBUTION_EMPLOYEE],
    "notifications:read": [SUPER_ADMIN, MD_DIRECTOR, MANAGER, PDIC_STAFF, SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR, CLUSTER, OPERATOR, SUB_DISTRIBUTION_EMPLOYEE],

    "approvals:submit": [SUB_DISTRIBUTION_EMPLOYEE],
    "approvals:review": [SUB_DISTRIBUTION_MANAGER, SUB_DISTRIBUTOR],
}


def check_permission(user_role: str, permission: str, user_permissions: dict = None) -> bool:
    role = normalize_role(user_role)

    if role == SUPER_ADMIN:
        return True

    if user_permissions and permission in user_permissions:
        return bool(user_permissions[permission])

    return role in PERMISSIONS.get(permission, [])


def get_user_permissions(user_role: str) -> List[str]:
    role = normalize_role(user_role)
    return [perm for perm, roles in PERMISSIONS.items() if role in roles]


def is_higher_role(role1: str, role2: str) -> bool:
    return ROLE_HIERARCHY.get(normalize_role(role1), 0) > ROLE_HIERARCHY.get(normalize_role(role2), 0)


def can_manage_user(manager_role: str, target_role: str) -> bool:
    manager = normalize_role(manager_role)
    target = normalize_role(target_role)

    if manager in {MD_DIRECTOR, PDIC_STAFF}:
        return False
    if manager == MANAGER and target in {SUPER_ADMIN, MD_DIRECTOR}:
        return False
    if manager == SUB_DISTRIBUTION_MANAGER and target in {SUPER_ADMIN, MD_DIRECTOR, MANAGER, PDIC_STAFF}:
        return False
    return is_higher_role(manager, target)


def get_viewable_roles(user_role: str) -> List[str]:
    role = normalize_role(user_role)
    user_level = ROLE_HIERARCHY.get(role, 0)
    return [r for r, level in ROLE_HIERARCHY.items() if level <= user_level]
