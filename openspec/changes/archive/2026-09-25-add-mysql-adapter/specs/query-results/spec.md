## MODIFIED Requirements

### Requirement: Stop reading results past the cap

The server SHALL stop reading a statement's rows from the database once it holds
one row more than the cap, so the time and memory needed to reply do not grow with
the number of rows past the cap. This SHALL hold for every registered Adapter, with
one exception. A MySQL request that is a `CALL` or holds several statements SHALL
read and discard its remaining rows so every step completes. That keeps memory
bounded, but its reply time grows with the discarded rows. This is a known gap.
The requirement does not bound work the database performs before producing its
first row, such as sorting or aggregating a large input; that work still runs to
completion unless the request is cancelled.

#### Scenario: Unbounded SQLite query replies
- **WHEN** `max_rows` is 100 and a client executes
  `WITH RECURSIVE s(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM s) SELECT x FROM s`
  on a SQLite Session
- **THEN** the request replies with rows 1 through 100 and a truncation warning

#### Scenario: Very large DuckDB query replies
- **WHEN** `max_rows` is 100 and a client executes
  `SELECT * FROM range(1000000000000)` on a DuckDB Session
- **THEN** the request replies with the first 100 rows and a truncation warning

#### Scenario: Large MySQL query replies
- **WHEN** `max_rows` is 100 and a client executes a single `SELECT` over 1,000,000
  rows on a MySQL Session
- **THEN** the request replies with the first 100 rows and a truncation warning
  within 1 second
