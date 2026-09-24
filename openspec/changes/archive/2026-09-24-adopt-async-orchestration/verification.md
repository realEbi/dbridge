# Verification

## Scope and decisions checked

The server change implements async orchestration and cancellation; the companion
client change is `dbridge.nvim: cancel-outstanding-query`. Server specifications
own scheduling, cancellation, framing, and cache behavior. The client change owns
request-id exposure, `:DbridgeCancel`, feedback, and editor integration.

The user approved two clarifications during implementation:

- Create the linked client change in its own worktree and verify the shared flow.
- Ordinary cancellation waits for the driver outcome. Shutdown instead attempts
  cleanup within its fixed grace period and may abandon an uninterruptible driver,
  logging incomplete physical connection cleanup. This avoids promising both a
  bounded exit and a guaranteed close of a driver that never returns.

Driver probes also showed that a DuckDB sibling cursor cannot observe the query
connection's `USE` state or temporary tables. The Adapter publishes scope and temp
metadata snapshots after query work, including partial effects of interrupted
multi-statement SQL. Tests cover quoted names, changes/drops, and mutation isolation.
Interruption retries close the idle gap between claiming a lane job and entering
the driver; every retry checks the same current-job lock. Post-SQL discovery is
protected from retries so committed partial effects remain visible.

## Request-concurrency scenario evidence

Test paths below are relative to the repository root. Every named scenario has a
behavior assertion; no scenario is satisfied only by a coverage percentage.

| Scenario | Passing test |
|---|---|
| Metadata on another Session during a long query | `tests/protocol/test_concurrency.py::test_other_session_metadata_query_profiles_and_invalid_request_stay_responsive` |
| Profile listing during a long query | Same test: Profile reply while gated query remains outstanding |
| Invalid request during a long query | Same test: `METHOD_NOT_FOUND` while gated query remains outstanding |
| A fast request overtakes a slow one | `tests/protocol/test_stdio_transport.py::test_fast_reply_overtakes_gated_slow_request` |
| Many concurrent replies stay well framed | `tests/protocol/test_stdio_transport.py::test_many_replies_are_complete_and_correlated` |
| An outstanding id is reused | `tests/protocol/test_concurrency.py::test_duplicate_outstanding_id_is_rejected_until_reply_then_reusable` |
| Two Sessions query at the same time | `tests/protocol/test_concurrency.py::test_other_session_metadata_query_profiles_and_invalid_request_stay_responsive` |
| Statements on one Session keep their order | `tests/protocol/test_concurrency.py::test_one_session_statements_keep_arrival_order` |
| DuckDB metadata during a long query | `tests/protocol/test_concurrency.py::test_real_query_cancellation_isolated_and_session_reusable[duckdb]` |
| SQLite requests keep arrival order | `tests/protocol/test_concurrency.py::test_sqlite_uncached_metadata_waits_but_cached_completion_does_not` |
| Cached completion during a long query | `tests/protocol/test_concurrency.py::test_real_query_cancellation_isolated_and_session_reusable[sqlite]` and `[duckdb]` |
| Disconnect during a long query | `tests/protocol/test_concurrency.py::test_disconnect_cancels_session_work_rejects_new_work_and_leaves_other_session` |
| Other Sessions are unaffected | `tests/protocol/test_concurrency.py::test_disconnect_leaves_another_sessions_running_query_intact` |
| Input closes during a long query | `tests/test_e2e_stdio.py::test_e2e_close_input_during_long_duckdb_query_exits_promptly` |
| A driver ignores shutdown interruption | `tests/protocol/test_stdio_transport.py::test_shutdown_abandons_stuck_driver_and_discards_queued_work` |

## Additional behavior evidence

- `tests/adapters/test_lane.py` gates FIFO order, thread ownership, queued/running
  cancellation, the start/finish races, idempotent disconnect, and abandonment
  during connect, execute, and close. Cooperative disconnect leaves no lane alive.
