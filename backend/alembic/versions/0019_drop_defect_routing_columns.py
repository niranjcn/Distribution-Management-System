"""Drop defect routing columns.

Defect reports now always go directly to manager/admin. The sub-distributor
routing flow (operator reports to sub distributor, then sub distributor
forwards to management) is removed, so the routing-only columns become unused:

- `defects.report_target`
- `defects.forwarded_to_management`
- `defects.forwarded_to_management_at`
- `defects.forwarded_to_management_by`
- `defects.forwarded_to_management_by_name`

`operator_id` and `sub_distributor_id` are kept: `sub_distributor_id` identifies
the concerned sub distributor for notification purposes.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("defects", "report_target")
    op.drop_column("defects", "forwarded_to_management")
    op.drop_column("defects", "forwarded_to_management_at")
    op.drop_column("defects", "forwarded_to_management_by")
    op.drop_column("defects", "forwarded_to_management_by_name")


def downgrade() -> None:
    op.add_column("defects", sa.Column("report_target", sa.String(length=32), nullable=True))
    op.add_column("defects", sa.Column("forwarded_to_management", sa.Boolean(), nullable=True))
    op.add_column("defects", sa.Column("forwarded_to_management_at", sa.DateTime(), nullable=True))
    op.add_column("defects", sa.Column("forwarded_to_management_by", sa.Integer(), nullable=True))
    op.add_column("defects", sa.Column("forwarded_to_management_by_name", sa.String(length=255), nullable=True))
