"""Add expense_sheets.manager_decided_by (manager's "Reviewed" history).

Records the manager who last advanced or returned a sheet out of manager review, so the
manager portal can show exactly the sheets they personally decided without scanning the
audit log (SCOPING §6.2).

Revision ID: 0008_sheet_manager_decided_by
Revises: 0007_receipt_library
Create Date: 2026-06-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_sheet_manager_decided_by"
down_revision = "0007_receipt_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expense_sheets", sa.Column("manager_decided_by", sa.String(), nullable=True)
    )
    op.create_index(
        "ix_expense_sheets_manager_decided_by",
        "expense_sheets",
        ["manager_decided_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_expense_sheets_manager_decided_by", table_name="expense_sheets")
    op.drop_column("expense_sheets", "manager_decided_by")
