# 062 - Investigate an intermittent DuckDB metadata timeout

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: `add-mysql-adapter` baseline verification, 2026-09-25

## Problem / opportunity

A Python 3.12 baseline run of
`uv run --no-sync --group test pytest --ignore=tests/adapters/test_optional_mysql.py --ignore=tests/adapters/mysql -q`
reported 581 passed and one failure in
`test_duckdb_metadata_runs_beside_query_and_sees_attached_catalog`.
At line 97, `list_tables(("side", "main"))` exceeded its three-second `wait_for`
deadline. SQLite and DuckDB code had not changed. An immediate focused rerun
passed in 0.22 seconds.

The timeout was observed; its cause is not established. This may be scheduling
sensitivity, contention, or a runtime issue. One successful rerun does not explain
the original failure.

## Desired outcome

Reproduce and distinguish a DuckDB metadata concurrency defect from an unreliable
test deadline. Preserve the requirement that metadata can complete while the
same Session's query runs, and improve the behavior or verification based on the
resulting evidence.

## Notes and references

See [the concurrency test](../../tests/adapters/test_driver_cancellation.py) and
[ADR-0003](../adr/0003-async-orchestration.md). Keep this investigation separate
from the MySQL Adapter change unless further evidence establishes a connection.
