"""Drop redundant duplicate indexes on the large devices table.

The devices table at scale has a high index/row ratio because it carries several
duplicate or superseded single-column indexes alongside the ones that actually
serve queries. This migration removes only indexes whose work is done by another
index with an identical or wider column prefix, so no query loses an access path
and page-load behaviour is unchanged.

Removed:

- ``idx_devices_status`` (status): a single-column index that is a strict prefix
  of the retained ``idx_devices_status_holder`` (status, current_holder_id).
  Every query that used it (status breakdowns ``GROUP BY status``, the
  ``status='available'`` device pool, status-filtered lists) uses the composite
  with identical results.
- ``idx_devices_nuid``: migration 0001 declared ``nuid VARCHAR(255) UNIQUE``
  inline (which creates a unique index literally named ``nuid``) **and** the
  supplemental index step separately created ``idx_devices_nuid`` on the same
  column. On migration-built databases both exist; the second is a byte-for-byte
  duplicate of the first. Only one unique NUID index is required for the
  constraint (and the bulk-upload dedupe lookups), so this migration drops
  ``idx_devices_nuid`` -- but only when another unique index covering ``nuid``
  remains, so uniqueness is never lost. Databases that never received the
  duplicate (only the inline ``nuid`` index) are a no-op.

Kept: every UNIQUE constraint for device_id / serial_number / mac_address /
nuid (data integrity + bulk-upload). Kept: the page-load indexes
(``idx_devices_current_holder_status``, ``idx_devices_holder_updated``,
``idx_devices_created_at``, ``idx_devices_status_holder``,
``idx_devices_current_distribution_id``).

Revision ID: 0037
Revises: 0036
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_indexes(bind, table: str) -> list:
    inspector = sa.inspect(bind)
    return inspector.get_indexes(table)


def _unique_indexes_on(indexes: list, column: str) -> list:
    """Return the unique indexes that cover exactly the given single column."""
    out = []
    for idx in indexes:
        names = list(idx.get("column_names") or [])
        if names == [column] and idx.get("unique"):
            out.append(idx["name"])
    return out


def upgrade() -> None:
    bind = op.get_bind()
    indexes = {i["name"] for i in _existing_indexes(bind, "devices")}

    if "idx_devices_status" in indexes:
        op.drop_index("idx_devices_status", table_name="devices")

    # Only drop the explicit NUID index when a second unique NUID index exists,
    # so the unique constraint is always preserved.
    nul_members = _unique_indexes_on(_existing_indexes(bind, "devices"), "nuid")
    if "idx_devices_nuid" in indexes and len(nul_members) > 1:
        op.drop_index("idx_devices_nuid", table_name="devices")


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {i["name"] for i in _existing_indexes(bind, "devices")}
    if "idx_devices_status" not in indexes:
        op.create_index("idx_devices_status", "devices", ["status"])
    if "idx_devices_nuid" not in indexes:
        op.create_index("idx_devices_nuid", "devices", ["nuid"], unique=True)