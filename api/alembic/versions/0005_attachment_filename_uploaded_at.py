"""Add attachment filename + uploaded_at (receipt visibility for manager/finance).

Revision ID: 0004_attachment_meta
Revises: 0003_notifications
Create Date: 2026-06-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_attachment_meta"
down_revision = "0003_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attachments", sa.Column("filename", sa.String(), nullable=True))
    op.add_column(
        "attachments",
        sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_column("attachments", "uploaded_at")
    op.drop_column("attachments", "filename")
