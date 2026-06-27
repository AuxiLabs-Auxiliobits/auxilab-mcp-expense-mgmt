"""Add notifications.archived (archive support for the notification center).

Backward-compatible and reversible; guarded by a column-existence check so it is a no-op on
databases where the baseline `create_all` already added the column.

Revision ID: 0006_notification_archived
Revises: 0005_password_reset_tokens
Create Date: 2026-06-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_notification_archived"
down_revision = "0005_password_reset_tokens"
branch_labels = None
depends_on = None

_TABLE = "notifications"
_COL = "archived"


def _has_column(insp) -> bool:
    return any(c["name"] == _COL for c in insp.get_columns(_TABLE))


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if _has_column(insp):
        return
    op.add_column(_TABLE, sa.Column(_COL, sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index(f"ix_{_TABLE}_{_COL}", _TABLE, [_COL])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not _has_column(insp):
        return
    op.drop_index(f"ix_{_TABLE}_{_COL}", table_name=_TABLE)
    op.drop_column(_TABLE, _COL)
