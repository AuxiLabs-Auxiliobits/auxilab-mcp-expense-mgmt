"""Merge the two divergent heads into a single revision line.

  • 0013_sheet_is_archived (main chain)
  • 0008_user_preferences  (stranded branch from a parallel work-stream)

No schema changes — this is a graph-reconciliation revision only.

Revision ID: 0014_merge_heads
Revises: 0013_sheet_is_archived, 0008_user_preferences
Create Date: 2026-06-29
"""
from __future__ import annotations

revision = "0014_merge_heads"
down_revision = ("0013_sheet_is_archived", "0008_user_preferences")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op: merge revision only."""


def downgrade() -> None:
    """No-op."""
