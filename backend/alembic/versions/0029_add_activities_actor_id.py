"""Add actor_id to the unified activities table.

The denormalised ``activities`` table (migration 0021) mirrored the three audit
sources by actor *name* only. Sub-distributors need a scoped feed showing only
the actions performed by their sub-distribution employees, which requires
matching by user id rather than a display name. This migration adds an
``actor_id`` column, backfills it from the three source tables, and recreates
the AFTER INSERT triggers so future rows carry the id too.

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DROP_TRIGGERS = [
    "DROP TRIGGER IF EXISTS trg_activities_device",
    "DROP TRIGGER IF EXISTS trg_activities_inventory",
    "DROP TRIGGER IF EXISTS trg_activities_api",
]


def _drop_triggers() -> None:
    for stmt in _DROP_TRIGGERS:
        op.execute(stmt)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND COLUMN_NAME = :column"
        ),
        {"table": table, "column": column},
    )
    return bool(rows.scalar())


def _index_exists(table: str, index: str) -> bool:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND INDEX_NAME = :index"
        ),
        {"table": table, "index": index},
    )
    return bool(rows.scalar())


def upgrade() -> None:
    if not _column_exists("activities", "actor_id"):
        op.execute("ALTER TABLE activities ADD COLUMN actor_id INT NULL AFTER actor")
    if not _index_exists("activities", "idx_activities_actor_id"):
        op.execute("CREATE INDEX idx_activities_actor_id ON activities (actor_id)")

    # --- Backfill actor_id from the source tables (activity_id mirrors the
    #     source row id: 'device-<id>', 'inventory-<id>', 'api-<id>') ---
    op.execute("""
    UPDATE activities a
    JOIN device_history d ON a.activity_id = CONCAT('device-', d.id)
    SET a.actor_id = d.performed_by
    WHERE a.category = 'device'
    """)

    op.execute("""
    UPDATE activities a
    JOIN external_device_history e ON a.activity_id = CONCAT('inventory-', e.id)
    SET a.actor_id = e.distributed_by
    WHERE a.category = 'inventory'
    """)

    op.execute("""
    UPDATE activities a
    JOIN api_activity_logs l ON a.activity_id = CONCAT('api-', l.id)
    SET a.actor_id = l.actor_id
    WHERE a.category = 'api'
    """)

    # --- Recreate AFTER INSERT triggers to also store actor_id ---
    _drop_triggers()

    op.execute("""
    CREATE TRIGGER trg_activities_device AFTER INSERT ON device_history FOR EACH ROW
    BEGIN
        IF NEW.action NOT IN ('bulk_registered', 'bulk_distributed')
           AND (NEW.notes IS NULL OR (NEW.notes NOT LIKE 'Device replaced by % for defect %'
                                      AND NEW.notes NOT LIKE 'Device serviced and reassigned for defect %'))
        THEN
            INSERT INTO activities
                (activity_id, category, action, actor, description, search_text, activity_date, method, path, actor_id)
            VALUES (
                CONCAT('device-', NEW.id),
                'device',
                COALESCE(NULLIF(NEW.action, ''), 'device_update'),
                COALESCE(NEW.performed_by_name, 'Unknown'),
                COALESCE(NULLIF(NEW.notes, ''),
                    CONCAT(COALESCE(NULLIF(NEW.action, ''), 'updated'), ' on device ',
                           COALESCE(CAST(NEW.device_id AS CHAR), '-'), '.')),
                CONCAT(COALESCE(NEW.action, ''), ' ', COALESCE(NEW.notes, ''), ' ',
                       COALESCE(NEW.device_id, ''), ' ', COALESCE(NEW.performed_by_name, '')),
                NEW.timestamp,
                NULL,
                NULL,
                NEW.performed_by
            );
        END IF;
    END
    """)

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

    op.execute("""
    CREATE TRIGGER trg_activities_api AFTER INSERT ON api_activity_logs FOR EACH ROW
    BEGIN
        IF NEW.description IS NOT NULL AND NEW.description NOT LIKE '% returned %' THEN
            INSERT INTO activities
                (activity_id, category, action, actor, description, search_text, activity_date, method, path, actor_id)
            VALUES (
                CONCAT('api-', NEW.id),
                'api',
                CONCAT(COALESCE(NEW.method, 'API'), ' ', COALESCE(NEW.path, '')),
                COALESCE(NEW.actor_name, 'Anonymous'),
                COALESCE(NULLIF(NEW.description, ''), 'API activity'),
                CONCAT(COALESCE(NEW.description, ''), ' ', COALESCE(NEW.path, ''), ' ',
                       COALESCE(NEW.method, ''), ' ', COALESCE(NEW.actor_name, '')),
                NEW.created_at,
                NEW.method,
                NEW.path,
                NEW.actor_id
            );
        END IF;
    END
    """)


def downgrade() -> None:
    _drop_triggers()

    op.execute("""
    CREATE TRIGGER trg_activities_device AFTER INSERT ON device_history FOR EACH ROW
    BEGIN
        IF NEW.action NOT IN ('bulk_registered', 'bulk_distributed')
           AND (NEW.notes IS NULL OR (NEW.notes NOT LIKE 'Device replaced by % for defect %'
                                      AND NEW.notes NOT LIKE 'Device serviced and reassigned for defect %'))
        THEN
            INSERT INTO activities
                (activity_id, category, action, actor, description, search_text, activity_date, method, path)
            VALUES (
                CONCAT('device-', NEW.id),
                'device',
                COALESCE(NULLIF(NEW.action, ''), 'device_update'),
                COALESCE(NEW.performed_by_name, 'Unknown'),
                COALESCE(NULLIF(NEW.notes, ''),
                    CONCAT(COALESCE(NULLIF(NEW.action, ''), 'updated'), ' on device ',
                           COALESCE(CAST(NEW.device_id AS CHAR), '-'), '.')),
                CONCAT(COALESCE(NEW.action, ''), ' ', COALESCE(NEW.notes, ''), ' ',
                       COALESCE(NEW.device_id, ''), ' ', COALESCE(NEW.performed_by_name, '')),
                NEW.timestamp,
                NULL,
                NULL
            );
        END IF;
    END
    """)

    op.execute("""
    CREATE TRIGGER trg_activities_inventory AFTER INSERT ON external_device_history FOR EACH ROW
    BEGIN
        INSERT INTO activities
            (activity_id, category, action, actor, description, search_text, activity_date, method, path)
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
            NULL
        );
    END
    """)

    op.execute("""
    CREATE TRIGGER trg_activities_api AFTER INSERT ON api_activity_logs FOR EACH ROW
    BEGIN
        IF NEW.description IS NOT NULL AND NEW.description NOT LIKE '% returned %' THEN
            INSERT INTO activities
                (activity_id, category, action, actor, description, search_text, activity_date, method, path)
            VALUES (
                CONCAT('api-', NEW.id),
                'api',
                CONCAT(COALESCE(NEW.method, 'API'), ' ', COALESCE(NEW.path, '')),
                COALESCE(NEW.actor_name, 'Anonymous'),
                COALESCE(NULLIF(NEW.description, ''), 'API activity'),
                CONCAT(COALESCE(NEW.description, ''), ' ', COALESCE(NEW.path, ''), ' ',
                       COALESCE(NEW.method, ''), ' ', COALESCE(NEW.actor_name, '')),
                NEW.created_at,
                NEW.method,
                NEW.path
            );
        END IF;
    END
    """)

    if _index_exists("activities", "idx_activities_actor_id"):
        op.execute("ALTER TABLE activities DROP INDEX idx_activities_actor_id")
    if _column_exists("activities", "actor_id"):
        op.execute("ALTER TABLE activities DROP COLUMN actor_id")
