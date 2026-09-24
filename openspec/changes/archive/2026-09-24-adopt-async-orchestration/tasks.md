## 1. Decision record and test tooling

- [x] 1.1 Add ADR-0003 recording asyncio orchestration, the async Adapter interface with its cancellation contract, and its provisional status until a native async driver validates it; mark ADR-0001 superseded with a link; verify both ADRs cross-link and ADR-0001 no longer reads "still applicable"
- [x] 1.2 Add `pytest-asyncio` to the `test` and `types` dependency groups and configure its mode in `pyproject.toml`; verify `uv run --group test pytest` still passes unchanged and a trivial async test runs

## 2. Thread-backed lanes

- [x] 2.1 Add a lane primitive: one daemon thread, a FIFO job queue, and a coroutine that submits a job and awaits its result; verify tests show jobs run in submission order on one thread identity and a job's exception reaches its awaiter
- [x] 2.2 Add lane cancellation under the `current`-job lock (design D4): dequeue a queued job, interrupt a running one, ignore a finished one; verify Event-gated tests cover each branch and that cancelling a job at the moment it finishes never interrupts the next job
- [x] 2.3 Add the thread-backed Adapter base that routes each method to a declared lane, creates connections on their lane thread, turns the driver's interrupt error into `CancelledError`, and stops its lanes on disconnect; verify with a fake adapter that the Engine-facing methods are coroutines and no lane thread survives disconnect

## 3. Async Adapter interface and shipped Adapters

- [x] 3.1 Make the database-touching `DBAdapter` methods coroutines, keep `scope_levels`, `dialect_name`, and `get_keywords` synchronous, and document the cancellation contract on the interface (design D2); verify `make check` passes
- [x] 3.2 Port the SQLite Adapter onto the base with one lane and the same-thread check left on; verify existing SQLite adapter tests pass as async tests and a new test cancels an unbounded recursive CTE, gets `CancelledError`, and then runs a query on the same Adapter
- [x] 3.3 Port the DuckDB Adapter onto the base with a query lane and a metadata lane whose cursor comes from the query connection; verify existing DuckDB tests pass as async tests, a listing completes while a long query runs, and a table in an attached catalog is visible to the metadata lane
- [x] 3.4 Pin the probed driver behaviors in adapter tests: cross-thread interrupt stops a running query on both drivers, an idle interrupt does not affect the next query, interrupting a DuckDB connection does not stop its cursor's query, and a cancelled multi-statement execute keeps earlier effects; verify each test fails if its assertion is inverted

## 4. Core Engine and SchemaRegistry

- [x] 4.1 Make `SchemaRegistry` async with a refresh generation: hits return without awaiting the Adapter, and a miss stores its result only if the generation is unchanged and the fetch was not cancelled (design D8); verify tests for a fetch overlapping `refresh()` and for a cancelled fetch, matching the `scope-addressing` scenarios
- [x] 4.2 Make completion await its table-listing and column-lookup callbacks while parsing stays synchronous (design D10); verify every existing completion test passes as an async test with unchanged expectations
- [x] 4.3 Make the Engine's Session and metadata methods coroutines, keep Profile methods synchronous (design D11), and make `connect` roll back a half-created Session on failure as it does today; verify the existing engine tests pass as async tests
- [x] 4.4 Implement Session closing for disconnect (design D9): mark closing, reject new requests with `SESSION_NOT_FOUND`, cancel and await the Session's work, then close the Adapter; verify a test disconnecting during a long query gets `QUERY_CANCELLED` for the query and success for the disconnect, and that another Session's query completes normally

## 5. Dispatcher, requests, and cancellation

- [x] 5.1 Make the Dispatcher run each request as a task in a registry keyed by JSON-RPC id with its `session_id`, reject a still-outstanding id with `INVALID_REQUEST`, and map `CancelledError` to `QUERY_CANCELLED`; verify tests for the duplicate-id scenario and that the registry is empty after every reply
- [x] 5.2 Handle `$/cancelRequest`: cancel the named task, send no reply, and ignore unknown ids and malformed params with a debug log only; verify tests for every `request-cancellation` scenario that uses a fake adapter, including the cancel-races-completion and queued-insert-never-runs scenarios
- [x] 5.3 Verify with real SQLite and DuckDB Sessions that a long query cancels promptly, the Session then runs a new query, cancelling one Session's query leaves another's intact, and cancelling a DuckDB query leaves a concurrent metadata request's result intact

## 6. Transport and framing

- [x] 6.1 Split `read_message` failures (design D7): an unparseable complete body produces a `PARSE_ERROR` result, while a truncated body or invalid `Content-Length` produces a distinct fatal result; update `tests/protocol/test_framing.py`, replacing `test_truncated_body_currently_raises`, and verify each case, including multi-byte UTF-8 bodies
- [x] 6.2 Serve over a blocking reader thread that hands frames to the loop, with replies written on the loop thread (design D6); verify an in-process test over `os.pipe` shows a fast request's reply overtaking a gated slow one, and that many concurrent replies each parse as one complete frame with exactly one reply per id
- [x] 6.3 Implement end-of-input and fatal-framing shutdown with the fixed grace period (design D9); verify in-process tests that shutdown cancels outstanding work, closes cooperative Adapters, and abandons an interrupt-ignoring daemon lane with a diagnostic within the grace period
- [x] 6.4 Extend `tests/test_e2e_stdio.py` with subprocess checks: closing input during a long DuckDB query exits with status 0 promptly, a truncated frame exits with status 0 and a stderr diagnostic, stdout contains only complete frames in both cases, and an invalid JSON body gets `PARSE_ERROR` and the next request is answered

## 7. Cross-cutting verification

- [x] 7.1 Verify every `request-concurrency` scenario has a passing test, naming the test for each scenario in the change's verification notes
- [x] 7.2 Run `make check` and `uv run --group test pytest --cov` on Python 3.11 and 3.12, and verify types, lint, and the 85% coverage floor all pass without lowering the threshold
- [x] 7.3 Cross-repository check, owned by `dbridge.nvim` through its own linked change: with the client's cancel command and returned request ids, cancel a long DuckDB query from Neovim and complete in a buffer while a query runs on the same Session; record the result with the client's tooling

## 8. Documentation

- [x] 8.1 Rewrite *Execution model* in `docs/architecture.md` for the loop, lanes, reply ordering, cancellation, and shutdown, update the sentence saying cancellation and notifications are not implemented, and remove the CONTEXT.md claim that multiple Sessions do not imply concurrent execution; verify no statement still describes the synchronous loop as current
- [x] 8.2 Add **Lane** to `CONTEXT.md` if the term appears in public docs, and update AGENTS.md's engineering convention that says the core is synchronous; verify both agree with ADR-0003
- [x] 8.3 Document `$/cancelRequest`, reply ordering, `QUERY_CANCELLED`, and `PARSE_ERROR` in the README method and error sections; verify every documented behavior matches the Dispatcher
- [x] 8.4 Add a manual check to `docs/manual-testing-guide.md` for cancelling a long query and completing during one; verify it runs as written against the `make manual-prepare` databases
- [x] 8.5 Update `docs/roadmap.md` milestone 2 to record the execution model and cancellation as shipped, with large results and notifications still open, without marking the milestone complete
- [x] 8.6 Mark backlog 012, 009, and 052 done with resolutions and archive links; record in 019 that MySQL uses a native async driver and must validate the provisional Adapter contract; note in 013 and 010 that the execution model is decided; verify each item's Status and Change fields follow the backlog conventions
