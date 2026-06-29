"""Quick read-only dump of the SQLite dev database. Usage: python inspect_db.py [path]"""
import sqlite3
import sys

db = sys.argv[1] if len(sys.argv) > 1 else "expense.db"
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row

tables = [r[0] for r in c.execute(
    "select name from sqlite_master where type='table' order by name")]
print(f"DB: {db}")
print("TABLES:", tables, "\n")

for t in tables:
    rows = c.execute(f"select * from {t}").fetchall()
    print(f"=== {t} ({len(rows)} rows) ===")
    for r in rows:
        print("  ", dict(r))
    print()
