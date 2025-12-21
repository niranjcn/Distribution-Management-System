from typing import List, Optional
from app.models.user import UserRole

# Define role hierarchy and permissions
ROLE_HIERARCHY = {
    UserRole.ADMIN: 5,
    UserRole.MANAGER: 4,
    UserRole.DISTRIBUTOR: 3,
    UserRole.SUB_DISTRIBUTOR: 2,
    UserRole.OPERATOR: 1
}

# Permission definitions
PERMISSIONS = {
    # User management
    "users:read": [UserRole.ADMIN, UserRole.MANAGER],
    "users:create": [UserRole.ADMIN, UserRole.MANAGER],
    "users:update": [UserRole.ADMIN, UserRole.MANAGER],
    "users:delete": [UserRole.ADMIN],
    
    # Device management
    "devices:read": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR, UserRole.SUB_DISTRIBUTOR, UserRole.OPERATOR],
    "devices:create": [UserRole.ADMIN, UserRole.MANAGER],
    "devices:update": [UserRole.ADMIN, UserRole.MANAGER],
    "devices:delete": [UserRole.ADMIN],
    
    # Distribution management
    "distributions:read": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR, UserRole.SUB_DISTRIBUTOR, UserRole.OPERATOR],
    "distributions:create": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR, UserRole.SUB_DISTRIBUTOR],
    "distributions:update": [UserRole.ADMIN, UserRole.MANAGER],
    "distributions:delete": [UserRole.ADMIN, UserRole.MANAGER],
    "distributions:approve": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR],
    
    # Defect management
    "defects:read": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR, UserRole.SUB_DISTRIBUTOR, UserRole.OPERATOR],
    "defects:create": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR, UserRole.SUB_DISTRIBUTOR, UserRole.OPERATOR],
    "defects:update": [UserRole.ADMIN, UserRole.MANAGER],
    "defects:delete": [UserRole.ADMIN],
    "defects:resolve": [UserRole.ADMIN, UserRole.MANAGER],
    
    # Return management
    "returns:read": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR, UserRole.SUB_DISTRIBUTOR, UserRole.OPERATOR],
    "returns:create": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR, UserRole.SUB_DISTRIBUTOR, UserRole.OPERATOR],
    "returns:update": [UserRole.ADMIN, UserRole.MANAGER],
    "returns:delete": [UserRole.ADMIN, UserRole.MANAGER],
    "returns:approve": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR],
    
    # Approval management
    "approvals:read": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR],
    "approvals:approve": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR],
    "approvals:reject": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR],
    
    # Operator management
    "operators:read": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR, UserRole.SUB_DISTRIBUTOR],
    "operators:create": [UserRole.ADMIN, UserRole.MANAGER, UserRole.SUB_DISTRIBUTOR],
    "operators:update": [UserRole.ADMIN, UserRole.MANAGER, UserRole.SUB_DISTRIBUTOR],
    "operators:delete": [UserRole.ADMIN, UserRole.MANAGER, UserRole.SUB_DISTRIBUTOR],
    
    # Reports
    "reports:read": [UserRole.ADMIN, UserRole.MANAGER],
    "reports:export": [UserRole.ADMIN, UserRole.MANAGER],
    
    # Dashboard
    "dashboard:read": [UserRole.ADMIN, UserRole.MANAGER, UserRole.DISTRIBUTOR, UserRole.SUB_DISTRIBUTOR, UserRole.OPERATOR],
}


def check_permission(user_role: str, permission: str) -> bool:
    """Check if a user role has a specific permission"""
    try:
        role = UserRole(user_role)
        allowed_roles = PERMISSIONS.get(permission, [])
        return role in allowed_roles
    except ValueError:
        return False


def get_user_permissions(user_role: str) -> List[str]:
    """Get all permissions for a user role"""
    permissions = []
    try:
        role = UserRole(user_role)
        for perm, roles in PERMISSIONS.items():
            if role in roles:
                permissions.append(perm)
    except ValueError:
        pass
    return permissions


def is_higher_role(role1: str, role2: str) -> bool:
    """Check if role1 is higher than role2 in hierarchy"""
    try:
        r1 = UserRole(role1)
        r2 = UserRole(role2)
        return ROLE_HIERARCHY.get(r1, 0) > ROLE_HIERARCHY.get(r2, 0)
    except ValueError:
        return False


def can_manage_user(manager_role: str, target_role: str) -> bool:
    """Check if a manager can manage a target user based on role hierarchy"""
    return is_higher_role(manager_role, target_role)


def get_viewable_roles(user_role: str) -> List[UserRole]:
    """Get roles that a user can view based on their role"""
    try:
        role = UserRole(user_role)
        user_level = ROLE_HIERARCHY.get(role, 0)
        return [r for r, level in ROLE_HIERARCHY.items() if level <= user_level]
    except ValueError:
        return []
