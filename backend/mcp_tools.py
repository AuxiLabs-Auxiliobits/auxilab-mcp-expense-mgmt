"""
ExpenseOps MCP Server Module
============================
Integrates Model Context Protocol (MCP) using FastMCP.
Allows LLMs and external MCP clients to interact with the core validation engines,
receipt parser, AI classifier, and auditing ledger directly.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional, Any

from mcp.server.fastmcp import FastMCP

from backend.database import get_db, init_db, ExpenseClaim
from backend.engines import PolicyEngine, RiskEngine, DuplicateEngine, ExpenseContext
from backend.exceptions_engine import ExceptionEngine
from backend.ai_layer import perform_ocr, parse_receipt_text, classify_expense, generate_batch_narrative

logger = logging.getLogger(__name__)

# Initialize the FastMCP server
mcp = FastMCP("ExpenseOps MCP Server")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP Tools Registry
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
def validate_expense_policy(
    amount: float,
    category: str,
    employee_role: str,
    receipt_attached: bool = True,
    location: Optional[str] = None,
) -> str:
    """
    Checks if a prospective expense claim complies with active policies.
    Returns PASS or details of the violations and manager/auditor routing.
    """
    db = next(get_db())
    try:
        # Mock file path or None based on receipt_attached
        receipt_path = "mock_receipt.jpg" if receipt_attached else None
        
        context = ExpenseContext(
            amount=amount,
            category=category,
            merchant_name="MCP Verification",
            transaction_date=date.today(),
            employee_role=employee_role,
            employee_id="MCP_TEST_USER",
            receipt_path=receipt_path,
            location=location,
            submission_hour=12
        )
        
        # Initialize engines
        policy_engine = PolicyEngine(db)
        exception_engine = ExceptionEngine(db)
        
        # 1. Run Policy Engine
        policy_res = policy_engine.evaluate(context)
        
        # 2. If EXCEPTION, check Exception Engine for escalation routing
        routing_info = None
        if policy_res.status == "EXCEPTION":
            # Pass a dummy RiskScoreResult since we aren't running RiskEngine in this standalone tool
            from backend.schemas import RiskScoreResult
            dummy_risk = RiskScoreResult(score=0.0, level="LOW", factors={}, recommended_action="auto_approve")
            
            # Run Exception Engine
            routing = exception_engine.evaluate(context, policy_result=policy_res, risk_result=dummy_risk)
            routing_info = (
                f"\nEscalation Action: {routing['action'].upper()}"
                f"\nRoute Path: {routing['escalation_path']}"
            )
            if routing.get("adjusted_max"):
                routing_info += f"\nAdjusted Max Cap: ${routing['adjusted_max']:.2f}"
            if routing.get("override_applied"):
                routing_info += f"\nOverride Applied: {routing['override_applied']}"
        
        result_str = (
            f"Validation Status: {policy_res.status}"
            f"\nOverage Risk Contribution: {policy_res.risk_score}"
            f"\nRequires Manual Review: {policy_res.requires_manual_review}"
        )
        if policy_res.failed_rules:
            result_str += f"\nViolated Rules: {', '.join(policy_res.failed_rules)}"
        if routing_info:
            result_str += routing_info
            
        return result_str
    except Exception as exc:
        logger.error(f"MCP policy check error: {exc}")
        return f"Error executing policy check: {str(exc)}"
    finally:
        db.close()


@mcp.tool()
def parse_receipt(file_path: str) -> str:
    """
    Takes a path to a receipt image/PDF, runs OCR, extracts key structured fields 
    (merchant, total_amount, tax, date, line items), and returns structured JSON.
    """
    try:
        if not file_path:
            return "Error: A valid file path must be provided."
            
        # 1. Perform OCR
        raw_text = perform_ocr(file_path)
        if not raw_text:
            return f"Error: Could not extract any text from file '{file_path}'."
            
        # 2. Parse OCR into structure
        extracted = parse_receipt_text(raw_text)
        
        # Format output nicely
        lines_str = "\n  - ".join(extracted.line_items) if extracted.line_items else "None"
        output = (
            f"--- Receipt Parse Results ---"
            f"\nMerchant: {extracted.merchant or 'Unknown'}"
            f"\nTotal Amount: ${extracted.total_amount:.2f}" if extracted.total_amount else "\nTotal Amount: Not Found"
            f"\nTax: ${extracted.tax:.2f}" if extracted.tax else "\nTax: Not Found"
            f"\nTransaction Date: {extracted.date or 'Unknown'}"
            f"\nExtracted Line Items:\n  - {lines_str}"
        )
        return output
    except Exception as exc:
        logger.error(f"MCP parse receipt error: {exc}")
        return f"Error parsing receipt: {str(exc)}"


@mcp.tool()
def classify_expense_category(merchant_name: str, description: Optional[str] = None) -> str:
    """
    AI-categorisation helper. Takes a merchant name and an optional description,
    classifies the expense into the appropriate category code, and provides confidence.
    """
    try:
        res = classify_expense(merchant_name, description)
        return (
            f"Suggested Category Code: {res.category_code}"
            f"\nCategory Name: {res.category_name}"
            f"\nClassifier Confidence: {res.confidence * 100:.1f}%"
        )
    except Exception as exc:
        return f"Error classifying expense: {str(exc)}"


@mcp.tool()
def detect_duplicate_claims(
    amount: float,
    merchant_name: str,
    transaction_date_iso: str,
    employee_id: str,
) -> str:
    """
    Cross-references a prospective claim against database history using a 2-day sweep
    and Levenshtein merchant distance, returning if a potential duplicate exists.
    """
    db = next(get_db())
    try:
        txn_date = date.fromisoformat(transaction_date_iso)
        context = ExpenseContext(
            amount=amount,
            category="Unknown",
            merchant_name=merchant_name,
            transaction_date=txn_date,
            employee_id=employee_id,
            employee_role="Unknown"
        )
        
        duplicate_engine = DuplicateEngine(db)
        res = duplicate_engine.evaluate(context)
        
        if res.is_duplicate:
            return (
                f"DUPLICATE DETECTED: YES"
                f"\nSimilarity Score: {res.similarity_score * 100:.1f}%"
                f"\nMatched Historical Claim IDs: {', '.join(res.matched_claims)}"
            )
        else:
            return "DUPLICATE DETECTED: NO (No matching transaction amount and date proximity found)."
    except Exception as exc:
        logger.error(f"MCP duplicate check error: {exc}")
        return f"Error executing duplicate check: {str(exc)}"
    finally:
        db.close()


@mcp.tool()
def summarise_expense_report(employee_id: str, start_date: str, end_date: str) -> str:
    """
    Given a set of expense claims for an employee and period, produce: total by category, 
    policy violation count, total at risk (flagged claims), compliance rate %, and a manager-ready summary narrative.
    Format of dates: YYYY-MM-DD
    """
    db = next(get_db())
    try:
        sd = date.fromisoformat(start_date)
        ed = date.fromisoformat(end_date)
        
        claims = db.query(ExpenseClaim).filter(
            ExpenseClaim.employee_id == employee_id,
            ExpenseClaim.transaction_date >= sd,
            ExpenseClaim.transaction_date <= ed
        ).all()
        
        total_claims = len(claims)
        if total_claims == 0:
            return f"No claims found for {employee_id} between {start_date} and {end_date}."
            
        total_amount = sum(float(c.amount) for c in claims)
        
        # Calculate categories
        category_totals = {}
        for c in claims:
            category_totals[c.category] = category_totals.get(c.category, 0.0) + float(c.amount)
            
        # Metrics
        violations_count = sum(1 for c in claims if c.status != "APPROVED")
        high_risk_count = sum(1 for c in claims if c.risk_score >= 70)
        total_at_risk = sum(float(c.amount) for c in claims if c.status != "APPROVED")
        
        # Compliance rate
        compliant_claims = total_claims - violations_count
        compliance_rate = (compliant_claims / total_claims) * 100
        
        # We reuse the narrative generator from ai_layer
        narrative = generate_batch_narrative(
            total_claims=total_claims,
            total_amount=total_amount,
            compliance_rate=compliance_rate,
            violations_count=violations_count,
            duplicate_count=0, # Simplifying duplicate count for summary
            high_risk_count=high_risk_count,
        )
        
        # Format the final report
        cat_str = "\n".join([f"  - {k}: ${v:.2f}" for k, v in category_totals.items()])
        
        report = (
            f"--- Expense Report Summary ---\n"
            f"Employee: {employee_id}\n"
            f"Period: {start_date} to {end_date}\n\n"
            f"Total Claims: {total_claims}\n"
            f"Total Amount: ${total_amount:.2f}\n\n"
            f"Category Breakdown:\n{cat_str}\n\n"
            f"Compliance Metrics:\n"
            f"  - Policy Violations: {violations_count}\n"
            f"  - Total Amount at Risk: ${total_at_risk:.2f}\n"
            f"  - Overall Compliance Rate: {compliance_rate:.1f}%\n\n"
            f"Manager Narrative:\n{narrative}"
        )
        
        return report
    except Exception as exc:
        logger.error(f"MCP summarise expense report error: {exc}")
        return f"Error executing summarise_expense_report: {str(exc)}"
    finally:
        db.close()


if __name__ == "__main__":
    # Ensure database is set up and tables created when starting the server stand-alone
    init_db()
    mcp.run()
