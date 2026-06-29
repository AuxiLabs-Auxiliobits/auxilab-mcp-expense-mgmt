-- TripSense SQLite Schema
-- Business travel expense management

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS employees (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    department      TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'employee',
    manager_id      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (manager_id) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS trip_plans (
    id                  TEXT PRIMARY KEY,
    employee_id         TEXT NOT NULL,
    destination         TEXT NOT NULL,
    duration_days       INTEGER NOT NULL,
    purpose             TEXT NOT NULL,
    budget_breakdown    TEXT NOT NULL,  -- JSON: {category: amount}
    approval_token      TEXT UNIQUE,
    budget_cap          REAL,
    expiry              TEXT,
    status              TEXT NOT NULL DEFAULT 'draft',
    compliance_checked  INTEGER DEFAULT 0,
    violations          TEXT,           -- JSON array of violation strings
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS receipts (
    id                  TEXT PRIMARY KEY,
    employee_id         TEXT NOT NULL,
    trip_plan_id        TEXT,
    merchant            TEXT NOT NULL,
    receipt_date        TEXT NOT NULL,
    amount              REAL NOT NULL,
    line_items          TEXT,           -- JSON array of {description, amount}
    ocr_confidence      REAL DEFAULT 0.0,
    reconciliation_flag INTEGER DEFAULT 0,
    image_path          TEXT,
    category            TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (trip_plan_id) REFERENCES trip_plans(id)
);

CREATE TABLE IF NOT EXISTS expense_claims (
    id                  TEXT PRIMARY KEY,
    employee_id         TEXT NOT NULL,
    trip_plan_id        TEXT,
    merchant            TEXT NOT NULL,
    amount              REAL NOT NULL,
    claim_date          TEXT NOT NULL,
    category            TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    receipt_id          TEXT,
    description         TEXT,
    policy_violation    INTEGER DEFAULT 0,
    duplicate_risk      REAL DEFAULT 0.0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (trip_plan_id) REFERENCES trip_plans(id),
    FOREIGN KEY (receipt_id) REFERENCES receipts(id)
);

CREATE INDEX IF NOT EXISTS idx_trip_plans_employee ON trip_plans(employee_id);
CREATE INDEX IF NOT EXISTS idx_trip_plans_token ON trip_plans(approval_token);
CREATE INDEX IF NOT EXISTS idx_receipts_employee ON receipts(employee_id);
CREATE INDEX IF NOT EXISTS idx_receipts_trip ON receipts(trip_plan_id);
CREATE INDEX IF NOT EXISTS idx_claims_employee ON expense_claims(employee_id);
CREATE INDEX IF NOT EXISTS idx_claims_merchant_amount ON expense_claims(merchant, amount, claim_date);
CREATE INDEX IF NOT EXISTS idx_claims_trip ON expense_claims(trip_plan_id);
