"""Build the sample databases from examples/sample.sql.

Produces examples/sample.db (sqlite) and examples/sample.duckdb, so both
registered adapters can be exercised against the same schema. Both are
generated and gitignored; sample.sql is the source of truth.

    uv run python scripts/make_sample_db.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_PATH = ROOT / "examples" / "sample.sql"
DB_PATH = ROOT / "examples" / "sample.db"
DUCKDB_PATH = ROOT / "examples" / "sample.duckdb"


def _line_items() -> list[tuple]:
    # 220 line items: more than the default max_rows (100), so a plain
    # `SELECT * FROM order_items` demonstrates the truncation warning.
    return [
        (i, (i % 10) + 1, (i % 10) + 1, (i % 4) + 1, round(19.99 + (i % 17) * 12.5, 2))
        for i in range(1, 221)
    ]


def build_sqlite() -> Path:
    DB_PATH.unlink(missing_ok=True)
    con = sqlite3.connect(DB_PATH, isolation_level=None)
    con.executescript(SQL_PATH.read_text())
    con.executemany(
        "INSERT INTO order_items (id, order_id, product_id, quantity, unit_price)"
        " VALUES (?, ?, ?, ?, ?)",
        _line_items(),
    )
    con.close()
    return DB_PATH


def build_duckdb() -> Path:
    import duckdb

    DUCKDB_PATH.unlink(missing_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH))
    # duckdb rejects the sqlite-style PRAGMA, so strip comments (otherwise the
    # header comment hides the PRAGMA from the check below) and replay the
    # script statement by statement, skipping what duckdb cannot parse.
    script = "\n".join(
        line for line in SQL_PATH.read_text().splitlines()
        if not line.strip().startswith("--")
    )
    for statement in script.split(";"):
        statement = statement.strip()
        if not statement or statement.upper().startswith("PRAGMA"):
            continue
        con.execute(statement)
    con.executemany(
        "INSERT INTO order_items (id, order_id, product_id, quantity, unit_price)"
        " VALUES (?, ?, ?, ?, ?)",
        _line_items(),
    )
    con.close()
    return DUCKDB_PATH


TABLES = ("customers", "order_items", "orders", "products")


def _summarize(label: str, counts: dict[str, int]) -> None:
    print(label)
    for table, n in counts.items():
        print(f"  {table:<12} {n:>4} rows")


if __name__ == "__main__":
    sqlite_path = build_sqlite()
    con = sqlite3.connect(sqlite_path)
    _summarize(
        f"built {sqlite_path}",
        {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES},  # noqa: S608
    )
    con.close()

    duckdb_path = build_duckdb()
    import duckdb

    dcon = duckdb.connect(str(duckdb_path))
    _summarize(
        f"built {duckdb_path}",
        {t: dcon.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES},  # noqa: S608
    )
    dcon.close()
