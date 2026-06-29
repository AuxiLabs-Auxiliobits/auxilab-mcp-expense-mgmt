"""Add user.preferences (in-app settings).

Revision ID: 0006_user_prefs
Revises: 0005_attachment_meta
Create Date: 2026-06-25

NOTE: This revision originally also created the `notifications` table on a parallel branch,
but that table is owned by `0003_notifications`. The history was since linearized into a
single chain, so this revision contributes ONLY `users.preferences`.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_user_prefs"
down_revision = "0005_attachment_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferences", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "preferences")
