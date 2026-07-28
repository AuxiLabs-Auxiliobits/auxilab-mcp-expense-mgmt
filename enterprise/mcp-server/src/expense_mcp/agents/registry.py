"""Agent registry — the single source of truth for the multi-agent layer.

Pure data: each `AgentSpec` declares an agent's role, responsibilities, the MCP **tools** it may
use, the **resources** it may read, and example **intents** for routing. The prompts and the
router are generated from this, so there is exactly one place to change an agent's capabilities
and nothing here duplicates business logic (the tools do the work).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    name: str  # stable id, also the MCP prompt name (e.g. "employee_agent")
    title: str
    role: str  # one-line mission
    responsibilities: list[str]
    tools: list[str]  # MCP tool names this agent may call
    resources: list[str] = field(default_factory=list)  # resource URIs it may read
    intents: list[str] = field(default_factory=list)  # routing keywords / example asks


AGENTS: list[AgentSpec] = [
    AgentSpec(
        name="employee_agent",
        title="Employee Agent",
        role="Help an employee build, submit, and track their own expense sheets.",
        responsibilities=[
            "Create expense sheets and add line items",
            "Upload receipts to line items",
            "Submit and resubmit expense sheets",
            "Explain a sheet's current approval status",
            "Explain why a sheet was returned or rejected and what to fix",
            "Answer the employee's questions about their own expenses",
        ],
        tools=[
            "create_expense", "add_line_item", "upload_receipt", "submit_expense",
            "resubmit_expense", "withdraw_expense", "list_my_expenses", "get_expense",
            "list_receipts", "my_activity", "ask_policy",
        ],
        resources=["expense://mine", "expense://{sheet_id}", "expense://{sheet_id}/history"],
        intents=[
            "create an expense", "add a line item", "upload a receipt", "submit my expense",
            "resubmit", "withdraw", "my expenses", "why was my sheet returned", "status of my sheet",
        ],
    ),
    AgentSpec(
        name="manager_agent",
        title="Manager Agent",
        role="Help a manager review, decide, and explain expense sheets for their agency.",
        responsibilities=[
            "Review the pending-approval queue",
            "View an employee's receipts (preview/download)",
            "Approve or reject line items / whole sheets",
            "Return a sheet to the employee with feedback",
            "Explain policy violations on a sheet",
            "Summarize an expense sheet for review",
        ],
        tools=[
            "get_pending_approvals", "get_expense", "list_receipts", "get_receipt_details",
            "download_receipt", "approve_line_item", "reject_line_item", "return_to_employee",
            "approve_sheet", "ask_policy",
        ],
        resources=["approvals://pending", "expense://{sheet_id}", "expense://{sheet_id}/receipts"],
        intents=[
            "pending approvals", "review queue", "approve", "reject", "return to employee",
            "view receipts", "summarize this sheet", "is this within policy",
        ],
    ),
    AgentSpec(
        name="finance_agent",
        title="Finance Agent",
        role="Help finance resolve routed sheets, override AI verdicts, and read finance metrics.",
        responsibilities=[
            "Review the finance manual-review queue",
            "Approve or reject routed sheets; override the AI approver",
            "Generate finance reports and KPIs",
            "Detect anomalies / likely duplicates",
            "Review policy violations and summarize financial metrics",
        ],
        tools=[
            "get_finance_queue", "list_all_expenses", "get_expense", "list_receipts",
            "finance_decision", "finance_override", "get_finance_kpis", "get_dashboard_metrics",
            "get_spend_by_category", "duplicate_detector", "ask_policy",
        ],
        resources=["finance://queue", "dashboard://summary", "expense://{sheet_id}"],
        intents=[
            "finance queue", "finance approve", "finance reject", "override", "finance kpis",
            "anomaly", "duplicate", "financial metrics",
        ],
    ),
    AgentSpec(
        name="admin_agent",
        title="Admin Agent",
        role="Help an admin manage users/roles and monitor the platform.",
        responsibilities=[
            "List and inspect users (role management is via the API)",
            "Produce dashboard summaries",
            "Report system/server health",
            "Summarize audit/activity",
        ],
        tools=[
            "list_users", "get_user", "get_dashboard_metrics", "server_health",
            "my_activity", "search_expenses",
        ],
        resources=["users://directory", "dashboard://summary", "activity://mine"],
        intents=["list users", "user details", "role", "system health", "admin dashboard", "activity report"],
    ),
    AgentSpec(
        name="policy_agent",
        title="Policy Agent",
        role="Answer agency policy questions and compare expenses against policy, with citations.",
        responsibilities=[
            "Answer policy questions and cite the governing clause",
            "Explain a violation in plain language",
            "Compare a line item / sheet against policy",
            "Recommend compliance actions (flag, don't decide)",
        ],
        tools=["ask_policy", "policy_checker", "get_expense"],
        resources=["expense://{sheet_id}"],
        intents=["policy", "what's the cap", "is this allowed", "receipt rule", "deadline", "compliance"],
    ),
    AgentSpec(
        name="audit_agent",
        title="Audit Agent",
        role="Reconstruct workflow history and surface unusual activity for compliance.",
        responsibilities=[
            "Generate audit reports for a sheet",
            "Track approval/decision history",
            "Identify unusual activity and suspicious patterns",
            "Summarize workflow events",
        ],
        tools=["get_expense", "my_activity", "search_expenses", "duplicate_detector"],
        resources=["expense://{sheet_id}/history", "activity://mine"],
        intents=["audit", "approval history", "trail", "suspicious", "unusual activity", "workflow events"],
    ),
    AgentSpec(
        name="reporting_agent",
        title="Reporting Agent",
        role="Produce spend analytics and KPI reports, grounded in tool data.",
        responsibilities=[
            "Generate monthly and category-wise spend reports",
            "Employee spend summaries",
            "Manager/finance KPI reports",
            "Aggregate and narrate metrics deterministically",
        ],
        tools=[
            "get_dashboard_metrics", "get_spend_by_category", "get_finance_kpis",
            "list_all_expenses", "search_expenses", "report_summariser",
        ],
        resources=["dashboard://summary"],
        intents=["report", "monthly report", "spend by category", "kpi", "spend summary", "analytics"],
    ),
]

AGENTS_BY_NAME: dict[str, AgentSpec] = {a.name: a for a in AGENTS}
