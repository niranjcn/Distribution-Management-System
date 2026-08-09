"""Normalize devices held by sub-distribution employees to their sub-distributor.

A sub-distribution employee acts on behalf of their parent sub-distributor
branch, so a device whose holder is an employee should be attributed to the
sub-distributor level. Earlier flows stored ``current_holder_type =
'sub_distribution_employee'`` on the employee themselves. This migration
re-points those rows at the parent sub-distributor so the device is shown
under the branch, matching the corrected write paths.

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Re-point devices held by a sub-distribution employee at their parent
    # sub-distributor branch. Only rows whose parent is a sub_distributor are
    # touched; anything else is left alone.
    op.execute("""
    UPDATE devices d
    JOIN users e ON d.current_holder_id = e.id
    JOIN users p ON e.parent_id = p.id
    SET d.current_holder_id = p.id,
        d.current_holder_name = p.name,
        d.current_holder_type = 'sub_distributor'
    WHERE d.current_holder_type = 'sub_distribution_employee'
      AND e.role = 'sub_distribution_employee'
      AND p.role = 'sub_distributor'
    """)

    # Fallback for employees whose parent is not a sub_distributor: keep the
    # holder but correct the type so reports/hierarchy show the branch level.
    op.execute("""
    UPDATE devices d
    JOIN users e ON d.current_holder_id = e.id
    SET d.current_holder_type = 'sub_distributor'
    WHERE d.current_holder_type = 'sub_distribution_employee'
      AND e.role = 'sub_distribution_employee'
    """)


def downgrade() -> None:
    # No reliable way to restore the original employee attribution.
    pass
