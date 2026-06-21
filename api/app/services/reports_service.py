"""Report aggregation for the dashboard (SCOPING §4 report summariser).

Deterministic aggregation over sheets/line items within the caller's scope, wrapped around
the engine's `summarise_report` so the API and the MCP tool produce identical numbers. Scope:
manager → own agency; finance/admin → all (optionally filtered to one agency).
"""

from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.principal import Principal, Scope
from app.schemas.dto import CategoryTotal, ReportSummaryOut
from expense_core.schemas.enums import Category, LineItemStatus
from expense_core.tools.report_summariser import SummaryLineItem, summarise_report


def _is_compliant(item: LineItem) -> bool:
    """A line item counts as a violation if a manager rejected it or policy failed it."""
    if item.manager_status is LineItemStatus.MANAGER_REJECTED:
        return False
    return item.policy_status is not LineItemStatus.POLICY_FAIL


def build_summary(
    session: Session,
    principal: Principal,
    *,
    period: str | None = None,
    agency_id: str | None = None,
) -> ReportSummaryOut:
    stmt = select(LineItem, ExpenseSheet).join(
        ExpenseSheet, LineItem.sheet_id == ExpenseSheet.id
    )

    # Scope: managers are pinned to their own agency; finance/admin (ALL) may filter.
    applied_agency: str | None = None
    if principal.scope is Scope.AGENCY:
        applied_agency = principal.agency_id
        stmt = stmt.where(ExpenseSheet.agency_id == principal.agency_id)
    elif agency_id:
        applied_agency = agency_id
        stmt = stmt.where(ExpenseSheet.agency_id == agency_id)

    if period:
        stmt = stmt.where(ExpenseSheet.period == period)

    rows = list(session.exec(stmt).all())

    summary_items = [
        SummaryLineItem(
            category=item.category or Category.OTHER,
            amount=item.amount,
            is_compliant=_is_compliant(item),
        )
        for item, _sheet in rows
    ]
    report = summarise_report(summary_items)

    # Distinct sheets in scope + their status breakdown.
    sheets = {sheet.id: sheet for _item, sheet in rows}
    by_status: dict[str, int] = {}
    for sheet in sheets.values():
        by_status[sheet.status.value] = by_status.get(sheet.status.value, 0) + 1

    grand_total = sum(report.total_by_category.values(), Decimal("0"))
    by_category = [
        CategoryTotal(category=cat.value, total=amount)
        for cat, amount in sorted(
            report.total_by_category.items(), key=lambda kv: kv[1], reverse=True
        )
    ]

    return ReportSummaryOut(
        period=period,
        agency_id=applied_agency,
        sheet_count=len(sheets),
        line_item_count=len(summary_items),
        grand_total=grand_total,
        total_at_risk=report.total_at_risk,
        violation_count=report.violation_count,
        compliance_rate_pct=report.compliance_rate_pct,
        by_category=by_category,
        by_status=by_status,
        narrative=report.narrative,
    )
