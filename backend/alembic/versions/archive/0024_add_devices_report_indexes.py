"""Add covering indexes on devices.device_type and devices.current_holder_type.

The hierarchy/inventory reports GROUP BY device_type and current_holder_type
across the (large) devices table. Without an index on those columns MySQL
falls back to a full table scan ("Using temporary; file sort"), which is the
dominant cost of loading the report overview. These two covering indexes let
the GROUP BY queries run entirely from the index.

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("idx_devices_type", "devices", ["device_type"])
    op.create_index("idx_devices_holder_type", "devices", ["current_holder_type"])


def downgrade() -> None:
    op.drop_index("idx_devices_holder_type", table_name="devices")
    op.drop_index("idx_devices_type", table_name="devices")
