from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class DistributionStatus(str, Enum):
    PENDING = "pending"
    PENDING_RECEIPT = "pending_receipt"   # Awaiting receiver confirmation
    APPROVED = "approved"                 # Receiver confirmed receipt
    DISPUTED = "disputed"                 # Receiver disputed — not received
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class UserType(str, Enum):
    NOC = "noc"
    STAFF = "pdic_staff"
    SUB_DISTRIBUTOR = "sub_distributor"
    CLUSTER = "cluster"
    OPERATOR = "operator"


class DistributionBase(BaseModel):
    to_user_id: str
    device_ids: List[str]
    notes: Optional[str] = None
    date_of_distribution: Optional[date] = None


class DistributionCreate(DistributionBase):
    pass


class DistributionUpdate(BaseModel):
    notes: Optional[str] = None
    status: Optional[DistributionStatus] = None


class Distribution(BaseModel):
    id: str = Field(..., alias="_id")
    distribution_id: str  # Unique like DIST-2026-0001
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
    date_of_distribution: Optional[date] = None
    approval_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    notes: Optional[str] = None
    manifest_file: Optional[str] = None
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
    date_of_distribution: Optional[date] = None
    approval_date: Optional[date] = None
    delivery_date: Optional[date] = None
    notes: Optional[str] = None
    manifest_file: Optional[str] = None
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    created_at: datetime


class DistributionStatusUpdate(BaseModel):
    status: DistributionStatus
    notes: Optional[str] = None

