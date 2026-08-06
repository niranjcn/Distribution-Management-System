from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db_models.base import Base


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(128), unique=True, nullable=False)
    request_type = Column(String(64), nullable=False)
    requested_by = Column(Integer, nullable=False)
    requested_by_name = Column(String(255), nullable=False)
    sub_distribution_id = Column(Integer, nullable=False)
    summary = Column(String(1000))
    payload = Column(Text, nullable=False)
    status = Column(String(32), default="pending")
    required_roles = Column(String(255), nullable=False)
    approvals = Column(Text)
    rejection_reason = Column(String(1000))
    execution_result = Column(Text)
    executed_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
