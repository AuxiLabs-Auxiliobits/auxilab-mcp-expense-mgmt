"""Initial baseline schema.

Frozen explicit DDL for the schema as of the initial release. This migration must NOT use
`SQLModel.metadata.create_all()` — that reflects the *current* models and would silently
include columns added by later migrations, colliding with them. Incremental changes go in
their own revisions (e.g. 0002 adds sheet.title + line-item tax/expense_type_other).

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-14
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agencies",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "SOFT_DELETED", name="agencystatus"), nullable=False),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agencies_name"), "agencies", ["name"], unique=True)

    op.create_table(
        "audit_log",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("actor_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("actor_role", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("agency_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("entity", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_audit_log_timestamp"), "audit_log", ["timestamp"], unique=False)

    op.create_table(
        "agency_policies",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("agency_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("doc_blob_uri", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("published_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agency_policies_agency_id"), "agency_policies", ["agency_id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("role", sa.Enum("EMPLOYEE", "MANAGER", "FINANCE", "ADMIN", "AGENT", name="role"), nullable=False),
        sa.Column("agency_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("entra_object_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_agency_id"), "users", ["agency_id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_entra_object_id"), "users", ["entra_object_id"], unique=False)

    op.create_table(
        "expense_sheets",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("employee_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("agency_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "SUBMITTED", "IN_MANAGER_REVIEW", "RETURNED_TO_EMPLOYEE",
                "IN_FINANCE_REVIEW", "FINANCE_APPROVED", "FINANCE_REJECTED",
                "FINANCE_MANUAL_REVIEW", "APPROVED", "REJECTED", "PAID", name="sheetstatus",
            ),
            nullable=False,
        ),
        sa.Column("period", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "finance_decision",
            sa.Enum("APPROVED", "REJECTED_WITH_COMMENTS", "ROUTED_TO_HUMAN", name="financedecision"),
            nullable=True,
        ),
        sa.Column("finance_decided_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("policy_version_used", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_expense_sheets_agency_id"), "expense_sheets", ["agency_id"], unique=False)
    op.create_index(op.f("ix_expense_sheets_employee_id"), "expense_sheets", ["employee_id"], unique=False)
    op.create_index(op.f("ix_expense_sheets_status"), "expense_sheets", ["status"], unique=False)

    op.create_table(
        "decisions",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sheet_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("actor_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("actor_role", sa.Enum("EMPLOYEE", "MANAGER", "FINANCE", "ADMIN", "AGENT", name="role"), nullable=False),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("llm_model_version", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("policy_version", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("cited_clauses", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["sheet_id"], ["expense_sheets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decisions_sheet_id"), "decisions", ["sheet_id"], unique=False)

    op.create_table(
        "line_items",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sheet_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("employee_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "MEALS_ENTERTAINMENT", "TRAVEL_AIR", "TRAVEL_HOTEL", "TRAVEL_GROUND",
                "OFFICE_SUPPLIES", "SOFTWARE_SUBSCRIPTIONS", "CLIENT_ENTERTAINMENT", "OTHER",
                name="category",
            ),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("merchant", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("receipt_datetime", sa.DateTime(), nullable=True),
        sa.Column("receipt_total", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("has_receipt", sa.Boolean(), nullable=False),
        sa.Column(
            "manager_status",
            sa.Enum(
                "PENDING_MANAGER", "MANAGER_APPROVED", "MANAGER_REJECTED", "INFO_REQUESTED",
                "POLICY_PASS", "POLICY_FAIL", "POLICY_UNCERTAIN", name="lineitemstatus",
            ),
            nullable=False,
        ),
        sa.Column("manager_actor_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("manager_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "policy_status",
            sa.Enum(
                "PENDING_MANAGER", "MANAGER_APPROVED", "MANAGER_REJECTED", "INFO_REQUESTED",
                "POLICY_PASS", "POLICY_FAIL", "POLICY_UNCERTAIN", name="lineitemstatus",
            ),
            nullable=True,
        ),
        sa.Column("policy_clause_ref", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["sheet_id"], ["expense_sheets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "receipt_datetime", "receipt_total", name="uq_line_item_dedupe_key"),
    )
    op.create_index(op.f("ix_line_items_employee_id"), "line_items", ["employee_id"], unique=False)
    op.create_index(op.f("ix_line_items_sheet_id"), "line_items", ["sheet_id"], unique=False)

    op.create_table(
        "attachments",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("line_item_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("blob_uri", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("file_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("scan_status", sa.Enum("PENDING", "CLEAN", "INFECTED", "FAILED", name="scanstatus"), nullable=False),
        sa.Column("ocr_status", sa.Enum("PENDING", "DONE", "FAILED", name="ocrstatus"), nullable=False),
        sa.ForeignKeyConstraint(["line_item_id"], ["line_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attachments_line_item_id"), "attachments", ["line_item_id"], unique=False)

    op.create_table(
        "claim_checks",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("line_item_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sheet_version", sa.Integer(), nullable=False),
        sa.Column("policy_result", sa.JSON(), nullable=True),
        sa.Column("category_result", sa.JSON(), nullable=True),
        sa.Column("duplicate_result", sa.JSON(), nullable=True),
        sa.Column("receipt_result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["line_item_id"], ["line_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_claim_checks_line_item_id"), "claim_checks", ["line_item_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_claim_checks_line_item_id"), table_name="claim_checks")
    op.drop_table("claim_checks")
    op.drop_index(op.f("ix_attachments_line_item_id"), table_name="attachments")
    op.drop_table("attachments")
    op.drop_index(op.f("ix_line_items_sheet_id"), table_name="line_items")
    op.drop_index(op.f("ix_line_items_employee_id"), table_name="line_items")
    op.drop_table("line_items")
    op.drop_index(op.f("ix_decisions_sheet_id"), table_name="decisions")
    op.drop_table("decisions")
    op.drop_index(op.f("ix_expense_sheets_status"), table_name="expense_sheets")
    op.drop_index(op.f("ix_expense_sheets_employee_id"), table_name="expense_sheets")
    op.drop_index(op.f("ix_expense_sheets_agency_id"), table_name="expense_sheets")
    op.drop_table("expense_sheets")
    op.drop_index(op.f("ix_users_entra_object_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_agency_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_agency_policies_agency_id"), table_name="agency_policies")
    op.drop_table("agency_policies")
    op.drop_index(op.f("ix_audit_log_timestamp"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_action"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_agencies_name"), table_name="agencies")
    op.drop_table("agencies")
