"""Ensure index on digital_identities(user_id).

The dashboard (scope-users, recent users) and user listing enrich rows with
``digital_id`` / ``broadband_id`` by filtering ``digital_identities`` on
``user_id``:

    SELECT user_id, digital_id, broadband_id
    FROM digital_identities
    WHERE user_id IN (...)

Migration 0006 created the index inline in its ``CREATE TABLE``, so Alembic-built
databases already have it. However, the SQLAlchemy model never declared it, so
any database created from the model tables rather than from migrations (e.g.
``create_all``) is missing it. This migration makes the index explicit and
present everywhere, guarded by an existence check so it is a safe no-op where
it already exists. No speculative composite index is added; the single-column
index fully serves the ``IN (...)`` lookups.

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_indexes(bind, table: str) -> set:
    inspector = sa.inspect(bind)
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if "idx_digital_identities_user_id" not in _existing_indexes(bind, "digital_identities"):
        op.create_index(
            "idx_digital_identities_user_id",
            "digital_identities",
            ["user_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "idx_digital_identities_user_id" in _existing_indexes(bind, "digital_identities"):
        op.drop_index("idx_digital_identities_user_id", table_name="digital_identities")
