## Context

See proposal.md for motivation and the specs for the behavior contract. The
existing Adapters are thread-backed. Each owns Lanes (`adapters/lane.py`,
`threaded.py`) that serialize blocking driver calls and interrupt them from
another thread. ADR-0003 expects a native async Adapter to meet the same contract
through its own mechanism, and calls that contract provisional until MySQL proves
it.

A spike on 2026-09-25 built a minimal `DBAdapter` for each of three drivers. Each
ran against the same 14 scenarios on MySQL 8.4.11. The spike code was throwaway
and has been deleted. This table and the facts below are the retained evidence.

| Measure | aiomysql 0.3.2 | asyncmy 0.2.15 | mysql.connector.aio 26.7.0 |
|---|---|---|---|
| Scenarios passed, reconnects | 14/14, 0 | 14/14, 0 | 14/14, 0 |
| Cancel latency | 0.002–0.008 s | 0.001 s | 0.001 s |
| `row_limit=101` on 1M rows | 0.022 s, 0.4 MB | 0.102 s, 0.0 MB | 0.068 s, 0.8 MB |
| Full 1M-row fetch, longest loop stall | 2.26 s, 77 ms | 0.59 s, 84 ms | 3.78 s, 110 ms |
| Private internals used | 2 | 5 | 1, plus a cursor bypass |
| Driver defects worked around | none | 2 | silent desync on a stray cancel |

The spike established these MySQL facts, which shape every decision below:

- A cancel that reaches a driver read breaks the connection. aiomysql and asyncmy
  close it; Connector/Python silently returns the previous reply next time.
- The drivers' kill helpers end the whole connection. Only SQL `KILL QUERY <id>`
  stops just the statement.
- MySQL discards a `KILL QUERY` that reaches an idle thread. A killed lone `SLEEP`
  returns `1` with no error, and a statement spanning several rows fails with 1317.
- An unbuffered result cannot be abandoned: closing it reads every row. A buffered
  cursor downloads the whole result first.
- Closing the client socket does not stop a running statement on the server.

## Goals / Non-Goals

**Goals:**

- Meet ADR-0003's cancellation, ordering, and lifecycle contract with a native
  async driver. The `DBAdapter` interface, Dispatcher, and executor stay unchanged.
- Keep every MySQL-specific concern inside `adapters/mysql.py`, loaded only when a
  MySQL Session connects.
- Turn the spike scenarios into a real-server regression suite that runs locally.

**Non-Goals:**

- Running a MySQL service in CI. MySQL is an optional feature, verified locally.
- Supporting proxies or load balancers, other server versions, TLS options, Unix
  sockets, or listing `TEMPORARY` tables.
- Pooling Session connections ([046](../../../../docs/backlog/046-adapter-pooling.md)).
  Only the control connection is shared.
- Converting result values that JSON cannot encode. That is shared with DuckDB;
  see Risks.

## Decisions

### 1. Driver: aiomysql

It met the contract using only two private attributes, and needed no driver-defect
workarounds. Its failure mode is also loud: a stray cancel closes the connection
rather than corrupting it.

- **asyncmy** was 3.8x faster on a full fetch. It needed five private Cython
  internals, a workaround for an `is True` bug on its unbuffered flag, and manual
  read backpressure. The default `max_rows` is 100, and capped fetches took 5–12 ms
  with every driver, so the speed gap rarely matters.
- **Connector/Python** is rejected. A cancel that ever reaches a read makes it
  return the previous statement's rows with no error. Its shim also had to bypass
  the cursor and rebuild warnings and multi-result handling.

The extra pins `aiomysql>=0.3.2,<0.4` and adds `cryptography`. MySQL 8.4's default
`caching_sha2_password` needs `cryptography` for a first login without TLS.

### 2. Native Channels instead of Lanes

A private `_Channel` class wraps one aiomysql connection. It is the native-async
counterpart of a Lane and holds:

- a FIFO `asyncio.Lock`, so statements run in arrival order
- the server thread id, from the handshake
- a method that runs one driver operation as its own reader task

Callers await that task through `asyncio.shield`, so cancellation never reaches
aiomysql's I/O. Each Session owns two Channels: query and metadata. Metadata
therefore never waits behind a long statement, matching DuckDB's two Lanes.

Rejected alternatives:

- **Reuse `ThreadBackedAdapter` with a sync driver.** This proves nothing about
  native drivers, which is what backlog 019 and ADR-0003 require.
- **Cancel the driver coroutine directly.** The spike showed this breaks the
  connection in every driver.

### 3. Interruption through `KILL QUERY` on a shared control connection

