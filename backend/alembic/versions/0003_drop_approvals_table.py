"""Drop approvals table — feature removed, table is unused.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.execute("DROP TABLE IF EXISTS approvals")
    except Exception:
        pass


def downgrade() -> None:
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
        updated_at VARCHAR(64) NOT NULL,
        INDEX idx_approvals_status_type (status, approval_type),
        INDEX idx_approvals_entity_type (entity_id, approval_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
