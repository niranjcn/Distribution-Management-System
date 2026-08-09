"""Drop obsolete defect columns and normalize zero return amounts.

- Drop `defects.symptoms` (never populated by the frontend, no UI consumer).
- Drop `defects.service_charge` (duplicates return_amount in the servicing flow).
- Normalize `defects.return_amount` so a zero bill is stored as NULL instead of 0.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # A zero bill means no amount is due: store NULL instead of 0.
    conn.execute(sa.text("UPDATE defects SET return_amount = NULL WHERE COALESCE(return_amount, 0) = 0"))

    op.drop_column("defects", "symptoms")
    op.drop_column("defects", "service_charge")


def downgrade() -> None:
    op.add_column("defects", sa.Column("symptoms", sa.String(length=1000), nullable=True))
    op.add_column("defects", sa.Column("service_charge", sa.Numeric(10, 2), nullable=True))
