from sqlalchemy import Column, Integer, String, DateTime
from app.db_models.base import Base


class Return(Base):
    __tablename__ = "returns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    return_id = Column(String(128), unique=True, nullable=False)
    device_id = Column(String(64), nullable=False)
    device_serial = Column(String(255))
    device_nuid = Column(String(255))
    device_type = Column(String(32))
    reason = Column(String(255), nullable=False)
    status = Column(String(16), default="pending")
    request_date = Column(DateTime, nullable=False)
    received_date = Column(DateTime)
    defect_id = Column(String(64))
    mac_address = Column(String(32))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
