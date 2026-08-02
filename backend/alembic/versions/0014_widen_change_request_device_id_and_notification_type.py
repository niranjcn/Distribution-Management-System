"""Widen change_requests.device_id and notifications.type.

`change_requests.device_id` stores a JSON list of device IDs for
`device_delete_change` bulk delete requests (e.g. {"device_ids": [...]}),
which exceeded the VARCHAR(64) capacity and caused INSERT failures with
"Data too long for column 'device_id'".

`notifications.type` needs to store values like "device_edit_request"
(19 chars), which exceeded the VARCHAR(16) capacity.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _modify(table: str, col: str, col_def: str) -> None:
    op.execute(f"ALTER TABLE {table} MODIFY COLUMN {col} {col_def}")


def upgrade() -> None:
    # The composite index idx_change_requests_type_user_device includes
    # device_id. A TEXT column cannot be part of a normal index, and a large
    # VARCHAR exceeds the 3072-byte InnoDB key limit, so drop the index first,
    # then widen the column to TEXT (device_delete_change stores a JSON list).
    op.drop_index(
        "idx_change_requests_type_user_device",
        table_name="change_requests",
    )
    op.execute("ALTER TABLE change_requests MODIFY COLUMN device_id TEXT")
    _modify("notifications", "type", "VARCHAR(32) DEFAULT 'info'")


def downgrade() -> None:
    op.execute("ALTER TABLE change_requests MODIFY COLUMN device_id VARCHAR(64)")
    op.create_index(
        "idx_change_requests_type_user_device",
        "change_requests",
        ["request_type", "requested_by", "device_id", "status"],
    )
    _modify("notifications", "type", "VARCHAR(16) DEFAULT 'info'")