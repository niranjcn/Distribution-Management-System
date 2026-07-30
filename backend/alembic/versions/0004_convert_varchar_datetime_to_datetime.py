"""Convert all VARCHAR(64) timestamp columns to native DATETIME type.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fix_t_separator(table: str, columns: list[str]) -> None:
    """Replace T separator with space in ISO datetime strings before column type change."""
    for col in columns:
        op.execute(f"UPDATE {table} SET {col} = REPLACE({col}, 'T', ' ') WHERE {col} LIKE '%T%'")


def _modify_columns(table: str, columns: list[tuple[str, str]]) -> None:
    """Modify multiple columns to DATETIME."""
    for col_name, nullable in columns:
        nullable_sql = "" if nullable == "NOT NULL" else ""
        op.execute(f"ALTER TABLE {table} MODIFY COLUMN {col_name} DATETIME {nullable_sql}")


def upgrade() -> None:
    # users
    _fix_t_separator("users", ["created_at", "updated_at", "last_login", "locked_until"])
    _modify_columns("users", [
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
        ("last_login", ""),
        ("locked_until", ""),
    ])

    # token_blacklist
    _fix_t_separator("token_blacklist", ["expires_at", "created_at"])
    _modify_columns("token_blacklist", [
        ("expires_at", "NOT NULL"),
        ("created_at", "NOT NULL"),
    ])

    # change_requests
    _fix_t_separator("change_requests", ["created_at", "updated_at"])
    _modify_columns("change_requests", [
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
    ])

    # reassignment_requests
    _fix_t_separator("reassignment_requests", ["created_at", "updated_at"])
    _modify_columns("reassignment_requests", [
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
    ])

    # devices
    _fix_t_separator("devices", ["purchase_date", "warranty_expiry", "created_at", "updated_at"])
    _modify_columns("devices", [
        ("purchase_date", ""),
        ("warranty_expiry", ""),
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
    ])

    # device_history
    _fix_t_separator("device_history", ["timestamp"])
    _modify_columns("device_history", [
        ("timestamp", "NOT NULL"),
    ])

    # distributions
    _fix_t_separator("distributions", [
        "request_date", "date_of_distribution", "approval_date",
        "delivery_date", "created_at", "updated_at",
    ])
    _modify_columns("distributions", [
        ("request_date", "NOT NULL"),
        ("date_of_distribution", ""),
        ("approval_date", ""),
        ("delivery_date", ""),
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
    ])

    # distribution_devices
    _fix_t_separator("distribution_devices", ["created_at"])
    _modify_columns("distribution_devices", [
        ("created_at", "NOT NULL"),
    ])

    # defects
    _fix_t_separator("defects", [
        "forwarded_to_management_at", "resolved_at", "replacement_requested_at",
        "replacement_confirmed_at", "payment_confirmed_at", "created_at", "updated_at",
    ])
    _modify_columns("defects", [
        ("forwarded_to_management_at", ""),
        ("resolved_at", ""),
        ("replacement_requested_at", ""),
        ("replacement_confirmed_at", ""),
        ("payment_confirmed_at", ""),
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
    ])

    # returns
    _fix_t_separator("returns", [
        "request_date", "approval_date", "received_date", "created_at", "updated_at",
    ])
    _modify_columns("returns", [
        ("request_date", "NOT NULL"),
        ("approval_date", ""),
        ("received_date", ""),
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
    ])

    # operators
    _fix_t_separator("operators", ["created_at", "updated_at"])
    _modify_columns("operators", [
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
    ])

    # notifications
    _fix_t_separator("notifications", ["created_at"])
    _modify_columns("notifications", [
        ("created_at", "NOT NULL"),
    ])

    # digital_ids
    _fix_t_separator("digital_ids", ["created_at", "updated_at"])
    _modify_columns("digital_ids", [
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
    ])

    # external_inventory_items
    _fix_t_separator("external_inventory_items", ["created_at", "updated_at"])
    _modify_columns("external_inventory_items", [
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
    ])

    # inventory_purchase_orders
    _fix_t_separator("inventory_purchase_orders", ["expected_date", "created_at", "updated_at"])
    _modify_columns("inventory_purchase_orders", [
        ("expected_date", ""),
        ("created_at", "NOT NULL"),
        ("updated_at", "NOT NULL"),
    ])

    # inventory_po_lines
    _fix_t_separator("inventory_po_lines", ["created_at"])
    _modify_columns("inventory_po_lines", [
        ("created_at", "NOT NULL"),
    ])

    # inventory_receipts
    _fix_t_separator("inventory_receipts", ["created_at"])
    _modify_columns("inventory_receipts", [
        ("created_at", "NOT NULL"),
    ])

    # inventory_stock_movements
    _fix_t_separator("inventory_stock_movements", ["created_at"])
    _modify_columns("inventory_stock_movements", [
        ("created_at", "NOT NULL"),
    ])

    # api_activity_logs
    _fix_t_separator("api_activity_logs", ["created_at"])
    _modify_columns("api_activity_logs", [
        ("created_at", "NOT NULL"),
    ])


def downgrade() -> None:
    """Revert DATETIME columns back to VARCHAR(64)."""
    def _revert_columns(table: str, columns: list[tuple[str, str]]) -> None:
        for col_name, nullable in columns:
            nullable_sql = "" if nullable == "NOT NULL" else ""
            op.execute(f"ALTER TABLE {table} MODIFY COLUMN {col_name} VARCHAR(64) {nullable_sql}")

    _revert_columns("users", [
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
        ("last_login", ""), ("locked_until", ""),
    ])
    _revert_columns("token_blacklist", [
        ("expires_at", "NOT NULL"), ("created_at", "NOT NULL"),
    ])
    _revert_columns("change_requests", [
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
    ])
    _revert_columns("reassignment_requests", [
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
    ])
    _revert_columns("devices", [
        ("purchase_date", ""), ("warranty_expiry", ""),
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
    ])
    _revert_columns("device_history", [("timestamp", "NOT NULL")])
    _revert_columns("distributions", [
        ("request_date", "NOT NULL"), ("date_of_distribution", ""),
        ("approval_date", ""), ("delivery_date", ""),
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
    ])
    _revert_columns("distribution_devices", [("created_at", "NOT NULL")])
    _revert_columns("defects", [
        ("forwarded_to_management_at", ""), ("resolved_at", ""),
        ("replacement_requested_at", ""), ("replacement_confirmed_at", ""),
        ("payment_confirmed_at", ""),
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
    ])
    _revert_columns("returns", [
        ("request_date", "NOT NULL"), ("approval_date", ""),
        ("received_date", ""),
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
    ])
    _revert_columns("operators", [
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
    ])
    _revert_columns("notifications", [("created_at", "NOT NULL")])
    _revert_columns("digital_ids", [
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
    ])
    _revert_columns("external_inventory_items", [
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
    ])
    _revert_columns("inventory_purchase_orders", [
        ("expected_date", ""),
        ("created_at", "NOT NULL"), ("updated_at", "NOT NULL"),
    ])
    _revert_columns("inventory_po_lines", [("created_at", "NOT NULL")])
    _revert_columns("inventory_receipts", [("created_at", "NOT NULL")])
    _revert_columns("inventory_stock_movements", [("created_at", "NOT NULL")])
    _revert_columns("api_activity_logs", [("created_at", "NOT NULL")])
