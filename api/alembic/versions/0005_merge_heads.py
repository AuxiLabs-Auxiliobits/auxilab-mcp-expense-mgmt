"""Merge the two divergent migration branches into a single head.

The history branched at 0002 into two parallel chains:
  • 0003_notifications        -> 0004_attachment_meta      (notifications table; attachment meta)
  • 0003_lineitem_human_review -> 0004_notifications_prefs  (line-item review flags; user.preferences)

Both originally created the `notifications` table; the duplicate was removed from
0004_notifications_prefs so the canonical table comes from 0003_notifications. This merge
revision rejoins the two heads so `alembic upgrade head` resolves to one head again. No
schema changes of its own.

Revision ID: 0005_merge_heads
Revises: 0004_attachment_meta, 0004_notifications_prefs
Create Date: 2026-06-27
"""
from __future__ import annotations

revision = "0005_merge_heads"
down_revision = ("0004_attachment_meta", "0004_notifications_prefs")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
