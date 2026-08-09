"""Make users.phone unique.

Phone numbers are used as an alternative login identifier (login matches email
OR phone), so two users sharing the same number makes phone login ambiguous.
This migration adds a unique index on ``users.phone``.

Phone stays optional: NULL is still allowed and MySQL permits multiple NULLs
in a UNIQUE column. Any pre-existing duplicate non-null phones are nulled out
(keeping the earliest row's number) so the constraint can always be created.

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_indexes(bind, table: str) -> set:
    inspector = sa.inspect(bind)
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if "uniq_users_phone" in _existing_indexes(bind, "users"):
        return

    # Null out duplicate phone numbers, keeping the number of the earliest row.
    bind.execute(
        sa.text(
            """
            UPDATE users u
            JOIN (
                SELECT phone, keep_id
                FROM (
                    SELECT phone, MIN(id) AS keep_id
                    FROM users
                    WHERE phone IS NOT NULL AND TRIM(phone) <> ''
                    GROUP BY phone
                    HAVING COUNT(*) > 1
                ) grouped
            ) dup ON u.phone = dup.phone AND u.id <> dup.keep_id
            SET u.phone = NULL
            """
        )
    )
    op.create_index("uniq_users_phone", "users", ["phone"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if "uniq_users_phone" in _existing_indexes(bind, "users"):
        op.drop_index("uniq_users_phone", table_name="users")