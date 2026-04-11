from enum import Enum
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator


class InventoryItemStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class PurchaseOrderStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class MovementType(str, Enum):
    IN = "in"
    OUT = "out"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"


class InventoryItemBase(BaseModel):
    item_id: str
    name: str
    serial_number: str
    mac_id: str
    identifier_type: Optional[str] = None
    identifier: Optional[str] = None
    device_type: str
    custom_device_type: Optional[str] = None
    price: float = Field(default=0, ge=0)
    unit: str = "pcs"
    supplier_name: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    image_url: Optional[str] = None

    @model_validator(mode="after")
    def validate_identifier_rules(self):
        device_type = str(self.device_type or "").strip().lower()
        normalized = device_type.replace("-", "").replace("_", "").replace(" ", "")
        mac_id = str(self.mac_id or "").strip()
        identifier_type = str(self.identifier_type or "").strip()
        identifier = str(self.identifier or "").strip()

        if normalized in {"olt", "adapter"}:
            if not mac_id:
                raise ValueError("MAC ID is required for OLT and Adapter")
        else:
            if not identifier_type or not identifier:
                raise ValueError("Identifier type and identifier are required for non-OLT/Adapter types")

        return self


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    item_id: Optional[str] = None
    name: Optional[str] = None
    serial_number: Optional[str] = None
    mac_id: Optional[str] = None
    identifier_type: Optional[str] = None
    identifier: Optional[str] = None
    device_type: Optional[str] = None
    custom_device_type: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = None
    supplier_name: Optional[str] = None
    location: Optional[str] = None
    status: Optional[InventoryItemStatus] = None
    notes: Optional[str] = None
    image_url: Optional[str] = None

    @model_validator(mode="after")
    def validate_identifier_rules(self):
        if self.device_type is None:
            return self

        device_type = str(self.device_type or "").strip().lower()
        normalized = device_type.replace("-", "").replace("_", "").replace(" ", "")
        mac_id = str(self.mac_id or "").strip() if self.mac_id is not None else ""
        identifier_type = str(self.identifier_type or "").strip() if self.identifier_type is not None else ""
        identifier = str(self.identifier or "").strip() if self.identifier is not None else ""

        if normalized in {"olt", "adapter"}:
            if self.mac_id is not None and not mac_id:
                raise ValueError("MAC ID is required for OLT and Adapter")
        else:
            has_identifier_fields = self.identifier_type is not None or self.identifier is not None
            if has_identifier_fields and (not identifier_type or not identifier):
                raise ValueError("Identifier type and identifier are required for non-OLT/Adapter types")

        return self


class PurchaseOrderLineCreate(BaseModel):
    item_inventory_id: str
    quantity_ordered: Optional[int] = Field(default=1, ge=1)
    unit_cost: Optional[float] = Field(default=None, ge=0)


class PurchaseOrderCreate(BaseModel):
    name: str = Field(validation_alias=AliasChoices("name", "supplier_name"))
    expected_date: Optional[str] = None
    status: PurchaseOrderStatus = PurchaseOrderStatus.SUBMITTED
    notes: Optional[str] = None
    lines: List[PurchaseOrderLineCreate]


class ReceiptLineCreate(BaseModel):
    item_inventory_id: str
    quantity_received: Optional[int] = Field(default=1, ge=1)
    unit_cost: Optional[float] = Field(default=None, ge=0)


class ReceiptCreate(BaseModel):
    notes: Optional[str] = None
    lines: List[ReceiptLineCreate]


class StockAdjustmentCreate(BaseModel):
    item_inventory_id: str
    quantity_change: int
    reason: str


class ExternalInventoryDashboard(BaseModel):
    total_skus: int
    total_units: int
    low_stock_items: int
    pending_purchase_orders: int
    inventory_value: float
