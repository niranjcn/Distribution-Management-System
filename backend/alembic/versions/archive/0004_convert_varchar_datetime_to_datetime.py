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

    # ── Convert VARCHAR(64) ID columns to Integer ──────────────────────

    def _modify_int(table: str, columns: list[tuple[str, str]]) -> None:
        for col_name, nullable in columns:
            nullable_sql = "" if nullable == "NOT NULL" else ""
            # Convert empty strings to NULL first where nullable
            if not nullable_sql:
                op.execute(f"UPDATE {table} SET {col_name} = NULL WHERE {col_name} = ''")
            op.execute(f"ALTER TABLE {table} MODIFY COLUMN {col_name} INTEGER {nullable_sql}")

    _modify_int("devices", [("current_holder_id", "")])
    _modify_int("device_history", [
        ("device_id", "NOT NULL"), ("from_user_id", ""),
        ("to_user_id", ""), ("performed_by", ""),
    ])
    _modify_int("distributions", [
        ("from_user_id", "NOT NULL"), ("to_user_id", "NOT NULL"),
        ("approved_by", ""), ("created_by", "NOT NULL"),
    ])
    _modify_int("defects", [
        ("reported_by", "NOT NULL"), ("forwarded_to_management_by", ""),
        ("operator_id", ""), ("sub_distributor_id", ""),
        ("resolved_by", ""), ("payment_confirmed_by", ""),
        ("payment_due_user_id", ""),
    ])
    _modify_int("returns", [
        ("requested_by", "NOT NULL"), ("approved_by", ""),
    ])
    _modify_int("operators", [("assigned_to", "NOT NULL")])
    _modify_int("notifications", [("user_id", "NOT NULL")])
    _modify_int("external_inventory_items", [("created_by", "")])
    _modify_int("inventory_purchase_orders", [("ordered_by", "NOT NULL")])
    _modify_int("inventory_receipts", [("received_by", "NOT NULL")])
    _modify_int("inventory_stock_movements", [("performed_by", "")])
    _modify_int("api_activity_logs", [("actor_id", "")])

    # ── Convert FLOAT monetary columns to DECIMAL(10,2) / DECIMAL(12,2) ──

    def _modify_decimal(table: str, columns: list[tuple[str, str, int, int]]) -> None:
        for col_name, nullable, precision, scale in columns:
            nullable_sql = "" if nullable == "NOT NULL" else ""
            default_sql = " DEFAULT 0" if nullable == "NOT NULL" else ""
            op.execute(
                f"ALTER TABLE {table} MODIFY COLUMN {col_name} "
                f"DECIMAL({precision}, {scale}) {nullable_sql}{default_sql}"
            )

    _modify_decimal("defects", [
        ("return_amount", "", 10, 2),
        ("service_charge", "", 10, 2),
    ])
    _modify_decimal("external_inventory_items", [
        ("price", "", 10, 2),
        ("unit_cost", "", 10, 2),
    ])
    _modify_decimal("inventory_purchase_orders", [
        ("total_amount", "", 10, 2),
    ])
    _modify_decimal("inventory_po_lines", [
        ("unit_cost", "", 10, 2),
        ("line_total", "", 12, 2),
    ])
    _modify_decimal("inventory_receipt_lines", [
        ("unit_cost", "", 10, 2),
        ("line_total", "", 12, 2),
    ])

    # ── VARCHAR(255) MAC addresses → VARCHAR(32) ──
    op.execute("ALTER TABLE devices MODIFY COLUMN mac_address VARCHAR(32) UNIQUE")
    op.execute("ALTER TABLE returns MODIFY COLUMN mac_address VARCHAR(32)")
    op.execute("ALTER TABLE external_inventory_items MODIFY COLUMN mac_id VARCHAR(32)")

    # ── returns.reason VARCHAR(64) → VARCHAR(255) ──
    op.execute("ALTER TABLE returns MODIFY COLUMN reason VARCHAR(255) NOT NULL")

    # ── users.password_hash TEXT → VARCHAR(255) ──
    op.execute("ALTER TABLE users MODIFY COLUMN password_hash VARCHAR(255) NOT NULL")

    # ── DATETIME → DATE where time-of-day is irrelevant ──
    op.execute("ALTER TABLE devices MODIFY COLUMN purchase_date DATE")
    op.execute("ALTER TABLE devices MODIFY COLUMN warranty_expiry DATE")
    op.execute("ALTER TABLE distributions MODIFY COLUMN date_of_distribution DATE")
    op.execute("ALTER TABLE distributions MODIFY COLUMN approval_date DATE")
    op.execute("ALTER TABLE distributions MODIFY COLUMN delivery_date DATE")
    op.execute("ALTER TABLE inventory_purchase_orders MODIFY COLUMN expected_date DATE")

    # ── Integer boolean flags → BOOLEAN (TINYINT(1)) ──
    op.execute("ALTER TABLE users MODIFY COLUMN force_email_change BOOLEAN DEFAULT 0")
    op.execute("ALTER TABLE users MODIFY COLUMN force_password_change BOOLEAN DEFAULT 0")
    op.execute("ALTER TABLE users MODIFY COLUMN is_verified BOOLEAN DEFAULT 0")
    op.execute("ALTER TABLE defects MODIFY COLUMN forwarded_to_management BOOLEAN DEFAULT 0")
    op.execute("ALTER TABLE defects MODIFY COLUMN payment_confirmed BOOLEAN DEFAULT 0")
    op.execute("ALTER TABLE notifications MODIFY COLUMN is_read BOOLEAN DEFAULT 0")


