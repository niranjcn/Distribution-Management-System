from pydantic import BaseModel
from typing import Optional, Any, List, Generic, TypeVar
from datetime import datetime

T = TypeVar('T')


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class StandardResponse(BaseModel):
    success: bool = True
    message: str = "Operation successful"
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    success: bool = True
    message: str = "Operation successful"
    data: List[Any] = []
    pagination: Pagination


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error: Optional[dict] = None


class ErrorDetail(BaseModel):
    code: str
    details: str


# Dashboard specific responses
class DashboardStats(BaseModel):
    total_devices: int = 0
    available_devices: int = 0
    distributed_devices: int = 0
    defective_devices: int = 0
    total_distributions: int = 0
    pending_distributions: int = 0
    total_defects: int = 0
    pending_defects: int = 0
    total_returns: int = 0
    pending_returns: int = 0
    total_users: int = 0
    active_users: int = 0
    total_operators: int = 0


class RecentActivity(BaseModel):
    id: str
    action: str
    description: str
    user_name: str
    timestamp: datetime
    category: str
    link: Optional[str] = None


# Report specific responses
class InventoryReport(BaseModel):
    total_devices: int
    by_status: dict
    by_type: dict
    by_location: dict


class DistributionSummary(BaseModel):
    total: int
    by_status: dict
    by_month: List[dict]
    top_distributors: List[dict]


class DefectSummary(BaseModel):
    total: int
    by_status: dict
    by_severity: dict
    by_type: dict
    by_month: List[dict]


class ReturnSummary(BaseModel):
    total: int
    by_status: dict
    by_reason: dict
    by_month: List[dict]
