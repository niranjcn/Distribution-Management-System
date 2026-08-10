"""Log a single activity entry for bulk external inventory distributions.

Bulk distributions write one row per distributed item into
``external_device_history``, and the ``trg_activities_inventory`` AFTER INSERT
trigger mirrored every one of those rows into the denormalised ``activities``
feed. A 10k-item bulk upload therefore produced 10k feed entries.

This mirrors the device-history pattern (``action`` marker
``bulk_distributed``, which ``trg_activities_device`` already skips): the bulk
history rows are tagged ``action = 'bulk_distributed'``, the trigger ignores
those rows, and the routes log one aggregate activity entry per bulk operation
via the API activity feed.

An ``action`` column is added (NULL for single distributions so their per-item
feed entries are preserved; existing rows are unaffected).

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-10
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE external_device_history "
        "ADD COLUMN action VARCHAR(64) NULL AFTER status"
    )

    op.execute("DROP TRIGGER IF EXISTS trg_activities_inventory")
    op.execute("""
    CREATE TRIGGER trg_activities_inventory AFTER INSERT ON external_device_history FOR EACH ROW
    BEGIN
        IF COALESCE(NEW.action, '') NOT IN ('bulk_distributed') THEN
            INSERT INTO activities
                (activity_id, category, action, actor, description, search_text, activity_date, method, path, actor_id)
            VALUES (
                CONCAT('inventory-', NEW.id),
                'inventory',
                'distribution',
                COALESCE(NEW.distributed_by_name, 'Unknown'),
                COALESCE(NULLIF(NEW.notes, ''),
                    CONCAT('Distributed ', COALESCE(NEW.item_name, '-'), ' to ',
                           COALESCE(NEW.recipient_name, '-'), '.')),
                CONCAT(COALESCE(NEW.history_id, ''), ' ', COALESCE(NEW.item_name, ''), ' ',
                       COALESCE(NEW.recipient_name, ''), ' ', COALESCE(NEW.distributed_by_name, ''),
                       ' ', COALESCE(NEW.notes, '')),
                NEW.distributed_at,
                NULL,
                NULL,
                NEW.distributed_by
            );
        END IF;
    END
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_activities_inventory")
    op.execute("""
    CREATE TRIGGER trg_activities_inventory AFTER INSERT ON external_device_history FOR EACH ROW
    BEGIN
        INSERT INTO activities
            (activity_id, category, action, actor, description, search_text, activity_date, method, path, actor_id)
        VALUES (
            CONCAT('inventory-', NEW.id),
            'inventory',
            'distribution',
            COALESCE(NEW.distributed_by_name, 'Unknown'),
            COALESCE(NULLIF(NEW.notes, ''),
                CONCAT('Distributed ', COALESCE(NEW.item_name, '-'), ' to ',
                       COALESCE(NEW.recipient_name, '-'), '.')),
            CONCAT(COALESCE(NEW.history_id, ''), ' ', COALESCE(NEW.item_name, ''), ' ',
                   COALESCE(NEW.recipient_name, ''), ' ', COALESCE(NEW.distributed_by_name, ''),
                   ' ', COALESCE(NEW.notes, '')),
            NEW.distributed_at,
            NULL,
            NULL,
            NEW.distributed_by
        );
    END
    """)
    op.execute("ALTER TABLE external_device_history DROP COLUMN action")