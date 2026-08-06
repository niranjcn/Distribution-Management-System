from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ApprovalRequestType(str, Enum):
    DISTRIBUTION = "distribution"
    DEFECT = "defect"
    CLUSTER = "cluster"
    OPERATOR = "operator"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_REASSIGN = "user_reassign"
    BULK_USERS = "bulk_users"
    BULK_DISTRIBUTION = "bulk_distribution"
    DELIVERY_RECEIPT = "delivery_receipt"
    RETURN_STATUS = "return_status"
    DEFECT_STATUS = "defect_status"
    PAYMENT_CONFIRMATION = "payment_confirmation"


class ApprovalRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalRequestCreate(BaseModel):
    request_type: ApprovalRequestType
    payload: Dict[str, Any] = Field(..., description="Operation payload, revalidated at approval time")
    summary: Optional[str] = Field(None, max_length=1000)


class ApprovalDecision(BaseModel):
    action: str = Field(..., description="'approve' or 'reject'")
    review_note: Optional[str] = Field(None, max_length=1000)