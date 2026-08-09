"""Minimize the returns table to just the returned-device record.

The `defects` table is now the source of truth for approval/actor information
(see 0010). This migration drops the workflow metadata duplicated on `returns`:
`requested_by`, `requested_by_name`, `return_to`, `return_to_name`, `description`,
`approval_date`, `approved_by`, `approved_by_name`. Consumers resolve these from
the linked defect via `defect_id`.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("returns", "approved_by_name")
    op.drop_column("returns", "approved_by")
    op.drop_column("returns", "approval_date")
    op.drop_column("returns", "description")
    op.drop_column("returns", "return_to_name")
    op.drop_column("returns", "return_to")
    op.drop_column("returns", "requested_by_name")
    op.drop_column("returns", "requested_by")


def downgrade() -> None:
    from alembic import op as _op
    import sqlalchemy as sa

    _op.add_column("returns", sa.Column("requested_by", sa.Integer(), nullable=True))
    _op.add_column("returns", sa.Column("requested_by_name", sa.String(length=255), nullable=True))
    _op.add_column("returns", sa.Column("return_to", sa.String(length=64), nullable=True))
    _op.add_column("returns", sa.Column("return_to_name", sa.String(length=255), nullable=True))
    _op.add_column("returns", sa.Column("description", sa.String(length=500), nullable=True))
    _op.add_column("returns", sa.Column("approval_date", sa.DateTime(), nullable=True))
    _op.add_column("returns", sa.Column("approved_by", sa.Integer(), nullable=True))
    _op.add_column("returns", sa.Column("approved_by_name", sa.String(length=255), nullable=True))
