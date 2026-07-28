"""MCP server — the exposed surface is exactly five tools, and each one works offline."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

import local_db.store as store_module
import mcp_server

#: A date inside the default 90-day claim window, computed rather than hard-coded so the
#: suite doesn't start failing once the calendar moves past a literal.
RECENT = date.today() - timedelta(days=1)

#: The published contract. Adding a sixth tool should fail this suite loudly.
EXPECTED_TOOLS = {
    "policy_checker",
    "receipt_parser",
    "category_classifier",
    "duplicate_detector",
    "report_summariser",
}


@pytest.fixture(autouse=True)
def isolated_store(shared_store):
    """Every test in this module runs against a throwaway, seeded database."""
    return shared_store


def registered_tools() -> dict[str, object]:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    return {t.name: t for t in tools}


# --------------------------------------------------------------------------- #
# The exposed surface
# --------------------------------------------------------------------------- #
def test_exactly_five_tools_are_exposed():
    assert set(registered_tools()) == EXPECTED_TOOLS


def test_no_enterprise_tools_leaked():
    """The enterprise build had 61 tools; none of the other 56 may appear here."""
    leaked = {
        "list_users",
        "approve_sheet",
        "reject_sheet",
        "admin_settings",
        "login",
        "get_dashboard",
        "list_notifications",
        "upload_receipt",
        "finance_queue",
        "assistant_chat",
        "whoami",
        "list_agencies",
        "audit_log",
    } & set(registered_tools())
    assert leaked == set()


def test_every_tool_is_documented():
    for name, tool in registered_tools().items():
        assert tool.description, f"{name} has no description"


def test_every_tool_has_an_input_schema():
    for name, tool in registered_tools().items():
        assert tool.inputSchema.get("type") == "object", f"{name} has no input schema"


# --------------------------------------------------------------------------- #
# 1. policy_checker
# --------------------------------------------------------------------------- #
def test_policy_checker_passes_a_compliant_expense():
    result = mcp_server.policy_checker(
        employee_id="emp-001",
        amount=Decimal("40.00"),
        merchant="Noodle House",
        expense_date=RECENT,
        category="Meals & Entertainment",
        has_receipt=True,
    )
    assert result["status"] == "pass"
    assert result["violations"] == []


def test_policy_checker_flags_an_over_cap_expense():
    result = mcp_server.policy_checker(
        employee_id="emp-001",
        amount=Decimal("500.00"),
        merchant="The Chophouse",
        expense_date=RECENT,
        category="Meals & Entertainment",
        has_receipt=True,
    )
    assert result["status"] == "fail"
    assert "OVER_CATEGORY_LIMIT" in {v["code"] for v in result["violations"]}


def test_policy_checker_returns_json_safe_types():
    result = mcp_server.policy_checker(
        employee_id="e", amount=Decimal("1"), merchant="m", expense_date=RECENT
    )
    import json

    json.dumps(result)  # must not raise


def test_policy_checker_does_not_expose_a_clock_override():
    """`today` is a library-level test seam. Exposing it would let a caller decide
    whether its own expense is future-dated or inside the claim window."""
    schema = registered_tools()["policy_checker"].inputSchema
    assert "today" not in schema.get("properties", {})


def test_policy_checker_uses_the_real_clock():
    result = mcp_server.policy_checker(
        employee_id="e",
        amount=Decimal("10"),
        merchant="m",
        expense_date=date.today() + timedelta(days=30),
        has_receipt=True,
    )
    assert "FUTURE_DATE" in {v["code"] for v in result["violations"]}


# --------------------------------------------------------------------------- #
# 2. receipt_parser
# --------------------------------------------------------------------------- #
def test_receipt_parser_from_text():
    result = mcp_server.receipt_parser(
        receipt_text="Marriott Hotels, 2 nights @ $210, Tax $42, Total $462"
    )
    assert result["total"] == "462"
    assert result["reconciles"] is True


def test_receipt_parser_from_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # reads are sandboxed to the working directory
    path = tmp_path / "receipt.txt"
    path.write_text("Cafe, Tax $2.00, Total $22.00", encoding="utf-8")
    result = mcp_server.receipt_parser(file_path=str(path))
    assert result["reconciles"] is True


def test_receipt_parser_requires_input():
    with pytest.raises(ValueError, match="receipt_text or file_path"):
        mcp_server.receipt_parser()


def test_receipt_text_takes_precedence_over_file_path(tmp_path):
    path = tmp_path / "receipt.txt"
    path.write_text("Ignored, Total $1.00", encoding="utf-8")
    result = mcp_server.receipt_parser(
        receipt_text="Used, Tax $2.00, Total $22.00", file_path=str(path)
    )
    assert result["merchant"] == "Used"


# --------------------------------------------------------------------------- #
# File-access sandbox
# --------------------------------------------------------------------------- #
def test_reads_are_sandboxed_to_the_working_directory_by_default(tmp_path, monkeypatch):
    """Secure by default: without configuration, only the working directory is readable."""
    monkeypatch.delenv("EXPENSE_RECEIPT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    inside = tmp_path / "receipt.txt"
    inside.write_text("Shop, Tax $1.00, Total $11.00", encoding="utf-8")
    assert mcp_server.receipt_parser(file_path=str(inside))["reconciles"] is True


def test_a_file_outside_the_working_directory_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("EXPENSE_RECEIPT_DIR", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    outside = tmp_path / "secret.txt"
    outside.write_text("nothing to see", encoding="utf-8")
    with pytest.raises(ValueError, match="must be inside"):
        mcp_server.receipt_parser(file_path=str(outside))


def test_the_refusal_explains_how_to_change_it(tmp_path, monkeypatch):
    """A security boundary nobody can find their way past is a usability bug."""
    monkeypatch.delenv("EXPENSE_RECEIPT_DIR", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    (tmp_path / "secret.txt").write_text("x", encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        mcp_server.receipt_parser(file_path=str(tmp_path / "secret.txt"))
    message = str(excinfo.value)
    assert "EXPENSE_RECEIPT_DIR" in message
    assert str(workdir) in message


def test_the_sandbox_can_be_opted_out_of(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPENSE_RECEIPT_DIR", mcp_server.SANDBOX_DISABLED)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    outside = tmp_path / "elsewhere.txt"
    outside.write_text("Shop, Tax $1.00, Total $11.00", encoding="utf-8")
    assert mcp_server.receipt_parser(file_path=str(outside))["reconciles"] is True


def test_sandbox_allows_a_file_inside_the_root(tmp_path, monkeypatch):
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    path = receipts / "receipt.txt"
    path.write_text("Shop, Tax $1.00, Total $11.00", encoding="utf-8")

    monkeypatch.setenv("EXPENSE_RECEIPT_DIR", str(receipts))
    assert mcp_server.receipt_parser(file_path=str(path))["reconciles"] is True


def test_sandbox_blocks_a_file_outside_the_root(tmp_path, monkeypatch):
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("nothing to see", encoding="utf-8")

    monkeypatch.setenv("EXPENSE_RECEIPT_DIR", str(receipts))
    with pytest.raises(ValueError, match="must be inside"):
        mcp_server.receipt_parser(file_path=str(outside))


def test_sandbox_cannot_be_escaped_by_traversal(tmp_path, monkeypatch):
    """`../` is resolved away before the containment check, not after."""
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    (tmp_path / "secret.txt").write_text("nothing to see", encoding="utf-8")

    monkeypatch.setenv("EXPENSE_RECEIPT_DIR", str(receipts))
    with pytest.raises(ValueError, match="must be inside"):
        mcp_server.receipt_parser(file_path=str(receipts / ".." / "secret.txt"))


# --------------------------------------------------------------------------- #
# 3. category_classifier
# --------------------------------------------------------------------------- #
def test_category_classifier():
    result = mcp_server.category_classifier(description="Airport transfer", merchant="Uber")
    assert result["category"] == "Travel - Ground"
    assert result["confidence"] >= 0.9


def test_category_classifier_merchant_is_optional():
    assert mcp_server.category_classifier(description="Team lunch")["category"] == (
        "Meals & Entertainment"
    )


# --------------------------------------------------------------------------- #
# 4. duplicate_detector
# --------------------------------------------------------------------------- #
def test_duplicate_detector_uses_stored_history_by_default():
    result = mcp_server.duplicate_detector(
        employee_id="emp-002",
        total=Decimal("42.50"),
        receipt_datetime=datetime(2026, 6, 5, 7, 30),
    )
    assert result["risk"] == "high"
    assert result["compared_against"] > 0


def test_duplicate_detector_finds_nothing_for_a_novel_expense():
    result = mcp_server.duplicate_detector(
        employee_id="emp-002",
        total=Decimal("19.99"),
        receipt_datetime=datetime(2026, 6, 9, 9, 0),
    )
    assert result["risk"] == "none"


def test_duplicate_detector_accepts_explicit_history():
    result = mcp_server.duplicate_detector(
        employee_id="emp-777",
        total=Decimal("50.00"),
        receipt_datetime=datetime(2026, 6, 1, 12, 0),
        history=[
            {
                "line_item_id": "x-1",
                "employee_id": "emp-777",
                "receipt_datetime": "2026-06-01T12:00:00",
                "total": "50.00",
            }
        ],
    )
    assert result["risk"] == "high"
    assert result["compared_against"] == 1


def test_explicit_empty_history_bypasses_the_database():
    result = mcp_server.duplicate_detector(
        employee_id="emp-002",
        total=Decimal("42.50"),
        receipt_datetime=datetime(2026, 6, 5, 7, 30),
        history=[],
    )
    assert result["risk"] == "none"
    assert result["compared_against"] == 0


# --------------------------------------------------------------------------- #
# 5. report_summariser
# --------------------------------------------------------------------------- #
def test_report_summariser_reads_the_database():
    result = mcp_server.report_summariser()
    assert result["item_count"] == 6
    assert result["narrative"]


def test_report_summariser_narrows_to_one_employee():
    result = mcp_server.report_summariser(employee_id="emp-001")
    assert result["item_count"] == 3


def test_report_summariser_accepts_explicit_items():
    result = mcp_server.report_summariser(
        items=[
            {"category": "Travel - Air", "amount": "320.00", "is_compliant": True},
            {"category": "Office Supplies", "amount": "28.50", "is_compliant": False},
        ]
    )
    assert result["item_count"] == 2
    assert result["violation_count"] == 1
    assert result["compliance_rate_pct"] == 50.0


# --------------------------------------------------------------------------- #
# Audit trail
# --------------------------------------------------------------------------- #
def test_tool_runs_are_recorded(isolated_store):
    before = len(isolated_store.recent_analyses(limit=100))
    mcp_server.category_classifier(description="Team lunch", merchant="Noodle House")
    after = isolated_store.recent_analyses(limit=100)
    assert len(after) == before + 1
    assert after[0]["tool"] == "category_classifier"


def test_a_broken_audit_write_does_not_break_the_tool(monkeypatch):
    """Bookkeeping is best-effort; it must never take a tool call down with it."""

    def explode(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(store_module.ExpenseStore, "record_analysis", explode)
    result = mcp_server.category_classifier(description="Team lunch", merchant="Noodle House")
    assert result["category"] == "Meals & Entertainment"
