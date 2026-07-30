from sqlalchemy import Column, Integer, String, Text, Date, DateTime
from app.db_models.base import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(128), unique=True, nullable=False)
    device_type = Column(String(32), nullable=False)
    model = Column(String(255), nullable=False)
    serial_number = Column(String(255), unique=True)
    mac_address = Column(String(32), unique=True)
    manufacturer = Column(String(255), nullable=False)
    band_type = Column(String(16))
    nuid = Column(String(255), unique=True)
    status = Column(String(32), default="available")
    current_location = Column(String(255))
    current_holder_id = Column(Integer)
    current_holder_name = Column(String(255))
    registered_by_name = Column(String(255))
    current_holder_type = Column(String(32))
    purchase_date = Column(Date)
    warranty_expiry = Column(Date)
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
    device_id = Column(Integer, nullable=False)
    action = Column(String(128), nullable=False)
    from_user_id = Column(Integer)
    from_user_name = Column(String(255))
    to_user_id = Column(Integer)
    to_user_name = Column(String(255))
    status_before = Column(String(64))
    status_after = Column(String(64))
    location = Column(String(255))
    notes = Column(String(500))
    performed_by = Column(Integer)
    performed_by_name = Column(String(255))
    timestamp = Column(DateTime, nullable=False)
