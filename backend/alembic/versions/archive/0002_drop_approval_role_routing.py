"""Drop approval_role_routing table — moved role-permission logic into code.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.execute("DROP TABLE IF EXISTS approval_role_routing")
    except Exception:
        pass


def downgrade() -> None:
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