- `tests/adapters/test_driver_cancellation.py` exercises real SQLite/DuckDB query
  interruption and reuse, cross-thread/idle interruption, DuckDB cursor isolation,
  attached-catalog metadata, and partial multi-statement effects. Six copied probe
  variants with inverted outcome assertions all failed as expected; copies were
  run from temporary storage, leaving repository assertions unchanged.
- `tests/protocol/test_concurrency.py` checks silent malformed/stale cancels,
  cancellation before a request task starts, exactly one reply when completion
  wins, a queued INSERT with no effects, running-query reuse, another real query
  remaining active, and in-flight DuckDB metadata surviving query cancellation.
- `tests/core/test_schema_registry.py` checks refresh-generation fencing, cancelled
  fetches, and independent concurrent misses. Existing completion expectations
  were preserved while callbacks became awaitable.
- Framing and pipe tests cover byte lengths, short reads, UTF-8 failures, deeply
  nested JSON parser failure, recovery at the next frame, complete concurrent
  replies, clean fatal framing shutdown, and closed output during cleanup.
- Subprocess tests confirm status 0 and protocol-only stdout on truncated input
  and EOF during a long DuckDB query, plus invalid-JSON recovery.

## Manual and client verification

The documented cancellation/completion procedure was run using temporary sample
SQLite and DuckDB databases generated from the existing sample script. SQLite
cached completion and DuckDB uncached completion each returned all six product
columns before the long query replied. Cancellation returned `QUERY_CANCELLED`,
and `SELECT count(*) FROM products` then returned 10 on the same Session. Processes
exited cleanly and the existing `examples/` databases were not overwritten.

Client integration selects the paired server checkout explicitly through
`DBRIDGE_SERVER_CMD="<server-worktree>/.venv/bin/python -m dbridge.server"`.
Detailed client evidence belongs to that change's `verification.md`. Before PR
delivery, all three real cancellation/completion integration cases passed again
against the paired server topic worktree, with no failures or notes.

## Final checks

Verified on 2026-09-24 on macOS ARM64:

| Environment | Type/lint | Full gated suite |
|---|---|---|
| Python 3.11.16, project `.venv` | `make check` passed | 519 passed; 96.58% coverage |
| Python 3.12.12, isolated temporary environment | `make check` passed | 519 passed; 96.58% coverage |
| Neovim 0.12.5 client worktree | Strict OpenSpec and whitespace checks passed | 176 passed, including real SQLite/DuckDB cancellation and buffer completion |

Server command: `uv run --group test pytest --cov -q`. The Python 3.12 run used
`UV_PYTHON=3.12` and an isolated `UV_PROJECT_ENVIRONMENT`; final matrix suites ran
sequentially. Coverage remains gated at 85%, without exclusions or threshold
reductions for new code. Both runs emitted two NumPy deprecation warnings from
DuckDB's Python-UDF probe; no server-runtime coroutine warnings remain.

One earlier Python 3.12 metadata probe exceeded its three-second test deadline
during parallel validation. It could not be reproduced in isolated/covered runs,
a full suite alongside ten Python 3.11 driver suites, or the final sequential
matrix. The deadline was not increased. Failure-path cleanup was strengthened to
cancel and drain the native query before any abandonment. A separate observed
DuckDB lifecycle issue was fixed: abandonment now retains metadata-before-parent
close ordering, with the wait confined to a daemon worker so exit remains bounded.

Initial baseline and unchanged suite after async test setup: 439 passed. A temporary
async test also verified the runner. Final spec synchronization verifies every full
delta requirement block against its main capability; unrelated scope-addressing
requirements remain intact. PR delivery uses separate scoped commits for the server
and client; merging and release remain separate decisions.

## Remaining boundaries

The async Adapter contract remains provisional until a native async MySQL driver
validates it. Result fetching remains fully materialized before truncation;
streaming/notifications and transaction APIs are separate work. Inherited JSON-null
versus EOF conflation was recorded as [backlog 057](../../../../docs/backlog/057-json-null-frame-ends-input.md)
and was not folded into this change. Deep parser recursion became a reader-thread
hang during migration, so that regression was fixed here.
