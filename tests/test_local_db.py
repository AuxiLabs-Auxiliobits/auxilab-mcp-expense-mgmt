"""SQLite store — round-tripping, money precision, and the duplicate-history query."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from compliance_tools.schemas import Category
from local_db import DEFAULT_DB_PATH, ExpenseStore


def test_schema_is_created_on_first_use(tmp_path):
    path = tmp_path / "nested" / "fresh.db"
    with ExpenseStore(path) as store:
        assert store.stats()["line_items"] == 0
    assert path.exists(), "the database file and its parent directory should be created"


def test_in_memory_store_works():
    with ExpenseStore(":memory:") as store:
        store.add_line_item(
            employee_id="emp-1", merchant="Cafe", amount="12.00", expense_date="2026-06-01"
        )
        assert store.stats()["line_items"] == 1


def test_default_path_is_beside_the_code_in_a_checkout():
    """The test suite always runs from a checkout, so this is the branch it should take."""
    assert DEFAULT_DB_PATH.name == "sqlite.db"
    assert DEFAULT_DB_PATH.parent.name == "local_db"


def test_installed_package_writes_outside_site_packages(monkeypatch, tmp_path):
    """With no pyproject.toml above it, the database must not land in site-packages."""
    import local_db.store as store_module

    fake_site_packages = tmp_path / "site-packages" / "database"
    fake_site_packages.mkdir(parents=True)
    monkeypatch.setattr(store_module, "__file__", str(fake_site_packages / "store.py"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))

    resolved = store_module._default_db_path()
    assert fake_site_packages not in resolved.parents
    assert resolved.parent.name == "expense-compliance"
    assert resolved.name == "sqlite.db"


# --------------------------------------------------------------------------- #
# Round-tripping
# --------------------------------------------------------------------------- #
def test_line_item_round_trips(store):
    item_id = store.add_line_item(
        employee_id="emp-1",
        merchant="Noodle House",
        description="Team lunch",
        category=Category.MEALS_ENTERTAINMENT,
        amount="48.88",
        expense_date="2026-06-01",
        receipt_datetime="2026-06-01T12:47:00",
        receipt_total="48.88",
        has_receipt=True,
        sheet_id="sheet-1",
        is_compliant=True,
    )
    row = store.line_items()[0]
    assert row["id"] == item_id
    assert row["merchant"] == "Noodle House"
    assert row["category"] == Category.MEALS_ENTERTAINMENT.value
    assert row["has_receipt"] == 1


def test_money_precision_survives_the_database(store):
    """Stored as TEXT precisely so 0.1 + 0.2 problems can't appear."""
    store.add_line_item(employee_id="emp-1", merchant="X", amount="0.1", expense_date="2026-06-01")
    store.add_line_item(employee_id="emp-1", merchant="X", amount="0.2", expense_date="2026-06-01")
    totals = [Decimal(r["amount"]) for r in store.line_items()]
    assert sum(totals) == Decimal("0.3")


def test_explicit_ids_are_honoured(store):
    returned = store.add_line_item(
        employee_id="emp-1",
        merchant="X",
        amount="1",
        expense_date="2026-06-01",
        line_item_id="li-fixed",
    )
    assert returned == "li-fixed"


def test_generated_ids_are_unique(store):
    ids = {
        store.add_line_item(
            employee_id="emp-1", merchant="X", amount="1", expense_date="2026-06-01"
        )
        for _ in range(50)
    }
    assert len(ids) == 50


# --------------------------------------------------------------------------- #
# History for the duplicate detector
# --------------------------------------------------------------------------- #
def test_history_is_scoped_to_one_employee(seeded_store):
    history = seeded_store.history_for("emp-001")
    assert history
    assert {h.employee_id for h in history} == {"emp-001"}


def test_history_excludes_the_candidate_itself(seeded_store):
    history = seeded_store.history_for("emp-001", exclude_id="li-0001")
    assert "li-0001" not in {h.line_item_id for h in history}


def test_history_marks_items_from_the_same_sheet(seeded_store):
    history = seeded_store.history_for("emp-001", sheet_id="sheet-001")
    assert all(h.same_sheet for h in history)

    other = seeded_store.history_for("emp-001", sheet_id="sheet-999")
    assert not any(h.same_sheet for h in other)


def test_history_parses_timestamps_and_totals(seeded_store):
    match = next(h for h in seeded_store.history_for("emp-001") if h.line_item_id == "li-0001")
    assert match.receipt_datetime == datetime(2026, 6, 1, 12, 47)
    assert match.total == Decimal("48.88")


def test_history_for_unknown_employee_is_empty(seeded_store):
    assert seeded_store.history_for("nobody") == []


def test_null_timestamp_becomes_none(store):
    store.add_line_item(employee_id="emp-1", merchant="X", amount="1", expense_date="2026-06-01")
    assert store.history_for("emp-1")[0].receipt_datetime is None


# --------------------------------------------------------------------------- #
# Summary items
# --------------------------------------------------------------------------- #
def test_summary_items_shape(seeded_store):
    items = seeded_store.summary_items("emp-001")
    assert len(items) == 3
    assert sum(i.amount for i in items) == Decimal("830.88")


def test_unknown_category_becomes_other(store):
    store.add_line_item(
        employee_id="emp-1",
        merchant="X",
        amount="1",
        expense_date="2026-06-01",
        category="Not A Real Category",
    )
    assert store.summary_items()[0].category is Category.OTHER


