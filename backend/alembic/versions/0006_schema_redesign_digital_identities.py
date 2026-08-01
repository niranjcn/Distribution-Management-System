"""Schema redesign: create digital_identities table, drop old users columns.

Adds address/designation/pincode to users, drops 11 unused columns,
creates digital_identities table, migrates data from old digital_ids table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _execute_if_table_exists(conn, table_name: str, sql: str) -> None:
    """Execute SQL only if the given table exists."""
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :name"
        ),
        {"name": table_name},
    )
    if result.scalar() > 0:
        conn.execute(sa.text(sql))


def _drop_table_if_exists(conn, table_name: str) -> None:
    """Drop a table if it exists.

    Best-effort: skips when the table is absent and tolerates a denied
    DROP privilege so migrations never fail on leftover cleanup tables.
    """
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :name"
        ),
        {"name": table_name},
    )
    if result.scalar() == 0:
        return
    try:
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {table_name}"))
    except Exception:
        pass


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() > 0


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Add new columns to users table ──
    for col in ("address", "designation", "pincode"):
        if not _column_exists(conn, "users", col):
            op.add_column("users", sa.Column(col, sa.String(255), nullable=True))

    # ── 2. Drop old columns from users table ──
    old_columns = (
        "digital_id", "broadband_id", "cluster_id", "operator_id",
        "department", "location", "theme", "compact_mode",
        "email_notifications", "push_notifications", "is_verified",
    )
    for col in old_columns:
        if _column_exists(conn, "users", col):
            op.drop_column("users", col)

    # ── 3. Create digital_identities table ──
    op.execute("""
    CREATE TABLE IF NOT EXISTS digital_identities (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        digital_id VARCHAR(128),
        broadband_id VARCHAR(128),
        is_primary TINYINT(1) DEFAULT 0,
        created_at DATETIME NOT NULL,
        INDEX idx_digital_identities_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # ── 4. Migrate data from old digital_ids table ──
    _execute_if_table_exists(conn, "digital_ids", """
        INSERT IGNORE INTO digital_identities (user_id, digital_id, broadband_id, is_primary, created_at)
        SELECT
            user_id,
            digital_id,
            broadband_id,
            0,
            created_at
        FROM digital_ids
    """)

    # ── 5. Drop old digital_ids table ──
    _drop_table_if_exists(conn, "digital_ids")


def downgrade() -> None:
    conn = op.get_bind()

    # ── 1. Recreate old columns in users table ──
    old_cols = {
        "digital_id": sa.String(255),
        "broadband_id": sa.String(255),
        "cluster_id": sa.String(64),
        "operator_id": sa.String(64),
        "department": sa.String(255),
        "location": sa.String(255),
        "theme": sa.String(32),
        "compact_mode": mysql.TINYINT(display_width=1),
        "email_notifications": mysql.TINYINT(display_width=1),
        "push_notifications": mysql.TINYINT(display_width=1),
        "is_verified": mysql.TINYINT(display_width=1),
    }
    for col_name, col_type in old_cols.items():
        if not _column_exists(conn, "users", col_name):
            op.add_column("users", sa.Column(col_name, col_type, nullable=True, server_default=None))

    # ── 2. Drop new columns from users ──
    for col in ("address", "designation", "pincode"):
        if _column_exists(conn, "users", col):
            op.drop_column("users", col)

    # ── 3. Recreate digital_ids table and restore data ──
    op.execute("""
    CREATE TABLE IF NOT EXISTS digital_ids (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        user_id_hash VARCHAR(64) NOT NULL,
        digital_id VARCHAR(255),
        broadband_id VARCHAR(255),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    _execute_if_table_exists(conn, "digital_identities", """
        INSERT IGNORE INTO digital_ids (user_id, user_id_hash, digital_id, broadband_id, created_at, updated_at)
        SELECT
            di.user_id,
            '',
            di.digital_id,
            di.broadband_id,
            di.created_at,
            di.created_at
        FROM digital_identities di
    """)

    # ── 4. Drop digital_identities table ──
    op.execute("DROP TABLE IF EXISTS digital_identities")
