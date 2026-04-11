from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
from app.models.device import DeviceType, DeviceBand


class DefectType(str, Enum):
    HARDWARE = "hardware"
    SOFTWARE = "software"
    PHYSICAL_DAMAGE = "physical_damage"
    PERFORMANCE = "performance"
    CONNECTIVITY = "connectivity"
    OTHER = "other"


class DefectSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DefectStatus(str, Enum):
    REPORTED = "reported"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REPLACEMENT_PENDING_CONFIRMATION = "replacement_pending_confirmation"
    REPLACEMENT_WAITING_FOR_DEVICE = "replacement_waiting_for_device"
    REJECTED = "rejected"
    RESOLVED = "resolved"


class DefectReportTarget(str, Enum):
    SUB_DISTRIBUTOR = "sub_distributor"
    MANAGER_ADMIN = "manager_admin"


class DefectBase(BaseModel):
    device_id: str
    defect_type: DefectType
    severity: DefectSeverity
    description: str = Field(..., min_length=10, max_length=1000)
    symptoms: Optional[str] = None


class DefectCreate(DefectBase):
    images: Optional[List[str]] = None
    report_target: Optional[DefectReportTarget] = None


class DefectUpdate(BaseModel):
    defect_type: Optional[DefectType] = None
    severity: Optional[DefectSeverity] = None
    description: Optional[str] = None
    symptoms: Optional[str] = None
    status: Optional[DefectStatus] = None


class DefectReport(BaseModel):
    id: str = Field(..., alias="_id")
    report_id: str  # Unique like DEFECT-2024-0001
    device_id: str
    device_serial: str
    device_type: str
    reported_by: str
    reported_by_name: str
    operator_id: Optional[str] = None
    sub_distributor_id: Optional[str] = None
    defect_type: DefectType
    severity: DefectSeverity
    description: str
    symptoms: Optional[str] = None
    report_target: DefectReportTarget = DefectReportTarget.MANAGER_ADMIN
    forwarded_to_management: bool = False
    forwarded_to_management_at: Optional[datetime] = None
    forwarded_to_management_by: Optional[str] = None
    forwarded_to_management_by_name: Optional[str] = None
    status: DefectStatus = DefectStatus.REPORTED
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    return_amount: Optional[float] = 0
    payment_bill_url: Optional[str] = None
    payment_confirmed: bool = False
    payment_confirmed_at: Optional[datetime] = None
    payment_confirmed_by: Optional[str] = None
    payment_confirmed_by_name: Optional[str] = None
    payment_due_user_id: Optional[str] = None
    payment_due_user_name: Optional[str] = None
    images: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        from_attributes = True


class ReplacementDeviceCreate(BaseModel):
    device_type: DeviceType
    model: str = Field(..., min_length=1, max_length=100)
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    manufacturer: str = Field(..., min_length=1, max_length=100)
    band_type: Optional[DeviceBand] = None
    box_type: Optional[str] = None
    nuid: Optional[str] = None

    @model_validator(mode="after")
    def validate_sb_fields(self):
        is_sb = self.device_type == DeviceType.SETUP_BOX
        if is_sb:
            box_type = str(self.box_type or "").strip().upper()
            if box_type not in {"HD", "OTT"}:
                raise ValueError("box_type is required for SB replacement and must be HD or OTT")
            if not str(self.nuid or "").strip():
                raise ValueError("NUID is required for SB replacement")
            self.box_type = box_type
        else:
            if not str(self.serial_number or "").strip() or not str(self.mac_address or "").strip():
                raise ValueError("Serial number and MAC address are required for non-SB replacement")
            if self.band_type is None:
                self.band_type = DeviceBand.SINGLE_BAND
            self.box_type = None
        return self


class ReplaceDeviceRequest(BaseModel):
    replacement_device_id: Optional[str] = None
    mac_address: Optional[str] = None
    serial_number: Optional[str] = None
    register_device: Optional[ReplacementDeviceCreate] = None
    notes: Optional[str] = None
    return_amount: Optional[float] = Field(default=None, ge=0)
    service_charge: Optional[float] = Field(default=None, ge=0)
    payment_bill_url: Optional[str] = None


class DefectResponse(BaseModel):
    id: str
    report_id: str
    device_id: str
    device_serial: str
    device_type: str
    reported_by: str
    reported_by_name: str
    operator_id: Optional[str] = None
    sub_distributor_id: Optional[str] = None
    defect_type: DefectType
    severity: DefectSeverity
    description: str
    symptoms: Optional[str] = None
    report_target: DefectReportTarget
    forwarded_to_management: bool = False
    forwarded_to_management_at: Optional[datetime] = None
    forwarded_to_management_by: Optional[str] = None
    forwarded_to_management_by_name: Optional[str] = None
    status: DefectStatus
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    return_amount: Optional[float] = 0
    service_charge: Optional[float] = 0
    payment_bill_url: Optional[str] = None
    payment_confirmed: bool = False
    payment_confirmed_at: Optional[datetime] = None
    payment_confirmed_by: Optional[str] = None
    payment_confirmed_by_name: Optional[str] = None
    payment_due_user_id: Optional[str] = None
    payment_due_user_name: Optional[str] = None
    images: Optional[List[str]] = None
    created_at: datetime


class DefectResolve(BaseModel):
    resolution: str = Field(..., min_length=10, max_length=1000)


class DefectStatusUpdate(BaseModel):
    status: DefectStatus
    notes: Optional[str] = None
    return_amount: Optional[float] = Field(default=None, ge=0)
    payment_bill_url: Optional[str] = None


class DefectPaymentConfirmRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=1000)


class ReplacementConfirmationRequest(BaseModel):
    notes: Optional[str] = None


class DefectEnquiryRequest(BaseModel):
    message: str = Field(..., min_length=5, max_length=1000)


class DefectActionRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=1000)