When a Channel's awaiting caller is cancelled:

1. If the reader task already finished, return its result.
2. Otherwise, mark interruption as issued and send `KILL QUERY <thread id>` on the
   control connection.
3. Wait for both the kill acknowledgement and the reader task, then raise
   `CancelledError`.

The Channel lock is held throughout. A kill therefore lands on the intended
statement or on an idle thread, where MySQL discards it; it never reaches the next
statement. A request cancelled while still waiting for the lock leaves the queue
without touching the server.

The control connection is shared per `(host, port, user)`. `KILL QUERY` without
`CONNECTION_ADMIN` works only on threads of the same account, so sharing per server
alone would fail across accounts.

- A module-level registry on the event loop reference-counts it.
- It opens eagerly on the first Session's connect, so `abandon()` can always reach
  the server.
- It closes when the last Session using it disconnects.
- An `asyncio.Lock` serializes kill commands.
- If it breaks, the next kill reopens it with the requesting Session's credentials.

If a kill cannot be confirmed, the Channel discards its query connection and opens
a new one. That is the only path that loses Session state, and it is logged.

Rejected alternatives:

- **A control connection per Session**, as the spike used. This costs one extra
  server connection per Session.
- **Opening it lazily on the first cancel.** This adds a connect to cancel latency,
  and `abandon()` would have no connection to use.

### 4. Row caps: stop with a kill only when nothing follows

`execute` always reads through an unbuffered cursor in chunks, converting rows as
it goes, which keeps loop stalls short. Each result set keeps at most `row_limit`
rows. When the cap is reached, the next step depends on the request:

- **A single statement that sqlglot parses, with the MySQL dialect, as a query**
  (`SELECT`, set operations, `WITH`, `SHOW`, `DESCRIBE`, `EXPLAIN`, `TABLE`,
  `VALUES`): the Channel sends `KILL QUERY` through the same path as
  cancellation. It then discards the in-flight bytes until the 1317 error and
  clears the driver's unbuffered flag. The spike measured this at 5–22 ms with
  under 1 MB of memory.
- **Anything else**, including `CALL`, several statements, or SQL sqlglot cannot
  parse: the Channel reads and discards the remaining rows and result sets. This
  keeps every step's effects, as the query-results spec requires.

The reply carries the last result set that has columns.

Implementation inspection of aiomysql 0.3.2 found that `SSCursor.nextset()`
inherits a buffered transition, and `Connection.next_result()` has no unbuffered
argument. The Adapter therefore advances later results through
`connection._read_query_result(unbuffered=True)` and `cursor._do_get_result()`,
using `connection._result.has_next` to detect them. This small private bridge
keeps later procedure and multi-statement result sets bounded too; testing only
the first result set would not establish the planned memory guarantee.

sqlglot 30.11 parses MySQL `TABLE name` as a column/alias expression rather than a
query. Classification validates its equivalent `SELECT * FROM name`, accepting
only a single table with optional ordering/limit, and rejecting aliases, joins,
filters, or additional statements. The original SQL still goes to MySQL unchanged.

Rejected alternatives:

- **Always kill.** A kill can cut a procedure's later writes.
- **Always drain.** The reply time for a large `SELECT` grows with every discarded
  row.
- **Drop the connection.** This is faster, but loses temporary tables, variables,
  and transactions.

### 5. Default Scope Path snapshot

The query Channel runs `SELECT DATABASE()` inside its lock after every execute,
including a cancelled one once its kill resolves, and publishes the result.
`default_scope()` reads that snapshot. When no database is selected, it falls back
to the first non-internal database in name order, then to `information_schema`.
This follows DuckDB's snapshot approach, so metadata never waits on the query
connection. The round trip costs under 1 ms.

Rejected alternative: parsing MySQL's session-state tracking. aiomysql does not
expose it.

### 6. Metadata from `information_schema`

All metadata queries run on the metadata Channel with bound parameters:

- `SCHEMATA` for databases
- `TABLES` for base tables and views
- `COLUMNS` in `ORDINAL_POSITION` order, using `COLUMN_TYPE`
- `KEY_COLUMN_USAGE` for keys: `CONSTRAINT_NAME = 'PRIMARY'`, and grouped foreign
  keys ordered by `ORDINAL_POSITION` with `REFERENCED_TABLE_SCHEMA` as
  `referenced_path`

The `sql_identifier` quoting helper lives in the MySQL module and uses backticks.
The shared double-quote helper stays unchanged. Keywords come from a module-level
list, as SQLite and DuckDB do.

### 7. Optional registration

