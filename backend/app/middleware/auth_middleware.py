from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List

from app.services.auth_service import get_current_user_from_token
from app.utils.permissions import check_permission
from app.utils.roles import normalize_role

security = HTTPBearer(auto_error=False)

FORCED_UPDATE_ALLOWLIST = {
    "/api/auth/me",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/complete-forced-update",
}


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Get current authenticated user from JWT token"""
    cached = getattr(request.state, "current_user", None)
    if cached is not None:
        return cached

    token = credentials.credentials if credentials else request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        user = await get_current_user_from_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user["role"] = normalize_role(user.get("role"))

    if user.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )

    requires_forced_update = bool(user.get("force_email_change")) or bool(user.get("force_password_change"))
    if requires_forced_update and request.url.path not in FORCED_UPDATE_ALLOWLIST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FORCED_CREDENTIAL_UPDATE_REQUIRED",
        )

    return user


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
):
    """Get current user if token is provided, else return None"""
    cached = getattr(request.state, "current_user", None)
    if cached is not None:
        return cached

    token = credentials.credentials if credentials else request.cookies.get("access_token")
    if token is None:
        return None

    try:
        return await get_current_user_from_token(token)
    except Exception:
        return None


class RoleChecker:
    """Dependency class to check user roles"""
    
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, user: dict = Depends(get_current_user)):
        if normalize_role(user.get("role")) not in {normalize_role(r) for r in self.allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return user


class PermissionChecker:
    """Dependency class to check specific permissions"""
    
    def __init__(self, permission: str):
        self.permission = permission
    
    async def __call__(self, user: dict = Depends(get_current_user)):
        if not check_permission(user.get("role"), self.permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.permission}"
            )
        return user


# Pre-defined role checkers
require_admin = RoleChecker(["super_admin"])
require_admin_or_md = RoleChecker(["super_admin", "md_director"])
require_admin_or_manager = RoleChecker(["super_admin", "manager"])
require_admin_or_manager_or_md = RoleChecker(["super_admin", "manager", "md_director"])
require_admin_or_manager_or_md_or_staff = RoleChecker(["super_admin", "manager", "md_director", "pdic_staff"])
require_management = RoleChecker(["super_admin", "manager", "pdic_staff"])
require_any_role = RoleChecker([
    "super_admin",
    "md_director",
    "manager",
    "pdic_staff",
    "sub_distribution_manager",
    "sub_distributor",
    "cluster",
    "operator",
    "sub_distribution_employee",
])
