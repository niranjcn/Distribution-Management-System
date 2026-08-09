"""Enforce unique (identifier_type, identifier) on external_inventory_items.

External inventory items are identified by their ``(identifier_type,
identifier)`` pair (e.g. IMEI + number), and bulk distribution now references
items by that pair instead of the row ``id``. This migration guarantees no two
items share the same non-null pair.

Rows without an identifier (NULL/NULL) are exempt because MySQL treats NULLs as
distinct in unique indexes, so un-tracked items remain unaffected. Any existing
duplicate non-null pairs are disambiguated first (keeping the oldest row and
suffixing the rest) so the unique index can be created without losing data.

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Keep the oldest row per non-null identifier pair and disambiguate the
    # rest so the unique index below can be created without losing data.
    conn.execute(sa.text("""
        UPDATE external_inventory_items i
        LEFT JOIN (
            SELECT MIN(id) AS keep_id
            FROM external_inventory_items
            WHERE identifier IS NOT NULL AND identifier_type IS NOT NULL
            GROUP BY identifier_type, identifier
        ) keep ON keep.keep_id = i.id
        SET i.identifier = CONCAT(LEFT(i.identifier, 230), ' (dup ', i.id, ')')
        WHERE keep.keep_id IS NULL
          AND i.identifier IS NOT NULL
          AND i.identifier_type IS NOT NULL
    """))

    op.create_index(
        "uq_external_inventory_items_identifier",
        "external_inventory_items",
        ["identifier_type", "identifier"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_external_inventory_items_identifier", table_name="external_inventory_items")
