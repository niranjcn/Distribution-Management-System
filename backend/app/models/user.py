import re
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    MD_DIRECTOR = "md_director"
    MANAGER = "manager"
    PDIC_STAFF = "pdic_staff"
    SUB_DISTRIBUTION_MANAGER = "sub_distribution_manager"
    SUB_DISTRIBUTOR = "sub_distributor"
    CLUSTER = "cluster"
    OPERATOR = "operator"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=100)
    role: UserRole
    digital_id: Optional[str] = Field(default=None, max_length=128)
    broadband_id: Optional[str] = Field(default=None, max_length=128)
    cluster_id: Optional[str] = Field(default=None, max_length=128)
    operator_id: Optional[str] = Field(default=None, max_length=128)
    phone: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    parent_id: Optional[str] = None
    theme: Optional[str] = "light"
    compact_mode: Optional[bool] = False
    email_notifications: Optional[bool] = True
    push_notifications: Optional[bool] = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    permissions: Optional[Dict[str, bool]] = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", value):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
            raise ValueError("Password must contain at least one special character")
        return value


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    digital_id: Optional[str] = Field(default=None, max_length=128)
    broadband_id: Optional[str] = Field(default=None, max_length=128)
    cluster_id: Optional[str] = Field(default=None, max_length=128)
    operator_id: Optional[str] = Field(default=None, max_length=128)
    phone: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    status: Optional[UserStatus] = None
    theme: Optional[str] = None
    compact_mode: Optional[bool] = None
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    permissions: Optional[Dict[str, bool]] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None
    cluster_id: Optional[str] = None
    operator_id: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    parent_id: Optional[str] = None
    status: UserStatus
    is_verified: bool
    permissions: Optional[Dict[str, bool]] = None
    created_at: str
    updated_at: str
    last_login: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", value):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
            raise ValueError("Password must contain at least one special character")
        return value


class ForcedCredentialUpdateRequest(BaseModel):
    current_password: str
    new_email: EmailStr
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", value):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
            raise ValueError("Password must contain at least one special character")
        return value


class UserPermissionUpdate(BaseModel):
    permissions: Dict[str, bool]
