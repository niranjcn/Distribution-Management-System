from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric, Index
from sqlalchemy import Boolean as SqlBool
from app.db_models.base import Base


class Defect(Base):
    __tablename__ = "defects"

    __table_args__ = (
        Index("idx_defects_status_created", "status", "created_at"),
        Index("idx_defects_device_status", "device_id", "status"),
        Index("idx_defects_reported_by_created", "reported_by", "created_at"),
        Index("idx_defects_created_at", "created_at"),
        Index("idx_defects_resolved_at", "resolved_at"),
        Index("idx_defects_return_approved_at", "return_approved_at"),
        Index("idx_defects_replacement_device_id", "replacement_device_id"),
        Index("idx_defects_payment_confirmed", "payment_confirmed", "return_amount"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(128), unique=True, nullable=False)
    device_id = Column(String(64), nullable=False)
    device_serial = Column(String(255))
    device_nuid = Column(String(255))
    device_type = Column(String(32))
    reported_by = Column(Integer, nullable=False)
    reported_by_name = Column(String(255))
    defect_type = Column(String(32), nullable=False)
    severity = Column(String(16), nullable=False)
    description = Column(String(1000), nullable=False)
    operator_id = Column(Integer)
    sub_distributor_id = Column(Integer)
    status = Column(String(48), default="reported")
    resolution = Column(String(1000))
    replacement_by = Column(Integer)
    replacement_by_name = Column(String(255))
    resolved_at = Column(DateTime)
    replacement_device_id = Column(String(64))
    replacement_confirmed_at = Column(DateTime)
    replacement_confirmed_by = Column(Integer)
    replacement_confirmed_by_name = Column(String(255))
    defect_approved_by = Column(Integer)
    defect_approved_by_name = Column(String(255))
    defect_approved_at = Column(DateTime)
    return_approved_by = Column(Integer)
    return_approved_by_name = Column(String(255))
    return_approved_at = Column(DateTime)
    return_amount = Column(Numeric(10, 2), default=0)
    payment_bill_url = Column(String(255))
    payment_confirmed = Column(SqlBool, default=False)
    payment_confirmed_at = Column(DateTime)
    payment_confirmed_by = Column(Integer)
    payment_confirmed_by_name = Column(String(255))
    payment_due_user_id = Column(Integer)
    payment_due_user_name = Column(String(255))
    images = Column(Text)
    auto_return_id = Column(String(64))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
