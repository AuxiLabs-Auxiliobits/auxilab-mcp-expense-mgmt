"""Add user.preferences (in-app settings).

Revision ID: 0004_notifications_prefs
Revises: 0003_lineitem_human_review
Create Date: 2026-06-25

NOTE: This revision originally also created the `notifications` table, but that table is
owned by the parallel `0003_notifications` revision (which carries the full, current schema:
agency_id / icon / entity). The two branches were merged in `0005_merge_heads`, and the
duplicate `create_table` here was removed so the merged history applies cleanly. This
revision now contributes ONLY `users.preferences`.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_notifications_prefs"
down_revision = "0003_lineitem_human_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferences", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "preferences")
