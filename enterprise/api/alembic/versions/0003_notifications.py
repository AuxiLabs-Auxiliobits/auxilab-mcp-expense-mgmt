"""Add the notifications table (in-app, event-driven, per-recipient).

Revision ID: 0003_notifications
Revises: 0002_sheet_title_tax_other
Create Date: 2026-06-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_notifications"
down_revision = "0002_sheet_title_tax_other"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("recipient_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agency_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False, server_default="info"),
        sa.Column("icon", sa.String(), nullable=False, server_default="notifications"),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("body", sa.String(), nullable=False, server_default=""),
        sa.Column("href", sa.String(), nullable=True),
        sa.Column("entity", sa.String(), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])
    op.create_index("ix_notifications_agency_id", "notifications", ["agency_id"])
    op.create_index("ix_notifications_read", "notifications", ["read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_read", table_name="notifications")
    op.drop_index("ix_notifications_agency_id", table_name="notifications")
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_table("notifications")
