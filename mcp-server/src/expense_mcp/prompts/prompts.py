"""Reusable MCP prompts. Each returns an instruction that tells the AI which tools/resources
to use, so workflows are consistent and grounded in real data (never invented)."""

from __future__ import annotations

from expense_mcp.instance import mcp


@mcp.prompt()
def summarize_expense(sheet_id: str) -> str:
    """Summarize an expense sheet for a reviewer."""
    return (
        f"Load the expense sheet via the `get_expense` tool (sheet_id={sheet_id}). Summarize it "
        "for a reviewer: who submitted it, the period, total, each line item (merchant, category, "
        "amount), how many receipts are attached, the current status, and any policy flags. "
        "Use only the returned data — do not invent figures."
    )


@mcp.prompt()
def explain_rejection(sheet_id: str) -> str:
    """Explain, in plain language, why a sheet was returned/rejected."""
    return (
        f"Use `get_expense` (sheet_id={sheet_id}) and the `expense://{sheet_id}/history` resource. "
        "Explain in plain, employee-friendly language why the sheet was returned or rejected, "
        "quoting the manager/finance reason and the specific line items affected, then list the "
        "concrete changes needed before resubmitting."
    )


@mcp.prompt()
def approval_summary() -> str:
    """Brief a manager on their pending approval queue."""
    return (
        "Call `get_pending_approvals`. Brief the manager: how many sheets are waiting, the total "
        "amount pending, which are oldest/most urgent, and any that look risky (large amounts, "
        "policy flags). Recommend an order to review them. Use only the returned data."
    )


@mcp.prompt()
def finance_report(period: str) -> str:
    """Generate a finance report for a period."""
    return (
        f"Build a finance report for period {period}. Call `get_dashboard_metrics(period='{period}')`, "
        "`get_spend_by_category`, and `get_finance_kpis`. Produce a concise report: total spend, "
        "spend by category, compliance rate, auto-approval rate, manual interventions, and notable "
        "risks. Ground every number in the tool outputs."
    )


@mcp.prompt()
def list_pending_approvals() -> str:
    """List pending approvals across manager + finance queues."""
    return (
        "Call `get_pending_approvals` (manager queue) and `get_finance_queue` (finance manual "
        "review). Present a single prioritized list with sheet title, employee, amount, age, and "
        "which queue it's in."
    )


@mcp.prompt()
def find_duplicate_expenses() -> str:
    """Look for likely duplicate expenses to review."""
    return (
        "Use `search_expenses(scope='all')` to gather sheets, then look across their line items for "
        "likely duplicates (same merchant + amount + date, or repeated receipt date/time/total). "
        "For any candidates, you may confirm with the `duplicate_detector` tool. Report the "
        "suspected pairs with the reason; do not assert a duplicate without matching fields."
    )


@mcp.prompt()
def audit_report(sheet_id: str) -> str:
    """Produce an audit trail summary for a sheet."""
    return (
        f"Use the `expense://{sheet_id}/history` resource and `get_expense` (sheet_id={sheet_id}). "
        "Produce an audit summary: every state transition and decision in order, who acted, when, "
        "and the reason given — suitable for a compliance record."
    )


@mcp.prompt()
def suggest_policy_violations(sheet_id: str) -> str:
    """Flag possible policy issues on a sheet, grounded in the agency policy."""
    return (
        f"Load the sheet with `get_expense` (sheet_id={sheet_id}). For each line item, check it "
        "against the agency policy using the `ask_policy` tool (e.g. ask the relevant cap/receipt "
        "rule) and/or the `policy_checker` tool. List any likely violations with the governing "
        "clause cited. Flag, don't decide — the human reviewer makes the call."
    )
