## Context

See [proposal.md](proposal.md) for why. This design starts from the code as
[adopt-explicit-scope-paths](../2026-09-24-adopt-explicit-scope-paths/design.md)
left it, with Scope Path signatures throughout.

Today one call chain holds the process from reading a request to writing its reply:

```
StdioTransport.serve --> Dispatcher.handle --> Engine --> SchemaRegistry --> DBAdapter
       ^                                                                   |
       +------------- next read_message only after this returns -----------+
```

These facts about the pinned drivers were measured with scratch probes, not assumed.
They shape the approach:

| Probe | Result |
|---|---|
| `interrupt()` from another thread, DuckDB 1.1.3 | running query stops, `InterruptException` |
| `interrupt()` from another thread, SQLite, same-thread check left on | running query stops, `OperationalError: interrupted` |
| Interrupt a DuckDB connection while its sibling cursor also runs a query | only the connection's query stops |
| DuckDB cursor metadata query while its parent connection runs a query | answered in about 10 ms |
| Interrupt an idle connection, then run a query, both drivers | the next query runs normally |
| Cancel a DuckDB multi-statement execute after its first statement | the first statement's effects stay |

Other constraints: SQLite connections stay bound to the thread that created them.
Neither driver has a real async API; aiosqlite is a thread wrapper. CI runs on Linux
with Python 3.11 and 3.12. The Neovim Client already routes replies to callbacks by
id and sends many requests without waiting.

## Goals / Non-Goals

**Goals:**

- The event loop never blocks on a database driver.
- One Adapter interface that a native async driver can implement later without a
  second interface or an Engine rewrite.
- Each Adapter owns its own concurrency: thread affinity, which work may overlap,
  and how an interruption reaches the database.
- Cancellation expressed through standard asyncio task cancellation, so no Adapter
  method gains a cancel parameter.

**Non-Goals:**

- No streaming, cursors, or pagination. `execute` still materializes rows and the row
  cap still applies afterwards. Backlog 013 decides the delivery model.
- No server-to-client notifications (backlog 010) and no new Transport (backlog 022).
- No connection pooling (backlog 046). DuckDB's metadata cursor belongs to its Session.
- No second SQLite connection for metadata. SQLite metadata misses queue behind
  queries. A later change can add one after deciding how `:memory:` databases, temp
  tables, and `ATTACH` should behave across two connections.
- No change to Profile storage, framing format, UTF-8 cursor offsets, or result shapes.

## Decisions

### D1. asyncio orchestration, superseding ADR-0001

The Transport, Dispatcher, Engine, and SchemaRegistry run on one asyncio event loop.
Blocking work runs off the loop. A new ADR-0003 records this and supersedes
[ADR-0001](../../../../docs/adr/0001-sync-core-for-phase-1.md).

*Alternatives:* A plain thread design with a reader thread, per-Session worker
queues, and a write lock would give the same responsiveness today with a smaller
diff. It was rejected because milestones 3 and 5 bring native async drivers and
network transports, which fit asyncio and would force a second migration. Worker
processes per Session isolate crashes and can cancel by kill, but they add
serialization and process management that nothing here needs.

### D2. Async Adapter interface; declarations stay synchronous

Every method that touches the database becomes a coroutine: `connect`, `disconnect`,
`execute`, `default_scope`, `list_databases`, `list_schemas`, `list_tables`, and
`get_table_schema`. Pure declarations stay synchronous because they never touch the
database and the Dispatcher calls them while validating: `scope_levels`,
`dialect_name`, and `get_keywords`.

The cancellation contract is part of the interface. When the task awaiting an Adapter
coroutine is cancelled, the Adapter attempts to stop the database work. When stopped,
it leaves the connection usable and lets `CancelledError` propagate. Work that has
already finished or cannot be interrupted completes normally, as required by the
best-effort cancellation contract. A native driver meets this its own way:
asyncpg cancels the query on the server, and aiomysql would need `KILL QUERY` from
another connection. The Engine does not know which way was used.

*Alternatives:* Keeping adapters synchronous, with the Engine owning threads, is a
smaller change. But it would make the Engine know each driver's thread affinity, and
milestone 3 would need a second interface. An explicit `cancel(handle)` method was
rejected because asyncio cancellation already carries the target task, and a handle
would have to be threaded through every call.

The contract is provisional until MySQL on a native async driver implements it.
ADR-0003 and backlog 019 say so.

### D3. A thread-backed base with per-Session lanes

SQLite and DuckDB share a base class for thread-backed adapters. A **lane** is one
dedicated thread with a FIFO job queue that owns one driver connection object. Each
coroutine method sends a job to a lane and awaits it:

