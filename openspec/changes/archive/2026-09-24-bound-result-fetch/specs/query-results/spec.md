## Purpose

Define what a `dbridge/execute` reply contains, how the configured row cap limits
it, and what capping guarantees about database work, so large local results stay
fast and bounded without changing the response shape.

## ADDED Requirements

### Requirement: Return ordered, positional query results

A successful `dbridge/execute` reply SHALL contain `columns`, `rows`, `row_count`,
`execution_time_ms`, and `warnings`. `columns` SHALL list result column names in the
order the statement produced them, and each row SHALL be a list of values in that
same order. A statement that produces no rows SHALL reply with empty `rows` and
a `row_count` of 0, preserving any column metadata the database supplies.
When the database supplies no column metadata, `columns` SHALL be empty.

#### Scenario: Column order follows the statement
- **WHEN** a client executes `SELECT 2 AS b, 1 AS a` on a Session
- **THEN** `columns` is `["b", "a"]` and `rows` is `[[2, 1]]`

#### Scenario: SQLite statement without a result set
- **WHEN** a client executes `CREATE TABLE t (id INTEGER)` on a SQLite Session
- **THEN** the reply has empty `columns` and `rows`, `row_count` 0, and no warnings

#### Scenario: DuckDB statement with column metadata and no rows
- **WHEN** a client executes `CREATE TABLE t (id INTEGER)` on a DuckDB Session
- **THEN** the reply has `columns` `["Count"]`, empty `rows`, `row_count` 0, and no warnings

### Requirement: Cap returned rows and report truncation

A reply SHALL contain at most `max_rows` rows, the configured row cap. `row_count`
SHALL equal the number of rows returned, not the number the statement could
produce. When the statement produced more rows than the cap, the reply SHALL keep
the first `max_rows` rows in the order the statement produced them and SHALL add
the warning `result truncated to <max_rows> rows` after any Adapter warnings. A
result with exactly `max_rows` rows SHALL NOT carry a truncation warning. The
reply SHALL NOT report the total number of rows the statement could produce.

#### Scenario: Result over the cap
- **WHEN** `max_rows` is 100 and a client executes a query producing 150 rows
- **THEN** the reply contains the first 100 rows, `row_count` is 100, and
  `warnings` contains `result truncated to 100 rows`

#### Scenario: Result exactly at the cap
- **WHEN** `max_rows` is 100 and a client executes a query producing 100 rows
- **THEN** the reply contains 100 rows, `row_count` is 100, and `warnings` is empty

#### Scenario: Result under the cap
- **WHEN** `max_rows` is 100 and a client executes a query producing 3 rows
- **THEN** the reply contains those 3 rows and no truncation warning

### Requirement: Stop reading results past the cap

The server SHALL stop reading a statement's rows from the database once it holds
one row more than the cap, so the time and memory needed to reply do not grow with
the number of rows past the cap. This SHALL hold for every registered Adapter.
It does not bound work the database performs before producing its first row, such
as sorting or aggregating a large input; that work still runs to completion unless
the request is cancelled.

#### Scenario: Unbounded SQLite query replies
- **WHEN** `max_rows` is 100 and a client executes
  `WITH RECURSIVE s(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM s) SELECT x FROM s`
  on a SQLite Session
- **THEN** the request replies with rows 1 through 100 and a truncation warning

#### Scenario: Very large DuckDB query replies
- **WHEN** `max_rows` is 100 and a client executes
  `SELECT * FROM range(1000000000000)` on a DuckDB Session
- **THEN** the request replies with the first 100 rows and a truncation warning

### Requirement: Release a capped statement before replying

When the server stops reading a statement early, it SHALL release that statement's
database resources before sending the reply. A capped query SHALL NOT keep holding
locks that block other connections to the same database, and the Session SHALL run
its next request normally.

#### Scenario: Capped SQLite read does not block another writer
- **WHEN** a client executes a query producing more rows than the cap on a SQLite
  Session backed by a database file, and receives its reply
- **THEN** another connection to that file can write to it without waiting for a
  lock

#### Scenario: Session keeps working after a capped query
- **WHEN** a client executes a query producing more rows than the cap and then
  executes `SELECT 42` on the same Session
- **THEN** the second request replies with `[[42]]`

### Requirement: Apply every change of a capped write

Capping the rows returned SHALL NOT limit what a statement changes. When a statement
that modifies data and returns rows, such as `INSERT ... RETURNING` or
`DELETE ... RETURNING`, produces more rows than the cap, every modification SHALL be
applied and the reply SHALL follow the cap and truncation rules.

#### Scenario: Capped INSERT RETURNING inserts every row
- **WHEN** `max_rows` is 100 and a client executes an `INSERT ... RETURNING` that
  inserts 1,000 rows into an empty table, on either a SQLite or a DuckDB Session
- **THEN** the reply contains 100 rows and a truncation warning
- **AND** a following `SELECT count(*)` on that table returns 1,000

#### Scenario: Capped DELETE RETURNING deletes every row
- **WHEN** `max_rows` is 100 and a client executes a `DELETE ... RETURNING` that
  matches 1,000 rows, on either a SQLite or a DuckDB Session
- **THEN** the reply contains 100 rows and a truncation warning
- **AND** a following `SELECT count(*)` on that table returns 0
