"""Drop the devices secondary indexes that are not needed for page loading.

Removed:

- ``idx_devices_type`` / ``idx_devices_holder_type`` (added in 0024) were
  meant to cover the report/dashboard grouping queries. Those queries GROUP BY
  on the columns wrapped in ``COALESCE(NULLIF(TRIM(...)))`` (the by-type /
  by-vendor breakdowns in ``device_service`` and the inventory report), so the
  optimizer can never use the covering index -- they execute as full-table
  scans regardless.
- ``idx_devices_status_created`` (added in 0001) only served the optional
  status+date-range filter on the ``/devices`` list. The list query continues
  to use ``idx_devices_status`` (status equality) and ``idx_devices_created_at``
  (pagination ``ORDER BY created_at DESC``), so the composite added nothing
  load-time.

Preserved: the PK and the UNIQUE constraints on ``device_id``,
``serial_number``, ``mac_address`` and ``nuid``. Those are consumed by bulk
upload (dedupe lookups via ``WHERE <col> IN (...)``) and enforce data integrity,
so they stay.

All dropped indexes did not serve any page-load path; their functionality is
provided by the existing paginated SQL queries (which were already running as
scans or via the remaining status / created_at indexes).

Revision ID: 0036
Revises: 0035
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_indexes(bind, table: str) -> set:
    inspector = sa.inspect(bind)
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    for name in (
        "idx_devices_type",
        "idx_devices_holder_type",
        "idx_devices_status_created",
    ):
        if name in _existing_indexes(bind, "devices"):
            op.drop_index(name, table_name="devices")


def downgrade() -> None:
    bind = op.get_bind()
    existing = _existing_indexes(bind, "devices")
    if "idx_devices_type" not in existing:
        op.create_index("idx_devices_type", "devices", ["device_type"])
    if "idx_devices_holder_type" not in existing:
        op.create_index("idx_devices_holder_type", "devices", ["current_holder_type"])
    if "idx_devices_status_created" not in existing:
        op.create_index("idx_devices_status_created", "devices", ["status", "created_at"])