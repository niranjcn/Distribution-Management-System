from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class ReturnReason(str, Enum):
    DEFECTIVE = "defective"
    UNUSED = "unused"
    END_OF_CONTRACT = "end_of_contract"
    UPGRADE = "upgrade"
    OTHER = "other"


class ReturnStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ReturnBase(BaseModel):
    device_id: str
    reason: ReturnReason
    description: Optional[str] = None


class ReturnCreate(ReturnBase):
    pass


class ReturnUpdate(BaseModel):
    reason: Optional[ReturnReason] = None
    description: Optional[str] = None
    status: Optional[ReturnStatus] = None


class ReturnRequest(BaseModel):
    id: str = Field(..., alias="_id")
    return_id: str  # Unique like RETURN-2024-0001
    device_id: str
    device_serial: str
    device_type: str
    requested_by: str
    requested_by_name: str
    return_to: str
    return_to_name: str
    reason: ReturnReason
    description: Optional[str] = None
    status: ReturnStatus = ReturnStatus.PENDING
    request_date: datetime
    approval_date: Optional[datetime] = None
    received_date: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        from_attributes = True


class ReturnResponse(BaseModel):
    id: str
    return_id: str
    device_id: str
    device_serial: str
    device_type: str
    requested_by: str
    requested_by_name: str
    return_to: str
    return_to_name: str
    reason: ReturnReason
    description: Optional[str] = None
    status: ReturnStatus
    request_date: datetime
    approval_date: Optional[datetime] = None
    received_date: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    created_at: datetime


class ReturnStatusUpdate(BaseModel):
    status: ReturnStatus
    notes: Optional[str] = None
