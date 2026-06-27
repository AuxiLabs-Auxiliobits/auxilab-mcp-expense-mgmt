"""Add the receipt library (unassigned uploads).

A per-employee, agency-scoped pool of receipts whose bytes are stored in Blob immediately
but are not yet attached to a line item. Attaching one moves it into an `attachments` row
and deletes the library row.

Revision ID: 0007_receipt_library
Revises: 0006_user_prefs
Create Date: 2026-06-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_receipt_library"
down_revision = "0006_user_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "receipt_uploads",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agency_id", sa.String(), nullable=True),
        sa.Column("blob_uri", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("scan_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("ocr_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_receipt_uploads_owner_id", "receipt_uploads", ["owner_id"])
    op.create_index("ix_receipt_uploads_agency_id", "receipt_uploads", ["agency_id"])
    op.create_index("ix_receipt_uploads_uploaded_at", "receipt_uploads", ["uploaded_at"])


def downgrade() -> None:
    op.drop_index("ix_receipt_uploads_uploaded_at", table_name="receipt_uploads")
    op.drop_index("ix_receipt_uploads_agency_id", table_name="receipt_uploads")
    op.drop_index("ix_receipt_uploads_owner_id", table_name="receipt_uploads")
    op.drop_table("receipt_uploads")
