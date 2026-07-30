from sqlalchemy import Column, Integer, String, DateTime
from app.db_models.base import Base


class ApiActivityLog(Base):
    __tablename__ = "api_activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(Integer)
    actor_name = Column(String(255))
    actor_role = Column(String(64))
    method = Column(String(16), nullable=False)
    path = Column(String(255), nullable=False)
    status_code = Column(Integer)
    description = Column(String(500))
    ip_address = Column(String(45))
    created_at = Column(DateTime, nullable=False)
