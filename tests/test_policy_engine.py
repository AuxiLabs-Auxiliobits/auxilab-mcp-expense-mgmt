"""
ExpenseOps Policy Engine & Core Validation Tests
=================================================
Automated unit tests to verify database seeding, deterministic policy rules,
VIP/location exception overrides, duplicate detections, and risk score calculations.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, Employee, ExpenseClaim, PolicyRule, init_db
from backend.engines import PolicyEngine, RiskEngine, DuplicateEngine
from backend.exceptions_engine import ExceptionEngine
from backend.schemas import PolicyCheckResult, DuplicateCheckResult, RiskScoreResult

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test Fixtures & Setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture(scope="function")
def db_session():
    """
    Creates an isolated in-memory SQLite database for each unit test.
    Applies standard migrations and mocks required seed datasets.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed core employee records
    employees = [
        Employee(employee_id="EMP001", name="Sarah Engineer", role="Software Engineer", department="Engineering"),
        Employee(employee_id="EMP002", name="Natasha Executive", role="VP", department="Operations"),
        Employee(employee_id="EMP003", name="Marcus Manager", role="Manager", department="Sales"),
    ]
    session.add_all(employees)

    # Seed core policy rules matching standard JSON specifications
    rules = [
        PolicyRule(
            rule_id="RULE_MEAL_ENG",
            category="Meals",
            max_amount=75.0,
            allowed_roles=json.dumps(["Software Engineer", "Analyst", "Manager"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=10,
        ),
        PolicyRule(
            rule_id="RULE_MEAL_DIR",
            category="Meals",
            max_amount=150.0,
            allowed_roles=json.dumps(["Director", "VP", "CEO"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=20,
        ),
        PolicyRule(
            rule_id="RULE_HOTEL_STD",
            category="Travel-Hotel",
            max_amount=250.0,
            allowed_roles=json.dumps(["Software Engineer", "Analyst", "Manager"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=10,
        ),
    ]
    session.add_all(rules)
    session.commit()

    yield session
    session.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Policy Engine Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_compliant_meal_claim(db_session):
    """
    Verifies that a Software Engineer claiming a $45.00 meal with a receipt
    passes standard policy checks with zero risk.
    """
    expense = {
        "amount": 45.0,
        "category": "Meals",
        "employee_role": "Software Engineer",
        "receipt_path": "uploads/receipt.jpg",
        "location": "NY_HQ",
    }
    result = PolicyEngine.check_policy(expense, db_session)
    assert result.status == "PASS"
    assert len(result.failed_rules) == 0
    assert result.risk_score == 0.0


def test_over_limit_meal_claim(db_session):
    """
    Verifies that a Software Engineer claiming a $95.00 meal (above $75 cap)
    triggers an EXCEPTION state with correct rule flags and risk penalties.
    """
    expense = {
        "amount": 95.0,
        "category": "Meals",
        "employee_role": "Software Engineer",
        "receipt_path": "uploads/receipt.jpg",
        "location": "NY_HQ",
    }
    result = PolicyEngine.check_policy(expense, db_session)
    assert result.status == "EXCEPTION"
    assert any("RULE_MEAL_ENG: amount $95.00 exceeds cap $75.00" in r for r in result.failed_rules)
    assert result.risk_score > 0.0


def test_missing_receipt_above_50(db_session):
    """
    Verifies that a claim above $50.00 without a receipt triggers a policy violation.
    """
    expense = {
        "amount": 60.0,
        "category": "Meals",
        "employee_role": "Software Engineer",
        "receipt_path": None,
    }
    result = PolicyEngine.check_policy(expense, db_session)
    assert result.status == "EXCEPTION"
    assert any("receipt required" in r for r in result.failed_rules)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Duplicate Detection Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_duplicate_claims_detection(db_session):
    """
    Ensures that submitting two claims with the exact same amount ($125) and
    dates within 2 days with identical/similar merchant names flags duplicates.
    """
    # 1. Save original claim to mock DB
    original = ExpenseClaim(
        claim_id="CLM_TEST_01",
        employee_id="EMP001",
        amount=125.00,
        currency="USD",
        category="Travel-Hotel",
        merchant_name="Marriott Inn",
        transaction_date=date(2026, 5, 10),
        status="APPROVED",
    )
    db_session.add(original)
    db_session.commit()

    # 2. Test duplicate check on a new matching transaction
    new_expense = {
        "amount": 125.00,
        "transaction_date": date(2026, 5, 11),  # Date within 1 day (limits = ±2 days)
        "merchant_name": "Marriott Inn",
        "employee_id": "EMP001",
    }
    result = DuplicateEngine.detect_duplicate(new_expense, db_session)
    assert result.is_duplicate is True
    assert "CLM_TEST_01" in result.matched_claims
    assert result.similarity_score > 0.9  # Same employee bonus + identical merchant


def test_merchant_levenshtein_detection(db_session):
    """
    Ensures duplicate detection catches slightly misspelled merchant names
    (e.g., 'Starbucks Corp' vs 'Starbucks Cpr') using Levenshtein distance.
    """
    original = ExpenseClaim(
        claim_id="CLM_TEST_02",
        employee_id="EMP001",
        amount=12.50,
        currency="USD",
        category="Meals",
        merchant_name="Starbucks Corp",
        transaction_date=date(2026, 5, 15),
        status="APPROVED",
    )
    db_session.add(original)
    db_session.commit()

    new_expense = {
        "amount": 12.50,
        "transaction_date": date(2026, 5, 15),
        "merchant_name": "Starbucks Cpr",  # 1 character diff (distance = 1)
        "employee_id": "EMP001",
    }
    result = DuplicateEngine.detect_duplicate(new_expense, db_session)
    assert result.is_duplicate is True
    assert "CLM_TEST_02" in result.matched_claims


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Exception & Escalation Override Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_vip_multiplier_override(db_session):
    """
    Tests the ExceptionEngine on VIP overrides. A VP (Natasha EMP002) is allowed
    up to a 2.0x multiplier. Verifies that a $130 meal (above $7 cap but within 2x)
    is routed to manager/auto-approved instead of standard critical failure.
    """
    expense = {
        "amount": 130.0,
        "category": "Meals",
        "employee_role": "VP",
        "employee_id": "EMP002",
        "receipt_path": "uploads/receipt.jpg",
        "location": "NY_HQ",
    }
    policy_res = PolicyCheckResult(
        status="EXCEPTION",
        failed_rules=["RULE_MEAL_DIR: amount $130.00 exceeds cap $150.00 (Standard VP test)"],
        risk_score=20.0
    )
    risk_res = RiskScoreResult(score=20.0, level="LOW")
    
    routing = ExceptionEngine.handle_exception(expense, policy_res, risk_res, db_session)
    assert routing["override_applied"] == "VIP_VP"
    # Auto-approve active for VP (within 2x standard meal cap)
    assert routing["action"] == "auto_approve"
    assert routing["adjusted_max"] == 300.0  # 2.0x of $150.00 rule cap


def test_location_cost_override(db_session):
    """
    Tests cost-of-living policy overrides. London meals cap is adjusted in exceptions.json.
    """
    expense = {
        "amount": 90.0,  # exceeds standard $75 meal cap
        "category": "Meals",
        "employee_role": "Software Engineer",
        "employee_id": "EMP001",
        "receipt_path": "uploads/receipt.jpg",
        "location": "LONDON",  # London override location
    }
    policy_res = PolicyCheckResult(
        status="EXCEPTION",
        failed_rules=["RULE_MEAL_ENG: amount $90.00 exceeds cap $75.00"],
        risk_score=15.0
    )
    risk_res = RiskScoreResult(score=15.0, level="LOW")
    routing = ExceptionEngine.handle_exception(expense, policy_res, risk_res, db_session)
    assert routing["override_applied"] == "LOCATION_LONDON"
    # Since London meals cap is adjusted to $120.00, $90 is within override limit
    assert routing["action"] == "route_to_manager"
    assert routing["adjusted_max"] == 120.0
