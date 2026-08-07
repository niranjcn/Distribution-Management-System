from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class InventoryItemStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class InventoryItemBase(BaseModel):
    name: str
    identifier_type: Optional[str] = None
    identifier: Optional[str] = None
    device_type: Optional[str] = None
    price: float = Field(default=0, ge=0)
    quantity: int = Field(default=1, ge=1)
    supplier_name: Optional[str] = None
    location: Optional[str] = None
    warranty_start_date: Optional[date] = None
    warranty_duration: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    identifier_type: Optional[str] = None
    identifier: Optional[str] = None
    device_type: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    quantity: Optional[int] = Field(default=None, ge=1)
    supplier_name: Optional[str] = None
    location: Optional[str] = None
    warranty_start_date: Optional[date] = None
    warranty_duration: Optional[int] = Field(default=None, ge=0)
    status: Optional[InventoryItemStatus] = None
    notes: Optional[str] = None


class ExternalDistributionCreate(BaseModel):
    item_id: int
    to_user_id: int
    quantity: int = Field(default=1, ge=1)
    notes: Optional[str] = None


class ExternalBulkDistributionItem(BaseModel):
    item_id: int
    to_user_id: Optional[int] = None
    recipient_email: Optional[str] = None
    quantity: int = Field(default=1, ge=1)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_recipient(self):
        if self.to_user_id is None and not (self.recipient_email or "").strip():
            raise ValueError("A recipient (to_user_id or recipient_email) is required")
        return self


class ExternalBulkDistributionCreate(BaseModel):
    items: List[ExternalBulkDistributionItem]