"""Drop unused / redundant indexes across all remaining tables.

Follows 0036/0037 (which trimmed the large ``devices`` table). Every index
removed here is either byte-for-byte duplicated by another index with the same
or a wider column prefix, or sits on a table/column that no query reads.

Removed:

distributions
  - ``idx_distributions_to_status`` (to_user_id, status): identical to the
    retained ``idx_distributions_to_user_status`` (0034).
  - ``idx_distributions_status`` (status): strict prefix of the retained
    ``idx_distributions_status_created`` (status, created_at).
  - ``idx_distributions_from_user_id`` (from_user_id): strict prefix of the
    retained ``idx_distributions_from_user_created`` (from_user_id, created_at).

users
- ``idx_users_parent_id`` (parent_id): strict prefix of the retained
  ``idx_users_parent_role`` (parent_id, role) which already backs the recursive
  descendant CTE and every ``parent_id = ... AND role = ...`` lookup.
- ``idx_users_role_status`` (role): strict prefix of the retained
  ``idx_users_role_parent`` (role, parent_id) which serves every role-equality
  lookup (including the ``status='active'`` filters evaluated against it).

api_activity_logs (write-only table: INSERT via activity_logger + DELETE by
created_at in activity_log_cleanup; the activity feed reads the denormalised
``activities`` table instead)
  - ``idx_api_activity_logs_actor_name`` (actor_name): never read.
  - ``idx_api_activity_logs_path`` (path): never read.
  - ``idx_api_activity_logs_path_status`` (path, status_code): never read.
  ``idx_api_activity_logs_created_at`` is kept for the cleanup DELETE range.

activities
  - ``idx_activities_actor`` (actor): only ever referenced through ``LIKE '%..%'``
    in the admin feed (index-defeating), never an equality/range lookup.
  - ``idx_activities_date`` (activity_date): shadowed by the always-filtered
    ``idx_activities_category_date`` (category, activity_date).

external_device_history
  - ``idx_external_device_history_recipient`` (recipient_user_id): the
    distribution-history report filters by item_id / identifier_type / device_type
    / text columns only; no query reads recipient_user_id.

Kept: every UNIQUE constraint (data integrity + bulk-upload). Kept: all
page-load and per-user feed indexes on notifications, change_requests, defects,
returns, device_history, token_blacklist, reassignment_requests,
digital_identities, and the remaining external inventory indexes.

All drops are guarded by existence checks and the wider/duplicate index is
verified to still exist, so a drop is a no-op on any database that never
received the redundant index.

Revision ID: 0038
Revises: 0037
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (index_name, columns_to_recreate, (keep_name, ...))
# keep_names must all exist before the drop is performed.
_DROPS = {
    "distributions": [
        ("idx_distributions_to_status", ["to_user_id", "status"], ["idx_distributions_to_user_status"]),
        ("idx_distributions_status", ["status"], ["idx_distributions_status_created"]),
        ("idx_distributions_from_user_id", ["from_user_id"], ["idx_distributions_from_user_created"]),
    ],
    "users": [
        ("idx_users_parent_id", ["parent_id"], ["idx_users_parent_role"]),
        ("idx_users_role_status", ["role"], ["idx_users_role_parent"]),
    ],
    "api_activity_logs": [
        ("idx_api_activity_logs_actor_name", ["actor_name"], []),
        ("idx_api_activity_logs_path", ["path"], []),
        ("idx_api_activity_logs_path_status", ["path", "status_code"], []),
    ],
    "activities": [
        ("idx_activities_actor", ["actor"], []),
        ("idx_activities_date", ["activity_date"], ["idx_activities_category_date"]),
    ],
    "external_device_history": [
        ("idx_external_device_history_recipient", ["recipient_user_id"], []),
    ],
}


def _existing_indexes(bind, table: str) -> set:
    inspector = sa.inspect(bind)
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    for table, drops in _DROPS.items():
        current = _existing_indexes(bind, table)
        for name, _cols, keep_names in drops:
            if name in current and all(k in current for k in keep_names):
                op.drop_index(name, table_name=table)


def downgrade() -> None:
    bind = op.get_bind()
    for table, drops in _DROPS.items():
        current = _existing_indexes(bind, table)
        for name, cols, _keep_names in drops:
            if name not in current:
                op.create_index(name, table, cols)