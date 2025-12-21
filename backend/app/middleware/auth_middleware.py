from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List

from app.services.auth_service import get_current_user_from_token
from app.utils.permissions import check_permission

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    
    user = await get_current_user_from_token(token)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if user.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
):
    """Get current user if token is provided, else return None"""
    if credentials is None:
        return None
    
    token = credentials.credentials
    return await get_current_user_from_token(token)


class RoleChecker:
    """Dependency class to check user roles"""
    
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, user: dict = Depends(get_current_user)):
        if user.get("role") not in self.allowed_roles:
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
require_admin = RoleChecker(["admin"])
require_admin_or_manager = RoleChecker(["admin", "manager"])
require_management = RoleChecker(["admin", "manager", "distributor"])
require_any_role = RoleChecker(["admin", "manager", "distributor", "sub_distributor", "operator"])
