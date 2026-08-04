"""Overhaul the external inventory module into a lightweight distribution system.

The external inventory module no longer supports purchasing, receipts, or stock
movements. This migration:

1. Renames `external_inventory_items.quantity_on_hand` -> `quantity`.
2. Backfills `identifier_type`/`identifier` from the legacy `mac_id` value so the
   MAC-based identifier data is preserved after the `mac_id` column is dropped.
3. Drops the columns that belong to the old catalog / procurement model:
   `inventory_id`, `item_id`, `serial_number`, `mac_id`, `sku`, `category`,
   `unit`, `reorder_level`, `unit_cost`, `image_url`.
4. Drops the procurement tables:
   `inventory_purchase_orders`, `inventory_po_lines`, `inventory_receipts`,
   `inventory_receipt_lines`, `inventory_stock_movements`.
5. Creates the new `external_device_history` table that records every completed
   external inventory distribution for reporting and audit purposes.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Rename quantity_on_hand -> quantity (new catalog uses plain quantity).
    conn.execute(sa.text(
        "ALTER TABLE external_inventory_items CHANGE COLUMN quantity_on_hand quantity INT DEFAULT 1"
    ))

    # 2. Preserve the legacy MAC identifier data before dropping mac_id.
    conn.execute(sa.text("""
        UPDATE external_inventory_items
        SET identifier_type = 'MAC ID', identifier = mac_id
        WHERE mac_id IS NOT NULL AND mac_id != ''
          AND (identifier IS NULL OR identifier = '')
    """))

    # 3. Drop catalog/procurement columns.
    op.drop_index("idx_external_inventory_items_item_id", table_name="external_inventory_items")
    op.drop_index("idx_external_inventory_items_serial_number", table_name="external_inventory_items")
    op.drop_index("idx_external_inventory_items_mac_id", table_name="external_inventory_items")
    op.drop_index("idx_external_inventory_items_sku", table_name="external_inventory_items")

    op.drop_column("external_inventory_items", "image_url")
    op.drop_column("external_inventory_items", "unit_cost")
    op.drop_column("external_inventory_items", "reorder_level")
    op.drop_column("external_inventory_items", "unit")
    op.drop_column("external_inventory_items", "category")
    op.drop_column("external_inventory_items", "sku")
    op.drop_column("external_inventory_items", "mac_id")
    op.drop_column("external_inventory_items", "serial_number")
    op.drop_column("external_inventory_items", "item_id")
    op.drop_column("external_inventory_items", "inventory_id")

    # 4. Drop procurement tables.
    op.drop_table("inventory_stock_movements")
    op.drop_table("inventory_receipt_lines")
    op.drop_table("inventory_receipts")
    op.drop_table("inventory_po_lines")
    op.drop_table("inventory_purchase_orders")

    # 5. Create external_device_history for completed distributions.
    op.create_table(
        "external_device_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("history_id", sa.String(length=128), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("identifier_type", sa.String(length=32), nullable=True),
        sa.Column("identifier", sa.String(length=255), nullable=True),
        sa.Column("device_type", sa.String(length=32), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("recipient_name", sa.String(length=255), nullable=True),
        sa.Column("previous_quantity", sa.Integer(), nullable=False),
        sa.Column("remaining_quantity", sa.Integer(), nullable=False),
        sa.Column("distributed_by", sa.Integer(), nullable=False),
        sa.Column("distributed_by_name", sa.String(length=255), nullable=True),
        sa.Column("distributed_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("history_id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
    )
    op.create_index(
        "idx_external_device_history_item_id",
        "external_device_history",
        ["item_id"],
    )
    op.create_index(
        "idx_external_device_history_recipient",
        "external_device_history",
        ["recipient_user_id"],
    )
    op.create_index(
        "idx_external_device_history_distributed_at",
        "external_device_history",
        ["distributed_at"],
    )


def downgrade() -> None:
    conn = op.get_bind()

    op.drop_index("idx_external_device_history_distributed_at", table_name="external_device_history")
    op.drop_index("idx_external_device_history_recipient", table_name="external_device_history")
    op.drop_index("idx_external_device_history_item_id", table_name="external_device_history")
    op.drop_table("external_device_history")

    op.create_table(
        "inventory_purchase_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("po_id", sa.String(length=128), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("ordered_by", sa.Integer(), nullable=False),
        sa.Column("ordered_by_name", sa.String(length=255), nullable=True),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("po_id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
    )
    op.create_table(
        "inventory_po_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("po_id", sa.String(length=128), nullable=False),
        sa.Column("item_inventory_id", sa.String(length=128), nullable=False),
        sa.Column("item_sku", sa.String(length=128), nullable=True),
        sa.Column("item_name", sa.String(length=255), nullable=True),
        sa.Column("quantity_ordered", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
    )
    op.create_table(
        "inventory_receipts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_id", sa.String(length=128), nullable=False),
        sa.Column("po_id", sa.String(length=128), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=True),
        sa.Column("received_by", sa.Integer(), nullable=False),
        sa.Column("received_by_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
    )
    op.create_table(
        "inventory_receipt_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_id", sa.String(length=128), nullable=False),
        sa.Column("item_inventory_id", sa.String(length=128), nullable=False),
        sa.Column("item_sku", sa.String(length=128), nullable=True),
        sa.Column("item_name", sa.String(length=255), nullable=True),
        sa.Column("quantity_received", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
    )
    op.create_table(
        "inventory_stock_movements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("movement_id", sa.String(length=128), nullable=False),
        sa.Column("item_inventory_id", sa.String(length=128), nullable=False),
        sa.Column("item_sku", sa.String(length=128), nullable=True),
        sa.Column("item_name", sa.String(length=255), nullable=True),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reference_type", sa.String(length=32), nullable=True),
        sa.Column("reference_id", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column("performed_by_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movement_id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
    )

    op.add_column("external_inventory_items", sa.Column("inventory_id", sa.String(length=128), nullable=True))
    op.add_column("external_inventory_items", sa.Column("item_id", sa.String(length=128), nullable=True))
    op.add_column("external_inventory_items", sa.Column("serial_number", sa.String(length=255), nullable=True))
    op.add_column("external_inventory_items", sa.Column("mac_id", sa.String(length=32), nullable=True))
    op.add_column("external_inventory_items", sa.Column("sku", sa.String(length=128), nullable=True))
    op.add_column("external_inventory_items", sa.Column("category", sa.String(length=64), nullable=True))
    op.add_column("external_inventory_items", sa.Column("unit", sa.String(length=32), nullable=True))
    op.add_column("external_inventory_items", sa.Column("reorder_level", sa.Integer(), nullable=True))
    op.add_column("external_inventory_items", sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True))
    op.add_column("external_inventory_items", sa.Column("image_url", sa.String(length=255), nullable=True))

    # Rebuild the previously dropped catalog/procurement indexes.
    op.create_index("idx_external_inventory_items_sku", "external_inventory_items", ["sku"])
    op.create_index("idx_external_inventory_items_mac_id", "external_inventory_items", ["mac_id"])
    op.create_index("idx_external_inventory_items_serial_number", "external_inventory_items", ["serial_number"])
    op.create_index("idx_external_inventory_items_item_id", "external_inventory_items", ["item_id"])

    conn.execute(sa.text(
        "ALTER TABLE external_inventory_items CHANGE COLUMN quantity quantity_on_hand INT DEFAULT 0"
    ))
