"""Drop unique name and add warranty fields to external_inventory_items.

``name`` is no longer a unique key on external_inventory_items (duplicate names
are allowed), so the unique index added in 0020 is dropped. Two warranty columns
are added: ``warranty_start_date`` (the date the item's warranty begins) and
``warranty_duration`` (warranty length in months). Both are nullable so
existing rows are unaffected.

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_external_inventory_items_name", table_name="external_inventory_items")
    op.add_column("external_inventory_items", sa.Column("warranty_start_date", sa.Date(), nullable=True))
    op.add_column("external_inventory_items", sa.Column("warranty_duration", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("external_inventory_items", "warranty_duration")
    op.drop_column("external_inventory_items", "warranty_start_date")
    op.create_index(
        "uq_external_inventory_items_name",
        "external_inventory_items",
        ["name"],
        unique=True,
    )
