"""Remove the distribution_devices junction table.

`distribution_devices` recorded which devices belong to which distribution.
Its functionality is fully preserved by two existing-tracked columns:

- `devices.current_distribution_id`: the distribution a device is currently
  locked in (status pending_receipt / disputed). Covers the "is this device
  currently in an open distribution" locking checks and current membership.
- `device_history.distribution_id`: links each device history entry back to the
  distribution that caused it. Covers historical / completed distribution
  membership.

This migration:
1. Adds `devices.current_distribution_id` (+ index).
2. Adds `device_history.distribution_id` (+ index).
3. Backfills `devices.current_distribution_id` for devices currently inside a
   pending_receipt / disputed distribution.
4. Backfills `device_history.distribution_id`:
   a. By matching the distribution code embedded in existing history notes
      (confirm/dispute/sync rows all write `... distribution {code}`).
   b. For remaining memberships (e.g. cancelled / legacy pending distributions
      that never generated a history row), inserts a lightweight
      `distribution_record` history entry so past membership stays resolvable.
5. Drops the `distribution_devices` table.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column("devices", sa.Column("current_distribution_id", sa.String(length=128), nullable=True))
    op.create_index("idx_devices_current_distribution_id", "devices", ["current_distribution_id"])

    op.add_column("device_history", sa.Column("distribution_id", sa.String(length=128), nullable=True))
    op.create_index("idx_device_history_distribution_id", "device_history", ["distribution_id"])

    # 1. Backfill devices.current_distribution_id for open (pending/disputed) distributions.
    conn.execute(sa.text("""
        UPDATE devices AS dev
        INNER JOIN distribution_devices AS dd ON dd.device_id = dev.id
        INNER JOIN distributions AS d ON d.distribution_id = dd.distribution_id
        SET dev.current_distribution_id = dd.distribution_id
        WHERE d.status IN ('pending_receipt', 'disputed')
    """))

    # 2a. Backfill device_history.distribution_id by matching the distribution
    #     code written into existing history notes.
    conn.execute(sa.text("""
        UPDATE device_history AS h
        INNER JOIN distributions AS d ON h.notes LIKE CONCAT('%distribution ', d.distribution_id, '%')
        SET h.distribution_id = d.distribution_id
        WHERE h.distribution_id IS NULL
    """))

    # 2b. Insert a lightweight membership record for any remaining
    #     (device, distribution) pairs that have no history representation
    #     (e.g. cancelled / legacy-pending distributions never confirmed).
    conn.execute(sa.text("""
        INSERT INTO device_history (
            device_id, action, notes, distribution_id, timestamp
        )
        SELECT
            dd.device_id,
            'distribution_record',
            CONCAT('Device was part of distribution ', dd.distribution_id, ' (migrated from distribution_devices)'),
            dd.distribution_id,
            COALESCE(d.date_of_distribution, d.created_at)
        FROM distribution_devices AS dd
        INNER JOIN distributions AS d ON d.distribution_id = dd.distribution_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM device_history AS h
            WHERE h.device_id = dd.device_id
              AND h.distribution_id = dd.distribution_id
        )
    """))

    op.drop_table("distribution_devices")


def downgrade() -> None:
    op.create_table(
        "distribution_devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("distribution_id", sa.String(length=128), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
    )
    op.create_index("idx_distribution_devices_device_id", "distribution_devices", ["device_id"])
    op.create_index("idx_distribution_devices_dist_id", "distribution_devices", ["distribution_id"])

    conn = op.get_bind()
    # Rebuild the junction from the two tracking columns (deduplicated).
    conn.execute(sa.text("""
        INSERT INTO distribution_devices (distribution_id, device_id, created_at)
        SELECT DISTINCT distribution_id, device_id,
               COALESCE((SELECT MIN(timestamp) FROM device_history h
                         WHERE h.device_id = dd.device_id AND h.distribution_id = dd.distribution_id),
                        NOW())
        FROM (
            SELECT current_distribution_id AS distribution_id, id AS device_id
            FROM devices
            WHERE current_distribution_id IS NOT NULL
            UNION
            SELECT distribution_id, device_id
            FROM device_history
            WHERE distribution_id IS NOT NULL
        ) dd
    """))

    op.drop_index("idx_device_history_distribution_id", table_name="device_history")
    op.drop_column("device_history", "distribution_id")

    op.drop_index("idx_devices_current_distribution_id", table_name="devices")
    op.drop_column("devices", "current_distribution_id")
