"""Initial baseline schema.

Creates all tables from SQLModel metadata. This is a pragmatic baseline migration; from
here, generate incremental migrations with `alembic revision --autogenerate -m "..."`.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-14
"""
from __future__ import annotations

from alembic import op
from sqlmodel import SQLModel

from app import models  # noqa: F401  — register tables on SQLModel.metadata

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    SQLModel.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    SQLModel.metadata.drop_all(bind=op.get_bind())
