from pydantic import BaseModel, Field, model_validator, field_validator
from typing import Optional, Dict, Any
from datetime import date, datetime
from enum import Enum


class DeviceType(str, Enum):
    ONU = "ONU"
    ONT = "ONT"
    ROUTER = "Router"
    SWITCH = "Switch"
    MODEM = "Modem"
    OLT = "OLT"
    ACCESS_POINT = "Access Point"
    SETUP_BOX = "Set-top box"
    OTHER = "Other"


class DeviceBand(str, Enum):
    SINGLE_BAND = "single_band"
    DUAL_BAND = "dual_band"


class DeviceStatus(str, Enum):
    AVAILABLE = "available"
    DISTRIBUTED = "distributed"
    IN_USE = "in_use"
    DEFECTIVE = "defective"
    REPLACED = "replaced"
    RETURNED = "returned"
    MAINTENANCE = "maintenance"


class HolderType(str, Enum):
    NOC = "noc"
    STAFF = "pdic_staff"
    SUB_DISTRIBUTOR = "sub_distributor"
    CLUSTER = "cluster"
    OPERATOR = "operator"


class DeviceBase(BaseModel):
    device_type: DeviceType
    model: str = Field(..., min_length=1, max_length=100)
    serial_number: Optional[str] = Field(default=None, max_length=100)
    mac_address: Optional[str] = Field(default=None, max_length=50)
    manufacturer: str = Field(..., min_length=1, max_length=100)
    band_type: Optional[DeviceBand] = None
    box_type: Optional[str] = None
    nuid: Optional[str] = Field(default=None, max_length=100)

    @field_validator("device_type", mode="before")
    @classmethod
    def normalize_device_type(cls, value):
        normalized = str(value or "").strip().lower()
        if normalized in {"sb", "set-top box", "set top box", "stb"}:
            return DeviceType.SETUP_BOX
        return value

    @model_validator(mode="after")
    def validate_identity_fields(self):
        is_sb = self.device_type == DeviceType.SETUP_BOX
        serial = str(self.serial_number or "").strip()
        mac = str(self.mac_address or "").strip()
        nuid = str(self.nuid or "").strip()
        box_type = str(self.box_type or "").strip().upper()

        if is_sb:
            if not nuid:
                raise ValueError("NUID is required for SB devices")
            if box_type not in {"HD", "OTT"}:
                raise ValueError("box_type is required for SB devices and must be HD or OTT")
            self.box_type = box_type
        else:
            if not serial:
                raise ValueError("Serial number is required for non-SB devices")
            self.box_type = None

        return self


class DeviceCreate(DeviceBase):
    purchase_date: Optional[date] = None
    warranty_expiry: Optional[date] = None
    metadata: Optional[Dict[str, Any]] = None


class DeviceUpdate(BaseModel):
    device_type: Optional[DeviceType] = None
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    band_type: Optional[DeviceBand] = None
    box_type: Optional[str] = None
    nuid: Optional[str] = None
    status: Optional[DeviceStatus] = None
    current_location: Optional[str] = None
    warranty_expiry: Optional[date] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("device_type", mode="before")
    @classmethod
    def normalize_device_type(cls, value):
        if value is None:
            return value
        normalized = str(value or "").strip().lower()
        if normalized in {"sb", "set-top box", "set top box", "stb"}:
            return DeviceType.SETUP_BOX
        return value


class Device(DeviceBase):
    id: str = Field(..., alias="_id")
    device_id: str  # Unique identifier like ONU-2026-0001
    status: DeviceStatus = DeviceStatus.AVAILABLE
    current_location: Optional[str] = None
    current_holder_id: Optional[str] = None
    current_holder_name: Optional[str] = None
    current_holder_type: Optional[HolderType] = None
    purchase_date: Optional[date] = None
    warranty_expiry: Optional[date] = None
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
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    manufacturer: str
    band_type: Optional[DeviceBand] = None
    box_type: Optional[str] = None
    nuid: Optional[str] = None
    status: DeviceStatus
    current_location: Optional[str] = None
    current_holder_id: Optional[str] = None
    current_holder_name: Optional[str] = None
    current_holder_type: Optional[HolderType] = None
    purchase_date: Optional[date] = None
    warranty_expiry: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class DeviceEditRequest(BaseModel):
    device_type: Optional[DeviceType] = None
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    band_type: Optional[DeviceBand] = None
    box_type: Optional[str] = None
    nuid: Optional[str] = None
    status: Optional[DeviceStatus] = None
    current_location: Optional[str] = None
    warranty_expiry: Optional[date] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("device_type", mode="before")
    @classmethod
    def normalize_device_type(cls, value):
        if value is None:
            return value
        normalized = str(value or "").strip().lower()
        if normalized in {"sb", "set-top box", "set top box", "stb"}:
            return DeviceType.SETUP_BOX
        return value


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

