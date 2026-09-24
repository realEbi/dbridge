## 1. Adapter row limit

- [x] 1.1 Add keyword-only `row_limit: int | None = None` to `DBAdapter.execute`, `ThreadBackedAdapter.execute`, and the abstract `_execute`, rejecting a limit below 1 with `ValueError` before any driver call (design D2); verify with a `tests/adapters/test_base.py` test that `row_limit=0` raises and no Lane job runs
- [x] 1.2 SQLite `_execute`: read with `cursor.fetchmany(row_limit)` when a limit is given and close the cursor in `finally` on success, error, and interruption (D3, D4); verify that the existing SQLite adapter and driver-cancellation tests still pass
- [x] 1.3 DuckDB `_execute`: read with `fetchmany(row_limit)` when a limit is given, keep `_capture_session_metadata` in `finally`, and add the D4 comment on how the pending result is released; verify that the existing DuckDB adapter and driver-cancellation tests still pass

## 2. Executor

- [x] 2.1 Make the executor call `execute(sql, row_limit=max(max_rows, 0) + 1)` and keep its truncation and warning logic; verify with `tests/core/test_executor.py` that the stub records limit 101 for `max_rows=100` and limit 1 for a negative cap, and that the existing truncation tests pass unchanged

## 3. Behavior tests for the query-results spec

- [x] 3.1 Add real-driver tests for *Stop reading results past the cap*: the unbounded SQLite recursive CTE and DuckDB `range(1000000000000)` each return their first 101 rows through `row_limit=101` within an `asyncio.wait_for` timeout (D6)
- [x] 3.2 Add the *Release a capped statement before replying* tests: after a capped SQLite read on a temporary file, a second `sqlite3` connection with a short timeout inserts successfully; on both drivers a capped query followed by `SELECT 42` on the same adapter returns `[[42]]`
- [x] 3.3 Add the *Apply every change of a capped write* tests on both drivers: `INSERT ... RETURNING` of 1,000 rows and `DELETE ... RETURNING` of 1,000 rows with `row_limit=101` return 101 rows and leave counts of 1,000 and 0
- [x] 3.4 Add or extend a stdio end-to-end test that a capped `dbridge/execute` reply keeps ordered `columns`, returns `max_rows` rows with `row_count` equal to `max_rows`, and carries `result truncated to <max_rows> rows`; verify it passes against a spawned server with isolated configuration
- [x] 3.5 Preserve existing DDL replies as agreed during implementation: verify through the bounded executor that `CREATE TABLE` returns empty columns on SQLite and `["Count"]` on DuckDB, with no rows or warnings on either; correct the new spec to match

## 4. Documentation and backlog

- [x] 4.1 Update `docs/architecture.md` (Queries and adapters) to say that Adapters stop at `max_rows + 1` rows and release capped statements, and that sorts and aggregates still run to completion; verify that no remaining text says results are fully materialized
- [x] 4.2 Update the AGENTS.md engineering convention "The row cap currently applies after materialization" and the roadmap's milestone 2 sentence to describe the bounded fetch, leaving 013's delivery model open; verify with `grep -rn -i materiali AGENTS.md docs/roadmap.md docs/architecture.md`
- [x] 4.3 Recheck the README settings row and the manual testing guide's 100-row check; update them only if their wording now misstates behavior (the reply shape is unchanged)
- [x] 4.4 Record a new backlog item for `Settings` accepting a negative `max_rows` (evidence: `Settings(max_rows=-5)` loads, and the executor then truncates with `rows[:-5]`), using the next unused ID and adding it to the backlog index

## 5. Verification and closure

- [x] 5.1 Run `make check` and `uv run --group test pytest --cov` in the worktree; verify that types and lint are clean and coverage stays at or above 85%
- [x] 5.2 Re-run the 2,000,000-row benchmark from backlog 056 against both Adapters through `execute(..., row_limit=101)` and record the measured time and peak memory in 056's resolution
- [x] 5.3 Validate with `openspec validate bound-result-fetch --strict`, sync the `query-results` spec, archive the change, mark backlog 056 done with a link to the archived change, and update 013's note to point to the archive location
