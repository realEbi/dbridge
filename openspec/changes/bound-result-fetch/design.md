## Context

See proposal.md for motivation. Since [ADR-0003](../../../docs/adr/0003-async-orchestration.md),
`DBAdapter.execute(sql)` is a coroutine. `ThreadBackedAdapter.execute` sends
`_execute(sql)` to the Session's query Lane, where SQLite and DuckDB each run the
statement and call `fetchall()`. `core/executor.py` is the only production caller;
it slices the rows to `settings.max_rows` and appends the truncation warning.
Tests call `adapter.execute(sql)` directly at 79 sites, mostly for fixture DDL.

Probes against the pinned drivers (SQLite 3.50.4, DuckDB 1.1.3) established:

- `fetchmany(n)` streams in both drivers. On 2,000,000 rows it takes under 1 ms, and
  it answers an unbounded recursive CTE or `range(10^12)` immediately. SQLite
  computes one row ahead of the rows returned.
- A partly read SQLite cursor blocks another connection's write (`database is
  locked`) until `cursor.close()`, even in autocommit mode.
- `INSERT/DELETE ... RETURNING` applies every change after a partial fetch in both
  drivers.
- `sqlite3.Cursor.fetchmany(0)` returns **all** remaining rows; DuckDB returns none.
  `Settings` accepts negative `max_rows`.

ADR-0003 notes that fetching still materializes all rows. That note describes the
scope of its decision. This design adds a bounded fetch within the same Lane model
and supersedes no ADR.

## Goals / Non-Goals

**Goals:**

- The rows read from a driver are bounded by the cap, not by the result size.
- The executor stays the only owner of truncation and its warning text.
- Behavior around cancellation, Lanes, and DuckDB metadata snapshots is unchanged.

**Non-Goals:**

- No change to `max_rows` configuration or validation. A negative value is a
  separate defect (see Risks).
- No bound on the SQL itself: no `LIMIT` rewriting, no statement classification.

## Decisions

### D1. The Adapter reads a requested number of rows; the executor decides truncation

The executor asks for `max_rows + 1` rows. If it receives more than `max_rows`, it
truncates and warns exactly as it does now. The Adapter only guarantees that it
reads no more than the requested number of rows from its driver.

*Alternatives:* The Adapter could apply the cap itself and return a `truncated`
flag. That moves the policy and the warning into every Adapter, including future
native async ones, for no gain. Rewriting SQL to add `LIMIT` requires parsing,
misclassifies statements such as `RETURNING`, DDL, and multi-statement input, and
changes query plans.

### D2. `execute(sql, row_limit=None)`: an optional keyword argument

`DBAdapter.execute`, `ThreadBackedAdapter.execute`, and `_execute` take a
keyword-only `row_limit: int | None = None`. `None` reads every row. An integer
must be at least 1; a smaller value raises `ValueError` before the driver is called,
because `sqlite3` treats `fetchmany(0)` as "fetch all". The executor passes
`max(max_rows, 0) + 1`, so a misconfigured negative cap never reaches a driver as an
unbounded fetch.

*Alternatives:* A required argument would guarantee that no production caller
fetches without a bound. But the executor is the only production caller, and making
it required would rewrite 79 fixture calls that run DDL, adding churn without
testing any behavior. A unit test asserts that the executor passes the limit. A
separate `execute_bounded` method would leave two paths to keep consistent.

### D3. Native bounded fetches on the query Lane

SQLite uses `cursor.fetchmany(row_limit)` and DuckDB uses `fetchmany(row_limit)` on
the query connection. Both keep the native fetch path (no pandas). The fetch stays
inside the Lane job, so cancellation interrupts it the same way it interrupts
execution, and the DuckDB `_capture_session_metadata` snapshot still runs in
`finally` after the statement.

### D4. Release the statement inside the Lane job

SQLite closes its cursor in a `finally` block on every path: success, error, and
interruption. This finalizes the statement, releasing the file lock before the reply
is sent. DuckDB has no separate result object. The query connection's pending result
is replaced by the metadata snapshot query that `_execute` already runs in
`finally`. DuckDB's process-level file lock is not affected by pending results, so
no extra call is added. A comment records this dependency, and the "next request on
the same Session" scenario covers it.

### D5. `execution_time_ms` keeps its meaning

It still measures executing the statement and reading the rows that are returned. It
naturally becomes smaller. Its documented meaning does not change.

### D6. Test strategy

- Executor unit tests with the existing stub Adapter: the requested limit is
  `max_rows + 1`, a negative cap requests 1, and the existing truncation assertions
  still hold.
- Adapter tests with real drivers for each spec scenario. Queries that would never
  finish without a bound (a recursive CTE, `range(10^12)`) are wrapped in
  `asyncio.wait_for` with a few seconds' timeout. A regression then fails through
  cancellation instead of hanging the suite. No new test dependency is needed.
- The SQLite lock scenario uses a temporary database file and a second
  `sqlite3` connection with a short `timeout`.
- `RETURNING` scenarios run on both drivers with 1,000 rows and a limit of 101.
- One stdio end-to-end check that a capped reply still has the same shape and
  warning.

## Risks / Trade-offs

- [SQLite's `fetchmany(0)` fetches all rows] → `row_limit < 1` is rejected at the
  Adapter boundary, and the executor never computes a value below 1.
- [Negative `max_rows` is still accepted and truncates oddly, e.g. `rows[:-1]`] →
  This defect predates the change and is left alone here. Record it as a new
  backlog item rather than change configuration validation in this change.
- [A future driver might not stream `fetchmany`] → The contract is on rows read, and
  the spec scenarios run against every registered Adapter, so a non-streaming
  Adapter fails them.
- [DuckDB release depends on the snapshot query in `finally`] → D4 comment, plus
  the next-request scenario. If the snapshot is ever removed, the pending result
  lives only until the Session's next statement. That costs memory, not
  correctness.
- [Sorts and aggregates over large inputs are no faster] → Out of scope. Clients
  can use `$/cancelRequest`.

## Migration Plan

Server-only and wire-compatible. Rolling back restores full materialization with
identical replies. No client coordination and no data migration.
