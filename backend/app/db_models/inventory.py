from sqlalchemy import Column, Integer, String, DateTime, Numeric
from app.db_models.base import Base


class ExternalInventoryItem(Base):
    __tablename__ = "external_inventory_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    identifier_type = Column(String(32))
    identifier = Column(String(255))
    device_type = Column(String(32))
    price = Column(Numeric(10, 2), default=0)
    quantity = Column(Integer, default=1)
    supplier_name = Column(String(255))
    location = Column(String(255))
    status = Column(String(32), default="active")
    notes = Column(String(500))
    created_by = Column(Integer)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ExternalDeviceHistory(Base):
    __tablename__ = "external_device_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    history_id = Column(String(128), unique=True, nullable=False)
    item_id = Column(Integer, nullable=False)
    item_name = Column(String(255), nullable=False)
    identifier_type = Column(String(32))
    identifier = Column(String(255))
    device_type = Column(String(32))
    price = Column(Numeric(10, 2), default=0)
    quantity = Column(Integer, nullable=False)
    recipient_user_id = Column(Integer, nullable=False)
    recipient_name = Column(String(255))
    previous_quantity = Column(Integer, nullable=False)
    remaining_quantity = Column(Integer, nullable=False)
    distributed_by = Column(Integer, nullable=False)
    distributed_by_name = Column(String(255))
    distributed_at = Column(DateTime, nullable=False)
    notes = Column(String(500))
    status = Column(String(32), default="completed")