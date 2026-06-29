"""Add is_archived to expense_sheets — soft-archive lets Finance/Manager park any sheet
out of active queues without changing its status or audit trail.

Boolean, non-nullable, defaults to FALSE. Additive and backward-compatible.
Guarded against databases where create_all already produced the column (local dev).

Revision ID: 0013_sheet_is_archived
Revises: 0012_sheet_employee_note
Create Date: 2026-06-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_sheet_is_archived"
down_revision = "0012_sheet_employee_note"
branch_labels = None
depends_on = None

_TABLE = "expense_sheets"
_COLUMN = "is_archived"


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}
    if _COLUMN not in existing:
        op.add_column(
            _TABLE,
            sa.Column(_COLUMN, sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}
    if _COLUMN in existing:
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COLUMN)
