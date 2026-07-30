from sqlalchemy import Column, Integer, String, DateTime
from app.db_models.base import Base


class DigitalId(Base):
    __tablename__ = "digital_ids"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    user_id_hash = Column(String(64), nullable=False)
    digital_id = Column(String(255), nullable=True)
    broadband_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
