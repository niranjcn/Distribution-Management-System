"""Add cache_version table for browser-side HTTP conditional caching.

A single row (id=1) tracks the global data version. Every successful
data-modifying transaction must bump `version` (see app/core/cache_version.py),
and cacheable GET endpoints serve it as an ETag so the browser can revalidate
with If-None-Match and receive a cheap HTTP 304 when nothing changed.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE cache_version (
            id TINYINT PRIMARY KEY,
            version BIGINT NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    op.execute("INSERT INTO cache_version (id, version) VALUES (1, 1)")


def downgrade() -> None:
    op.drop_table("cache_version")
