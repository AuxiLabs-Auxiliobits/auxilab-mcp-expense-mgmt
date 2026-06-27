"""Add users.source (account origin for hybrid auth: "azure" | "manual" | NULL).

"azure" accounts sign in via Microsoft SSO (no local password); everyone else uses the
local password form. Backward-compatible and reversible; guarded by a column-existence
check so it is a no-op where the baseline `create_all` already added the column.

Revision ID: 0007_user_source
Revises: 0006_notification_archived
Create Date: 2026-06-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_user_source"
down_revision = "0006_notification_archived"
branch_labels = None
depends_on = None

_TABLE = "users"
_COL = "source"


def _has_column(insp) -> bool:
    return any(c["name"] == _COL for c in insp.get_columns(_TABLE))


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not _has_column(insp):
        op.add_column(_TABLE, sa.Column(_COL, sa.String(), nullable=True))
        op.create_index(f"ix_{_TABLE}_{_COL}", _TABLE, [_COL])
    # Backfill: federated accounts (no local password) sign in via Azure; the rest are local.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE users SET source='azure' "
            "WHERE source IS NULL AND password_hash IS NULL AND role <> 'AGENT'"
        )
    )
    bind.execute(
        sa.text("UPDATE users SET source='manual' WHERE source IS NULL AND password_hash IS NOT NULL")
    )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not _has_column(insp):
        return
    op.drop_index(f"ix_{_TABLE}_{_COL}", table_name=_TABLE)
    op.drop_column(_TABLE, _COL)
