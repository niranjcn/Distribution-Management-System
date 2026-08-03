"""Rename distributions approved_by -> confirmed_by.

The `approved_by` / `approved_by_name` / `approval_date` columns on
`distributions` actually record the recipient who confirmed receipt (the
"approval" event in this workflow is the receipt confirmation), not an
approver. Rename them to `confirmed_by` / `confirmed_by_name` / `confirmed_at`
to reflect their meaning. The confirmed_* columns stay NULL until the delivery
is confirmed by the recipient.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import Date, Integer, String


revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("distributions", "approval_date", new_column_name="confirmed_at", existing_type=Date())
    op.alter_column("distributions", "approved_by", new_column_name="confirmed_by", existing_type=Integer())
    op.alter_column("distributions", "approved_by_name", new_column_name="confirmed_by_name", existing_type=String(length=255))


def downgrade() -> None:
    op.alter_column("distributions", "confirmed_at", new_column_name="approval_date", existing_type=Date())
    op.alter_column("distributions", "confirmed_by", new_column_name="approved_by", existing_type=Integer())
    op.alter_column("distributions", "confirmed_by_name", new_column_name="approved_by_name", existing_type=String(length=255))
