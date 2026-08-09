"""Add indexes backing the sub-distribution / operator dashboard queries.

Role-scoped dashboards (sub-distributor, sub-distribution manager, cluster,
operator) filter and GROUP BY the following columns on first load; none of
them had an index, so every role dashboard triggered full-table / file-sort
scans:

devices:
  - current_holder_id, status  -> holder-scoped status breakdowns
                                  (COUNT ... GROUP BY status per holder), plus
                                  the status IN (...) active-device counts and
                                  current_holder_id lookups used by per-holder
                                  distribution analytics.
  - status                     -> the global device status breakdown
                                  (device_service.get_device_stats GROUP BY
                                  status) feeding the management dashboard
                                  (manager / admin) device counts.

distributions:
  - from_user_id                -> sum of distributions sent by a scope.
  - to_user_id, status          -> distributions received by a scope and the
                                   pending_receipt confirmation counts/banner.
  - status                      -> the distribution status breakdown
                                   (distribution_service.get_distribution_stats
                                   GROUP BY status) and status-filtered lists.

users:
  - role, parent_id             -> hierarchy lookups ('role = <r> AND parent_id
                                   IN (...)' for clusters / operators under a
                                   scope) and active/inactive role splits.
  - parent_id                   -> the recursive descendant CTE resolves the
                                   scope purely by parent_id.

All are guarded by existence checks (as in 0033) so they are safe no-ops on
databases already carrying them, and each is reversible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEXES = [
    ("idx_devices_current_holder_status", "devices", ["current_holder_id", "status"]),
    ("idx_devices_status", "devices", ["status"]),
    ("idx_distributions_from_user_id", "distributions", ["from_user_id"]),
    ("idx_distributions_to_user_status", "distributions", ["to_user_id", "status"]),
    ("idx_distributions_status", "distributions", ["status"]),
    ("idx_users_role_parent", "users", ["role", "parent_id"]),
    ("idx_users_parent_id", "users", ["parent_id"]),
]


def _existing_indexes(bind, table: str) -> set:
    inspector = sa.inspect(bind)
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    for name, table, cols in _INDEXES:
        if name not in _existing_indexes(bind, table):
            op.create_index(name, table, cols)


def downgrade() -> None:
    bind = op.get_bind()
    for name, table, _cols in _INDEXES:
        if name in _existing_indexes(bind, table):
            op.drop_index(name, table_name=table)