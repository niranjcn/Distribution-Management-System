from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum


class OperatorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class ConnectionType(str, Enum):
    FIBER = "fiber"
    BROADBAND = "broadband"
    DSL = "dsl"
    WIRELESS = "wireless"
    OTHER = "other"


class OperatorBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    area: Optional[str] = None
    city: Optional[str] = None
    connection_type: Optional[ConnectionType] = None


class OperatorCreate(OperatorBase):
    pass


class OperatorUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    area: Optional[str] = None
    city: Optional[str] = None
    connection_type: Optional[ConnectionType] = None
    status: Optional[OperatorStatus] = None


class Operator(BaseModel):
    id: str = Field(..., alias="_id")
    operator_id: str  # Unique like OP-2024-0001
    name: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    area: Optional[str] = None
    city: Optional[str] = None
    assigned_to: str  # Sub-distributor ID
    assigned_to_name: str
    status: OperatorStatus = OperatorStatus.ACTIVE
    device_count: int = 0
    connection_type: Optional[ConnectionType] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        from_attributes = True


class OperatorResponse(BaseModel):
    id: str
    operator_id: str
    name: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    area: Optional[str] = None
    city: Optional[str] = None
    assigned_to: str
    assigned_to_name: str
    status: OperatorStatus
    device_count: int
    connection_type: Optional[ConnectionType] = None
    created_at: datetime