The registry maps `mysql` to a loader that imports `dbridge.adapters.mysql` inside
`create_adapter`. A missing `aiomysql` or `cryptography` raises `AdapterError`
naming the `dbridge[mysql]` extra, which the Dispatcher already maps to
`ADAPTER_NOT_SUPPORTED`. The adapter module itself imports aiomysql normally.
Nothing imports that module at server load.

The loader stays in the measured registry, and an in-process test covers it by
blocking the import.

### 8. Disconnect and abandon

`disconnect()` rejects new work, cancels outstanding operations through the normal
kill path, closes both Channels, and releases the control connection reference. It
follows ADR-0003's rule that cancelling a disconnect does not reverse it.

`abandon()` is synchronous:

1. Write a complete `COM_QUERY "KILL <thread id>"` packet for each Channel to the
   control connection's stream writer, a private aiomysql attribute.
2. Fail each pending awaiter with `CancelledError`.
3. Close the sockets.

Whole-packet writes keep the transport's byte stream ordered, and replies are
never read during shutdown.

The shared control stream remains open until the last Session reference is
released, allowing every Session in one synchronous abandonment pass to send its
kills. Raw writes mark it as having unread replies: if another Session remains
live, its next ordinary control operation discards and reopens that stream.
Pending connection handshakes and their outer waiters are tracked separately so
abandonment can close an unfinished login and release a connect request too.

### 9. Local real-server verification

Tests live in `tests/adapters/mysql/` and skip unless `DBRIDGE_TEST_MYSQL_HOST` or
a related variable is set. A compose file for MySQL 8.4 with seed data, and two
Makefile targets, make the suite reproducible:

- `make mysql-up` starts the server.
- `make test-mysql` runs the suite with the extra installed.

The spike scenarios become regression tests, joined by metadata, identifier, key,
default-scope, `CALL` cap, and missing-extra tests. `pyproject.toml` adds
`src/dbridge/adapters/mysql.py` to the coverage `omit` list, following the
test-coverage delta.

### 10. ADR updates

**ADR-0003 is amended, not superseded.**

- Its revisit trigger is met: the contract is validated for a native driver.
- The boundary for "finished work keeps its result" becomes "a result that reached
  the Adapter before interruption was issued".
- A native Adapter must never let cancellation reach its driver's I/O.

**New ADR-0004 records the MySQL interruption design.** It covers the kill path
shared by cancellation, row caps, and abandon; the shared control connection; and
the proxy limitation.

## Risks / Trade-offs

- **[KILL by thread id through a proxy]** The kill can reach an unrelated backend.
  → Documented as unsupported (spec requirement). No detection is attempted.
- **[Kill-discarded-when-idle verified on 8.4.11 only]** The wrong-statement guard
  relies on this server behavior. → New backlog item for 8.0, 9.x, and MariaDB.
  The README names 8.4 as the only verified version.
- **[Private aiomysql internals]** The spike used `_result.unbuffered_active` and
  `_writer`. Production also uses `_result.has_next`, `_read_query_result`, and
  `_do_get_result` to keep later result sets unbuffered, as described above.
  → Pin below 0.4, and real-server tests cover cancellation, abandonment, and
  later result sets.
- **[aiomysql release cadence]** The last release was 2025-10-22. → The Channel
  design is driver-neutral, and the asyncmy spike shows a working fallback.
- **[A result arriving just after the kill is sent is reported as cancelled]** The
  statement's effects are retained. → ADR-0003 already provides no rollback. The
  README states the rule.
- **[Kill cannot be confirmed]** The reconnect fallback loses Session state.
  → This happens only when the control connection fails. It is logged, and the
  reconnect count is visible in tests.
- **[Draining capped `CALL` or multi-statement requests]** Reply time grows.
  → Documented known gap in the query-results and mysql-adapter specs.
- **[Two connections per Session plus one shared]** This uses more server
  connections. → Accepted. Pooling stays in 046.
- **[Values JSON cannot encode]** In a probe, a DuckDB `execute` returning
  `DECIMAL`, `DATE`, or `BLOB` values sent no reply within 120 s, because the stdio
  writer uses plain `json.dumps`. MySQL returns `Decimal`, `datetime`, and `bytes`
  often. → Pre-existing and shared with DuckDB, so it is not fixed here. It is
  tracked in [backlog 061](../../../../docs/backlog/061-non-json-result-values.md);
  the MySQL tests avoid depending on it.

## Migration Plan

The change is additive. The parked `adapters/_parked/mysql.py` is deleted, and the
`mysql` extra changes from `pymysql` to `aiomysql` plus `cryptography`. Nothing
imported the old extra's driver. Rollback reverts the change; no stored Profile
format changes.
