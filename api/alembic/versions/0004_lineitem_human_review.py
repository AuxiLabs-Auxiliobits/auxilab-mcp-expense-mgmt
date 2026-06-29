"""Add line-item human-review flag (receipt-scan vs entered-amount mismatch → Finance).

Revision ID: 0004_lineitem_human_review
Revises: 0003_notifications
Create Date: 2026-06-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_lineitem_human_review"
down_revision = "0003_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "line_items",
        sa.Column("needs_human_review", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("line_items", sa.Column("review_reason", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("line_items", "review_reason")
    op.drop_column("line_items", "needs_human_review")
