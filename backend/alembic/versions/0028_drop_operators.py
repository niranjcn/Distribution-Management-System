"""Drop operators table.

The legacy ``operators`` table (field operator records separate from the
``users`` table) is no longer used. Operator accounts are stored in the
``users`` table with role ``operator``; the operators CRUD API, service,
models and the cluster-dashboard stats that read from this table are removed.
The table is dropped here.

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.execute("DROP TABLE IF EXISTS operators")
    except Exception:
        pass


def downgrade() -> None:
    op.create_table(
        "operators",
        op.Column("id", op.Integer(), primary_key=True, autoincrement=True),
        op.Column("operator_id", op.String(length=128), nullable=False, unique=True),
        op.Column("name", op.String(length=255), nullable=False),
        op.Column("phone", op.String(length=64), nullable=False),
        op.Column("email", op.String(length=255)),
        op.Column("address", op.String(length=255)),
        op.Column("area", op.String(length=255)),
        op.Column("city", op.String(length=255)),
        op.Column("assigned_to", op.Integer(), nullable=False),
        op.Column("assigned_to_name", op.String(length=255)),
        op.Column("status", op.String(length=32), server_default="active"),
        op.Column("device_count", op.Integer(), server_default="0"),
        op.Column("connection_type", op.String(length=16)),
        op.Column("created_at", op.DateTime(), nullable=False),
        op.Column("updated_at", op.DateTime(), nullable=False),
    )
