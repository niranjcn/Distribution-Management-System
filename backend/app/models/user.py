import re
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    MD_DIRECTOR = "md_director"
    MANAGER = "manager"
    PDIC_STAFF = "pdic_staff"
    SUB_DISTRIBUTION_MANAGER = "sub_distribution_manager"
    SUB_DISTRIBUTOR = "sub_distributor"
    CLUSTER = "cluster"
    OPERATOR = "operator"


class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=100)
    role: UserRole
    status: UserStatus = UserStatus.ACTIVE
    phone: str = Field(..., min_length=10)
    designation: Optional[str] = None
    location: Optional[str] = None
    parent_id: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None

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
    phone: Optional[str] = None
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    designation: Optional[str] = None
    location: Optional[str] = None
    status: Optional[UserStatus] = None
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    status: UserStatus
    phone: Optional[str] = None
    designation: Optional[str] = None
    location: Optional[str] = None
    parent_id: Optional[str] = None
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    digital_ids: Optional[List[Dict[str, Any]]] = None


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
    new_phone: str = Field(..., min_length=10)
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


class AdminCredentialUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)


class StatusUpdateRequest(BaseModel):
    status: UserStatus
