"""Report aggregation for the dashboard (SCOPING §4 report summariser).

Deterministic aggregation over sheets/line items within the caller's scope, wrapped around
the engine's `summarise_report` so the API and the MCP tool produce identical numbers. Scope:
manager → own agency; finance/admin → all (optionally filtered to one agency).
"""

from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models.decision import Decision
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.principal import Principal, Scope
from app.schemas.dto import (
    CategoryTotal,
    FinanceKpisOut,
    ReportSummaryOut,
    SpendByCategoryOut,
)
from expense_core.schemas.enums import Category, LineItemStatus, SheetStatus
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


def _scoped_line_items(
    session: Session, principal: Principal, agency_id: str | None = None
) -> list[LineItem]:
    """Line items visible to the caller: manager → own agency; finance/admin → all (optionally
    filtered to one agency)."""
    stmt = select(LineItem).join(ExpenseSheet, LineItem.sheet_id == ExpenseSheet.id)
    if principal.scope is Scope.AGENCY:
        stmt = stmt.where(ExpenseSheet.agency_id == principal.agency_id)
    elif agency_id:
        stmt = stmt.where(ExpenseSheet.agency_id == agency_id)
    return list(session.exec(stmt).all())


def spend_by_category(
    session: Session, principal: Principal, *, agency_id: str | None = None
) -> list[SpendByCategoryOut]:
    """Total spend per expense category within the caller's scope, highest first."""
    totals: dict[str, Decimal] = {}
    for item in _scoped_line_items(session, principal, agency_id):
        cat = (item.category or Category.OTHER)
        cat = cat.value if hasattr(cat, "value") else str(cat)
        totals[cat] = totals.get(cat, Decimal("0")) + item.amount
    return [
        SpendByCategoryOut(category=cat, amount=amount)
        for cat, amount in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    ]


# Statuses that mean a sheet reached a finance-stage outcome (the KPI denominator).
_FINANCE_REACHED = {
    SheetStatus.IN_FINANCE_REVIEW,
    SheetStatus.FINANCE_APPROVED,
    SheetStatus.FINANCE_REJECTED,
    SheetStatus.FINANCE_MANUAL_REVIEW,
    SheetStatus.APPROVED,
    SheetStatus.REJECTED,
    SheetStatus.PAID,
}


def build_finance_kpis(session: Session, principal: Principal) -> FinanceKpisOut:
    """Deterministic finance KPIs over all sheets in the caller's scope (SCOPING §4)."""
    stmt = select(ExpenseSheet)
    if principal.scope is Scope.AGENCY:
        stmt = stmt.where(ExpenseSheet.agency_id == principal.agency_id)
    sheets = list(session.exec(stmt).all())

    reached = [s for s in sheets if s.status in _FINANCE_REACHED]
    auto_approved = sum(1 for s in reached if s.status is SheetStatus.FINANCE_APPROVED)
    manual = sum(1 for s in sheets if s.status is SheetStatus.FINANCE_MANUAL_REVIEW)
    auto_rate = round(100.0 * auto_approved / len(reached), 1) if reached else 0.0

    # Policy citations: finance decisions that cited at least one clause.
    citations = sum(
        1
        for d in session.exec(select(Decision)).all()
        if d.cited_clauses and d.cited_clauses not in ("[]", "null", "")
    )

    items = _scoped_line_items(session, principal)
    compliant = sum(1 for i in items if _is_compliant(i))
    compliance_rate = round(100.0 * compliant / len(items), 1) if items else 100.0

    return FinanceKpisOut(
        auto_approval_rate=auto_rate,
        manual_interventions=manual,
        policy_citations=citations,
        policy_compliance_rate=compliance_rate,
        finance_reached=len(reached),
    )
