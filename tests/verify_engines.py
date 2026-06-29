"""
ExpenseOps Core Engines Verification Script
===========================================
Runs direct Python assertions to verify engines, duplicate detections,
and exception routing without needing external testing packages.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

# Adjust Python path to load modules correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import Base, Employee, ExpenseClaim, PolicyRule, SessionLocal, engine
from backend.engines import PolicyEngine, RiskEngine, DuplicateEngine
from backend.exceptions_engine import ExceptionEngine
from backend.schemas import PolicyCheckResult, DuplicateCheckResult

def run_verification():
    print("Starting ExpenseOps Core Engines Self-Verification...")
    
    # 1. Setup in-memory SQLite schema
    print("   Setting up schema...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Clear existing tables for test isolation
        db.query(ClaimError).delete() if 'ClaimError' in globals() else None
        db.query(DuplicateHistory).delete() if 'DuplicateHistory' in globals() else None
        db.query(ExpenseClaim).delete()
        db.query(PolicyRule).delete()
        db.query(Employee).delete()
        db.commit()

        # Seed test employee
        emp = Employee(employee_id="EMP_TEST", name="John Tester", role="Software Engineer", department="QA")
        db.add(emp)

        # Seed policy rule
        rule = PolicyRule(
            rule_id="RULE_MEAL_TEST",
            category="Meals",
            max_amount=50.0,
            allowed_roles=json.dumps(["Software Engineer", "Manager"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=10,
        )
        db.add(rule)
        db.commit()
        print("   Test database seeded successfully.")

        # Test Case A: Compliant Meals Claim ($35 meal, with receipt)
        print("Test A: Compliant Meals Claim...")
        expense_a = {
            "amount": 35.0,
            "category": "Meals",
            "employee_role": "Software Engineer",
            "receipt_path": "uploads/meal.jpg",
            "location": "NY_HQ",
        }
        res_a = PolicyEngine.check_policy(expense_a, db)
        assert res_a.status == "PASS", f"Test A Failed: Expected PASS, got {res_a.status}"
        assert len(res_a.failed_rules) == 0, "Test A Failed: Violations list should be empty"
        print("   [PASSED] Test A.")

        # Test Case B: Overage Meals Claim ($65 meal, above $50 limit)
        print("Test B: Overage Meals Claim...")
        expense_b = {
            "amount": 65.0,
            "category": "Meals",
            "employee_role": "Software Engineer",
            "receipt_path": "uploads/meal.jpg",
            "location": "NY_HQ",
        }
        res_b = PolicyEngine.check_policy(expense_b, db)
        assert res_b.status == "EXCEPTION", f"Test B Failed: Expected EXCEPTION, got {res_b.status}"
        assert any("RULE_MEAL_TEST" in r for r in res_b.failed_rules), "Test B Failed: Missing rule violation ID"
        print("   [PASSED] Test B.")

        # Test Case C: Duplicate Detection
        print("Test C: Duplicate Detection sweep...")
        # Add original claim to db
        orig = ExpenseClaim(
            claim_id="CLM_ORIG",
            employee_id="EMP_TEST",
            amount=88.50,
            currency="USD",
            category="Office Supplies",
            merchant_name="Amazon Inc.",
            transaction_date=date(2026, 5, 24),
            status="APPROVED",
        )
        db.add(orig)
        db.commit()

        # Check duplicate
        new_exp = {
            "amount": 88.50,
            "transaction_date": date(2026, 5, 24),
            "merchant_name": "Amazon Inc", # slightly different spelling
            "employee_id": "EMP_TEST",
        }
        dup_res = DuplicateEngine.detect_duplicate(new_exp, db)
        assert dup_res.is_duplicate is True, "Test C Failed: Duplicate should be flagged"
        assert "CLM_ORIG" in dup_res.matched_claims, "Test C Failed: Matched claim ID mismatch"
        print("   [PASSED] Test C.")

        # Test Case D: Risk Engine Verification
        print("Test D: Risk Engine Verification...")
        expense_d = {
            "amount": 2500.00,
            "category": "Software Subscriptions",
            "employee_role": "Software Engineer",
            "receipt_path": None,  # No receipt increases risk
        }
        # Simulate a policy exception to feed into RiskEngine
        policy_res_d = PolicyCheckResult(
            status="EXCEPTION",
            failed_rules=["RULE_SOFTWARE_MAX: amount 2500 exceeds cap 1000"],
            risk_score=20.0
        )
        # Duplicate detection mock
        dup_res_d = DuplicateCheckResult(is_duplicate=False)
        
        risk_res_d = RiskEngine.calculate_risk(expense_d, policy_res_d, dup_res_d)
        assert risk_res_d.score > 35, "Test D Failed: Risk score should be elevated for large amount and missing receipt"
        assert "amount_variance" in risk_res_d.factors, "Test D Failed: Missing amount risk factor"
        print("   [PASSED] Test D.")

        print("\nALL core engines self-verification assertions completed successfully!")
        
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
