"""Add password_reset_tokens (local forgot/reset-password flow).

Single-use, time-limited reset tokens, stored as a SHA-256 hash. Backward-compatible and
reversible: guarded by an existence check so it is a no-op on databases where the baseline
`create_all` already produced the table (and a clean create on existing prod DBs at 0004).

Revision ID: 0005_password_reset_tokens
Revises: 0004_attachment_meta
Create Date: 2026-06-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_password_reset_tokens"
down_revision = "0004_attachment_meta"
branch_labels = None
depends_on = None

_TABLE = "password_reset_tokens"


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if _TABLE in insp.get_table_names():
        return  # already present (baseline create_all) — nothing to do
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(f"ix_{_TABLE}_user_id", _TABLE, ["user_id"])
    op.create_index(f"ix_{_TABLE}_token_hash", _TABLE, ["token_hash"], unique=True)


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if _TABLE not in insp.get_table_names():
        return
    op.drop_index(f"ix_{_TABLE}_token_hash", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_user_id", table_name=_TABLE)
    op.drop_table(_TABLE)
