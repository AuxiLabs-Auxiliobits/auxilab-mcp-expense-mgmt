"""Local SQLite persistence.

Uses the standard library's ``sqlite3`` — no ORM, no migration framework, no server.
The database file is created and migrated on first use, so a fresh clone works with no
setup step at all.

Persistence exists here for one concrete reason: the Duplicate Detector needs to compare
a new expense against ones it has already seen. Everything else the store does (the tool
audit trail, report aggregation) falls out of having that history available.

    >>> store = ExpenseStore(":memory:")
    >>> _ = store.add_line_item(employee_id="emp-1", merchant="Cafe", amount="12.00",
    ...                         expense_date="2026-06-01")
    >>> store.stats()["line_items"]
    1
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib import resources
from pathlib import Path
from typing import Any

from compliance_tools.schemas import Category, HistoricalLineItem, SummaryLineItem


def _default_db_path() -> Path:
    """Where the database lives when nothing overrides it.

    In a source checkout — the way this project is normally used — that is
    ``local_db/sqlite.db`` beside the code. Everything stays self-contained, and deleting
    the file to start over is obvious.

    Installed as a package, ``local_db/`` sits inside ``site-packages``, which may be
    read-only and is the wrong home for user data regardless. There we fall back to the
    platform's per-user data directory. ``EXPENSE_DB_PATH`` overrides both.
    """
    package_dir = Path(__file__).resolve().parent
    if (package_dir.parent / "pyproject.toml").is_file():
        return package_dir / "sqlite.db"

    if os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        root = Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "expense-compliance" / "sqlite.db"


#: Resolved once at import. ``local_db/sqlite.db`` in a checkout, a per-user data
#: directory when installed.
DEFAULT_DB_PATH = _default_db_path()

#: The demo dataset, as ``(id, employee, merchant, description, category, amount, date,
#: time, sheet, is_compliant)``. Every row has a receipt whose total equals the claimed
#: amount, so nothing here trips the parser or the amount-mismatch rule by accident.
#:
#: li-0006 repeats li-0005 exactly — same employee, timestamp and total — so the
#: Duplicate Detector has something real to find the moment the demo starts.
#:
#: Formatting is suppressed below: this is a data table, and one field per line would
#: turn six readable records into sixty lines.
# fmt: off
SEED_ROWS: tuple[tuple, ...] = (
    ("li-0001", "emp-001", "Noodle House", "Team lunch - project kickoff",
     Category.MEALS_ENTERTAINMENT, "48.88", "2026-06-01", "12:47:00", "sheet-001", True),
    ("li-0002", "emp-001", "Delta Airlines", "JFK to LAX - client visit",
     Category.TRAVEL_AIR, "320.00", "2026-06-02", "08:15:00", "sheet-001", True),
    ("li-0003", "emp-001", "Marriott", "2 nights - downtown LA",
     Category.TRAVEL_HOTEL, "462.00", "2026-06-03", "19:00:00", "sheet-001", False),
    ("li-0004", "emp-002", "GitHub", "Copilot annual subscription",
     Category.SOFTWARE_SUBSCRIPTIONS, "100.00", "2026-06-04", "10:00:00", "sheet-002", True),
    ("li-0005", "emp-002", "Uber", "Airport transfer",
     Category.TRAVEL_GROUND, "42.50", "2026-06-05", "07:30:00", "sheet-002", True),
    ("li-0006", "emp-002", "Uber", "Airport transfer (resubmitted)",
     Category.TRAVEL_GROUND, "42.50", "2026-06-05", "07:30:00", "sheet-003", False),
)
# fmt: on


def _iso(value: date | datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _money(value: Decimal | float | int | str | None, field: str = "amount") -> str | None:
    """Money goes to the database as text so it round-trips exactly.

    Raises ``ValueError`` rather than letting ``decimal.InvalidOperation`` surface, which
    is an opaque error to hit from three call frames away.
    """
    if value is None:
        return None
    try:
        return str(Decimal(str(value)))
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"{field} must be a number, got {value!r}") from e


def _to_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


class ExpenseStore:
    """A connection to the local expense database.

    Safe to share across threads: every statement runs under an internal lock, which is
    what the MCP server needs when its runtime dispatches tool calls from a pool.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = ":memory:" if path == ":memory:" else Path(path or DEFAULT_DB_PATH)
        if isinstance(self.path, Path):
            self.path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.initialize()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def initialize(self) -> None:
        """Create tables and indexes if they don't already exist."""
        schema = resources.files("local_db").joinpath("schema.sql").read_text("utf-8")
        with self._lock:
            self._conn.executescript(schema)
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ExpenseStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def add_line_item(
        self,
        *,
        employee_id: str,
        merchant: str,
        amount: Decimal | float | int | str,
        expense_date: date | str,
        description: str = "",
        category: Category | str | None = None,
        currency: str = "USD",
        receipt_datetime: datetime | str | None = None,
        receipt_total: Decimal | float | int | str | None = None,
        has_receipt: bool = False,
        sheet_id: str | None = None,
        is_compliant: bool | None = None,
        line_item_id: str | None = None,
    ) -> str:
        """Insert a line item and return its id."""
        item_id = line_item_id or uuid.uuid4().hex
        category_value = category.value if isinstance(category, Category) else category

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO line_items (
                    id, employee_id, merchant, description, category, amount, currency,
                    expense_date, receipt_datetime, receipt_total, has_receipt, sheet_id,
                    is_compliant, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    item_id,
                    employee_id,
                    merchant,
                    description,
                    category_value,
                    _money(amount, "amount"),
                    currency,
                    _iso(expense_date),
                    _iso(receipt_datetime),
                    _money(receipt_total, "receipt_total"),
                    int(has_receipt),
                    sheet_id,
                    None if is_compliant is None else int(is_compliant),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            self._conn.commit()
        return item_id

    def record_analysis(
        self, tool: str, result: dict[str, Any], line_item_id: str | None = None
    ) -> None:
        """Append a tool run to the audit trail."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO analyses (line_item_id, tool, result_json, created_at) "
                "VALUES (?,?,?,?)",
                (
                    line_item_id,
                    tool,
                    json.dumps(result, default=str),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            self._conn.commit()

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def history_for(
        self,
        employee_id: str,
        *,
        exclude_id: str | None = None,
        sheet_id: str | None = None,
    ) -> list[HistoricalLineItem]:
        """Prior line items for an employee, shaped for the Duplicate Detector.

        ``sheet_id`` marks items from that same submission, which the detector escalates
        to an intra-sheet duplicate. ``exclude_id`` omits the candidate itself when it has
        already been persisted.
        """
        rows = self._query(
            "SELECT id, employee_id, receipt_datetime, amount AS total, sheet_id "
            "FROM line_items WHERE employee_id = ? AND (? IS NULL OR id != ?) ORDER BY id",
            (employee_id, exclude_id, exclude_id),
        )
        return [
            HistoricalLineItem(
                line_item_id=row["id"],
                employee_id=row["employee_id"],
                receipt_datetime=_to_datetime(row["receipt_datetime"]),
                total=Decimal(row["total"]),
                same_sheet=bool(sheet_id and row["sheet_id"] == sheet_id),
            )
            for row in rows
        ]

    def line_items(self, employee_id: str | None = None) -> list[dict[str, Any]]:
        """All stored line items, newest first."""
        if employee_id:
            rows = self._query(
                "SELECT * FROM line_items WHERE employee_id = ? ORDER BY created_at DESC, id",
                (employee_id,),
            )
        else:
            rows = self._query("SELECT * FROM line_items ORDER BY created_at DESC, id")
        return [dict(row) for row in rows]

    def summary_items(self, employee_id: str | None = None) -> list[SummaryLineItem]:
        """Stored items shaped for the Report Summariser.

        Items with an unknown category fall into ``Other``; items never assessed for
        compliance are counted as compliant, so an unreviewed sheet reads as 100% rather
        than as an unexplained pile of violations.
        """
        out: list[SummaryLineItem] = []
        for row in self.line_items(employee_id):
            try:
                category = Category(row["category"]) if row["category"] else Category.OTHER
            except ValueError:
                category = Category.OTHER
            out.append(
                SummaryLineItem(
                    category=category,
                    amount=Decimal(row["amount"]),
                    is_compliant=bool(row["is_compliant"])
                    if row["is_compliant"] is not None
                    else True,
                )
            )
        return out

    def recent_analyses(self, limit: int = 20) -> list[dict[str, Any]]:
        """The most recent tool runs from the audit trail."""
        rows = self._query(
            "SELECT id, line_item_id, tool, result_json, created_at FROM analyses "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "id": row["id"],
                "line_item_id": row["line_item_id"],
                "tool": row["tool"],
                "result": json.loads(row["result_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def stats(self) -> dict[str, Any]:
        """Row counts and totals. ``total_amount`` is a ``Decimal``, exact to the cent."""
        counts = self._query(
            "SELECT COUNT(*) AS items, COUNT(DISTINCT employee_id) AS employees FROM line_items"
        )[0]
        analyses = self._query("SELECT COUNT(*) AS n FROM analyses")[0]

        # Summed in Python rather than with SQL's SUM(CAST(amount AS REAL)): casting to
        # REAL would reintroduce exactly the float imprecision that storing money as TEXT
        # exists to avoid.
        amounts = self._query("SELECT amount FROM line_items")
        total = sum((Decimal(row["amount"]) for row in amounts), Decimal("0"))

        return {
            "line_items": counts["items"],
            "employees": counts["employees"],
            "analyses": analyses["n"],
            "total_amount": total,
            "path": str(self.path),
        }

    # ------------------------------------------------------------------ #
    # Maintenance
    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        """Drop all rows, keeping the schema."""
        with self._lock:
            self._conn.execute("DELETE FROM analyses")
            self._conn.execute("DELETE FROM line_items")
            self._conn.commit()

    def seed(self) -> int:
        """Load the deterministic demo dataset. Returns the number of rows inserted."""
        for item_id, employee, merchant, note, category, amount, day, clock, sheet, ok in SEED_ROWS:
            self.add_line_item(
                line_item_id=item_id,
                employee_id=employee,
                merchant=merchant,
                description=note,
                category=category,
                amount=amount,
                expense_date=day,
                receipt_datetime=f"{day}T{clock}",
                receipt_total=amount,
                has_receipt=True,
                sheet_id=sheet,
                is_compliant=ok,
            )
        return len(SEED_ROWS)


_default_store: ExpenseStore | None = None
_default_lock = threading.Lock()


def get_store(path: str | Path | None = None) -> ExpenseStore:
    """Return the process-wide store, creating and seeding it on first call.

    With no argument the location comes from ``EXPENSE_DB_PATH``, falling back to
    ``local_db/sqlite.db``. Resolving it here rather than in each caller is what keeps the
    demo, the CLI and the MCP server pointing at the same database.

    A brand-new database is seeded so a fresh clone has data to work with immediately; an
    existing one is left exactly as the user left it.

    Asking for a different path than the cached store closes the old one and opens the new
    one — silently handing back a store pointing somewhere else would be a hard bug to spot.
    """
    global _default_store

    if path is None:
        path = os.getenv("EXPENSE_DB_PATH") or None
    requested = ":memory:" if path == ":memory:" else Path(path or DEFAULT_DB_PATH)

    with _default_lock:
        if _default_store is not None and _default_store.path != requested:
            _default_store.close()
            _default_store = None

        if _default_store is None:
            fresh = requested == ":memory:" or not requested.exists()
            _default_store = ExpenseStore(requested)
            if fresh or _default_store.stats()["line_items"] == 0:
                _default_store.seed()

        return _default_store