```
                 +-- query lane ----- thread Q -- connection    execute
 DuckDB Session -+                                              (FIFO)
                 +-- metadata lane -- thread M -- con.cursor()  list_*, get_table_schema,
                                                                default_scope (FIFO)

 SQLite Session ---- lane ----------- thread L -- connection    everything (FIFO)
```

- A connection is created on its lane's thread. SQLite keeps its same-thread check on.
- The DuckDB metadata lane's cursor is created from the query connection, so attached
  catalogs are visible to both. The spec's rule that a client waits for an `execute`
  reply before expecting metadata to reflect it covers the remaining visibility gap.
  The cursor has its own current catalog/schema: a probe of DuckDB 1.1.3 shows that
  `USE` on the parent does not update its sibling. The query lane therefore publishes
  an immutable default Scope Path snapshot after connecting and after execution,
  including failed or interrupted multi-statement execution. `default_scope` reads
  that snapshot on the metadata lane. Snapshot discovery never masks an execution
  error if the connection cannot answer it.
  Temporary tables and views are also connection-local and invisible to the sibling
  cursor. The query lane snapshots their listings, columns, and temporary schemas
  after each execution; metadata serves only `temp` paths from this snapshot and
  continues querying the sibling for other catalogs. Snapshots include partial
  effects before interruption and preserve literal identifiers. This adds small
  catalog queries to execution but preserves existing metadata behavior without
  queuing metadata behind long queries.
- The adapter declares which lane each method uses. The base provides lanes, queueing,
  and cancellation. Adapters provide driver calls and the interrupt function.
- Lane threads are daemon threads so a driver that ignores an interrupt cannot keep
  the process alive at shutdown (D9).

*Alternative:* `asyncio.to_thread` on the default executor. Rejected because it
doesn't keep thread affinity and doesn't keep per-Session order.

### D4. Cancellation reaches only its own job

Each lane holds a lock guarding its `current` job. The worker takes the lock to set
`current` before calling the driver, and takes it again to clear `current` after the
driver returns. Cancelling a job goes through three branches:

```
cancel(job):
  lock
    if job is queued      -> remove it, fail it with CancelledError
    elif job is current   -> interrupt the lane's connection
    else                  -> nothing (already finished)
  unlock
```

Because `current` only changes under the same lock, an interrupt can never land on a
job that started after the check. A leftover interrupt arriving after the driver
returned, but before `current` is cleared, finds the connection idle. The probes show
both drivers ignore that. A regression test pins this driver behavior so an upgrade
that changes it fails loudly.

An interrupted job reports the driver's interrupt error, and the base turns it into
`CancelledError`. A job whose driver call finished before the interrupt keeps its
normal result, as the spec's race scenario requires.

The awaiter retries interruption while its cancelled job remains current. This
closes the gap between marking a job current and entering the driver: an interrupt
in that gap finds an idle connection and is ignored. Every retry takes the same
current-job lock, so none can reach a successor. A gated regression test exercises
this start gap explicitly.

### D5. A request registry keyed by JSON-RPC id

The Dispatcher starts one asyncio task per request and records it by id until the
reply is written. `$/cancelRequest` looks up the id and cancels the task. The
Dispatcher maps `CancelledError` to `QUERY_CANCELLED` and the task leaves the registry
when the reply is written. An id that is already registered is rejected with
`INVALID_REQUEST` before a task starts. An unknown id or a malformed cancel is
dropped with a debug-level log only.

The registry also records each task's `session_id` when the params carry one, so
disconnect and shutdown can find the Session's work.

### D6. The reader stays a blocking thread; writes stay on the loop

A dedicated reader thread runs the existing byte-based `read_message` against
`sys.stdin.buffer` and hands each frame to the loop with `call_soon_threadsafe`.
Replies are written on the loop thread, which serializes frames without a separate
lock.

*Alternative:* `loop.connect_read_pipe` on stdin. Rejected because it fails when
stdin is a regular file or a terminal, and it would have to reimplement framing on a
`StreamReader`. The thread keeps today's tested framing code. If the client stops
reading, a blocking write could stall the loop. That's acceptable for a local child
process and will be revisited with network transports.

### D7. Framing failures split by whether the stream can resynchronize

`read_message` distinguishes two cases. A complete body that isn't valid JSON leaves
the stream aligned, so the reader emits a `PARSE_ERROR` reply with a null id and
continues. A short read at end of input, or an invalid `Content-Length` value, loses
the stream position, so the reader logs to stderr and triggers the shutdown path
(D9). This resolves backlog 052 by choosing "report and continue" where that's safe
and "close cleanly" where it isn't.

### D8. The SchemaRegistry stays on the loop, with a refresh generation

Cache hits are answered on the loop without touching a lane, which is why cached
completion stays responsive on SQLite. On a miss, the registry records the current
generation, awaits the Adapter, and stores the result only if the generation is
unchanged and the fetch wasn't cancelled. `refresh()` clears the cache and increments
the generation.

