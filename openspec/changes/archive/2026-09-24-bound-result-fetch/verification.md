# Verification

## Checks passed

- Python 3.12.12: `make check` and `uv run --group test pytest --cov`;
  535 tests passed, 96.53% coverage (85% required).
- Python 3.11.16: mypy, Ruff, and the complete `pytest --cov` suite;
  535 tests passed, 96.53% coverage. This run used a separate virtual environment.
- Real-driver tests cover the infinite SQLite CTE and trillion-row DuckDB range,
  SQLite file-lock release, subsequent Session reuse, and all 1,000 modifications
  from capped insert/delete `RETURNING` statements.
- Stdio subprocess tests cover both Adapters with row caps of 3 and 100,
  preserving result fields, column/row order, returned count, and warning text.
- DDL cases through the bounded executor preserve SQLite's empty columns and
  DuckDB's `["Count"]` metadata, with no rows or warnings on either engine.
- Existing cancellation/concurrency tests pass, including the executor's bounded
  path. Additional direct Adapter probes confirmed cancellation with
  `row_limit=101` and successful subsequent `SELECT 42` on both drivers.
- `openspec validate bound-result-fetch --strict` and `git diff --check` pass.
- Architecture, roadmap, and AGENTS.md contain no stale materialization claims;
  README settings and manual row-cap checks remain accurate without edits.
- Two-million-row Adapter benchmark results and measurement limits are recorded
  in [backlog 056](../../../../docs/backlog/056-bounded-result-fetch.md#resolution).

Both Python suites emit two existing NumPy deprecation warnings from the DuckDB
driver cancellation probe; neither suite has a failure.

## Contract correction

The initial no-result scenario said `CREATE TABLE` returns empty `columns`, but a
direct probe of existing behavior returns `columns: ["Count"]`, empty `rows`,
and `row_count: 0` on DuckDB. SQLite returns empty `columns`. The accepted
resolution preserves existing replies and corrects the spec to retain supplied
column metadata. Separate scenarios now describe each engine's DDL reply.

Negative `max_rows` validation remains deliberately unchanged and is recorded as
[backlog 058](../../../../docs/backlog/058-negative-max-rows.md).

## Closure

All 16 tasks are complete. The five `query-results` requirements were synchronized
and compared with the delta before archive. Strict validation passes for all
11 main specs. Backlog 056 is done, backlog 013 retains delivery beyond the cap,
and their links point to this archive. ADR-0003 retains its historical scope.
