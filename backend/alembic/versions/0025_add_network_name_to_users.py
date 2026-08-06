"""Add network_name column to users table.

Operators (users with role='operator') can optionally carry a network name
(e.g. the service provider / ISP network they belong to). The column is
nullable so existing user rows are unaffected.

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("network_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "network_name")