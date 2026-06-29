"""
ExpenseOps Database Module
===========================
SQLAlchemy 2.0 ORM models, engine/session setup, table creation, and seed data.

Every model maps 1-to-1 with the tables defined in the System Design Document (SDD).
Indexes are created for the most common query patterns (duplicate lookup,
employee filtering, audit-log time-range scans).
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Generator

import bcrypt

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    inspect,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from backend.config import get_settings

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Engine & Session Factory
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

settings = get_settings()

# We maintain a global variable for the active environment: "demo" (SQLite) or "production" (Supabase)
ACTIVE_ENV = "demo"

# 1. SQLite Engine (Demo)
sqlite_connect_args = {"check_same_thread": False}
sqlite_engine = create_engine(
    settings.DATABASE_URL,
    connect_args=sqlite_connect_args,
    echo=False,
)
SqliteSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)

# 2. Postgres Engine (Production / Supabase)
postgres_engine = None
PostgresSessionLocal = None
if settings.SUPABASE_URL:
    postgres_engine = create_engine(
        settings.SUPABASE_URL,
        echo=False,
    )
    PostgresSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=postgres_engine)

# For backwards compatibility with init_db, we alias engine to sqlite_engine by default, 
# but init_db will be modified to support both.
engine = sqlite_engine


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Base Class
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base."""
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ORM Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Employee(Base):
    """
    An employee who can submit expense claims.
    Keyed by a human-readable employee_id (e.g. "EMP001").
    """
    __tablename__ = "employees"

    employee_id = Column(String(64), primary_key=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    department = Column(String, nullable=False)
    
    # Auth fields
    email = Column(String, unique=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    account_status = Column(String, default="APPROVED") # PENDING_APPROVAL, APPROVED, REJECTED
    manager_id = Column(String(64), ForeignKey("employees.employee_id"), nullable=True)

    # Relationships
    claims = relationship("ExpenseClaim", back_populates="employee")
    manager = relationship("Employee", remote_side=[employee_id], backref="subordinates")

class AccountApproval(Base):
    """
    Tracks multi-signature account approvals for high-level roles.
    """
    __tablename__ = "account_approvals"

    approval_id = Column(Integer, primary_key=True, autoincrement=True)
    pending_employee_id = Column(String(64), ForeignKey("employees.employee_id"), nullable=False)
    approver_id = Column(String(64), ForeignKey("employees.employee_id"), nullable=False)
    approver_role = Column(String, nullable=False)
    status = Column(String, default="APPROVED")
    timestamp = Column(DateTime, default=datetime.utcnow)

class OTPVerification(Base):
    """
    Stores OTP codes generated during signup.
    """
    __tablename__ = "otp_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, index=True, nullable=False)
    otp_code = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class ExpenseClaim(Base):
    """
    A single expense submission.  Goes through the validation pipeline
    (policy → risk → duplicate) before landing in a terminal status.
    """
    __tablename__ = "expense_claims"

    claim_id = Column(
        String(64), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    employee_id = Column(
        String(64),
        ForeignKey("employees.employee_id"),
        nullable=False,
    )
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD")
    category = Column(String(64), nullable=False)
    merchant_name = Column(String(255), nullable=False)
    transaction_date = Column(Date, nullable=False)
    submission_timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(32), default="PENDING")
    risk_score = Column(Numeric(5, 2), default=0)
    receipt_path = Column(String, nullable=True)
    system_notes = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)

    # Relationships
    employee = relationship("Employee", back_populates="claims")
    errors = relationship("ClaimError", back_populates="claim")

    @property
    def employee_name(self):
        return self.employee.name if self.employee else None

    # ── Composite index for fast duplicate lookups ──────────────────────
    __table_args__ = (
        Index("idx_claims_dup_lookup", "amount", "transaction_date", "merchant_name"),
        Index("idx_claims_employee", "employee_id"),
    )


class ClaimError(Base):
    """
    Records each policy rule that a claim violated.
    One claim can have zero-to-many errors.
    """
    __tablename__ = "claim_errors"

    error_id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(
        String(64),
        ForeignKey("expense_claims.claim_id"),
        nullable=False,
    )
    rule_violated = Column(String, nullable=False)

    claim = relationship("ExpenseClaim", back_populates="errors")


class PolicyRule(Base):
    """
    A single policy rule loaded from the JSON policy file and cached in the DB.
    Rules are matched by category + employee role, with the highest-precedence
    rule winning when multiple rules match.
    """
    __tablename__ = "policy_rules"

    rule_id = Column(String, primary_key=True)
    category = Column(String, nullable=False)
    max_amount = Column(Float, nullable=False)
    allowed_roles = Column(Text, nullable=True)        # JSON-encoded list
    location_restrictions = Column(Text, nullable=True) # JSON-encoded list
    requires_receipt = Column(Boolean, default=True)
    precedence = Column(Integer, default=0)


class SystemAuditLedger(Base):
    """
    Immutable audit trail.  Every significant action (submit, approve, reject,
    escalate) is logged here with before/after state snapshots.
    """
    __tablename__ = "system_audit_ledger"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    actor_id = Column(String(64), nullable=False)
    action_type = Column(String(64), nullable=False)
    target_resource = Column(String(128), nullable=False)
    before_state_json = Column(Text, nullable=True)
    after_state_json = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
    )


