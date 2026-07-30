from sqlalchemy import Column, Integer, String, DateTime
from app.db_models.base import Base


class Return(Base):
    __tablename__ = "returns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    return_id = Column(String(128), unique=True, nullable=False)
    device_id = Column(String(64), nullable=False)
    device_serial = Column(String(255))
    device_type = Column(String(32))
    requested_by = Column(Integer, nullable=False)
    requested_by_name = Column(String(255))
    return_to = Column(String(64))
    return_to_name = Column(String(255))
    reason = Column(String(255), nullable=False)
    description = Column(String(500))
    status = Column(String(16), default="pending")
    request_date = Column(DateTime, nullable=False)
    approval_date = Column(DateTime)
    received_date = Column(DateTime)
    approved_by = Column(Integer)
    approved_by_name = Column(String(255))
    defect_id = Column(String(64))
    mac_address = Column(String(32))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
