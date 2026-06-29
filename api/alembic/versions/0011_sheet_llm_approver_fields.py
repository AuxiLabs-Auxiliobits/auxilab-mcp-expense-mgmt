"""Add LLM finance-approver outcome fields to expense_sheets (SCOPING §6.3).

Surfaces the AI approver's verdict on the sheet itself so the Finance review UI can show
confidence + routing reason without re-deriving them from the decision trail:
  • llm_confidence       — approver confidence (0..1), set when it decides
  • route_reason         — why it routed to a human (NULL when auto-decided)
  • route_reason_detail  — human-readable detail / cited clause text
All nullable and additive — backward-compatible. Guarded so it is a no-op on databases
where the baseline `create_all` already produced the columns (local dev startup).

Revision ID: 0011_sheet_llm_approver_fields
Revises: 0010_merge_heads
Create Date: 2026-06-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_sheet_llm_approver_fields"
down_revision = "0010_merge_heads"
branch_labels = None
depends_on = None

_TABLE = "expense_sheets"
_COLUMNS = {
    "llm_confidence": sa.Column("llm_confidence", sa.Float(), nullable=True),
    "route_reason": sa.Column("route_reason", sa.String(), nullable=True),
    "route_reason_detail": sa.Column("route_reason_detail", sa.String(), nullable=True),
}


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}
    for name, column in _COLUMNS.items():
        if name not in existing:
            op.add_column(_TABLE, column)


def downgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}
    # SQLite needs batch mode to drop columns; harmless on other dialects too.
    with op.batch_alter_table(_TABLE) as batch:
        for name in reversed(list(_COLUMNS)):
            if name in existing:
                batch.drop_column(name)
