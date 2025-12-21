from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class DeviceType(str, Enum):
    ONU = "ONU"
    ONT = "ONT"
    ROUTER = "Router"
    SWITCH = "Switch"
    MODEM = "Modem"
    ACCESS_POINT = "Access Point"
    OTHER = "Other"


class DeviceStatus(str, Enum):
    AVAILABLE = "available"
    DISTRIBUTED = "distributed"
    IN_USE = "in_use"
    DEFECTIVE = "defective"
    RETURNED = "returned"
    MAINTENANCE = "maintenance"


class HolderType(str, Enum):
    NOC = "noc"
    DISTRIBUTOR = "distributor"
    SUB_DISTRIBUTOR = "sub_distributor"
    OPERATOR = "operator"


class DeviceBase(BaseModel):
    device_type: DeviceType
    model: str = Field(..., min_length=1, max_length=100)
    serial_number: str = Field(..., min_length=1, max_length=100)
    mac_address: str = Field(..., min_length=1, max_length=50)
    manufacturer: str = Field(..., min_length=1, max_length=100)


class DeviceCreate(DeviceBase):
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class DeviceUpdate(BaseModel):
    device_type: Optional[DeviceType] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    status: Optional[DeviceStatus] = None
    current_location: Optional[str] = None
    warranty_expiry: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class Device(DeviceBase):
    id: str = Field(..., alias="_id")
    device_id: str  # Unique identifier like ONU-2024-0001
    status: DeviceStatus = DeviceStatus.AVAILABLE
    current_location: Optional[str] = None
    current_holder_id: Optional[str] = None
    current_holder_name: Optional[str] = None
    current_holder_type: Optional[HolderType] = None
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True
        from_attributes = True


class DeviceResponse(BaseModel):
    id: str
    device_id: str
    device_type: DeviceType
    model: str
    serial_number: str
    mac_address: str
    manufacturer: str
    status: DeviceStatus
    current_location: Optional[str] = None
    current_holder_id: Optional[str] = None
    current_holder_name: Optional[str] = None
    current_holder_type: Optional[HolderType] = None
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DeviceHistory(BaseModel):
    id: str = Field(..., alias="_id")
    device_id: str
    action: str
    from_user_id: Optional[str] = None
    from_user_name: Optional[str] = None
    to_user_id: Optional[str] = None
    to_user_name: Optional[str] = None
    status_before: Optional[str] = None
    status_after: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    performed_by: str
    performed_by_name: str
    timestamp: datetime
    
    class Config:
        populate_by_name = True


class DeviceHistoryCreate(BaseModel):
    device_id: str
    action: str
    from_user_id: Optional[str] = None
    from_user_name: Optional[str] = None
    to_user_id: Optional[str] = None
    to_user_name: Optional[str] = None
    status_before: Optional[str] = None
    status_after: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    performed_by: str
    performed_by_name: str
