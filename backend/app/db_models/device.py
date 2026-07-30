from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from app.db_models.base import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(128), unique=True, nullable=False)
    device_type = Column(String(128), nullable=False)
    model = Column(String(255), nullable=False)
    serial_number = Column(String(255), unique=True)
    mac_address = Column(String(255), unique=True)
    manufacturer = Column(String(255), nullable=False)
    band_type = Column(String(64))
    nuid = Column(String(255), unique=True)
    status = Column(String(64), default="available")
    current_location = Column(String(255))
    current_holder_id = Column(String(64))
    current_holder_name = Column(String(255))
    registered_by_name = Column(String(255))
    current_holder_type = Column(String(64))
    purchase_date = Column(DateTime)
    warranty_expiry = Column(DateTime)
    device_metadata = Column("metadata", Text)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def to_dict(self):
        d = super().to_dict()
        if "device_metadata" in d:
            d["metadata"] = d.pop("device_metadata")
        return d


class DeviceHistory(Base):
    __tablename__ = "device_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), nullable=False)
    action = Column(String(128), nullable=False)
    from_user_id = Column(String(64))
    from_user_name = Column(String(255))
    to_user_id = Column(String(64))
    to_user_name = Column(String(255))
    status_before = Column(String(64))
    status_after = Column(String(64))
    location = Column(String(255))
    notes = Column(Text)
    performed_by = Column(String(64))
    performed_by_name = Column(String(255))
    timestamp = Column(DateTime, nullable=False)
