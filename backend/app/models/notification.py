from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class NotificationCategory(str, Enum):
    DISTRIBUTION = "distribution"
    RETURN = "return"
    DEFECT = "defect"
    APPROVAL = "approval"
    SYSTEM = "system"
    USER = "user"


class NotificationBase(BaseModel):
    title: str
    message: str
    type: NotificationType = NotificationType.INFO
    category: NotificationCategory
    link: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class NotificationCreate(NotificationBase):
    user_id: str


class Notification(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    title: str
    message: str
    type: NotificationType
    category: NotificationCategory
    is_read: bool = False
    link: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        populate_by_name = True
        from_attributes = True


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    type: NotificationType
    category: NotificationCategory
    is_read: bool
    link: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
