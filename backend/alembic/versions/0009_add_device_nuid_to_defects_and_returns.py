"""Add device_nuid columns and normalize device identity by type.

Set-top box (SB) devices are identified by their NUID, not by a serial number.
This migration:
- Adds `device_nuid` to `defects` and `returns`.
- Backfills `device_nuid` from `devices.nuid` for SB rows and clears the
  `device_serial` of SB rows; non-SB rows keep `device_serial` and get a NULL
  `device_nuid`.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SB_TYPES = ("set-top box", "set top box", "setup box", "sb", "stb")


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("ALTER TABLE defects ADD COLUMN device_nuid VARCHAR(255) NULL AFTER device_serial"))
    conn.execute(sa.text("ALTER TABLE returns ADD COLUMN device_nuid VARCHAR(255) NULL AFTER device_serial"))

    conn.execute(sa.text(f"""
        UPDATE defects d
        JOIN devices dev ON dev.id = d.device_id
        SET d.device_nuid = CASE
                WHEN LOWER(TRIM(dev.device_type)) IN {_SB_TYPES} THEN dev.nuid
                ELSE NULL
            END,
            d.device_serial = CASE
                WHEN LOWER(TRIM(dev.device_type)) IN {_SB_TYPES} THEN NULL
                ELSE d.device_serial
            END
    """))
    conn.execute(sa.text(f"""
        UPDATE returns r
        JOIN devices dev ON dev.id = r.device_id
        SET r.device_nuid = CASE
                WHEN LOWER(TRIM(dev.device_type)) IN {_SB_TYPES} THEN dev.nuid
                ELSE NULL
            END,
            r.device_serial = CASE
                WHEN LOWER(TRIM(dev.device_type)) IN {_SB_TYPES} THEN NULL
                ELSE r.device_serial
            END
    """))


def downgrade() -> None:
    op.drop_column("returns", "device_nuid")
    op.drop_column("defects", "device_nuid")
