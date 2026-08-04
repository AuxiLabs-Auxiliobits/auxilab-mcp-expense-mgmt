"""Demo handlers.

``app.py`` keeps every handler free of Gradio imports so they can be exercised directly —
which also means the demo keeps working (as a CLI) on machines where Gradio won't import.
These tests hold that boundary in place.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

import app

RECENT = (date.today() - timedelta(days=1)).isoformat()

pytestmark = pytest.mark.usefixtures("shared_store")


# --------------------------------------------------------------------------- #
# 1. Policy Checker
# --------------------------------------------------------------------------- #
def test_policy_pass_renders_a_pass_report():
    report, raw = app.run_policy_checker(
        employee_id="emp-001",
        amount="40.00",
        merchant="Noodle House",
        expense_date=RECENT,
        category="Meals & Entertainment",
        description="Team lunch",
        has_receipt=True,
        receipt_total="",
    )
    assert "PASS" in report
    assert raw["status"] == "pass"


def test_policy_failure_lists_each_violation():
    report, raw = app.run_policy_checker(
        employee_id="emp-001",
        amount="187.00",
        merchant="The Chophouse",
        expense_date=RECENT,
        category="Meals & Entertainment",
        description="Client dinner",
        has_receipt=True,
        receipt_total="",
    )
    assert "FAIL" in report
    assert "OVER_CATEGORY_LIMIT" in report
    assert raw["status"] == "fail"


def test_blank_receipt_total_skips_the_match_check():
    _, raw = app.run_policy_checker(
        employee_id="emp-001",
        amount="40.00",
        merchant="X",
        expense_date=RECENT,
        category="Meals & Entertainment",
        description="",
        has_receipt=True,
        receipt_total="   ",
    )
    assert "AMOUNT_MISMATCH" not in {v["code"] for v in raw["violations"]}


def test_receipt_total_mismatch_is_reported():
    _, raw = app.run_policy_checker(
        employee_id="emp-001",
        amount="50.00",
        merchant="X",
        expense_date=RECENT,
        category="Meals & Entertainment",
        description="",
        has_receipt=True,
        receipt_total="47.50",
    )
    assert "AMOUNT_MISMATCH" in {v["code"] for v in raw["violations"]}


def test_non_numeric_amount_gives_a_readable_error():
    with pytest.raises(ValueError, match="Amount must be a number"):
        app.run_policy_checker(
            employee_id="emp-001",
            amount="lots",
            merchant="X",
            expense_date=RECENT,
            category="Meals & Entertainment",
            description="",
            has_receipt=True,
            receipt_total="",
        )


def test_malformed_date_is_rejected():
    with pytest.raises(ValueError):
        app.run_policy_checker(
            employee_id="emp-001",
            amount="10.00",
            merchant="X",
            expense_date="last tuesday",
            category="Meals & Entertainment",
            description="",
            has_receipt=True,
            receipt_total="",
        )


# --------------------------------------------------------------------------- #
# 2. Receipt Parser
# --------------------------------------------------------------------------- #
def test_receipt_parser_reports_reconciliation():
    report, rows, raw = app.run_receipt_parser(app.SAMPLE_RECEIPT, None)
    assert "Reconciles" in report
    assert raw["reconciles"] is True
    assert rows[-1][0] == "TOTAL"
    assert rows[-2][0] == "Tax"


def test_receipt_parser_flags_a_bad_total():
    tampered = app.SAMPLE_RECEIPT.replace("Total                  48.88", "Total   58.88")
    report, _, raw = app.run_receipt_parser(tampered, None)
    assert "does not reconcile" in report.lower()
    assert raw["reconciles"] is False


def test_receipt_parser_reads_an_uploaded_file(tmp_path):
    path = tmp_path / "receipt.txt"
    path.write_text("Corner Shop, Tax $2.00, Total $22.00", encoding="utf-8")
    _, _, raw = app.run_receipt_parser("", str(path))
    assert raw["merchant"] == "Corner Shop"


def test_uploaded_file_wins_over_pasted_text(tmp_path):
    path = tmp_path / "receipt.txt"
    path.write_text("From File, Tax $1.00, Total $11.00", encoding="utf-8")
    _, _, raw = app.run_receipt_parser("From Textbox, Total $99.00", str(path))
    assert raw["merchant"] == "From File"


def test_empty_receipt_input_is_rejected():
    with pytest.raises(ValueError, match="Paste receipt text or upload"):
        app.run_receipt_parser("   ", None)


# --------------------------------------------------------------------------- #
# 3. Category Classifier
# --------------------------------------------------------------------------- #
def test_classifier_reports_the_category_and_confidence():
    report, raw = app.run_category_classifier("Airport transfer", "Uber")
    assert "Travel - Ground" in report
    assert "high" in report
    assert raw["confidence"] >= 0.9


def test_classifier_marks_low_confidence():
    report, raw = app.run_category_classifier("Blue widget", "AcmeCo")
    assert "low" in report
    assert raw["category"] == "Other"


def test_classifier_needs_some_input():
    with pytest.raises(ValueError, match="description or a merchant"):
        app.run_category_classifier("", "  ")


# --------------------------------------------------------------------------- #
# 4. Duplicate Detector
# --------------------------------------------------------------------------- #
def test_duplicate_detector_finds_the_seeded_pair():
    report, rows, raw = app.run_duplicate_detector("emp-002", "42.50", "2026-06-05T07:30:00", 3)
    assert "HIGH risk" in report
    assert raw["risk"] == "high"
    assert rows and rows[0][1] == "EXACT_KEY"


def test_duplicate_detector_reports_a_clean_result():
    report, rows, raw = app.run_duplicate_detector("emp-002", "19.99", "2026-06-09T09:00:00", 3)
    assert "No duplicates" in report
    assert rows == []
    assert raw["risk"] == "none"


def test_duplicate_detector_accepts_a_blank_timestamp():
    _, _, raw = app.run_duplicate_detector("emp-002", "42.50", "   ", 3)
    assert raw["risk"] in {"none", "medium", "high"}


def test_duplicate_detector_rejects_a_bad_total():
    with pytest.raises(ValueError, match="Total must be a number"):
        app.run_duplicate_detector("emp-002", "free", "", 3)


# --------------------------------------------------------------------------- #
# 5. Report Summariser
# --------------------------------------------------------------------------- #
def test_summariser_reads_the_database():
    report, rows, raw = app.run_report_summariser("", "")
    assert "compliant" in report
    assert rows[-1][0] == "TOTAL"
    assert raw["compliance_rate_pct"] >= 0


def test_summariser_narrows_to_one_employee():
    report, _, _ = app.run_report_summariser("emp-001", "")
    assert "emp-001" in report


def test_summariser_accepts_pasted_json():
    items = json.dumps([{"category": "Travel - Air", "amount": "320.00", "is_compliant": True}])
    report, rows, raw = app.run_report_summariser("", items)
    assert raw["compliance_rate_pct"] == 100.0
    assert "supplied directly" in report
    assert rows[0][0] == "Travel - Air"


def test_pasted_json_overrides_the_employee_filter():
    items = json.dumps([{"category": "Other", "amount": "1.00", "is_compliant": False}])
    _, _, raw = app.run_report_summariser("emp-001", items)
    assert raw["violation_count"] == 1


def test_summariser_handles_an_unknown_employee():
    report, rows, raw = app.run_report_summariser("nobody-at-all", "")
    assert "Nothing to summarise" in report
    assert rows == []
    assert raw == {}


def test_summariser_rejects_malformed_json():
    with pytest.raises(json.JSONDecodeError):
        app.run_report_summariser("", "{not json")


def test_summariser_rejects_items_missing_required_fields():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        app.run_report_summariser("", json.dumps([{"category": "Travel - Air"}]))


# --------------------------------------------------------------------------- #
# Status panel and formatting helpers
# --------------------------------------------------------------------------- #
def test_display_path_abbreviates_home():
    """Keeps the status line short and keeps a username out of screenshots."""
    from pathlib import Path

    shown = app._display_path(str(Path.home() / "somewhere" / "sqlite.db"))
    assert shown == "~/somewhere/sqlite.db"


def test_display_path_leaves_paths_outside_home_alone():
    outside = "/var/lib/expense/sqlite.db"
    assert app._display_path(outside) == outside


def test_database_status_reports_counts(shared_store):
    status = app.database_status()
    assert str(shared_store.stats()["line_items"]) in status
    assert "line items" in status


def test_money_formatting_uses_thousands_separators():
    assert app._money(Decimal("1234567.5")) == "1,234,567.50"


def test_money_formatting_pads_to_two_places():
    assert app._money(Decimal("5")) == "5.00"


# --------------------------------------------------------------------------- #
# Input coercion — Gradio hands back None for a cleared component
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("value", "expected"), [(None, ""), ("", ""), ("  x  ", "x"), (7, "7"), (False, "False")]
)
def test_text_coercion(value, expected):
    assert app._text(value) == expected


def test_cleared_optional_fields_do_not_crash():
    """A None from a cleared Textbox must not surface as AttributeError."""
    _, raw = app.run_policy_checker(
        employee_id=None,
        amount="40.00",
        merchant=None,
        expense_date=RECENT,
        category="Meals & Entertainment",
        description=None,
        has_receipt=True,
        receipt_total=None,
    )
    assert raw["status"] == "pass"


def test_cleared_duplicate_timestamp_does_not_crash():
    _, _, raw = app.run_duplicate_detector("emp-002", "42.50", None, 3)
    assert "risk" in raw


def test_cleared_summariser_fields_fall_back_to_the_database():
    report, rows, raw = app.run_report_summariser(None, None)
    assert "stored item(s) for all employees" in report
    assert rows and rows[-1][0] == "TOTAL"
    assert raw["total_by_category"]


def test_bad_date_names_the_expected_format():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        app.run_policy_checker(
            employee_id="e",
            amount="1",
            merchant="m",
            expense_date="14/06/2026",
            category=None,
            description="",
            has_receipt=True,
            receipt_total="",
        )


def test_bad_timestamp_names_the_expected_format():
    with pytest.raises(ValueError, match="ISO timestamp"):
        app.run_duplicate_detector("emp-002", "42.50", "yesterday", 3)


def test_slider_float_is_accepted():
    """gr.Slider yields a float even with step=1."""
    _, _, raw = app.run_duplicate_detector("emp-002", "42.50", "2026-06-05T07:30:00", 3.0)
    assert raw["risk"] == "high"


def test_non_list_json_gives_a_useful_message():
    """Iterating a dict would yield keys and produce a baffling pydantic error."""
    with pytest.raises(ValueError, match="Expected a JSON list"):
        app.run_report_summariser("", '{"category": "Travel - Air"}')


# --------------------------------------------------------------------------- #
# The Gradio boundary
# --------------------------------------------------------------------------- #
def test_handlers_do_not_import_gradio_at_all():
    """The separation that lets the demo fall back to the terminal, and lets these
    handlers be tested without a browser. `demo_handlers` must stay Gradio-free."""
    import ast
    from pathlib import Path

    import demo_handlers

    source = Path(demo_handlers.__file__).read_text("utf-8")
    assert "gradio" not in source, "demo_handlers must not reference Gradio"

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(a.name.split(".")[0] != "gradio" for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] != "gradio"


def test_app_module_does_not_import_gradio_at_module_level():
    """`app` may use Gradio, but only inside functions — otherwise importing it to reach
    the handlers would fail on a machine where Gradio is broken."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(app.__file__).read_text("utf-8"))
    top_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {
        alias.name.split(".")[0]
        for node in top_level
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    names |= {
        n.module.split(".")[0] for n in top_level if isinstance(n, ast.ImportFrom) and n.module
    }
    assert "gradio" not in names


def test_guard_converts_errors_into_gradio_errors():
    gr = pytest.importorskip("gradio")

    def explode():
        raise ValueError("Amount must be a number")

    with pytest.raises(gr.Error, match="Amount must be a number"):
        app._guard(explode)()


def test_guard_passes_results_through():
    pytest.importorskip("gradio")
    assert app._guard(lambda x: x * 2)(21) == 42


def test_the_server_actually_starts_and_serves():
    """Builds *and launches*, then fetches the page.

    Building the UI is not enough: `launch()` takes a different set of parameters, and
    Gradio 6 removed one that Gradio 5 accepted. That mismatch is a hard TypeError on
    startup which no build-only test can see.
    """
    pytest.importorskip("gradio")
    import urllib.request

    ui = app.build_ui()
    options = app.launch_options() | {"server_port": 7873, "quiet": True}
    ui.launch(prevent_thread_lock=True, inbrowser=False, **options)
    try:
        with urllib.request.urlopen("http://127.0.0.1:7873/", timeout=30) as response:
            body = response.read().decode("utf-8", "replace")
        assert response.status == 200
        assert "Expense Compliance Tools" in body
    finally:
        ui.close()


def test_launch_options_are_accepted_by_this_gradio():
    """Every option must exist in the installed Gradio's launch signature."""
    gr = pytest.importorskip("gradio")
    import inspect

    accepted = set(inspect.signature(gr.Blocks.launch).parameters)
    unknown = set(app.launch_options()) - accepted
    assert not unknown, f"launch() would raise TypeError for: {sorted(unknown)}"


def test_the_ui_builds():
    """Constructs every component and event wiring without starting a server.

    Catches the failure mode a demo is most prone to: a typo'd component argument that
    only surfaces the moment someone actually runs `python app.py`.
    """
    pytest.importorskip("gradio")
    ui = app.build_ui()
    assert ui is not None


def test_the_ui_wires_up_five_tabs():
    gr = pytest.importorskip("gradio")

    ui = app.build_ui()
    labels = [
        block.label
        for block in ui.blocks.values()
        if isinstance(block, gr.Tab) and getattr(block, "label", None)
    ]
    assert len(labels) == 5
    for n, tool in enumerate(
        [
            "Policy Checker",
            "Receipt Parser",
            "Category Classifier",
            "Duplicate Detector",
            "Report Summariser",
        ],
        start=1,
    ):
        assert any(label.startswith(f"{n} ") and tool in label for label in labels), (
            f"no tab for {tool}"
        )
