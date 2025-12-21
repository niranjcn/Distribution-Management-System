# Models package
from app.models.user import User, UserCreate, UserUpdate, UserInDB, UserRole
from app.models.device import Device, DeviceCreate, DeviceUpdate, DeviceStatus, DeviceType
from app.models.distribution import Distribution, DistributionCreate, DistributionUpdate, DistributionStatus
from app.models.defect import DefectReport, DefectCreate, DefectUpdate, DefectStatus, DefectSeverity, DefectType
from app.models.return_device import ReturnRequest, ReturnCreate, ReturnUpdate, ReturnStatus, ReturnReason
from app.models.operator import Operator, OperatorCreate, OperatorUpdate
from app.models.approval import Approval, ApprovalCreate, ApprovalUpdate, ApprovalStatus, ApprovalType
from app.models.notification import Notification, NotificationCreate, NotificationType, NotificationCategory
from app.models.auth import Token, TokenData, LoginRequest
