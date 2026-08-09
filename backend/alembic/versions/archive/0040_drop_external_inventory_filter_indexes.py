"""Drop the filter-only indexes on the external inventory tables.

Follows 0036-0039. On external inventory the list/report pages run optional
*filter* parameters (``type``, ``status``, ``item_id``) while both the default
load path and every bulk-import/dedupe path are index-free or keyed by the
unique ``(identifier_type, identifier)`` / ``name`` constraints.

Removed:

external_inventory_items
  - ``idx_external_inventory_items_device_type`` (device_type): only used when
    the list is filtered by ``?type=...``; the default load filters by
    ``quantity > 0`` only, and bulk import/dedup issues SELECTs on
    ``(identifier_type, identifier)`` and ``name``.
  - ``idx_external_inventory_items_status`` (status): only used when the list
    is filtered by ``?status=...``, which the frontend does not send by
    default; never referenced by import or distribution flows (the bulk
    distribute path reads rows FOR UPDATE by id and validates status in code).

external_device_history
  - ``idx_external_device_history_item_id`` (item_id): the distribution history
    report filters by ``item_id`` only as an optional parameter; the default
    report sorts by ``distributed_at`` (whose index is retained).

Kept: every UNIQUE constraint (bulk-import dedupe + data integrity), all
page-load indexes on the other tables, and ``idx_external_device_history``
``distributed_at`` (report ordering). ``idx_api_activity_logs_created_at``,
``idx_token_blacklist_expires_at`` and the reassignment/change/notification/
defect/return/distribution/user indexes are all load- or maintenance-critical
and are intentionally untouched.

All drops are guarded by existence checks and reverse cleanly.

Revision ID: 0040
Revises: 0039
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, index_name, columns_for_recreate)
_DROPS = [
    ("external_inventory_items", "idx_external_inventory_items_device_type", ["device_type"]),
    ("external_inventory_items", "idx_external_inventory_items_status", ["status"]),
    ("external_device_history", "idx_external_device_history_item_id", ["item_id"]),
]


def _existing_indexes(bind, table: str) -> set:
    inspector = sa.inspect(bind)
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    for table, index_name, _cols in _DROPS:
        if index_name in _existing_indexes(bind, table):
            op.drop_index(index_name, table_name=table)


def downgrade() -> None:
    bind = op.get_bind()
    for table, index_name, cols in _DROPS:
        if index_name not in _existing_indexes(bind, table):
            op.create_index(index_name, table, cols)