"""Add defect/return approval tracking to defects and rename replacement actor columns.

- Rename `defects.resolved_by` -> `replacement_by` and
  `defects.resolved_by_name` -> `replacement_by_name`: these record who assigned
  the replacement device (the `replace_defect_device` actor), not who confirmed
  receipt.
- Rename `defects.replacement_requested_at` -> `return_approved_at`: records when
  the linked return was approved.
- Add `return_approved_by` / `return_approved_by_name` to defects (who approved
  the return).
- Add `defect_approved_by` / `defect_approved_by_name` / `defect_approved_at` to
  defects (who approved the defect report and when).
- New columns are positioned in logical order after the replacement fields;
  `return_approved_at` and `replacement_device_id` are re-positioned to match.

Historical data is backfilled from the existing `returns` table before it is
minimized (see 0011).

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    op.alter_column("defects", "resolved_by", new_column_name="replacement_by", existing_type=sa.Integer())
    op.alter_column("defects", "resolved_by_name", new_column_name="replacement_by_name", existing_type=sa.String(length=255))
    op.alter_column("defects", "replacement_requested_at", new_column_name="return_approved_at", existing_type=sa.DateTime())

    # Position the new approval-tracking columns right after the replacement
    # fields (replacement_confirmed_by_name) so the table reads logically:
    # replacement -> defect approval -> return approval.
    conn.execute(sa.text("ALTER TABLE defects ADD COLUMN defect_approved_by INT NULL AFTER replacement_confirmed_by_name"))
    conn.execute(sa.text("ALTER TABLE defects ADD COLUMN defect_approved_by_name VARCHAR(255) NULL AFTER defect_approved_by"))
    conn.execute(sa.text("ALTER TABLE defects ADD COLUMN defect_approved_at DATETIME NULL AFTER defect_approved_by_name"))
    conn.execute(sa.text("ALTER TABLE defects ADD COLUMN return_approved_by INT NULL AFTER defect_approved_at"))
    conn.execute(sa.text("ALTER TABLE defects ADD COLUMN return_approved_by_name VARCHAR(255) NULL AFTER return_approved_by"))

    # Return approval timestamp belongs with the other return-approval fields
    # (it was renamed in place from replacement_requested_at).
    conn.execute(sa.text("ALTER TABLE defects MODIFY COLUMN return_approved_at DATETIME NULL AFTER return_approved_by_name"))
    # replacement_device_id was created near the end of the original table;
    # move it next to the replacement tracking fields.
    conn.execute(sa.text("ALTER TABLE defects MODIFY COLUMN replacement_device_id VARCHAR(64) NULL AFTER resolved_at"))

    # Backfill from the auto-created returns. The auto-return is created at the
    # moment the defect is approved, so returns.request_date is a proxy for the
    # historical defect approval time. Who approved the defect historically is
    # unrecoverable and left NULL.
    conn.execute(sa.text("""
        UPDATE defects d
        JOIN returns r ON r.defect_id = d.id
        SET d.return_approved_at = r.approval_date,
            d.return_approved_by = r.approved_by,
            d.return_approved_by_name = r.approved_by_name,
            d.defect_approved_at = r.request_date
    """))


def downgrade() -> None:
    op.drop_column("defects", "defect_approved_at")
    op.drop_column("defects", "defect_approved_by_name")
    op.drop_column("defects", "defect_approved_by")
    op.drop_column("defects", "return_approved_by_name")
    op.drop_column("defects", "return_approved_by")
    op.alter_column("defects", "return_approved_at", new_column_name="replacement_requested_at", existing_type=sa.DateTime())
    op.alter_column("defects", "replacement_by_name", new_column_name="resolved_by_name", existing_type=sa.String(length=255))
    op.alter_column("defects", "replacement_by", new_column_name="resolved_by", existing_type=sa.Integer())