class DuplicateHistory(Base):
    """
    Stores every duplicate pair the DuplicateEngine has flagged.
    Useful for analytics and audit reviews.
    """
    __tablename__ = "duplicate_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_claim_id = Column(
        String(64), ForeignKey("expense_claims.claim_id"), nullable=False
    )
    duplicate_claim_id = Column(
        String(64), ForeignKey("expense_claims.claim_id"), nullable=False
    )
    merchant = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    employee = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    similarity_score = Column(Float, nullable=False)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FastAPI Dependency – yields a DB session per request
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_db() -> Generator[Session, None, None]:
    """
    Dependency-injection generator for FastAPI.
    Yields session based on ACTIVE_ENV.
    """
    global ACTIVE_ENV
    if ACTIVE_ENV == "production" and PostgresSessionLocal:
        db = PostgresSessionLocal()
    else:
        db = SqliteSessionLocal()
        
    try:
        yield db
    finally:
        db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Seed Data
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def seed_data(db: Session) -> None:
    """
    Populate the database with realistic demo data.
    Idempotent – skips if employees already exist.
    """
    # Guard: don't re-seed if we already have data
    if db.query(Employee).first() is not None or db.query(PolicyRule).first() is not None:
        return

    default_hash = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8")

    # ── 1. Employees ────────────────────────────────────────────────────
    employees = [
        Employee(employee_id="EMP001", name="John Smith", email="john@expenseops.com", hashed_password=default_hash, account_status="APPROVED",
                 role="Software Engineer", department="Engineering"),
        Employee(employee_id="EMP003", name="Mike Johnson", email="mike@expenseops.com", hashed_password=default_hash, account_status="APPROVED",
                 role="Manager", department="Sales"),
        Employee(employee_id="EMP004", name="Natasha Kapoor", email="natasha@expenseops.com", hashed_password=default_hash, account_status="APPROVED",
                 role="VP", department="Operations"),
    ]
    db.add_all(employees)
    db.flush()  # make employee_ids available for FK references

    # ── 2. Policy Rules (matching SDD §8.3) ─────────────────────────────
    policy_rules = [
        # Meals – standard engineers/analysts
        PolicyRule(
            rule_id="RULE_MEAL_ENG",
            category="Meals",
            max_amount=75.0,
            allowed_roles=json.dumps(["Software Engineer", "Analyst", "Manager"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=10,
        ),
        # Meals – directors & above get higher limit
        PolicyRule(
            rule_id="RULE_MEAL_DIR",
            category="Meals",
            max_amount=150.0,
            allowed_roles=json.dumps(["Director", "VP", "CEO"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=20,
        ),
        # Entertainment cap
        PolicyRule(
            rule_id="RULE_ENT_CAP",
            category="Entertainment",
            max_amount=200.0,
            allowed_roles=json.dumps(["Manager", "Director", "VP", "CEO"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=10,
        ),
        # Hotel – standard
        PolicyRule(
            rule_id="RULE_HOTEL_STD",
            category="Travel-Hotel",
            max_amount=250.0,
            allowed_roles=json.dumps(["Software Engineer", "Analyst", "Manager"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=10,
        ),
        # Hotel – directors/VP
        PolicyRule(
            rule_id="RULE_HOTEL_DIR",
            category="Travel-Hotel",
            max_amount=500.0,
            allowed_roles=json.dumps(["Director", "VP", "CEO"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=20,
        ),
        # Air travel
        PolicyRule(
            rule_id="RULE_TRAVEL_AIR",
            category="Travel-Air",
            max_amount=1500.0,
            allowed_roles=json.dumps(["Software Engineer", "Analyst", "Manager",
                                       "Director", "VP", "CEO"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=10,
        ),
        # Software / subscriptions
        PolicyRule(
            rule_id="RULE_SOFTWARE",
            category="Software",
            max_amount=500.0,
            allowed_roles=json.dumps(["Software Engineer", "Manager",
                                       "Director", "VP"]),
            location_restrictions=json.dumps([]),
            requires_receipt=False,
            precedence=10,
        ),
        # Office supplies
        PolicyRule(
            rule_id="RULE_OFFICE",
            category="Office Supplies",
            max_amount=200.0,
            allowed_roles=json.dumps(["Software Engineer", "Analyst", "Manager",
                                       "Director", "VP", "CEO"]),
            location_restrictions=json.dumps([]),
            requires_receipt=True,
            precedence=10,
        ),
        # Ground transport
        PolicyRule(
            rule_id="RULE_GROUND",
            category="Travel-Ground",
            max_amount=100.0,
            allowed_roles=json.dumps(["Software Engineer", "Analyst", "Manager",
                                       "Director", "VP", "CEO"]),
            location_restrictions=json.dumps([]),
            requires_receipt=False,
            precedence=10,
        ),
    ]
    db.add_all(policy_rules)
    db.flush()

    # ── 3. Expense Claims ───────────────────────────────────────────────
    # 25 claims with a realistic mix:
    #   • 5 over-limit violations
    #   • 2 duplicate pairs (same merchant+amount, dates within 2 days)
    #   • 3 high-risk (risk_score >= 70)
    #   • Mixed statuses: PENDING, APPROVED, EXCEPTION_HOLD, REJECTED
    base_date = date(2026, 5, 1)

    claims = [
        # ── Compliant claims ────────────────────────────────────────────
        # 1 – normal meal
        ExpenseClaim(
            claim_id="CLM001", employee_id="EMP001", amount=45.00,
            category="Meals", merchant_name="Starbucks",
            transaction_date=base_date, status="APPROVED",
            risk_score=10.0,
        ),
        # 2 – normal ground transport
        ExpenseClaim(
            claim_id="CLM002", employee_id="EMP001", amount=32.50,
            category="Travel-Ground", merchant_name="Uber",
            transaction_date=base_date + timedelta(days=1), status="APPROVED",
            risk_score=5.0,
        ),
        # 3 – director meal (within higher limit)
        ExpenseClaim(
            claim_id="CLM003", employee_id="EMP003", amount=120.00,
            category="Meals", merchant_name="KFC",
            transaction_date=base_date + timedelta(days=2), status="APPROVED",
            risk_score=15.0,
        ),
        # 4 – hotel within limit
        ExpenseClaim(
            claim_id="CLM004", employee_id="EMP003", amount=210.00,
            category="Travel-Hotel", merchant_name="Marriott",
            transaction_date=base_date + timedelta(days=3), status="APPROVED",
            risk_score=12.0,
        ),
        # 5 – office supplies
        ExpenseClaim(
            claim_id="CLM005", employee_id="EMP001", amount=55.00,
            category="Office Supplies", merchant_name="Amazon",
            transaction_date=base_date + timedelta(days=4), status="PENDING",
            risk_score=8.0,
        ),
        # 6 – software
        ExpenseClaim(
            claim_id="CLM006", employee_id="EMP001", amount=199.99,
            category="Software", merchant_name="Adobe",
            transaction_date=base_date + timedelta(days=5), status="APPROVED",
            risk_score=10.0,
        ),
        # 7 – air travel within limit
        ExpenseClaim(
            claim_id="CLM007", employee_id="EMP003", amount=850.00,
            category="Travel-Air", merchant_name="Delta Airlines",
            transaction_date=base_date + timedelta(days=6), status="APPROVED",
            risk_score=20.0,
        ),
        # 8 – ground transport
        ExpenseClaim(
            claim_id="CLM008", employee_id="EMP004", amount=28.00,
            category="Travel-Ground", merchant_name="Lyft",
            transaction_date=base_date + timedelta(days=7), status="APPROVED",
            risk_score=5.0,
        ),
        # 9 – VP hotel (within higher limit)
        ExpenseClaim(
            claim_id="CLM009", employee_id="EMP004", amount=420.00,
            category="Travel-Hotel", merchant_name="Hilton",
            transaction_date=base_date + timedelta(days=8), status="PENDING",
            risk_score=18.0,
        ),
        # 10 – coworking space
        ExpenseClaim(
            claim_id="CLM010", employee_id="EMP003", amount=150.00,
            category="Office Supplies", merchant_name="WeWork",
            transaction_date=base_date + timedelta(days=9), status="APPROVED",
            risk_score=12.0,
        ),

        # ── OVER-LIMIT VIOLATIONS (5 claims) ───────────────────────────
        # 11 – engineer meal over $75 cap
        ExpenseClaim(
            claim_id="CLM011", employee_id="EMP001", amount=95.00,
            category="Meals", merchant_name="Starbucks",
            transaction_date=base_date + timedelta(days=10), status="EXCEPTION_HOLD",
            risk_score=45.0,
            system_notes="Amount exceeds Meals cap for Software Engineer ($75).",
        ),
        # 12 – manager hotel over $250 cap
        ExpenseClaim(
            claim_id="CLM012", employee_id="EMP003", amount=310.00,
            category="Travel-Hotel", merchant_name="Marriott",
            transaction_date=base_date + timedelta(days=11), status="EXCEPTION_HOLD",
            risk_score=40.0,
            system_notes="Amount exceeds Travel-Hotel cap for Manager ($250).",
        ),
        # 13 – air travel over $1500 cap
        ExpenseClaim(
            claim_id="CLM013", employee_id="EMP001", amount=1800.00,
            category="Travel-Air", merchant_name="Delta Airlines",
            transaction_date=base_date + timedelta(days=12), status="REJECTED",
            risk_score=55.0,
            system_notes="Amount exceeds Travel-Air cap ($1500).",
        ),
        # 14 – software over $500 cap
        ExpenseClaim(
            claim_id="CLM014", employee_id="EMP001", amount=650.00,
            category="Software", merchant_name="Adobe",
            transaction_date=base_date + timedelta(days=13), status="EXCEPTION_HOLD",
            risk_score=42.0,
            system_notes="Amount exceeds Software cap ($500).",
        ),
        # 15 – entertainment over $200 cap
        ExpenseClaim(
            claim_id="CLM015", employee_id="EMP003", amount=275.00,
            category="Entertainment", merchant_name="KFC",
            transaction_date=base_date + timedelta(days=14), status="EXCEPTION_HOLD",
            risk_score=48.0,
            system_notes="Amount exceeds Entertainment cap ($200).",
        ),

        # ── DUPLICATE PAIRS (2 pairs → 4 claims) ───────────────────────
        # Pair A – same merchant (Uber), same amount ($32.50), dates 1 day apart
        # CLM002 is the original; CLM016 is the duplicate
        ExpenseClaim(
            claim_id="CLM016", employee_id="EMP001", amount=32.50,
            category="Travel-Ground", merchant_name="Uber",
            transaction_date=base_date + timedelta(days=2), status="EXCEPTION_HOLD",
            risk_score=60.0,
            system_notes="Potential duplicate of CLM002 (Uber, $32.50).",
        ),
        # Pair B – same merchant (Marriott), same amount ($210), dates 1 day apart
        # CLM004 is the original; CLM017 is the duplicate
        ExpenseClaim(
            claim_id="CLM017", employee_id="EMP003", amount=210.00,
            category="Travel-Hotel", merchant_name="Marriott",
            transaction_date=base_date + timedelta(days=4), status="EXCEPTION_HOLD",
            risk_score=62.0,
            system_notes="Potential duplicate of CLM004 (Marriott, $210).",
        ),

        # ── HIGH-RISK CLAIMS (risk_score >= 70) ────────────────────────
        # 18 – suspicious large entertainment, off-hours
        ExpenseClaim(
            claim_id="CLM018", employee_id="EMP003", amount=190.00,
            category="Entertainment", merchant_name="KFC",
            transaction_date=base_date + timedelta(days=15), status="PENDING",
            risk_score=75.0,
            system_notes="High-risk: off-hours submission + entertainment category.",
        ),
        # 19 – very large air travel + weekend
        ExpenseClaim(
            claim_id="CLM019", employee_id="EMP001", amount=1450.00,
            category="Travel-Air", merchant_name="Delta Airlines",
            transaction_date=date(2026, 5, 17), status="PENDING",
            risk_score=82.0,
            system_notes="High-risk: near-cap amount + weekend transaction.",
        ),
        # 20 – suspicious ground transport amount
        ExpenseClaim(
            claim_id="CLM020", employee_id="EMP001", amount=98.00,
            category="Travel-Ground", merchant_name="Lyft",
            transaction_date=date(2026, 5, 18), status="PENDING",
            risk_score=72.0,
            system_notes="High-risk: near-cap ground transport + weekend.",
        ),

        # ── Additional filler claims ───────────────────────────────────
        ExpenseClaim(
            claim_id="CLM021", employee_id="EMP003", amount=65.00,
            category="Meals", merchant_name="Starbucks",
            transaction_date=base_date + timedelta(days=16), status="APPROVED",
            risk_score=8.0,
        ),
        ExpenseClaim(
            claim_id="CLM022", employee_id="EMP004", amount=350.00,
            category="Travel-Hotel", merchant_name="Hilton",
            transaction_date=base_date + timedelta(days=17), status="APPROVED",
            risk_score=15.0,
        ),
        ExpenseClaim(
            claim_id="CLM023", employee_id="EMP003", amount=480.00,
            category="Software", merchant_name="Adobe",
            transaction_date=base_date + timedelta(days=18), status="PENDING",
            risk_score=22.0,
        ),
        ExpenseClaim(
            claim_id="CLM024", employee_id="EMP003", amount=45.00,
            category="Travel-Ground", merchant_name="Uber",
            transaction_date=base_date + timedelta(days=19), status="APPROVED",
            risk_score=10.0,
        ),
        ExpenseClaim(
            claim_id="CLM025", employee_id="EMP004", amount=130.00,
            category="Office Supplies", merchant_name="Amazon",
            transaction_date=base_date + timedelta(days=20), status="PENDING",
            risk_score=14.0,
        ),
    ]
    db.add_all(claims)
    db.flush()

    # ── 4. Claim Errors for the violations ──────────────────────────────
    claim_errors = [
        ClaimError(claim_id="CLM011", rule_violated="RULE_MEAL_ENG: amount $95.00 exceeds cap $75.00"),
        ClaimError(claim_id="CLM012", rule_violated="RULE_HOTEL_STD: amount $310.00 exceeds cap $250.00"),
        ClaimError(claim_id="CLM013", rule_violated="RULE_TRAVEL_AIR: amount $1800.00 exceeds cap $1500.00"),
        ClaimError(claim_id="CLM014", rule_violated="RULE_SOFTWARE: amount $650.00 exceeds cap $500.00"),
        ClaimError(claim_id="CLM015", rule_violated="RULE_ENT_CAP: amount $275.00 exceeds cap $200.00"),
        ClaimError(claim_id="CLM016", rule_violated="DUPLICATE: matches CLM002 (Uber $32.50)"),
        ClaimError(claim_id="CLM017", rule_violated="DUPLICATE: matches CLM004 (Marriott $210.00)"),
    ]
    db.add_all(claim_errors)

    # ── 5. Duplicate History records ────────────────────────────────────
    dup_records = [
        DuplicateHistory(
            original_claim_id="CLM002", duplicate_claim_id="CLM016",
            merchant="Uber", amount=32.50, employee="EMP001",
            date=base_date + timedelta(days=2), similarity_score=1.0,
        ),
        DuplicateHistory(
            original_claim_id="CLM004", duplicate_claim_id="CLM017",
            merchant="Marriott", amount=210.00, employee="EMP003",
            date=base_date + timedelta(days=4), similarity_score=1.0,
        ),
    ]
    db.add_all(dup_records)

    # ── 6. Sample audit entries ─────────────────────────────────────────
    audit_entries = [
        SystemAuditLedger(
            actor_id="SYSTEM", action_type="SEED_DATA",
            target_resource="database",
            after_state_json=json.dumps({"message": "Initial seed completed"}),
        ),
    ]
    db.add_all(audit_entries)

    db.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Initialization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def init_db() -> None:
    """
    Create all tables (if they don't exist) and seed demo data.
    Called once on application startup.
    """
    import os
    # Ensure the data/ directory exists for SQLite
    db_url = get_settings().DATABASE_URL
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    Base.metadata.create_all(bind=sqlite_engine)

    # Seed inside a fresh sqlite session
    db = SqliteSessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()
        
    # If Supabase is configured, initialize it as well
    if postgres_engine:
        Base.metadata.create_all(bind=postgres_engine)
        pdb = PostgresSessionLocal()
        try:
            seed_data(pdb)
        finally:
            pdb.close()
