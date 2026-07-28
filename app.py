#!/usr/bin/env python3
"""Browser demo for the five expense-compliance tools.

    python app.py

Opens on http://127.0.0.1:7860. Everything runs locally against ``local_db/sqlite.db``.

This module builds and launches the interface. The logic behind each tab lives in
:mod:`demo_handlers`, which imports no Gradio — that separation is what lets this module
fall back to the terminal demo when Gradio is unavailable, and what makes the handlers
directly testable.

The handlers are re-exported here so ``app.run_policy_checker`` keeps working.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from functools import wraps

from compliance_tools import Category
from demo_handlers import (
    CATEGORIES,
    SAMPLE_RECEIPT,
    _date,
    _datetime,
    _decimal,
    _display_path,
    _money,
    _text,
    database_status,
    run_category_classifier,
    run_duplicate_detector,
    run_policy_checker,
    run_receipt_parser,
    run_report_summariser,
)

__all__ = [
    "CATEGORIES",
    "SAMPLE_RECEIPT",
    "build_ui",
    "database_status",
    "launch_options",
    "main",
    "run_category_classifier",
    "run_duplicate_detector",
    "run_policy_checker",
    "run_receipt_parser",
    "run_report_summariser",
]

# Imported for backwards compatibility with callers (and tests) that reach for the
# coercion helpers through this module.
_ = (_text, _decimal, _date, _datetime, _money, _display_path)


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #
def _guard(handler):
    """Surface handler errors to the user as readable text.

    Gradio renders an uncaught exception as a generic "Error" toast with no detail, which
    is useless when the real problem is "Amount must be a number". Wrapping at the UI
    boundary keeps the handlers above free of any Gradio import — which is what makes them
    directly testable, and what lets this module fall back to the CLI when Gradio is absent.
    """
    import gradio as gr

    @wraps(handler)
    def wrapped(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception as e:
            raise gr.Error(str(e) or e.__class__.__name__) from e

    return wrapped


def build_ui():
    import gradio as gr

    # No explicit theme: Gradio 6 moved `theme` from Blocks() to launch(), and the default
    # looks fine on every version. Not worth a version branch for something cosmetic.
    with gr.Blocks(title="Expense Compliance Tools") as ui:
        gr.Markdown(
            "# Expense Compliance Tools\n"
            "Five offline tools for expense policy enforcement. No cloud, no credentials, "
            "no network — everything below runs on your machine against a local SQLite file."
        )
        status = gr.Markdown(database_status())

        # -- 1 ------------------------------------------------------------ #
        with gr.Tab("1 · Policy Checker"):
            gr.Markdown(
                "Check one expense against the policy in `compliance_tools/baseline_policy.json`."
            )
            with gr.Row():
                with gr.Column():
                    pc_employee = gr.Textbox(label="Employee ID", value="emp-001")
                    pc_amount = gr.Textbox(label="Amount", value="187.00")
                    pc_merchant = gr.Textbox(label="Merchant", value="The Chophouse")
                    pc_date = gr.Textbox(label="Expense date (YYYY-MM-DD)", value=str(date.today()))
                    pc_category = gr.Dropdown(
                        CATEGORIES, label="Category", value=Category.MEALS_ENTERTAINMENT.value
                    )
                    pc_description = gr.Textbox(label="Description", value="Client dinner")
                    pc_has_receipt = gr.Checkbox(label="Receipt attached", value=True)
                    pc_receipt_total = gr.Textbox(
                        label="Receipt total (optional)",
                        placeholder="Leave blank to skip the match check",
                    )
                    pc_run = gr.Button("Check policy", variant="primary")
                with gr.Column():
                    pc_report = gr.Markdown()
                    pc_json = gr.JSON(label="Raw result")
            pc_run.click(
                _guard(run_policy_checker),
                [
                    pc_employee,
                    pc_amount,
                    pc_merchant,
                    pc_date,
                    pc_category,
                    pc_description,
                    pc_has_receipt,
                    pc_receipt_total,
                ],
                [pc_report, pc_json],
            )

        # -- 2 ------------------------------------------------------------ #
        with gr.Tab("2 · Receipt Parser"):
            gr.Markdown(
                "Extract fields from a receipt and re-check the maths. "
                "The default sample reconciles; change a number to see it caught."
            )
            with gr.Row():
                with gr.Column():
                    rp_text = gr.Textbox(label="Receipt text", value=SAMPLE_RECEIPT, lines=16)
                    rp_file = gr.File(
                        label="…or upload a receipt file",
                        # Mirrors compliance_tools.receipt_parser.READABLE_SUFFIXES, so the
                        # picker offers exactly what the parser will accept.
                        file_types=[".txt", ".text", ".md", ".pdf"],
                        type="filepath",
                    )
                    rp_run = gr.Button("Parse receipt", variant="primary")
                with gr.Column():
                    rp_report = gr.Markdown()
                    rp_table = gr.Dataframe(headers=["Item", "Amount"], label="Extracted lines")
                    rp_json = gr.JSON(label="Raw result")
            rp_run.click(
                _guard(run_receipt_parser), [rp_text, rp_file], [rp_report, rp_table, rp_json]
            )

        # -- 3 ------------------------------------------------------------ #
        with gr.Tab("3 · Category Classifier"):
            gr.Markdown("Sort an expense into one of the eight standard categories.")
            with gr.Row():
                with gr.Column():
                    cc_description = gr.Textbox(label="Description", value="Airport transfer")
                    cc_merchant = gr.Textbox(label="Merchant", value="Uber")
                    cc_run = gr.Button("Classify", variant="primary")
                    gr.Examples(
                        [
                            ["Team lunch", "Noodle House"],
                            ["Copilot annual subscription", "GitHub"],
                            ["JFK to LAX", "Delta Airlines"],
                            ["2 nights downtown", "Marriott"],
                            ["Blue widget", "AcmeCo"],
                        ],
                        [cc_description, cc_merchant],
                    )
                with gr.Column():
                    cc_report = gr.Markdown()
                    cc_json = gr.JSON(label="Raw result")
            cc_run.click(
                _guard(run_category_classifier), [cc_description, cc_merchant], [cc_report, cc_json]
            )

        # -- 4 ------------------------------------------------------------ #
        with gr.Tab("4 · Duplicate Detector"):
            gr.Markdown(
                "Screen an expense against stored history. The seeded database already "
                "contains a duplicate pair for `emp-002` — the defaults below will find it."
            )
            with gr.Row():
                with gr.Column():
                    dd_employee = gr.Textbox(label="Employee ID", value="emp-002")
                    dd_total = gr.Textbox(label="Total", value="42.50")
                    dd_datetime = gr.Textbox(
                        label="Receipt timestamp (ISO, optional)", value="2026-06-05T07:30:00"
                    )
                    dd_days = gr.Slider(0, 30, value=3, step=1, label="Near-match window (days)")
                    dd_run = gr.Button("Check for duplicates", variant="primary")
                with gr.Column():
                    dd_report = gr.Markdown()
                    dd_table = gr.Dataframe(
                        headers=["Line item", "Reason", "Timestamp", "Total"], label="Matches"
                    )
                    dd_json = gr.JSON(label="Raw result")
            dd_run.click(
                _guard(run_duplicate_detector),
                [dd_employee, dd_total, dd_datetime, dd_days],
                [dd_report, dd_table, dd_json],
            )

        # -- 5 ------------------------------------------------------------ #
        with gr.Tab("5 · Report Summariser"):
            gr.Markdown(
                "Aggregate stored expenses into totals and a compliance rate. "
                "Leave both fields blank to summarise everything in the database."
            )
            with gr.Row():
                with gr.Column():
                    rs_employee = gr.Textbox(label="Employee ID (blank = everyone)", value="")
                    rs_items = gr.Textbox(
                        label="…or paste items as JSON (overrides the database)",
                        placeholder=(
                            '[{"category": "Travel - Air", "amount": "320.00", '
                            '"is_compliant": true}]'
                        ),
                        lines=5,
                    )
                    rs_run = gr.Button("Summarise", variant="primary")
                with gr.Column():
                    rs_report = gr.Markdown()
                    rs_table = gr.Dataframe(
                        headers=["Category", "Amount"], label="Spend by category"
                    )
                    rs_json = gr.JSON(label="Raw result")
            rs_run.click(
                _guard(run_report_summariser),
                [rs_employee, rs_items],
                [rs_report, rs_table, rs_json],
            )

        # Refresh the counters after any tool run, so the audit trail is visibly growing.
        for button in (pc_run, rp_run, cc_run, dd_run, rs_run):
            button.click(database_status, None, status)

        gr.Markdown(
            "---\n"
            "The same five tools are available to AI agents over MCP — run `python mcp_server.py`. "
            "See `README.md` for client setup."
        )
    return ui


def main() -> int:
    try:
        ui = build_ui()
    except ImportError as e:
        # Covers both "gradio not installed" and an installed-but-broken import chain
        # (its compiled pandas dependency is blocked by policy on some Windows machines).
        print(f"The browser UI is unavailable ({e}).")
        print("Falling back to the terminal demo. To fix: pip install -r requirements.txt\n")
        from cli import main as cli_main

        return cli_main()

    ui.launch(inbrowser=True, **launch_options())
    return 0


def launch_options() -> dict:
    """Server options shared by ``main()`` and the tests that actually start the server.

    Only parameters common to Gradio 5 and 6 are used. `show_api` looks like it belongs
    here but was removed in Gradio 6, and passing it raises `TypeError` on startup — the
    kind of break that never shows up until someone runs the app, which is why
    ``tests/test_app.py`` launches the server for real rather than only building the UI.
    """
    return {
        # Loopback only. This is a local developer tool with no authentication, and it
        # must not become reachable from the network by accident.
        "server_name": os.getenv("GRADIO_SERVER_NAME", "127.0.0.1"),
        "server_port": int(os.getenv("GRADIO_SERVER_PORT", "7860")),
        # Reject oversized uploads at the HTTP layer. Without this Gradio would spool the
        # whole file to disk before the parser's own 10 MB check could reject it.
        "max_file_size": "10mb",
        # Surface handler errors (raised as gr.Error by _guard) in the browser.
        "show_error": True,
        "share": False,
    }


if __name__ == "__main__":
    sys.exit(main())
