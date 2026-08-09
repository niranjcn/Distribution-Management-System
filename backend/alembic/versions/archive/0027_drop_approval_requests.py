"""Drop approval_requests table.

The sub-distribution employee proposal/approval flow has been removed.
Employees now perform every action their parent sub-distributor can, directly,
with no approvals. The approval_requests table created by revision 0026 is no
longer referenced by application code and is dropped here.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.execute("DROP TABLE IF EXISTS approval_requests")
    except Exception:
        pass


def downgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("request_type", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("requested_by_name", sa.String(length=255), nullable=False),
        sa.Column("sub_distribution_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(length=1000)),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("required_roles", sa.String(length=255), nullable=False),
        sa.Column("approvals", sa.Text()),
        sa.Column("rejection_reason", sa.String(length=1000)),
        sa.Column("execution_result", sa.Text()),
        sa.Column("executed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
