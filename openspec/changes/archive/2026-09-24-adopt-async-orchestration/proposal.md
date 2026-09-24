## Why

One long query freezes the whole server. The stdio loop reads a request, runs it to
completion, and only then reads the next one, so while a query runs on a Session the
client gets no completion, no metadata for any Session, and no way to stop it.
`QUERY_CANCELLED` (-32004) has been reserved since Phase 1 but can never be emitted,
because nothing reads the cancel. Milestone 2 of the [roadmap](../../../../docs/roadmap.md)
starts by choosing the concurrent execution model; this change makes that choice and
proves it with cancellation, the first feature that cannot work without it.

Probing the pinned drivers showed SQLite and DuckDB are enough to prove the model
without new infrastructure. Both stop a running query within one polling interval
when `interrupt()` is called from another thread. An interrupt on a DuckDB
connection does not reach a sibling cursor's query, and a DuckDB cursor answers
metadata while its parent connection is busy.

## What Changes

- Adopt asyncio orchestration. The stdio Transport keeps reading while requests
  run, the Core Engine awaits its work, and one writer emits each reply as soon as
  its request finishes. **BREAKING** (ordering only): replies to concurrently
  outstanding requests may arrive in a different order than the requests. Every
  reply still carries its request's id; no method's params or result shape changes.
- Replace the synchronous Adapter interface with an async one. SQLite and DuckDB
  implement it through a shared thread-backed base that owns each Session's
  connection thread, so the Core Engine owns no threads. The interface is provisional
  until a native async driver validates it; MySQL on a native async driver is
  deferred to milestone 3.
- Requests on different Sessions run in parallel. On one Session, `execute` requests
  run one at a time in arrival order. Metadata requests may overlap a running
  `execute` when the Adapter supports it: DuckDB serves them from a sibling cursor,
  while SQLite queues them in arrival order.
- Add `$/cancelRequest`, a client notification naming the JSON-RPC id of an
  outstanding request. A queued request is dequeued, a running one is interrupted,
  and either replies with `QUERY_CANCELLED`. Cancelling one request never stops
  another. A cancel for an unknown or already-answered id is ignored.
- `dbridge/disconnect` cancels that Session's outstanding requests before closing.
  End of input cancels outstanding work and attempts to close every Adapter within
  a fixed grace period. A stuck driver is abandoned with a diagnostic so exit stays
  bounded; physical connection closure is not guaranteed in that case.
- A frame whose body is not valid JSON returns `PARSE_ERROR` (-32700) and the server
  keeps serving. A frame that cannot be delimited, such as a truncated body or a
  non-numeric `Content-Length`, logs a diagnostic and shuts down cleanly instead of
  crashing with a traceback.
- `dbridge/refreshSchema` stays authoritative under concurrency: an introspection
  result fetched before a refresh is never cached after it.

## Capabilities

### New Capabilities

- `request-concurrency`: How the server accepts, schedules, and answers requests
  while others are running — non-blocking intake, reply correlation and ordering,
  cross-Session parallelism, per-Session ordering, and disconnect and shutdown with
  work in flight.
- `request-cancellation`: Cancelling an outstanding request by its JSON-RPC id,
  including queued versus running requests, isolation between requests, races with
  completion, and partial effects of a cancelled `execute`.
- `protocol-framing`: How the stdio Transport handles a frame it cannot parse or
  cannot delimit, without corrupting stdout or terminating on a traceback.

### Modified Capabilities

- `scope-addressing`: *Cache and invalidate every introspection result by Scope
  Path* gains a concurrency guarantee: a result whose fetch began before
  `dbridge/refreshSchema` is not cached after the refresh completes.

## Impact

**Roadmap and backlog.** Implements the execution-model choice opening milestone 2
and resolves [012](../../../../docs/backlog/012-concurrent-execution.md),
[009](../../../../docs/backlog/009-query-cancellation.md), and
[052](../../../../docs/backlog/052-truncated-frame-crashes-loop.md). Supersedes
[ADR-0001](../../../../docs/adr/0001-sync-core-for-phase-1.md) with a new ADR.
[019](../../../../docs/backlog/019-mysql-adapter.md) gains the decision that MySQL uses
a native async driver and validates the provisional Adapter contract in milestone 3.
[013](../../../../docs/backlog/013-large-results.md) and
[010](../../../../docs/backlog/010-server-notifications.md) stay open: this change adds
no streaming and no server notifications, and does not pre-decide cursors versus
pagination. Transactions, bound parameters, and additional transports are out of
scope.

**Repositories.** This change owns server behavior and the DSP contract. The
`dbridge.nvim` client is owned by the linked `cancel-outstanding-query` change in
[dbridge.nvim](https://github.com/realebi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-24-cancel-outstanding-query). It will: return the
request id from its request function, add a command that cancels the latest
`execute`, and present `QUERY_CANCELLED` as a cancellation rather than a failure.
The client already correlates replies by id, so out-of-order replies need no client
change. Sending `$/cancelRequest` to a server without this change is harmless, since
notifications are ignored, so the client change can merge first.

**Protocol compatibility.** No method is removed or reshaped. Reply order changes,
one notification method is added, and `QUERY_CANCELLED` and `PARSE_ERROR` become
reachable.

**Code and dependencies.** Transport, Dispatcher, Core Engine, SchemaRegistry,
completion's metadata lookups, and both Adapters become async-aware. Tests gain an
async runner in the `test` dependency group. CI keeps its existing Linux matrix and
tests SQLite and DuckDB only; nothing needs provisioning. Profile file handling and
the row cap are unchanged.
