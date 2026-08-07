from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy import Boolean as SqlBool
from app.db_models.base import Base


class DigitalIdentity(Base):
    __tablename__ = "digital_identities"

    __table_args__ = (
        Index("idx_digital_identities_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    digital_id = Column(String(128), nullable=True, unique=True)
    broadband_id = Column(String(128), nullable=True, unique=True)
    is_primary = Column(SqlBool, default=False)
    created_at = Column(DateTime, nullable=False)
