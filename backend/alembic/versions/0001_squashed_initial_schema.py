"""Squashed initial schema.

All 40 historical Alembic revisions (0001-0040) have been collapsed into this
single migration. For a brand-new database this produces exactly the schema the
migration chain did:

- 17 application tables (including the denormalised ``activities`` feed table
  and the ``backup_schedules`` table the DB backup scheduler expects).
- The ``activities`` AFTER INSERT triggers that keep the feed in sync with
  ``device_history`` / ``external_device_history`` / ``api_activity_logs``.
- The single ``cache_version`` row used by HTTP conditional caching.

The original 0001-0040 revision files are preserved unchanged in
``versions/archive/`` for reference; Alembic only loads this squashed file from
``versions/``, so a fresh database builds the whole schema in one step. This
migration runs with the root (migration) database user on startup, so the
runtime ``dms_user`` only needs DML privileges.

Revision ID: 0001
Revises: None
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Order matters for downgrade (children dropped before parents; there are no
# real FKs, but keep a stable reverse order for readability).
_TABLES = [
    "activities",
    "backup_schedules",
    "cache_version",
    "token_blacklist",
    "api_activity_logs",
    "reassignment_requests",
    "digital_identities",
    "external_device_history",
    "external_inventory_items",
    "change_requests",
    "notifications",
    "returns",
    "defects",
    "distributions",
    "device_history",
    "devices",
    "users",
]


def upgrade() -> None:
    op.execute("""
    CREATE TABLE users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        name VARCHAR(255) NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(64) NOT NULL,
        status VARCHAR(32) DEFAULT 'active',
        force_email_change TINYINT(1) DEFAULT 0,
        force_password_change TINYINT(1) DEFAULT 0,
        phone VARCHAR(64),
        designation VARCHAR(255),
        address VARCHAR(255),
        pincode VARCHAR(255),
        network_name VARCHAR(255),
        parent_id INT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        last_login DATETIME,
        failed_login_attempts INT DEFAULT 0,
        locked_until DATETIME,
        created_by INT NULL,
        UNIQUE KEY uq_users_email (email),
        UNIQUE KEY uniq_users_phone (phone),
        KEY idx_users_parent_role (parent_id, role),
        KEY idx_users_role_parent (role, parent_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE devices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(128) NOT NULL,
        device_type VARCHAR(32) NOT NULL,
        model VARCHAR(255) NOT NULL,
        serial_number VARCHAR(255),
        mac_address VARCHAR(32),
        manufacturer VARCHAR(255) NOT NULL,
        band_type VARCHAR(16),
        nuid VARCHAR(255),
        box_type VARCHAR(16),
        status VARCHAR(32) DEFAULT 'available',
        current_location VARCHAR(255),
        current_holder_id INT,
        current_holder_name VARCHAR(255),
        current_distribution_id VARCHAR(128),
        registered_by_name VARCHAR(255),
        current_holder_type VARCHAR(32),
        purchase_date DATE,
        warranty_expiry DATE,
        metadata LONGTEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        UNIQUE KEY uq_devices_device_id (device_id),
        UNIQUE KEY uq_devices_serial_number (serial_number),
        UNIQUE KEY uq_devices_mac_address (mac_address),
        UNIQUE KEY uq_devices_nuid (nuid),
        KEY idx_devices_status_holder (status, current_holder_id),
        KEY idx_devices_holder_updated (current_holder_id, updated_at),
        KEY idx_devices_created_at (created_at),
        KEY idx_devices_current_distribution_id (current_distribution_id),
        KEY idx_devices_current_holder_status (current_holder_id, status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE device_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_id INT NOT NULL,
        action VARCHAR(128) NOT NULL,
        distribution_id VARCHAR(128),
        from_user_id INT,
        from_user_name VARCHAR(255),
        to_user_id INT,
        to_user_name VARCHAR(255),
        status_before VARCHAR(64),
        status_after VARCHAR(64),
        location VARCHAR(255),
        notes VARCHAR(500),
        performed_by INT,
        performed_by_name VARCHAR(255),
        timestamp DATETIME NOT NULL,
        KEY idx_device_history_device_id (device_id),
        KEY idx_device_history_timestamp (timestamp DESC),
        KEY idx_device_history_distribution_id (distribution_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE distributions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        distribution_id VARCHAR(128) NOT NULL,
        device_count INT DEFAULT 0,
        from_user_id INT NOT NULL,
        from_user_name VARCHAR(255),
        from_user_type VARCHAR(32),
        to_user_id INT NOT NULL,
        to_user_name VARCHAR(255),
        to_user_type VARCHAR(32),
        status VARCHAR(32) DEFAULT 'pending',
        request_date DATETIME NOT NULL,
        date_of_distribution DATE,
        confirmed_at DATE,
        delivery_date DATE,
        notes VARCHAR(500),
        manifest_file VARCHAR(255),
        confirmed_by INT,
        confirmed_by_name VARCHAR(255),
        created_by INT NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        UNIQUE KEY uq_distributions_distribution_id (distribution_id),
        KEY idx_distributions_status_created (status, created_at),
        KEY idx_distributions_from_user_created (from_user_id, created_at),
        KEY idx_distributions_to_user_created (to_user_id, created_at),
        KEY idx_distributions_to_user_status (to_user_id, status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE defects (
        id INT AUTO_INCREMENT PRIMARY KEY,
        report_id VARCHAR(128) NOT NULL,
        device_id VARCHAR(64) NOT NULL,
        device_serial VARCHAR(255),
        device_nuid VARCHAR(255),
        device_type VARCHAR(32),
        reported_by INT NOT NULL,
        reported_by_name VARCHAR(255),
        defect_type VARCHAR(32) NOT NULL,
        severity VARCHAR(16) NOT NULL,
        description VARCHAR(1000) NOT NULL,
        operator_id INT,
        sub_distributor_id INT,
        status VARCHAR(48) DEFAULT 'reported',
        resolution VARCHAR(1000),
        replacement_by INT,
        replacement_by_name VARCHAR(255),
        resolved_at DATETIME,
        replacement_device_id VARCHAR(64),
        replacement_confirmed_at DATETIME,
        replacement_confirmed_by INT,
        replacement_confirmed_by_name VARCHAR(255),
        defect_approved_by INT,
        defect_approved_by_name VARCHAR(255),
        defect_approved_at DATETIME,
        return_approved_by INT,
        return_approved_by_name VARCHAR(255),
        return_approved_at DATETIME,
        return_amount NUMERIC(10, 2),
        payment_bill_url VARCHAR(255),
        payment_confirmed TINYINT(1) DEFAULT 0,
        payment_confirmed_at DATETIME,
        payment_confirmed_by INT,
        payment_confirmed_by_name VARCHAR(255),
        payment_due_user_id INT,
        payment_due_user_name VARCHAR(255),
        images LONGTEXT,
        auto_return_id VARCHAR(64),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        UNIQUE KEY uq_defects_report_id (report_id),
        KEY idx_defects_status_created (status, created_at),
        KEY idx_defects_device_status (device_id, status),
        KEY idx_defects_reported_by_created (reported_by, created_at),
        KEY idx_defects_created_at (created_at),
        KEY idx_defects_resolved_at (resolved_at),
        KEY idx_defects_return_approved_at (return_approved_at),
        KEY idx_defects_replacement_device_id (replacement_device_id),
        KEY idx_defects_payment_confirmed (payment_confirmed, return_amount)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE returns (
        id INT AUTO_INCREMENT PRIMARY KEY,
        return_id VARCHAR(128) NOT NULL,
        device_id VARCHAR(64) NOT NULL,
        device_serial VARCHAR(255),
        device_nuid VARCHAR(255),
        device_type VARCHAR(32),
        reason VARCHAR(255) NOT NULL,
        status VARCHAR(16) DEFAULT 'pending',
        request_date DATETIME NOT NULL,
        received_date DATETIME,
        defect_id VARCHAR(64),
        mac_address VARCHAR(32),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        UNIQUE KEY uq_returns_return_id (return_id),
        KEY idx_returns_status_created (status, created_at),
        KEY idx_returns_device_status (device_id, status),
        KEY idx_returns_defect_id (defect_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE notifications (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        title VARCHAR(255) NOT NULL,
        message VARCHAR(500) NOT NULL,
        type VARCHAR(32) DEFAULT 'info',
        category VARCHAR(32) NOT NULL,
        is_read TINYINT(1) DEFAULT 0,
        link VARCHAR(255),
        metadata LONGTEXT,
        created_at DATETIME NOT NULL,
        KEY idx_notifications_user_created (user_id, created_at DESC),
        KEY idx_notifications_user_read (user_id, is_read)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE change_requests (
        id INT AUTO_INCREMENT PRIMARY KEY,
        request_id VARCHAR(128) NOT NULL,
        requested_by INT NOT NULL,
        requested_by_name VARCHAR(255) NOT NULL,
        requested_by_role VARCHAR(64) NOT NULL,
        request_type VARCHAR(64) NOT NULL,
        new_email VARCHAR(255),
        new_password VARCHAR(255),
        device_id TEXT,
        requested_status VARCHAR(64),
        reason VARCHAR(500),
        status VARCHAR(32) DEFAULT 'pending',
        reviewed_by INT,
        reviewed_by_name VARCHAR(255),
        review_note VARCHAR(500),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        UNIQUE KEY uq_change_requests_request_id (request_id),
        KEY idx_change_requests_status_created (status, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE external_inventory_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        identifier_type VARCHAR(32),
        identifier VARCHAR(255),
        device_type VARCHAR(32),
        price NUMERIC(10, 2),
        quantity INT DEFAULT 1,
        supplier_name VARCHAR(255),
        location VARCHAR(255),
        status VARCHAR(32) DEFAULT 'active',
        notes VARCHAR(500),
        warranty_start_date DATE,
        warranty_duration INT,
        created_by INT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        UNIQUE KEY uq_external_inventory_items_identifier (identifier_type, identifier)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE external_device_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        history_id VARCHAR(128) NOT NULL,
        item_id INT NOT NULL,
        item_name VARCHAR(255) NOT NULL,
        identifier_type VARCHAR(32),
        identifier VARCHAR(255),
        device_type VARCHAR(32),
        price NUMERIC(10, 2),
        quantity INT NOT NULL,
        recipient_user_id INT NOT NULL,
        recipient_name VARCHAR(255),
        previous_quantity INT NOT NULL,
        remaining_quantity INT NOT NULL,
        distributed_by INT NOT NULL,
        distributed_by_name VARCHAR(255),
        distributed_at DATETIME NOT NULL,
        notes VARCHAR(500),
        status VARCHAR(32) DEFAULT 'completed',
        UNIQUE KEY uq_external_device_history_history_id (history_id),
        KEY idx_external_device_history_distributed_at (distributed_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
    """)

    op.execute("""
    CREATE TABLE digital_identities (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        digital_id VARCHAR(128),
        broadband_id VARCHAR(128),
        is_primary TINYINT(1) DEFAULT 0,
        created_at DATETIME NOT NULL,
        UNIQUE KEY uq_digital_identities_digital_id (digital_id),
        UNIQUE KEY uq_digital_identities_broadband_id (broadband_id),
        KEY idx_digital_identities_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE api_activity_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        actor_id INT,
        actor_name VARCHAR(255),
        actor_role VARCHAR(64),
        method VARCHAR(16) NOT NULL,
        path VARCHAR(255) NOT NULL,
        status_code INT,
        description VARCHAR(500),
        ip_address VARCHAR(45),
        created_at DATETIME NOT NULL,
        KEY idx_api_activity_logs_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE reassignment_requests (
        id INT AUTO_INCREMENT PRIMARY KEY,
        request_id VARCHAR(128) NOT NULL,
        deleted_user_id INT NOT NULL,
        deleted_user_name VARCHAR(255),
        deleted_user_role VARCHAR(64) NOT NULL,
        status VARCHAR(32) DEFAULT 'pending',
        reassigned_to_id INT,
        reassigned_to_name VARCHAR(255),
        reassigned_to_role VARCHAR(64),
        children_json LONGTEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        UNIQUE KEY uq_reassignment_requests_request_id (request_id),
        KEY idx_reassignment_requests_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE token_blacklist (
        token_hash VARCHAR(255) PRIMARY KEY,
        expires_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL,
        KEY idx_token_blacklist_expires_at (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE cache_version (
        id TINYINT PRIMARY KEY,
        version BIGINT NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    op.execute("INSERT INTO cache_version (id, version) VALUES (1, 1)")

    op.execute("""
    CREATE TABLE backup_schedules (
        id INT PRIMARY KEY,
        frequency VARCHAR(16) NOT NULL,
        day_of_week INT NULL,
        day_of_month INT NULL,
        time_of_day VARCHAR(5) NOT NULL,
        last_run_at VARCHAR(64),
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # --- Denormalised admin activity feed (migration 0021 + 0029) ---
    op.execute("""
    CREATE TABLE activities (
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
        actor_id INT NULL,
        UNIQUE KEY uq_activities_activity_id (activity_id),
        KEY idx_activities_category_date (category, activity_date),
        KEY idx_activities_actor_id (actor_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
    """)

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
                CONCAT(COALESCE(NEW.description, ''), ' ', COALESCE(NEW.path), ' ',
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
    for trigger in (
        "trg_activities_api",
        "trg_activities_inventory",
        "trg_activities_device",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")