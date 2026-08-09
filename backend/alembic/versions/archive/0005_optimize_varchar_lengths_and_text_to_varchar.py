"""Optimize VARCHAR lengths and convert short TEXT columns to VARCHAR.

- Shrink VARCHAR lengths for enum-like fields (device_type, status, etc.)
- Convert TEXT to VARCHAR(500/1000) for short text fields (notes, description, etc.)
- Shrink ip_address from 64 to 45

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _modify(table: str, col: str, col_def: str) -> None:
    op.execute(f"ALTER TABLE {table} MODIFY COLUMN {col} {col_def}")


def upgrade() -> None:
    # ── devices ──
    _modify("devices", "device_type", "VARCHAR(32) NOT NULL")
    _modify("devices", "band_type", "VARCHAR(16)")
    _modify("devices", "status", "VARCHAR(32) DEFAULT 'available'")
    _modify("devices", "current_holder_type", "VARCHAR(32)")

    # device_history
    _modify("device_history", "notes", "VARCHAR(500)")

    # ── defects ──
    _modify("defects", "device_type", "VARCHAR(32)")
    _modify("defects", "severity", "VARCHAR(16) NOT NULL")
    _modify("defects", "defect_type", "VARCHAR(32) NOT NULL")
    _modify("defects", "description", "VARCHAR(1000) NOT NULL")
    _modify("defects", "symptoms", "VARCHAR(1000)")
    _modify("defects", "report_target", "VARCHAR(32) DEFAULT 'manager_admin'")
    _modify("defects", "status", "VARCHAR(48) DEFAULT 'reported'")
    _modify("defects", "resolution", "VARCHAR(1000)")

    # ── distributions ──
    _modify("distributions", "from_user_type", "VARCHAR(32)")
    _modify("distributions", "to_user_type", "VARCHAR(32)")
    _modify("distributions", "status", "VARCHAR(32) DEFAULT 'pending'")
    _modify("distributions", "notes", "VARCHAR(500)")

    # ── returns ──
    _modify("returns", "device_type", "VARCHAR(32)")
    _modify("returns", "status", "VARCHAR(16) DEFAULT 'pending'")
    _modify("returns", "description", "VARCHAR(500)")

    # ── notifications ──
    _modify("notifications", "message", "VARCHAR(500) NOT NULL")
    _modify("notifications", "type", "VARCHAR(16) DEFAULT 'info'")
    _modify("notifications", "category", "VARCHAR(32) NOT NULL")

    # ── operators ──
    _modify("operators", "connection_type", "VARCHAR(16)")

    # ── external_inventory_items ──
    _modify("external_inventory_items", "device_type", "VARCHAR(32)")
    _modify("external_inventory_items", "identifier_type", "VARCHAR(32)")
    _modify("external_inventory_items", "category", "VARCHAR(64)")
    _modify("external_inventory_items", "notes", "VARCHAR(500)")

    # ── inventory_purchase_orders ──
    _modify("inventory_purchase_orders", "notes", "VARCHAR(500)")

    # ── inventory_receipts ──
    _modify("inventory_receipts", "notes", "VARCHAR(500)")

    # ── inventory_stock_movements ──
    _modify("inventory_stock_movements", "movement_type", "VARCHAR(32) NOT NULL")
    _modify("inventory_stock_movements", "reference_type", "VARCHAR(32)")
    _modify("inventory_stock_movements", "notes", "VARCHAR(500)")

    # ── api_activity_logs ──
    _modify("api_activity_logs", "description", "VARCHAR(500)")
    _modify("api_activity_logs", "ip_address", "VARCHAR(45)")

    # ── change_requests ──
    _modify("change_requests", "request_type", "VARCHAR(64) NOT NULL")
    _modify("change_requests", "reason", "VARCHAR(500)")
    _modify("change_requests", "review_note", "VARCHAR(500)")


def downgrade() -> None:
    # ── devices ──
    _modify("devices", "device_type", "VARCHAR(128) NOT NULL")
    _modify("devices", "band_type", "VARCHAR(64)")
    _modify("devices", "status", "VARCHAR(64) DEFAULT 'available'")
    _modify("devices", "current_holder_type", "VARCHAR(64)")

    # device_history
    _modify("device_history", "notes", "TEXT")

    # ── defects ──
    _modify("defects", "device_type", "VARCHAR(128)")
    _modify("defects", "severity", "VARCHAR(64) NOT NULL")
    _modify("defects", "defect_type", "VARCHAR(64) NOT NULL")
    _modify("defects", "description", "TEXT NOT NULL")
    _modify("defects", "symptoms", "TEXT")
    _modify("defects", "report_target", "VARCHAR(64) DEFAULT 'manager_admin'")
    _modify("defects", "status", "VARCHAR(64) DEFAULT 'reported'")
    _modify("defects", "resolution", "TEXT")

    # ── distributions ──
    _modify("distributions", "from_user_type", "VARCHAR(64)")
    _modify("distributions", "to_user_type", "VARCHAR(64)")
    _modify("distributions", "status", "VARCHAR(64) DEFAULT 'pending'")
    _modify("distributions", "notes", "TEXT")

    # ── returns ──
    _modify("returns", "device_type", "VARCHAR(128)")
    _modify("returns", "status", "VARCHAR(64) DEFAULT 'pending'")
    _modify("returns", "description", "TEXT")

    # ── notifications ──
    _modify("notifications", "message", "TEXT NOT NULL")
    _modify("notifications", "type", "VARCHAR(64) DEFAULT 'info'")
    _modify("notifications", "category", "VARCHAR(64) NOT NULL")

    # ── operators ──
    _modify("operators", "connection_type", "VARCHAR(64)")

    # ── external_inventory_items ──
    _modify("external_inventory_items", "device_type", "VARCHAR(128)")
    _modify("external_inventory_items", "identifier_type", "VARCHAR(128)")
    _modify("external_inventory_items", "category", "VARCHAR(128)")
    _modify("external_inventory_items", "notes", "TEXT")

    # ── inventory_purchase_orders ──
    _modify("inventory_purchase_orders", "notes", "TEXT")

    # ── inventory_receipts ──
    _modify("inventory_receipts", "notes", "TEXT")

    # ── inventory_stock_movements ──
    _modify("inventory_stock_movements", "movement_type", "VARCHAR(64) NOT NULL")
    _modify("inventory_stock_movements", "reference_type", "VARCHAR(64)")
    _modify("inventory_stock_movements", "notes", "TEXT")

    # ── api_activity_logs ──
    _modify("api_activity_logs", "description", "TEXT")
    _modify("api_activity_logs", "ip_address", "VARCHAR(64)")

    # ── change_requests ──
    _modify("change_requests", "request_type", "VARCHAR(128) NOT NULL")
    _modify("change_requests", "reason", "TEXT")
    _modify("change_requests", "review_note", "TEXT")
