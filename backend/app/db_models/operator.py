from sqlalchemy import Column, Integer, String, DateTime
from app.db_models.base import Base


class Operator(Base):
    __tablename__ = "operators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator_id = Column(String(128), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(64), nullable=False)
    email = Column(String(255))
    address = Column(String(255))
    area = Column(String(255))
    city = Column(String(255))
    assigned_to = Column(Integer, nullable=False)
    assigned_to_name = Column(String(255))
    status = Column(String(32), default="active")
    device_count = Column(Integer, default=0)
    connection_type = Column(String(16))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
