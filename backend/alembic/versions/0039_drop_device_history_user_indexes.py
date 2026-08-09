"""Drop the per-user composite indexes on the large device_history table.

device_history carries the second-largest index footprint in the database
(~242 MB at 898K+ rows). Three of its indexes exist only to serve the
"Recent Activity" widget on cluster/operator dashboards, which reads the last
N rows for a single user across ``performed_by`` / ``from_user_id`` /
``to_user_id``. Dropping them trades a small speed-up of that one widget for a
meaningful index-space reclaim (~60-90 MB) and faster INSERTs on every history
write, without touching any page-load path:

Removed:
  - ``idx_device_history_performed_by`` (performed_by, timestamp DESC)
  - ``idx_device_history_from_user`` (from_user_id, timestamp DESC)
  - ``idx_device_history_to_user`` (to_user_id, timestamp DESC)

Kept (all load / bulk critical):
  - ``idx_device_history_device_id`` (device detail page, Track, DELETE on device)
  - ``idx_device_history_distribution_id`` (distribution membership lookups)
  - ``idx_device_history_timestamp`` (recent-activity + report feeds)
  - PRIMARY, ``id``

All drops are guarded by existence checks and are no-ops on databases that
never received the index.

Revision ID: 0039
Revises: 0038
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEXES = [
    ("idx_device_history_performed_by", ["performed_by", "timestamp"]),
    ("idx_device_history_from_user", ["from_user_id", "timestamp"]),
    ("idx_device_history_to_user", ["to_user_id", "timestamp"]),
]


def _existing_indexes(bind, table: str) -> set:
    inspector = sa.inspect(bind)
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    current = _existing_indexes(bind, "device_history")
    for name, _cols in _INDEXES:
        if name in current:
            op.drop_index(name, table_name="device_history")


def downgrade() -> None:
    bind = op.get_bind()
    current = _existing_indexes(bind, "device_history")
    for name, cols in _INDEXES:
        if name not in current:
            op.create_index(name, "device_history", cols)
