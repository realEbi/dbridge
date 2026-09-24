## Why

`dbridge/execute` returns at most `max_rows` rows (default 100), but both registered
Adapters call `fetchall()` first and the executor discards the excess afterwards.
On a 2,000,000-row local table this spends 3.5 s (SQLite) to 4.8 s (DuckDB) and
0.7–0.9 GB of peak memory to return 100 rows; fetching `max_rows + 1` rows takes
under 1 ms. With async orchestration and cancellation shipped, this is the largest
remaining cost on the local query path. See [backlog 056](../../../../docs/backlog/056-bounded-result-fetch.md).

## What Changes

- Adapters stop reading query results once they hold one row more than the row cap.
  The extra row tells the executor whether to truncate; rows past it are never
  fetched from the driver. Execution time and memory no longer grow with the number
  of rows a query could return beyond the cap.
- The response is unchanged: `columns`, `rows`, `row_count` (rows returned),
  `execution_time_ms`, and `warnings`, with the same `result truncated to N rows`
  warning when more rows existed. A result exactly at the cap still carries no
  warning.
- A SQLite statement whose rows were not all read is finalized before the reply, so
  it does not keep a read lock on the database file that blocks other writers.
- Statements that write and return rows (`INSERT/UPDATE/DELETE ... RETURNING`) apply
  every change even when only the capped rows are returned. Probing both pinned
  drivers confirmed this; tests keep it that way.
- The Adapter `execute` coroutine gains an optional row limit. The executor always
  passes one.

Out of scope: fetching rows beyond the cap (pagination, server-side cursors,
streaming) stays with [backlog 013](../../../../docs/backlog/013-large-results.md).
Queries whose cost comes before the first row, such as sorts and aggregates over
large tables, get no faster; cancellation covers them. `max_rows` configuration
and validation are unchanged.

## Capabilities

### New Capabilities

- `query-results`: The shape of a `dbridge/execute` result, how the row cap
  truncates it and reports truncation, and the guarantees that capping gives: rows
  past the cap are not fetched, the capped statement releases its database
  resources, and writes are not cut short by capping.

### Modified Capabilities

None. `request-cancellation` and `request-concurrency` keep their requirements; a
bounded fetch still runs on the Session's query lane and remains interruptible.

## Impact

**Roadmap and backlog.** Advances milestone 2 (*Responsive queries and larger
results*) without resolving it: [013](../../../../docs/backlog/013-large-results.md)
keeps the delivery model for rows beyond the cap, and [010](../../../../docs/backlog/010-server-notifications.md)
is unaffected. Resolves [056](../../../../docs/backlog/056-bounded-result-fetch.md).

**Repositories.** Server only. No client repository change is needed.

**Protocol compatibility.** None. No method, param, result field, error code, or
warning text changes. Clients see the same responses sooner. Existing DDL replies
also remain unchanged: DuckDB's `CREATE TABLE` includes `columns: ["Count"]`
with no rows, while SQLite returns empty columns.

**Code.** `DBAdapter.execute` and `ThreadBackedAdapter` gain a row limit; the
SQLite and DuckDB `_execute` implementations use native bounded fetches; the
executor requests `max_rows + 1` rows. No dependency changes.

**Documentation.** Current architecture says results are fully materialized before
the cap and is updated. ADR-0003's note that fetching "still materializes all rows"
records that decision's scope; this change neither reverses nor supersedes it, so
the ADR is not edited.
