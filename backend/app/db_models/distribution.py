from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db_models.base import Base


class Distribution(Base):
    __tablename__ = "distributions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    distribution_id = Column(String(128), unique=True, nullable=False)
    device_ids = Column(Text, nullable=False)
    device_count = Column(Integer, default=0)
    from_user_id = Column(String(64), nullable=False)
    from_user_name = Column(String(255))
    from_user_type = Column(String(64))
    to_user_id = Column(String(64), nullable=False)
    to_user_name = Column(String(255))
    to_user_type = Column(String(64))
    status = Column(String(64), default="pending")
    request_date = Column(DateTime, nullable=False)
    date_of_distribution = Column(DateTime)
    approval_date = Column(DateTime)
    delivery_date = Column(DateTime)
    notes = Column(Text)
    manifest_file = Column(String(255))
    approved_by = Column(String(64))
    approved_by_name = Column(String(255))
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class DistributionDevice(Base):
    __tablename__ = "distribution_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    distribution_id = Column(String(128), nullable=False)
    device_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)
