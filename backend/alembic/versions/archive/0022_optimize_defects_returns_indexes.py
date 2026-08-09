"""Add query-optimization indexes on defects and returns.

Adds indexes for columns that the defect/return queries filter, group, or
join on but which currently have no index:

defects:
  - created_at              (date-range counts, monthly charts)
  - resolved_at             (resolution charts, resolved date ranges)
  - return_approved_at      (replacement/return monthly trend)
  - replacement_device_id   (replacement counts / "has replacement")

returns:
  - defect_id               (returns<->defects joins and the defect-detail
                             lookups that match returns back to defects)

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEXES = [
    ("idx_defects_created_at", "defects", ["created_at"]),
    ("idx_defects_resolved_at", "defects", ["resolved_at"]),
    ("idx_defects_return_approved_at", "defects", ["return_approved_at"]),
    ("idx_defects_replacement_device_id", "defects", ["replacement_device_id"]),
    ("idx_returns_defect_id", "returns", ["defect_id"]),
]


def _existing_indexes(bind, table: str) -> set:
    inspector = sa.inspect(bind)
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    for name, table, cols in _INDEXES:
        if name not in _existing_indexes(bind, table):
            op.create_index(name, table, cols)


def downgrade() -> None:
    bind = op.get_bind()
    for name, table, _cols in _INDEXES:
        if name in _existing_indexes(bind, table):
            op.drop_index(name, table_name=table)
