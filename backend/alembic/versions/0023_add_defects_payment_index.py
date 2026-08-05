"""Add pending-dues payment index on defects.

The pending-dues aggregate queries (get_pending_dues_users / for_user) scan
defects filtered by `payment_confirmed = 0` with `return_amount > 0`, then
GROUP BY the responsible user. A composite index on (payment_confirmed,
return_amount) turns that scan into a narrow range scan as the table grows.

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {i["name"] for i in inspector.get_indexes("defects")}
    if "idx_defects_payment_confirmed" not in existing:
        op.create_index("idx_defects_payment_confirmed", "defects", ["payment_confirmed", "return_amount"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {i["name"] for i in inspector.get_indexes("defects")}
    if "idx_defects_payment_confirmed" in existing:
        op.drop_index("idx_defects_payment_confirmed", table_name="defects")
