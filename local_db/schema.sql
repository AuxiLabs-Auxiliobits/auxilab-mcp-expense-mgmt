-- Local SQLite schema. Created automatically on first use.
--
-- Money is stored as TEXT, not REAL: SQLite has no decimal type, and storing 48.88 as
-- a float and reading it back is how reconciliation bugs get introduced. Values round-trip
-- through Python's Decimal exactly.
--
-- Timestamps are ISO-8601 TEXT, which sorts correctly as a string.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS line_items (
    id               TEXT PRIMARY KEY,
    employee_id      TEXT NOT NULL,
    merchant         TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    category         TEXT,
    amount           TEXT NOT NULL,
    currency         TEXT NOT NULL DEFAULT 'USD',
    expense_date     TEXT NOT NULL,
    receipt_datetime TEXT,
    receipt_total    TEXT,
    has_receipt      INTEGER NOT NULL DEFAULT 0,
    sheet_id         TEXT,
    is_compliant     INTEGER,
    created_at       TEXT NOT NULL
);

-- The duplicate detector always queries by employee, so keep that path indexed.
CREATE INDEX IF NOT EXISTS idx_line_items_employee ON line_items (employee_id);
CREATE INDEX IF NOT EXISTS idx_line_items_sheet ON line_items (sheet_id);

-- Audit trail: one row per tool invocation, so any verdict can be explained later.
CREATE TABLE IF NOT EXISTS analyses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    line_item_id TEXT,
    tool         TEXT NOT NULL,
    result_json  TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (line_item_id) REFERENCES line_items (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analyses_tool ON analyses (tool);
CREATE INDEX IF NOT EXISTS idx_analyses_line_item ON analyses (line_item_id);
