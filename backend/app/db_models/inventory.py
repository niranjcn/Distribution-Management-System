from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric
from app.db_models.base import Base


class ExternalInventoryItem(Base):
    __tablename__ = "external_inventory_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inventory_id = Column(String(128), unique=True, nullable=False)
    item_id = Column(String(128))
    name = Column(String(255), nullable=False)
    serial_number = Column(String(255))
    mac_id = Column(String(32))
    identifier_type = Column(String(32))
    identifier = Column(String(255))
    device_type = Column(String(32))
    price = Column(Numeric(10, 2), default=0)
    sku = Column(String(128))
    category = Column(String(64))
    unit = Column(String(32), default="pcs")
    quantity_on_hand = Column(Integer, default=0)
    reorder_level = Column(Integer, default=0)
    unit_cost = Column(Numeric(10, 2), default=0)
    supplier_name = Column(String(255))
    location = Column(String(255))
    status = Column(String(32), default="active")
    notes = Column(String(500))
    image_url = Column(String(255))
    created_by = Column(Integer)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class InventoryPurchaseOrder(Base):
    __tablename__ = "inventory_purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_id = Column(String(128), unique=True, nullable=False)
    supplier_name = Column(String(255), nullable=False)
    status = Column(String(32), default="draft")
    expected_date = Column(Date)
    ordered_by = Column(Integer, nullable=False)
    ordered_by_name = Column(String(255))
    total_amount = Column(Numeric(10, 2), default=0)
    notes = Column(String(500))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class InventoryPoLine(Base):
    __tablename__ = "inventory_po_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_id = Column(String(128), nullable=False)
    item_inventory_id = Column(String(128), nullable=False)
    item_sku = Column(String(128))
    item_name = Column(String(255))
    quantity_ordered = Column(Integer, nullable=False)
    unit_cost = Column(Numeric(10, 2), default=0)
    line_total = Column(Numeric(12, 2), default=0)
    created_at = Column(DateTime, nullable=False)


class InventoryReceipt(Base):
    __tablename__ = "inventory_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(String(128), unique=True, nullable=False)
    po_id = Column(String(128), nullable=False)
    supplier_name = Column(String(255))
    received_by = Column(Integer, nullable=False)
    received_by_name = Column(String(255))
    notes = Column(String(500))
    created_at = Column(DateTime, nullable=False)


class InventoryReceiptLine(Base):
    __tablename__ = "inventory_receipt_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(String(128), nullable=False)
    item_inventory_id = Column(String(128), nullable=False)
    item_sku = Column(String(128))
    item_name = Column(String(255))
    quantity_received = Column(Integer, nullable=False)
    unit_cost = Column(Numeric(10, 2), default=0)
    line_total = Column(Numeric(12, 2), default=0)


class InventoryStockMovement(Base):
    __tablename__ = "inventory_stock_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    movement_id = Column(String(128), unique=True, nullable=False)
    item_inventory_id = Column(String(128), nullable=False)
    item_sku = Column(String(128))
    item_name = Column(String(255))
    movement_type = Column(String(32), nullable=False)
    quantity = Column(Integer, nullable=False)
    reference_type = Column(String(32))
    reference_id = Column(String(128))
    notes = Column(String(500))
    performed_by = Column(Integer)
    performed_by_name = Column(String(255))
    created_at = Column(DateTime, nullable=False)
