from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class ApprovalType(str, Enum):
    DISTRIBUTION = "distribution"
    RETURN = "return"
    DEFECT = "defect"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ApprovalBase(BaseModel):
    approval_type: ApprovalType
    entity_id: str
    priority: Optional[ApprovalPriority] = ApprovalPriority.MEDIUM
    notes: Optional[str] = None


class ApprovalCreate(ApprovalBase):
    pass


class ApprovalUpdate(BaseModel):
    status: Optional[ApprovalStatus] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None


class Approval(BaseModel):
    id: str = Field(..., alias="_id")
    approval_type: ApprovalType
    entity_id: str
    entity_type: str  # distribution, return, defect
    requested_by: str
    requested_by_name: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    priority: ApprovalPriority = ApprovalPriority.MEDIUM
    request_date: datetime
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    approval_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Additional context
    entity_details: Optional[dict] = None
    
    class Config:
        populate_by_name = True
        from_attributes = True


class ApprovalResponse(BaseModel):
    id: str
    approval_type: ApprovalType
    entity_id: str
    entity_type: str
    requested_by: str
    requested_by_name: str
    status: ApprovalStatus
    priority: ApprovalPriority
    request_date: datetime
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    approval_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    entity_details: Optional[dict] = None
    created_at: datetime


class ApprovalAction(BaseModel):
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
