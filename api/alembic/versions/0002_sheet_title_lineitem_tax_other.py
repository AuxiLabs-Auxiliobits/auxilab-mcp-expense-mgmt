"""Add sheet title and line-item tax / expense_type_other (expense module change req).

Revision ID: 0002_sheet_title_tax_other
Revises: 0001_initial
Create Date: 2026-06-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_sheet_title_tax_other"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expense_sheets", sa.Column("title", sa.String(), nullable=True))
    op.add_column("line_items", sa.Column("expense_type_other", sa.String(), nullable=True))
    op.add_column("line_items", sa.Column("tax", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("line_items", "tax")
    op.drop_column("line_items", "expense_type_other")
    op.drop_column("expense_sheets", "title")