def downgrade() -> None:
    """Revert DATETIME columns back to VARCHAR(64) and Integer back to VARCHAR(64)."""
    def _revert_columns(table: str, columns: list[tuple[str, str]]) -> None:
        for col_name, nullable in columns:
            nullable_sql = "" if nullable == "NOT NULL" else ""
            op.execute(f"ALTER TABLE {table} MODIFY COLUMN {col_name} VARCHAR(64) {nullable_sql}")

    # Revert Integer columns back to VARCHAR(64)
    def _revert_int(table: str, columns: list[tuple[str, str]]) -> None:
        for col_name, nullable in columns:
            nullable_sql = "" if nullable == "NOT NULL" else ""
            op.execute(f"ALTER TABLE {table} MODIFY COLUMN {col_name} VARCHAR(64) {nullable_sql}")

    _revert_int("devices", [("current_holder_id", "")])
    _revert_int("device_history", [
        ("device_id", "NOT NULL"), ("from_user_id", ""),
        ("to_user_id", ""), ("performed_by", ""),
    ])
    _revert_int("distributions", [
        ("from_user_id", "NOT NULL"), ("to_user_id", "NOT NULL"),
        ("approved_by", ""), ("created_by", "NOT NULL"),
    ])
    _revert_int("defects", [
        ("reported_by", "NOT NULL"), ("forwarded_to_management_by", ""),
        ("operator_id", ""), ("sub_distributor_id", ""),
        ("resolved_by", ""), ("payment_confirmed_by", ""),
        ("payment_due_user_id", ""),
    ])
    _revert_int("returns", [
        ("requested_by", "NOT NULL"), ("approved_by", ""),
    ])
    _revert_int("operators", [("assigned_to", "NOT NULL")])
    _revert_int("notifications", [("user_id", "NOT NULL")])
    _revert_int("external_inventory_items", [("created_by", "")])
    _revert_int("inventory_purchase_orders", [("ordered_by", "NOT NULL")])
    _revert_int("inventory_receipts", [("received_by", "NOT NULL")])
    _revert_int("inventory_stock_movements", [("performed_by", "")])
    _revert_int("api_activity_logs", [("actor_id", "")])

    # Revert DECIMAL columns back to FLOAT
    def _revert_float(table: str, columns: list[str]) -> None:
        for col_name in columns:
            op.execute(f"ALTER TABLE {table} MODIFY COLUMN {col_name} FLOAT DEFAULT 0")

    _revert_float("defects", ["return_amount", "service_charge"])
    _revert_float("external_inventory_items", ["price", "unit_cost"])
    _revert_float("inventory_purchase_orders", ["total_amount"])
    _revert_float("inventory_po_lines", ["unit_cost", "line_total"])
    _revert_float("inventory_receipt_lines", ["unit_cost", "line_total"])

    # Revert VARCHAR(32) MAC addresses back to VARCHAR(255)
    op.execute("ALTER TABLE devices MODIFY COLUMN mac_address VARCHAR(255) UNIQUE")
    op.execute("ALTER TABLE returns MODIFY COLUMN mac_address VARCHAR(255)")
    op.execute("ALTER TABLE external_inventory_items MODIFY COLUMN mac_id VARCHAR(255)")

    # Revert returns.reason VARCHAR(255) back to VARCHAR(64)
    op.execute("ALTER TABLE returns MODIFY COLUMN reason VARCHAR(64) NOT NULL")

    # Revert users.password_hash VARCHAR(255) back to TEXT
    op.execute("ALTER TABLE users MODIFY COLUMN password_hash TEXT NOT NULL")

    # Revert DATE columns back to DATETIME
    op.execute("ALTER TABLE devices MODIFY COLUMN purchase_date DATETIME")
    op.execute("ALTER TABLE devices MODIFY COLUMN warranty_expiry DATETIME")
    op.execute("ALTER TABLE distributions MODIFY COLUMN date_of_distribution DATETIME")
    op.execute("ALTER TABLE distributions MODIFY COLUMN approval_date DATETIME")
    op.execute("ALTER TABLE distributions MODIFY COLUMN delivery_date DATETIME")
    op.execute("ALTER TABLE inventory_purchase_orders MODIFY COLUMN expected_date DATETIME")

    # Revert BOOLEAN boolean flags back to Integer
    op.execute("ALTER TABLE users MODIFY COLUMN force_email_change INTEGER DEFAULT 0")
    op.execute("ALTER TABLE users MODIFY COLUMN force_password_change INTEGER DEFAULT 0")
    op.execute("ALTER TABLE users MODIFY COLUMN is_verified INTEGER DEFAULT 0")
    op.execute("ALTER TABLE defects MODIFY COLUMN forwarded_to_management INTEGER DEFAULT 0")
    op.execute("ALTER TABLE defects MODIFY COLUMN payment_confirmed INTEGER DEFAULT 0")
    op.execute("ALTER TABLE notifications MODIFY COLUMN is_read INTEGER DEFAULT 0")

    # Revert DATETIME columns back to VARCHAR(64)
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
