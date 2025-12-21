from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    DISTRIBUTOR = "distributor"
    SUB_DISTRIBUTOR = "sub_distributor"
    OPERATOR = "operator"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=100)
    role: UserRole
    phone: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    status: Optional[UserStatus] = None


class UserInDB(UserBase):
    id: str = Field(..., alias="_id")
    password_hash: str
    status: UserStatus = UserStatus.ACTIVE
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        populate_by_name = True


class User(UserBase):
    id: str = Field(..., alias="_id")
    status: UserStatus = UserStatus.ACTIVE
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        from_attributes = True


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    phone: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    status: UserStatus
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)
