# 056 - Stop fetching rows beyond the row cap

- Repo: dbridge
- Status: planned
- Change: [bound-result-fetch](../../openspec/changes/bound-result-fetch/proposal.md)
- Origin: Exploration of local-database performance after planning
  [adopt-async-orchestration](../../openspec/changes/archive/2026-09-24-adopt-async-orchestration/proposal.md).

## Problem / opportunity

Both registered Adapters call `fetchall()` in `execute`, and the
[executor](../../src/dbridge/core/executor.py) applies `settings.max_rows`
(default 100) afterwards. A large local result is fully materialized as Python
lists and then almost entirely discarded.

Evidence, measured on a 2,000,000-row, 4-column table with the same
`[list(r) for r in ...]` shape the Adapters use (SQLite 3.50.4, DuckDB 1.1.3):

```text
                                   time       peak memory
sqlite  fetchall                 3,475 ms       705 MB
sqlite  fetchmany(101)               0.2 ms      ~0 MB
sqlite  ORDER BY + fetchmany(101)  428 ms        ~0 MB
duckdb  fetchall                 4,840 ms       857 MB
duckdb  fetchmany(101)               0.9 ms      ~0 MB
```

JSON encoding of the 100 returned rows takes about 0.1 ms, so serialization is
not the cost. Queries whose work precedes the first row, such as sorts and
aggregates, are not helped by bounded fetching; cancellation from
[009](009-query-cancellation.md) covers them.

## Desired outcome

Each Adapter fetches at most `max_rows + 1` rows and stops, so the executor can
still decide truncation. The wire shape does not change: `row_count` continues to
mean rows returned, and the existing truncation warning stays accurate because it
never reported a total. Server-only; no client change is needed.

Decided in exploration:

- Plan this as its own change after `adopt-async-orchestration` is archived. That
  change keeps its non-goal of applying the cap after materialization, and this
  one adds the limit to the async Adapter `execute` it introduces.
- Fetching rows past the cap (pages, cursors, streaming) is out of scope and
  stays with [013](013-large-results.md).

## Notes and references

Risks to cover with behavior tests:

- A partially consumed SQLite cursor keeps its statement active, which holds a
  read transaction open in autocommit mode and can block writers from other
  processes. Finalize the cursor after the bounded fetch.
- Stopping early must not stop a write early. SQLite applies all changes of a
  `... RETURNING` statement on its first step; verify DuckDB behaves the same
  before relying on it.

Inspect [SqliteAdapter](../../src/dbridge/adapters/sqlite.py),
[DuckDBAdapter](../../src/dbridge/adapters/duckdb.py), the thread-backed Adapter
base introduced by the async change, and
[settings](../../src/dbridge/config/settings.py).
