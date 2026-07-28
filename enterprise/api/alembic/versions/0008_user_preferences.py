"""Add users.preferences (free-form JSON owned by the Settings page).

Backward-compatible and reversible; guarded by a column-existence check so it is a no-op
where the baseline `create_all` already added the column.

Revision ID: 0008_user_preferences
Revises: 0007_user_source
Create Date: 2026-06-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_user_preferences"
down_revision = "0007_user_source"
branch_labels = None
depends_on = None

_TABLE = "users"
_COL = "preferences"


def _has_column(insp) -> bool:
    return any(c["name"] == _COL for c in insp.get_columns(_TABLE))


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if _has_column(insp):
        return
    op.add_column(_TABLE, sa.Column(_COL, sa.JSON(), nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not _has_column(insp):
        return
    op.drop_column(_TABLE, _COL)