Concurrent misses for the same key each fetch separately. Merging them into one
shared fetch would mean one requester's cancel could cancel another's work, or the
merged fetch would need its own lifetime. That isn't worth the complexity yet.

### D9. Disconnect and shutdown drain in a fixed order

Disconnect: mark the Session closing so new requests get `SESSION_NOT_FOUND`, cancel
its registered tasks, await them, then await `adapter.disconnect()` on its lanes and
stop the lanes. Shutdown at end of input: cancel every registered task, wait up to a
fixed grace period (a module constant, not a setting) for them to settle, disconnect
every Session within the same bound, then return from the Transport. If a driver
ignores interruption beyond that deadline, synchronously abandon its daemon lane:
reject new submissions, discard queued work, release coroutine waiters, detach the
Session, and log the incomplete connection cleanup to stderr. Driver cleanup is
queued for execution if the blocked call eventually returns. This is process-exit
cleanup only, not a guarantee that the underlying connection was closed. Releasing
waiters also prevents asyncio loop teardown from waiting indefinitely. Ordinary
disconnect completes its cleanup even if its caller sends a cancel notification.
Replies produced
during shutdown are written if the pipe is still open and dropped otherwise.

### D10. Completion awaits its metadata lookups

`complete` keeps its sqlglot parsing and scope logic synchronous and becomes a
coroutine whose table-listing and column-lookup callbacks are awaited. Parsing runs on
the loop. It takes milliseconds on editor-sized input, so moving it to a thread would
only add overhead. Keyword lookup stays synchronous under D2.

### D11. Profile RPCs run inline on the loop

`listProfiles`, `saveProfile`, and `deleteProfile` keep their synchronous file
handling and run directly on the loop. The files are small, and running inline keeps
concurrent saves from interleaving writes to `connections.toml`.

### D12. Test strategy: controllable fakes for order, real drivers for effects

- Add `pytest-asyncio` to the `test` and `types` dependency groups.
- Ordering and race tests use a fake thread-backed adapter whose jobs block on
  `threading.Event`s the test releases. That makes "the reply for id 2 arrives before
  id 1" deterministic without sleeps.
- Cancellation and effect tests use real slow queries: DuckDB
  `SELECT sum(hash(i)) FROM range(20000000000) t(i)` and an unbounded SQLite recursive
  CTE. Each test waits only for the cancel reply, and every such test has a timeout.
- Transport tests drive the served loop in-process over `os.pipe` pairs so they count
  toward the 85% coverage floor. Subprocess tests in `tests/test_e2e_stdio.py` check
  exit status, stdout cleanliness, and end-of-input shutdown.

## Risks / Trade-offs

- [A driver upgrade changes interrupt semantics, for example an idle interrupt
  poisoning the next query] → Tests pin each probed driver behavior (D4), so a
  dependency bump fails CI instead of production.
- [DuckDB metadata served on a cursor can differ from the query connection's
  transaction view] → Autocommit means statements are visible once their reply is
  sent. The spec tells clients to wait for that reply. Explicit transactions
  (backlog 014) must revisit this.
- [The async Adapter contract is shaped without a native driver] → The contract only
  requires honoring task cancellation and the existing method shapes. ADR-0003 marks
  it provisional and backlog 019 makes validating it an explicit outcome.
- [Timing-sensitive tests flake in CI] → Ordering tests use Event-gated fakes, not
  timing. Real-driver tests assert only that a cancel reply arrives within a generous
  timeout.
- [A lane thread stuck in a driver that ignores interrupts] → Daemon lanes and the
  bounded shutdown grace period (D9) keep the process from hanging. The stuck Session
  replies `QUERY_CANCELLED` and is unusable until disconnected.
- [Each Session costs one or two threads] → Fine for a local editor client with a
  handful of Sessions. Revisit with pooling or idle expiry (backlogs 046 and 039).
- [sqlglot parsing on the loop delays other replies] → Milliseconds on editor-sized
  input. If a measurement shows otherwise, move parsing to a thread without changing
  any spec.

## Migration Plan

The server change is internally breaking because every Adapter and Engine method
signature changes. Adapter and Engine are internal, and the parked adapters are not
loaded, so nothing outside the repository depends on them. On the wire, only reply
order changes, plus the addition of `$/cancelRequest` and the now-reachable error
codes.

1. The linked `dbridge.nvim` change may merge first: the client can return request
   ids and send `$/cancelRequest`, which today's server ignores as a notification.
2. Merge the server change. Existing clients keep working because they already
   correlate by id.
3. Verify the shared flow with the client's tooling: cancel a long DuckDB query from
   Neovim and keep completing while a query runs.

Rollback is a revert of the server change. The client's cancel command then becomes a
no-op, because the server ignores the notification.
