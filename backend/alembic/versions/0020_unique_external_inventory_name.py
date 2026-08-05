"""Enforce unique name on external_inventory_items.

The bulk upload and item creation already treat ``name`` as the natural key,
but the database has never enforced it. Without a unique constraint:

- the bulk-upload duplicate pre-check is a full table scan with no index;
- concurrent uploads can both pass the check and insert the same name.

This migration disambiguates any existing duplicates (keeping the oldest row,
marking the rest) and then adds a unique index.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Keep the oldest row per name and disambiguate the rest so the unique
    # index below can be created without losing data.
    conn.execute(sa.text("""
        UPDATE external_inventory_items i
        LEFT JOIN (
            SELECT MIN(id) AS keep_id FROM external_inventory_items GROUP BY name
        ) keep ON keep.keep_id = i.id
        SET i.name = CONCAT(LEFT(i.name, 220), ' (duplicate ', i.id, ')')
        WHERE keep.keep_id IS NULL
    """))

    op.create_index(
        "uq_external_inventory_items_name",
        "external_inventory_items",
        ["name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_external_inventory_items_name", table_name="external_inventory_items")
