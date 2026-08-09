"""Store box_type in its own column on devices instead of metadata.

Set-top box (SB) devices historically carried their box type (HD/OTT) inside
the `metadata` JSON column. This migration:
- Adds a dedicated `box_type` column to `devices`.
- Backfills `box_type` from the existing `metadata.box_type` for SB rows.
- Removes `box_type` from `metadata` so that column only holds other objects.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SB_TYPES = ("set-top box", "set top box", "setup box", "sb", "stb")


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("ALTER TABLE devices ADD COLUMN box_type VARCHAR(16) NULL AFTER nuid"))

    # Backfill box_type from the legacy metadata JSON field (SB devices only).
    conn.execute(sa.text(f"""
        UPDATE devices
        SET box_type = CASE
            WHEN LOWER(TRIM(device_type)) IN {_SB_TYPES}
                 AND metadata IS NOT NULL AND JSON_VALID(metadata) = 1
                 AND UPPER(JSON_UNQUOTE(JSON_EXTRACT(metadata, '$.box_type'))) IN ('HD', 'OTT')
            THEN UPPER(JSON_UNQUOTE(JSON_EXTRACT(metadata, '$.box_type')))
            ELSE NULL
        END
    """))

    # Strip box_type out of metadata so it only holds other objects.
    conn.execute(sa.text("""
        UPDATE devices
        SET metadata = CASE
            WHEN CAST(JSON_REMOVE(CAST(metadata AS JSON), '$.box_type') AS CHAR) = '{}'
                THEN NULL
            ELSE CAST(JSON_REMOVE(CAST(metadata AS JSON), '$.box_type') AS CHAR)
        END
        WHERE metadata IS NOT NULL AND JSON_VALID(metadata) = 1
          AND JSON_CONTAINS_PATH(metadata, 'one', '$.box_type')
    """))


def downgrade() -> None:
    op.drop_column("devices", "box_type")
