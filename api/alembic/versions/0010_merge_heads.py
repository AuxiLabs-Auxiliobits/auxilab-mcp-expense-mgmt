"""Merge the two divergent migration branches into a single head.

Two parallel lines of work each advanced the schema and were never rejoined:
  • 0005_attachment_meta → 0006_user_prefs → 0007_receipt_library → 0008_…manager_decided_by
    → 0009_sheet_escalation
  • 0005_attachment_meta → 0005_password_reset_tokens → 0006_notification_archived
    → 0007_user_source
This is a no-op merge revision (no schema change) that makes `alembic upgrade head`
resolve to one head again, so subsequent migrations have a single, unambiguous parent.

Revision ID: 0010_merge_heads
Revises: 0007_user_source, 0009_sheet_escalation
Create Date: 2026-06-27
"""
from __future__ import annotations

revision = "0010_merge_heads"
down_revision = ("0007_user_source", "0009_sheet_escalation")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op: a merge revision only reconciles the revision graph."""


def downgrade() -> None:
    """No-op: splitting back into two heads is not meaningful."""
