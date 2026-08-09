"""Drop the denormalized device_ids column from distributions.

`distributions.device_ids` (LONGTEXT JSON) duplicated the
`distribution_devices` junction table. This migration:
- Backfills `distribution_devices` from `device_ids` JSON for any rows that
  do not already have junction records (NOT EXISTS guards against duplicates,
  since the junction has no unique constraint).
- Drops the `device_ids` column.

Consumers now resolve distribution devices exclusively from
`distribution_devices`.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        INSERT INTO distribution_devices (distribution_id, device_id, created_at)
        SELECT d.distribution_id, jt.device_id, d.created_at
        FROM distributions d
        CROSS JOIN JSON_TABLE(
            d.device_ids,
            '$[*]' COLUMNS (device_id INT PATH '$')
        ) jt
        WHERE NOT EXISTS (
            SELECT 1
            FROM distribution_devices dd
            WHERE dd.distribution_id = d.distribution_id
              AND dd.device_id = jt.device_id
        )
    """))

    op.drop_column("distributions", "device_ids")


def downgrade() -> None:
    op.add_column(
        "distributions",
        sa.Column("device_ids", sa.Text(), nullable=True),
    )

    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE distributions d
        SET device_ids = (
            SELECT JSON_ARRAYAGG(dd.device_id)
            FROM distribution_devices dd
            WHERE dd.distribution_id = d.distribution_id
        )
    """))
