# 056 - Stop fetching rows beyond the row cap

- Repo: dbridge
- Status: done
- Change: [bound-result-fetch](../../openspec/changes/archive/2026-09-24-bound-result-fetch/proposal.md)
- Origin: Exploration of local-database performance after planning
  [adopt-async-orchestration](../../openspec/changes/archive/2026-09-24-adopt-async-orchestration/proposal.md).

## Problem / opportunity

Before this change, both registered Adapters called `fetchall()` in `execute`, and the
[executor](../../src/dbridge/core/executor.py) applied `settings.max_rows`
(default 100) afterwards. A large local result was fully materialized as Python
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

## Resolution

Both registered Adapters now fetch at most the executor's requested
`max_rows + 1` rows. SQLite closes its cursor before replying; DuckDB's existing
metadata snapshot queries release its pending result. Tests verify prompt replies
for an unbounded SQLite result and a trillion-row DuckDB range, SQLite writer-lock
release, Session reuse, and complete effects of capped `INSERT/DELETE ... RETURNING`.
Fetching beyond the cap remains [013](013-large-results.md).

Measured on 2026-09-24 through `await adapter.execute("SELECT * FROM bench",
row_limit=101)`, including Lane dispatch and DuckDB metadata snapshots:

| Adapter | Median elapsed time | Peak traced Python allocation |
|---|---:|---:|
| SQLite 3.50.4 | 0.388 ms | 34,026 bytes |
| DuckDB 1.1.3 | 3.826 ms | 34,784 bytes |

The fixture was a temporary file-backed 2,000,000-row table on Python 3.12.12,
with columns `id INTEGER`, `label VARCHAR`, `value DOUBLE`, and `group_id INTEGER`.
For ids 0 through 1,999,999, values were `'row-' || id`, `id * 0.5`, and `id % 10`.
Five calls each returned 101 rows; setup and `count(*)` verification were outside
measurement. Each call used `time.perf_counter()` and a fresh `tracemalloc` session
after `gc.collect()`; the table reports median elapsed time and the largest peak.
Traced allocation excludes native driver memory and is not process RSS. The earlier
driver-only figures excluded Lane dispatch and metadata snapshots, so their
sub-millisecond DuckDB time is not directly comparable to this full Adapter call.
