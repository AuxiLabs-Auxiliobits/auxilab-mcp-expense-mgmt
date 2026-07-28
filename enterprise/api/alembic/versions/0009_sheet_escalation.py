"""Add expense_sheets escalation tracking (SLA / aging alerts, SCOPING §6.4, §8).

`last_escalation_level` (0 none / 1 warning / 2 critical) and `last_escalated_at` let the
escalation job alert once per level per stage without re-notifying every run.

Revision ID: 0009_sheet_escalation
Revises: 0008_sheet_manager_decided_by
Create Date: 2026-06-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_sheet_escalation"
down_revision = "0008_sheet_manager_decided_by"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expense_sheets",
        sa.Column("last_escalation_level", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "expense_sheets",
        sa.Column("last_escalated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("expense_sheets", "last_escalated_at")
    op.drop_column("expense_sheets", "last_escalation_level")
