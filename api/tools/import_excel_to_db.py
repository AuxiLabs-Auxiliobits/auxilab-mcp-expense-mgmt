"""Load an .xlsx snapshot (produced by export_db_to_excel.py) into a SQLite expense DB.

Two modes:

  --mode replace (default): each table in the workbook is emptied and repopulated from the
    sheet — the DB becomes an exact copy of the snapshot's data. Tables the DB doesn't have
    are created from the sheet. Use this to adopt a teammate's dataset wholesale.

  --mode add (additive): NON-destructive. Your existing tables and their rows are left exactly
    as they are; only *new* tables (present in the snapshot, absent in your DB) are created and
    loaded, and *new* columns (in the snapshot, missing from an existing table) are added via
    ALTER TABLE. Use this to pull in a teammate's new tables/columns without touching your data.

Foreign-key enforcement is off for the load and everything runs in one transaction.

NOTE on created tables: the workbook carries column names + data, not full DDL, so a created
table's schema is *inferred* (types from the data; `id` becomes PRIMARY KEY) and lacks the real
FKs/constraints/indexes. For production-correct schema, get the teammate's SQLModel model +
Alembic migration instead; this is a pragmatic dev-data convenience.

Usage (from api/, venv active) — back up first:
    python tools/import_excel_to_db.py snap.xlsx                 # replace (default)
    python tools/import_excel_to_db.py snap.xlsx --mode add      # additive: only new tables/cols
    python tools/import_excel_to_db.py snap.xlsx --only ai_feedback,ai_recommendation --mode add
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sqlite3
from pathlib import Path

from openpyxl import load_workbook

_DEFAULT_DB = Path(__file__).resolve().parents[2] / "expense.db"


def _db_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _col_meta(conn: sqlite3.Connection, table: str) -> dict[str, tuple[str, int, object]]:
    """name -> (type, notnull, default) from PRAGMA table_info."""
    return {
        c[1]: (c[2] or "", c[3], c[4])
        for c in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    }


def _notnull_fallback(col_type: str, default: object) -> object:
    """A safe value for a NOT NULL column whose snapshot cell is empty."""
    if default is not None:
        return str(default).strip("'\"")
    t = col_type.upper()
    if any(k in t for k in ("INT", "REAL", "NUM", "DEC", "FLOAT", "DOUB")):
        return 0
    if "DATE" in t or "TIME" in t:
        return "1970-01-01T00:00:00"  # recognizable sentinel — dev data only
    return ""


def _bind(v: object) -> object:
    """Make a cell value safe to bind in sqlite3 (datetimes -> ISO strings)."""
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.isoformat()
    return v


def _infer_type(values: list[object]) -> str:
    """Infer a SQLite column type from a column's sample values."""
    seen_float = seen_int = seen_any = False
    for v in values:
        if v is None:
            continue
        seen_any = True
        if isinstance(v, bool) or isinstance(v, int):
            seen_int = True
        elif isinstance(v, float):
            seen_float = True
        else:
            return "TEXT"  # strings, datetimes-as-iso, etc.
    if not seen_any:
        return "TEXT"
    if seen_float:
        return "REAL"
    return "INTEGER" if seen_int else "TEXT"


def _create_table(conn: sqlite3.Connection, name: str, header: list[str], rows: list[tuple]) -> None:
    defs = []
    for j, col in enumerate(header):
        typ = _infer_type([r[j] for r in rows])
        pk = " PRIMARY KEY" if col == "id" else ""
        defs.append(f'"{col}" {typ}{pk}')
    conn.execute(f'CREATE TABLE "{name}" ({", ".join(defs)})')


def _insert_rows(conn: sqlite3.Connection, name: str, cols: list[str], make_values) -> int:
    placeholders = ",".join("?" for _ in cols)
    collist = ",".join(f'"{c}"' for c in cols)
    sql = f'INSERT INTO "{name}" ({collist}) VALUES ({placeholders})'
    n = 0
    for vals in make_values:
        conn.execute(sql, vals)
        n += 1
    return n


def import_workbook(xlsx: Path, db_path: Path, only: set[str] | None, mode: str) -> None:
    if not xlsx.exists():
        raise SystemExit(f"snapshot not found: {xlsx}")
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path} (create it: alembic upgrade head, or start the API once)")

    wb = load_workbook(str(xlsx), read_only=True, data_only=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")
    existing = _db_tables(conn)

    loaded = 0
    notes: list[str] = []
    try:
        for name in wb.sheetnames:
            if name.startswith("_") or name == "alembic_version":
                continue
            if only and name not in only:
                continue

            ws = wb[name]
            it = ws.iter_rows(values_only=True)
            try:
                header = list(next(it))
            except StopIteration:
                continue  # empty sheet
            data = [tuple(r) for r in it]

            # ---- New table: create it and load all rows (both modes) ----
            if name not in existing:
                _create_table(conn, name, header, data)
                n = _insert_rows(
                    conn, name, header,
                    ([_bind(v) for v in row] for row in data),
                )
                loaded += n
                existing.add(name)
                print(f"  {name}: CREATED (inferred schema) + {n} rows")
                continue

            meta = _col_meta(conn, name)

            # ---- Additive mode: only add missing columns; never touch existing rows ----
            if mode == "add":
                new_cols = [c for c in header if c not in meta]
                for c in new_cols:
                    j = header.index(c)
                    typ = _infer_type([r[j] for r in data])
                    conn.execute(f'ALTER TABLE "{name}" ADD COLUMN "{c}" {typ}')
                if new_cols:
                    print(f"  {name}: added columns {new_cols} (rows kept as-is)")
                else:
                    print(f"  {name}: unchanged (no new columns)")
                continue

            # ---- Replace mode: empty + repopulate, back-filling NOT NULL gaps ----
            present = [c for c in header if c in meta]
            if not present:
                notes.append(f"{name} (no matching columns)")
                continue
            missing = [
                c for c, (typ, nn, dflt) in meta.items()
                if c not in header and nn and dflt is None
            ]
            cols = present + missing
            posn = {c: header.index(c) for c in present}

            conn.execute(f'DELETE FROM "{name}"')

            def values_for(row, cols=cols, meta=meta, posn=posn):
                out = []
                for c in cols:
                    typ, nn, dflt = meta[c]
                    if c in posn:
                        v = row[posn[c]]
                        if v is None and nn:
                            v = _notnull_fallback(typ, dflt)
                    else:
                        v = _notnull_fallback(typ, dflt)
                    out.append(_bind(v))
                return out

            n = _insert_rows(conn, name, cols, (values_for(row) for row in data))
            loaded += n
            extra = f" (back-filled: {', '.join(missing)})" if missing else ""
            print(f"  {name}: replaced with {n} rows{extra}")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        wb.close()

    print(f"done ({mode} mode). {loaded} rows loaded from {xlsx.name}.")
    for s in notes:
        print(f"  skipped {s}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Load an .xlsx DB snapshot into the SQLite expense DB.")
    ap.add_argument("xlsx", help="snapshot .xlsx produced by export_db_to_excel.py")
    ap.add_argument("--db", default=str(_DEFAULT_DB), help="target sqlite db (default: repo-root expense.db)")
    ap.add_argument("--only", help="comma-separated subset of tables to import")
    ap.add_argument(
        "--mode", choices=("replace", "add"), default="replace",
        help="replace = exact copy of snapshot data (default); add = only create new tables / add new columns",
    )
    args = ap.parse_args()
    only = {t.strip() for t in args.only.split(",")} if args.only else None
    import_workbook(Path(args.xlsx).resolve(), Path(args.db).resolve(), only, args.mode)


if __name__ == "__main__":
    main()
