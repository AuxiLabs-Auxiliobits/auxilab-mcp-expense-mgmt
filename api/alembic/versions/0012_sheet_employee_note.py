"""Add employee_note to expense_sheets — employee can annotate a returned sheet before
resubmitting; the note is shown to the manager when they review the resubmission.

Nullable, additive, backward-compatible. Guarded against databases where create_all
already produced the column (local dev startup).

Revision ID: 0012_sheet_employee_note
Revises: 0011_sheet_llm_approver_fields
Create Date: 2026-06-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_sheet_employee_note"
down_revision = "0011_sheet_llm_approver_fields"
branch_labels = None
depends_on = None

_TABLE = "expense_sheets"
_COLUMN = "employee_note"


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}
    if _COLUMN not in existing:
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(), nullable=True))


def downgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}
    if _COLUMN in existing:
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COLUMN)
