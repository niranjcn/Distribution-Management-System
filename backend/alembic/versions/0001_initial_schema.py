"""Initial schema - all 21 tables with full column definitions and indexes.

Revision ID: 0001
Revises: None
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAMES = [
    "users",
    "devices",
    "device_history",
    "distribution_devices",
    "distributions",
    "defects",
    "returns",
    "approvals",
    "operators",
    "notifications",
    "change_requests",
    "external_inventory_items",
    "inventory_purchase_orders",
    "inventory_po_lines",
    "inventory_receipts",
    "inventory_receipt_lines",
    "inventory_stock_movements",
    "api_activity_logs",
    "approval_role_routing",
    "token_blacklist",
    "reassignment_requests",
    "digital_ids",
]


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        password_hash TEXT NOT NULL,
        role VARCHAR(64) NOT NULL,
        status VARCHAR(32) DEFAULT 'active',
        force_email_change TINYINT(1) DEFAULT 0,
        force_password_change TINYINT(1) DEFAULT 0,
        phone VARCHAR(64),
        designation VARCHAR(255),
        location VARCHAR(255),
        parent_id INT NULL,
        is_verified TINYINT(1) DEFAULT 0,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL,
        last_login VARCHAR(64),
        failed_login_attempts INT DEFAULT 0,
        locked_until VARCHAR(64),
        created_by INT NULL,
        INDEX idx_users_parent_role(parent_id, role)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(128) UNIQUE NOT NULL,
        device_type VARCHAR(128) NOT NULL,
        model VARCHAR(255) NOT NULL,
        serial_number VARCHAR(255) UNIQUE,
        mac_address VARCHAR(255) UNIQUE,
        manufacturer VARCHAR(255) NOT NULL,
        band_type VARCHAR(64),
        nuid VARCHAR(255) UNIQUE,
        status VARCHAR(64) DEFAULT 'available',
        current_location VARCHAR(255),
        current_holder_id VARCHAR(64),
        current_holder_name VARCHAR(255),
        registered_by_name VARCHAR(255),
        current_holder_type VARCHAR(64),
        purchase_date VARCHAR(64),
        warranty_expiry VARCHAR(64),
        metadata LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS device_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(64) NOT NULL,
        action VARCHAR(128) NOT NULL,
        from_user_id VARCHAR(64),
        from_user_name VARCHAR(255),
        to_user_id VARCHAR(64),
        to_user_name VARCHAR(255),
        status_before VARCHAR(64),
        status_after VARCHAR(64),
        location VARCHAR(255),
        notes LONGTEXT,
        performed_by VARCHAR(64),
        performed_by_name VARCHAR(255),
        timestamp VARCHAR(64) NOT NULL,
        INDEX idx_device_history_device_id(device_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS distribution_devices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        distribution_id VARCHAR(128) NOT NULL,
        device_id INT NOT NULL,
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_distribution_devices_dist_id (distribution_id),
        INDEX idx_distribution_devices_device_id (device_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS distributions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        distribution_id VARCHAR(128) UNIQUE NOT NULL,
        device_ids LONGTEXT NOT NULL,
        device_count INT DEFAULT 0,
        from_user_id VARCHAR(64) NOT NULL,
        from_user_name VARCHAR(255),
        from_user_type VARCHAR(64),
        to_user_id VARCHAR(64) NOT NULL,
        to_user_name VARCHAR(255),
        to_user_type VARCHAR(64),
        status VARCHAR(64) DEFAULT 'pending',
        request_date VARCHAR(64) NOT NULL,
        date_of_distribution VARCHAR(64),
        approval_date VARCHAR(64),
        delivery_date VARCHAR(64),
        notes LONGTEXT,
        manifest_file VARCHAR(255),
        approved_by VARCHAR(64),
        approved_by_name VARCHAR(255),
        created_by VARCHAR(64) NOT NULL,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS defects (
        id INT AUTO_INCREMENT PRIMARY KEY,
        report_id VARCHAR(128) UNIQUE NOT NULL,
        device_id VARCHAR(64) NOT NULL,
        device_serial VARCHAR(255),
        device_type VARCHAR(128),
        reported_by VARCHAR(64) NOT NULL,
        reported_by_name VARCHAR(255),
        defect_type VARCHAR(64) NOT NULL,
        severity VARCHAR(64) NOT NULL,
        description LONGTEXT NOT NULL,
        symptoms LONGTEXT,
        report_target VARCHAR(64) DEFAULT 'manager_admin',
        forwarded_to_management TINYINT(1) DEFAULT 0,
        forwarded_to_management_at VARCHAR(64),
        forwarded_to_management_by VARCHAR(64),
        forwarded_to_management_by_name VARCHAR(255),
        operator_id VARCHAR(64),
        sub_distributor_id VARCHAR(64),
        status VARCHAR(64) DEFAULT 'reported',
        resolution LONGTEXT,
        resolved_by VARCHAR(64),
        resolved_by_name VARCHAR(255),
        resolved_at VARCHAR(64),
        replacement_requested_at VARCHAR(64),
        replacement_confirmed_at VARCHAR(64),
        replacement_confirmed_by VARCHAR(64),
        replacement_confirmed_by_name VARCHAR(255),
        return_amount DOUBLE DEFAULT 0,
        service_charge DOUBLE DEFAULT 0,
        payment_bill_url VARCHAR(255),
        payment_confirmed TINYINT(1) DEFAULT 0,
        payment_confirmed_at VARCHAR(64),
        payment_confirmed_by VARCHAR(64),
        payment_confirmed_by_name VARCHAR(255),
        payment_due_user_id VARCHAR(64),
        payment_due_user_name VARCHAR(255),
        images LONGTEXT,
        auto_return_id VARCHAR(64),
        replacement_device_id VARCHAR(64),
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS returns (
        id INT AUTO_INCREMENT PRIMARY KEY,
        return_id VARCHAR(128) UNIQUE NOT NULL,
        device_id VARCHAR(64) NOT NULL,
        device_serial VARCHAR(255),
        device_type VARCHAR(128),
        requested_by VARCHAR(64) NOT NULL,
        requested_by_name VARCHAR(255),
        return_to VARCHAR(64),
        return_to_name VARCHAR(255),
        reason VARCHAR(64) NOT NULL,
        description LONGTEXT,
        status VARCHAR(64) DEFAULT 'pending',
        request_date VARCHAR(64) NOT NULL,
        approval_date VARCHAR(64),
        received_date VARCHAR(64),
        approved_by VARCHAR(64),
        approved_by_name VARCHAR(255),
        defect_id VARCHAR(64),
        mac_address VARCHAR(255),
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS approvals (
        id INT AUTO_INCREMENT PRIMARY KEY,
        approval_type VARCHAR(64) NOT NULL,
        entity_id VARCHAR(64) NOT NULL,
        entity_type VARCHAR(64) NOT NULL,
        requested_by VARCHAR(64) NOT NULL,
        requested_by_name VARCHAR(255),
        status VARCHAR(64) DEFAULT 'pending',
        priority VARCHAR(32) DEFAULT 'medium',
        request_date VARCHAR(64) NOT NULL,
        approved_by VARCHAR(64),
        approved_by_name VARCHAR(255),
        approval_date VARCHAR(64),
        rejection_reason LONGTEXT,
        notes LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS operators (
        id INT AUTO_INCREMENT PRIMARY KEY,
        operator_id VARCHAR(128) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        phone VARCHAR(64) NOT NULL,
        email VARCHAR(255),
        address VARCHAR(255),
        area VARCHAR(255),
        city VARCHAR(255),
        assigned_to VARCHAR(64) NOT NULL,
        assigned_to_name VARCHAR(255),
        status VARCHAR(32) DEFAULT 'active',
        device_count INT DEFAULT 0,
        connection_type VARCHAR(64),
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        title VARCHAR(255) NOT NULL,
        message LONGTEXT NOT NULL,
        type VARCHAR(64) DEFAULT 'info',
        category VARCHAR(64) NOT NULL,
        is_read TINYINT(1) DEFAULT 0,
        link VARCHAR(255),
        metadata LONGTEXT,
        created_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS change_requests (
        id INT AUTO_INCREMENT PRIMARY KEY,
        request_id VARCHAR(128) UNIQUE NOT NULL,
        requested_by INT NOT NULL,
        requested_by_name VARCHAR(255) NOT NULL,
        requested_by_role VARCHAR(64) NOT NULL,
        request_type VARCHAR(128) NOT NULL,
        new_email VARCHAR(255),
        new_password VARCHAR(255),
        device_id VARCHAR(64),
        requested_status VARCHAR(64),
        reason LONGTEXT,
        status VARCHAR(32) DEFAULT 'pending',
        reviewed_by INT,
        reviewed_by_name VARCHAR(255),
        review_note LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS external_inventory_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        inventory_id VARCHAR(128) UNIQUE NOT NULL,
        item_id VARCHAR(128) NOT NULL,
        name VARCHAR(255) NOT NULL,
        serial_number VARCHAR(255),
        mac_id VARCHAR(255),
        identifier_type VARCHAR(128),
        identifier VARCHAR(255),
        device_type VARCHAR(128) NOT NULL,
        price DOUBLE DEFAULT 0,
        sku VARCHAR(128),
        category VARCHAR(128),
        unit VARCHAR(32) DEFAULT 'pcs',
        quantity_on_hand INT DEFAULT 0,
        reorder_level INT DEFAULT 0,
        unit_cost DOUBLE DEFAULT 0,
        supplier_name VARCHAR(255),
        location VARCHAR(255),
        status VARCHAR(32) DEFAULT 'active',
        notes LONGTEXT,
        image_url VARCHAR(255),
        created_by VARCHAR(64),
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL,
        INDEX idx_external_inventory_items_item_id(item_id),
        INDEX idx_external_inventory_items_serial_number(serial_number),
        INDEX idx_external_inventory_items_mac_id(mac_id),
        INDEX idx_external_inventory_items_device_type(device_type),
        INDEX idx_external_inventory_items_status(status),
        INDEX idx_external_inventory_items_sku(sku)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS inventory_purchase_orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        po_id VARCHAR(128) UNIQUE NOT NULL,
        supplier_name VARCHAR(255) NOT NULL,
        status VARCHAR(32) DEFAULT 'draft',
        expected_date VARCHAR(64),
        ordered_by VARCHAR(64) NOT NULL,
        ordered_by_name VARCHAR(255),
        total_amount DOUBLE DEFAULT 0,
        notes LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL,
        INDEX idx_inventory_purchase_orders_status(status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS inventory_po_lines (
        id INT AUTO_INCREMENT PRIMARY KEY,
        po_id VARCHAR(128) NOT NULL,
        item_inventory_id VARCHAR(128) NOT NULL,
        item_sku VARCHAR(128),
        item_name VARCHAR(255),
        quantity_ordered INT NOT NULL,
        unit_cost DOUBLE DEFAULT 0,
        line_total DOUBLE DEFAULT 0,
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_inventory_po_lines_po_id(po_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS inventory_receipts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        receipt_id VARCHAR(128) UNIQUE NOT NULL,
        po_id VARCHAR(128) NOT NULL,
        supplier_name VARCHAR(255),
        received_by VARCHAR(64) NOT NULL,
        received_by_name VARCHAR(255),
        notes LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_inventory_receipts_po_id(po_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS inventory_receipt_lines (
        id INT AUTO_INCREMENT PRIMARY KEY,
        receipt_id VARCHAR(128) NOT NULL,
        item_inventory_id VARCHAR(128) NOT NULL,
        item_sku VARCHAR(128),
        item_name VARCHAR(255),
        quantity_received INT NOT NULL,
        unit_cost DOUBLE DEFAULT 0,
        line_total DOUBLE DEFAULT 0
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS inventory_stock_movements (
        id INT AUTO_INCREMENT PRIMARY KEY,
        movement_id VARCHAR(128) UNIQUE NOT NULL,
        item_inventory_id VARCHAR(128) NOT NULL,
        item_sku VARCHAR(128),
        item_name VARCHAR(255),
        movement_type VARCHAR(64) NOT NULL,
        quantity INT NOT NULL,
        reference_type VARCHAR(64),
        reference_id VARCHAR(128),
        notes LONGTEXT,
        performed_by VARCHAR(64),
        performed_by_name VARCHAR(255),
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_inventory_stock_movements_item_id(item_inventory_id),
        INDEX idx_inventory_stock_movements_created_at(created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS api_activity_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        actor_id VARCHAR(64),
        actor_name VARCHAR(255),
        actor_role VARCHAR(64),
        method VARCHAR(16) NOT NULL,
        path VARCHAR(255) NOT NULL,
        status_code INT,
        description LONGTEXT,
        ip_address VARCHAR(64),
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_api_activity_logs_created_at(created_at),
        INDEX idx_api_activity_logs_actor_name(actor_name),
        INDEX idx_api_activity_logs_path(path)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS approval_role_routing (
        id INT AUTO_INCREMENT PRIMARY KEY,
        approval_type VARCHAR(64) UNIQUE NOT NULL,
        admin_enabled TINYINT(1) DEFAULT 1,
        manager_enabled TINYINT(1) DEFAULT 1,
        staff_enabled TINYINT(1) DEFAULT 1,
        updated_by VARCHAR(64),
        updated_at VARCHAR(64) NOT NULL,
        INDEX idx_approval_role_routing_type(approval_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS token_blacklist (
        token_hash VARCHAR(255) PRIMARY KEY,
        expires_at VARCHAR(64) NOT NULL,
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_token_blacklist_expires_at(expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS digital_ids (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        user_id_hash VARCHAR(64) NOT NULL,
        digital_id VARCHAR(255),
        broadband_id VARCHAR(255),
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS reassignment_requests (
        id INT AUTO_INCREMENT PRIMARY KEY,
        request_id VARCHAR(128) UNIQUE NOT NULL,
        deleted_user_id INT NOT NULL,
        deleted_user_name VARCHAR(255),
        deleted_user_role VARCHAR(64) NOT NULL,
        status VARCHAR(32) DEFAULT 'pending',
        reassigned_to_id INT,
        reassigned_to_name VARCHAR(255),
        reassigned_to_role VARCHAR(64),
        children_json LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL,
        INDEX idx_reassignment_requests_status(status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Additional indexes that are not inline in CREATE TABLE statements
    # These are safe to run because IF NOT EXISTS is used per-table above,
    # but MySQL doesn't support CREATE INDEX IF NOT EXISTS, so we use
    # a best-effort approach. These will succeed on new DBs and may
    # warn on existing DBs if the index already exists.
    _create_additional_indexes()


def _create_additional_indexes() -> None:
    """Create indexes that are not part of the original CREATE TABLE IF NOT EXISTS.

    These were added via ALTER TABLE in previous migration scripts.
    Uses try/except per index since MySQL lacks CREATE INDEX IF NOT EXISTS.
    """
    conn = op.get_bind()

    _run_index(conn, "idx_users_role_status", "CREATE INDEX idx_users_role_status ON users (role)")

    # Notifications
    _run_index(conn, "idx_notifications_user_created", "CREATE INDEX idx_notifications_user_created ON notifications (user_id, created_at DESC)")
    _run_index(conn, "idx_notifications_user_read", "CREATE INDEX idx_notifications_user_read ON notifications (user_id, is_read)")

    # Distributions
    _run_index(conn, "idx_distributions_status_created", "CREATE INDEX idx_distributions_status_created ON distributions (status, created_at)")
    _run_index(conn, "idx_distributions_from_user_created", "CREATE INDEX idx_distributions_from_user_created ON distributions (from_user_id, created_at)")
    _run_index(conn, "idx_distributions_to_user_created", "CREATE INDEX idx_distributions_to_user_created ON distributions (to_user_id, created_at)")
    _run_index(conn, "idx_distributions_to_status", "CREATE INDEX idx_distributions_to_status ON distributions (to_user_id, status)")

    # Defects
    _run_index(conn, "idx_defects_status_created", "CREATE INDEX idx_defects_status_created ON defects (status, created_at)")
    _run_index(conn, "idx_defects_device_status", "CREATE INDEX idx_defects_device_status ON defects (device_id, status)")
    _run_index(conn, "idx_defects_reported_by_created", "CREATE INDEX idx_defects_reported_by_created ON defects (reported_by, created_at)")

    # Returns
    _run_index(conn, "idx_returns_status_created", "CREATE INDEX idx_returns_status_created ON returns (status, created_at)")
    _run_index(conn, "idx_returns_device_status", "CREATE INDEX idx_returns_device_status ON returns (device_id, status)")
    _run_index(conn, "idx_returns_requested_by", "CREATE INDEX idx_returns_requested_by ON returns (requested_by, created_at)")

    # Devices
    _run_index(conn, "idx_devices_status_holder", "CREATE INDEX idx_devices_status_holder ON devices (status, current_holder_id)")
    _run_index(conn, "idx_devices_holder_updated", "CREATE INDEX idx_devices_holder_updated ON devices (current_holder_id, updated_at)")
    _run_index(conn, "idx_devices_status_created", "CREATE INDEX idx_devices_status_created ON devices (status, created_at)")
    _run_index(conn, "idx_devices_created_at", "CREATE INDEX idx_devices_created_at ON devices (created_at)")
    _run_index(conn, "idx_devices_nuid", "CREATE UNIQUE INDEX idx_devices_nuid ON devices (nuid)")

    # Approvals
    _run_index(conn, "idx_approvals_status_type", "CREATE INDEX idx_approvals_status_type ON approvals (status, approval_type)")
    _run_index(conn, "idx_approvals_entity_type", "CREATE INDEX idx_approvals_entity_type ON approvals (entity_id, approval_type)")

    # Change requests
    _run_index(conn, "idx_change_requests_status_created", "CREATE INDEX idx_change_requests_status_created ON change_requests (status, created_at)")
    _run_index(conn, "idx_change_requests_type_user_device", "CREATE INDEX idx_change_requests_type_user_device ON change_requests (request_type, requested_by, device_id, status)")

    # Operators
    _run_index(conn, "idx_operators_assigned_status", "CREATE INDEX idx_operators_assigned_status ON operators (assigned_to, status)")
    _run_index(conn, "idx_operators_status_created", "CREATE INDEX idx_operators_status_created ON operators (status, created_at)")

    # Device history
    _run_index(conn, "idx_device_history_timestamp", "CREATE INDEX idx_device_history_timestamp ON device_history (timestamp DESC)")
    _run_index(conn, "idx_device_history_performed_by", "CREATE INDEX idx_device_history_performed_by ON device_history (performed_by, timestamp DESC)")
    _run_index(conn, "idx_device_history_from_user", "CREATE INDEX idx_device_history_from_user ON device_history (from_user_id, timestamp DESC)")
    _run_index(conn, "idx_device_history_to_user", "CREATE INDEX idx_device_history_to_user ON device_history (to_user_id, timestamp DESC)")

    # API activity logs
    _run_index(conn, "idx_api_activity_logs_path_status", "CREATE INDEX idx_api_activity_logs_path_status ON api_activity_logs (path, status_code)")


def _run_index(conn, index_name: str, ddl: str) -> None:
    """Execute a CREATE INDEX statement, ignoring errors if the index already exists."""
    try:
        conn.execute(sa.text(ddl))
    except Exception:
        pass


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    tables_to_drop = [
        "digital_ids",
        "reassignment_requests",
        "token_blacklist",
        "approval_role_routing",
        "api_activity_logs",
        "inventory_stock_movements",
        "inventory_receipt_lines",
        "inventory_receipts",
        "inventory_po_lines",
        "inventory_purchase_orders",
        "external_inventory_items",
        "change_requests",
        "notifications",
        "operators",
        "approvals",
        "returns",
        "defects",
        "distributions",
        "distribution_devices",
        "device_history",
        "devices",
        "users",
    ]
    for table in tables_to_drop:
        op.execute(f"DROP TABLE IF EXISTS {table}")
