from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy import Boolean as SqlBool
from app.db_models.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(String(500), nullable=False)
    type = Column(String(16), default="info")
    category = Column(String(32), nullable=False)
    is_read = Column(SqlBool, default=False)
    link = Column(String(255))
    notif_metadata = Column("metadata", Text)
    created_at = Column(DateTime, nullable=False)

    def to_dict(self):
        d = super().to_dict()
        if "notif_metadata" in d:
            d["metadata"] = d.pop("notif_metadata")
        return d