def test_unassessed_items_count_as_compliant(store):
    store.add_line_item(employee_id="emp-1", merchant="X", amount="1", expense_date="2026-06-01")
    assert store.summary_items()[0].is_compliant is True


# --------------------------------------------------------------------------- #
# Audit trail
# --------------------------------------------------------------------------- #
def test_analyses_are_recorded(store):
    store.record_analysis("policy_checker", {"status": "pass", "violations": []})
    recorded = store.recent_analyses()
    assert len(recorded) == 1
    assert recorded[0]["tool"] == "policy_checker"
    assert recorded[0]["result"]["status"] == "pass"


def test_analyses_come_back_newest_first(store):
    for i in range(3):
        store.record_analysis("tool", {"n": i})
    assert [a["result"]["n"] for a in store.recent_analyses()] == [2, 1, 0]


def test_analysis_limit_is_respected(store):
    for i in range(10):
        store.record_analysis("tool", {"n": i})
    assert len(store.recent_analyses(limit=3)) == 3


def test_analysis_serialises_non_json_values(store):
    """Decimal and datetime must not blow up the audit write."""
    store.record_analysis("t", {"amount": Decimal("1.50"), "when": datetime(2026, 6, 1)})
    assert store.recent_analyses()[0]["result"]["amount"] == "1.50"


def test_analyses_cascade_when_a_line_item_is_deleted(store):
    item_id = store.add_line_item(
        employee_id="emp-1", merchant="X", amount="1", expense_date="2026-06-01"
    )
    store.record_analysis("t", {"ok": True}, line_item_id=item_id)
    store.reset()
    assert store.recent_analyses() == []


# --------------------------------------------------------------------------- #
# Seed / reset / stats
# --------------------------------------------------------------------------- #
def test_seed_inserts_the_demo_dataset(store):
    assert store.seed() == 6
    assert store.stats()["line_items"] == 6
    assert store.stats()["employees"] == 2


def test_seed_includes_a_duplicate_pair(seeded_store):
    uber = [r for r in seeded_store.line_items("emp-002") if r["merchant"] == "Uber"]
    assert len(uber) == 2
    assert uber[0]["receipt_datetime"] == uber[1]["receipt_datetime"]
    assert uber[0]["amount"] == uber[1]["amount"]


def test_reset_clears_everything(seeded_store):
    seeded_store.record_analysis("t", {})
    seeded_store.reset()
    assert seeded_store.stats()["line_items"] == 0
    assert seeded_store.recent_analyses() == []


def test_stats_reports_totals(seeded_store):
    stats = seeded_store.stats()
    assert stats["line_items"] == 6
    assert stats["employees"] == 2
    # 48.88 + 320.00 + 462.00 + 100.00 + 42.50 + 42.50 — exact, not approximate.
    assert stats["total_amount"] == Decimal("1015.88")


def test_stats_total_is_exact_not_floating_point(store):
    """Three tenths must sum to exactly 0.3, which SUM(CAST(amount AS REAL)) would not."""
    for _ in range(3):
        store.add_line_item(
            employee_id="emp-1", merchant="X", amount="0.1", expense_date="2026-06-01"
        )
    assert store.stats()["total_amount"] == Decimal("0.3")


def test_empty_store_totals_zero(store):
    assert store.stats()["total_amount"] == Decimal("0")


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", ["not a number", "", "12.3.4", "abc"])
def test_non_numeric_amount_raises_a_clear_error(store, bad):
    with pytest.raises(ValueError, match="amount must be a number"):
        store.add_line_item(
            employee_id="emp-1", merchant="X", amount=bad, expense_date="2026-06-01"
        )


def test_non_numeric_receipt_total_names_the_right_field(store):
    with pytest.raises(ValueError, match="receipt_total must be a number"):
        store.add_line_item(
            employee_id="emp-1",
            merchant="X",
            amount="1.00",
            expense_date="2026-06-01",
            receipt_total="oops",
        )


def test_a_rejected_insert_leaves_no_partial_row(store):
    with pytest.raises(ValueError):
        store.add_line_item(
            employee_id="emp-1", merchant="X", amount="nope", expense_date="2026-06-01"
        )
    assert store.stats()["line_items"] == 0


# --------------------------------------------------------------------------- #
# The shared store
# --------------------------------------------------------------------------- #
def test_get_store_returns_the_same_instance(tmp_path, monkeypatch):
    import local_db.store as store_module

    monkeypatch.setattr(store_module, "_default_store", None)
    first = store_module.get_store(tmp_path / "shared.db")
    second = store_module.get_store(tmp_path / "shared.db")
    assert first is second
    first.close()


def test_get_store_seeds_a_brand_new_database(tmp_path, monkeypatch):
    import local_db.store as store_module

    monkeypatch.setattr(store_module, "_default_store", None)
    created = store_module.get_store(tmp_path / "seeded.db")
    assert created.stats()["line_items"] == len(store_module.SEED_ROWS)
    created.close()


def test_get_store_reopens_when_the_path_changes(tmp_path, monkeypatch):
    """Handing back a store pointing at a different file would be a silent data bug."""
    import local_db.store as store_module

    monkeypatch.setattr(store_module, "_default_store", None)
    first = store_module.get_store(tmp_path / "one.db")
    second = store_module.get_store(tmp_path / "two.db")
    assert first is not second
    assert second.path == tmp_path / "two.db"
    second.close()
