"""Unified activities table for the admin activity feed.

The ``/api/dashboard/activities`` feed used to merge three separate audit
tables (``device_history``, ``external_device_history``,
``api_activity_logs``) with a ``UNION ALL`` plus a global
``ORDER BY + LIMIT``. MySQL materialises and sorts every matching row from all
three tables before applying the limit, and three full-scan ``COUNT(*)``
queries run per request, which gets slow as the tables grow.

This migration introduces a single denormalised ``activities`` table that
mirrors the three sources in a fixed shape. AFTER INSERT triggers keep it in
sync automatically, so the feed query becomes a plain indexed SELECT + COUNT.

Existing rows are backfilled with exactly the exclusions the feed previously
applied at read time (bulk device receipts, defect-replacement notes, and
"returned" API logs), so the table mirrors the old UNION output.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS trg_activities_device;
DROP TRIGGER IF EXISTS trg_activities_inventory;
DROP TRIGGER IF EXISTS trg_activities_api;
"""


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS activities (
        id INT AUTO_INCREMENT PRIMARY KEY,
        activity_id VARCHAR(255) NOT NULL,
        category VARCHAR(16) NOT NULL,
        action VARCHAR(512) NOT NULL,
        actor VARCHAR(255) NOT NULL DEFAULT 'Unknown',
        description LONGTEXT NOT NULL,
        search_text LONGTEXT NOT NULL,
        activity_date DATETIME NOT NULL,
        method VARCHAR(16) NULL,
        path VARCHAR(255) NULL,
        UNIQUE KEY uq_activities_activity_id (activity_id),
        INDEX idx_activities_date (activity_date),
        INDEX idx_activities_category_date (category, activity_date),
        INDEX idx_activities_actor (actor)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
    """)

    # --- Backfill existing rows (same exclusions the feed applied at read time) ---
    # INSERT IGNORE makes the backfill idempotent: if a previous startup died
    # mid-migration (rows already inserted but version not yet stamped), a
    # re-run skips existing rows instead of failing on the unique key.
    op.execute("""
    INSERT IGNORE INTO activities
        (activity_id, category, action, actor, description, search_text, activity_date, method, path)
    SELECT
        CONCAT('device-', id),
        'device',
        COALESCE(NULLIF(action, ''), 'device_update'),
        COALESCE(performed_by_name, 'Unknown'),
        COALESCE(NULLIF(notes, ''),
            CONCAT(COALESCE(NULLIF(action, ''), 'updated'), ' on device ',
                   COALESCE(CAST(device_id AS CHAR), '-'), '.')),
        CONCAT(COALESCE(action, ''), ' ', COALESCE(notes, ''), ' ',
               COALESCE(device_id, ''), ' ', COALESCE(performed_by_name, '')),
        timestamp,
        NULL,
        NULL
    FROM device_history
    WHERE action NOT IN ('bulk_registered', 'bulk_distributed')
      AND (notes IS NULL OR (notes NOT LIKE 'Device replaced by % for defect %'
                             AND notes NOT LIKE 'Device serviced and reassigned for defect %'))
    """)

    op.execute("""
    INSERT IGNORE INTO activities
        (activity_id, category, action, actor, description, search_text, activity_date, method, path)
    SELECT
        CONCAT('inventory-', id),
        'inventory',
        'distribution',
        COALESCE(distributed_by_name, 'Unknown'),
        COALESCE(NULLIF(notes, ''),
            CONCAT('Distributed ', COALESCE(item_name, '-'), ' to ',
                   COALESCE(recipient_name, '-'), '.')),
        CONCAT(COALESCE(history_id, ''), ' ', COALESCE(item_name, ''), ' ',
               COALESCE(recipient_name, ''), ' ', COALESCE(distributed_by_name, ''),
               ' ', COALESCE(notes, '')),
        distributed_at,
        NULL,
        NULL
    FROM external_device_history
    """)

    op.execute("""
    INSERT IGNORE INTO activities
        (activity_id, category, action, actor, description, search_text, activity_date, method, path)
    SELECT
        CONCAT('api-', id),
        'api',
        CONCAT(COALESCE(method, 'API'), ' ', COALESCE(path, '')),
        COALESCE(actor_name, 'Anonymous'),
        COALESCE(NULLIF(description, ''), 'API activity'),
        CONCAT(COALESCE(description, ''), ' ', COALESCE(path, ''), ' ',
               COALESCE(method, ''), ' ', COALESCE(actor_name, '')),
        created_at,
        method,
        path
    FROM api_activity_logs
    WHERE description IS NOT NULL AND description NOT LIKE '% returned %'
    """)

    # --- AFTER INSERT triggers keep the table in sync for new writes ---
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


def downgrade() -> None:
    op.execute(_DROP_TRIGGERS)
    op.execute("DROP TABLE IF EXISTS activities")
