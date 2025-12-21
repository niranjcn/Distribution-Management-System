from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class DistributionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class UserType(str, Enum):
    NOC = "noc"
    DISTRIBUTOR = "distributor"
    SUB_DISTRIBUTOR = "sub_distributor"
    OPERATOR = "operator"


class DistributionBase(BaseModel):
    to_user_id: str
    device_ids: List[str]
    notes: Optional[str] = None


class DistributionCreate(DistributionBase):
    pass


class DistributionUpdate(BaseModel):
    notes: Optional[str] = None
    status: Optional[DistributionStatus] = None


class Distribution(BaseModel):
    id: str = Field(..., alias="_id")
    distribution_id: str  # Unique like DIST-2024-0001
    device_ids: List[str]
    device_count: int
    from_user_id: str
    from_user_name: str
    from_user_type: UserType
    to_user_id: str
    to_user_name: str
    to_user_type: UserType
    status: DistributionStatus = DistributionStatus.PENDING
    request_date: datetime
    approval_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    notes: Optional[str] = None
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        from_attributes = True


class DistributionResponse(BaseModel):
    id: str
    distribution_id: str
    device_ids: List[str]
    device_count: int
    from_user_id: str
    from_user_name: str
    from_user_type: UserType
    to_user_id: str
    to_user_name: str
    to_user_type: UserType
    status: DistributionStatus
    request_date: datetime
    approval_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    notes: Optional[str] = None
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    created_at: datetime


class DistributionStatusUpdate(BaseModel):
    status: DistributionStatus
    notes: Optional[str] = None
