"""Enforce unique digital_id and broadband_id across digital_identities.

No two users may share the same digital ID or broadband ID.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Normalize empty-string values to NULL so they do not collide under the
    # unique index. MySQL allows multiple NULLs but not multiple empty strings.
    conn.execute(sa.text("UPDATE digital_identities SET digital_id = NULL WHERE TRIM(digital_id) = ''"))
    conn.execute(sa.text("UPDATE digital_identities SET broadband_id = NULL WHERE TRIM(broadband_id) = ''"))

    op.create_unique_constraint("uq_digital_identities_digital_id", "digital_identities", ["digital_id"])
    op.create_unique_constraint("uq_digital_identities_broadband_id", "digital_identities", ["broadband_id"])


def downgrade() -> None:
    op.drop_constraint("uq_digital_identities_digital_id", "digital_identities", type_="unique")
    op.drop_constraint("uq_digital_identities_broadband_id", "digital_identities", type_="unique")
