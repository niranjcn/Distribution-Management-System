from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


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
    REJECTED = "rejected"
    RESOLVED = "resolved"


class DefectBase(BaseModel):
    device_id: str
    defect_type: DefectType
    severity: DefectSeverity
    description: str = Field(..., min_length=10, max_length=1000)
    symptoms: Optional[str] = None


class DefectCreate(DefectBase):
    images: Optional[List[str]] = None


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
    defect_type: DefectType
    severity: DefectSeverity
    description: str
    symptoms: Optional[str] = None
    status: DefectStatus = DefectStatus.REPORTED
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    images: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        from_attributes = True


class DefectResponse(BaseModel):
    id: str
    report_id: str
    device_id: str
    device_serial: str
    device_type: str
    reported_by: str
    reported_by_name: str
    defect_type: DefectType
    severity: DefectSeverity
    description: str
    symptoms: Optional[str] = None
    status: DefectStatus
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    images: Optional[List[str]] = None
    created_at: datetime


class DefectResolve(BaseModel):
    resolution: str = Field(..., min_length=10, max_length=1000)


class DefectStatusUpdate(BaseModel):
    status: DefectStatus
    notes: Optional[str] = None
