# Async orchestration with Adapter-owned execution lanes

Status: accepted; supersedes [ADR-0001](0001-sync-core-for-phase-1.md).

## Decision and rationale

Transport, Dispatcher, and Core Engine coordinate requests on one asyncio event
loop. The reader continues accepting frames while requests await database work;
replies carry their request id and are written on the loop in completion order.
Database-touching Adapter methods are coroutines. Driver imports, thread affinity,
and interruption remain Adapter responsibilities; pure declarations stay synchronous.

SQLite and DuckDB use a shared thread-backed Adapter base. Each execution lane owns
a daemon thread and FIFO queue. SQLite uses one lane with its same-thread check
enabled. DuckDB uses a query connection and a sibling cursor for metadata, each on
its own lane. Separate Sessions can run concurrently; executes on one Session keep
arrival order. Cached metadata needs no lane. Because the DuckDB sibling cursor
has separate `USE` state and cannot see the query connection's temporary objects,
the query lane publishes replacement default-scope and temporary-metadata
snapshots after connect/execute. Metadata readers use those snapshots without
accessing the busy query connection; effects of earlier completed statements
remain visible after cancellation. Discovery after SQL finishes must not let a
late cancel replace that SQL outcome.

Cancelling an Adapter coroutine removes queued work or interrupts its running job
under the lock that protects the current job. The awaiter waits for the driver's
outcome: interrupted work raises `CancelledError`, and a result that reached the
Adapter before interruption was issued keeps its result. Cancellation must leave
the Session usable and cannot interrupt another request. Earlier statements'
effects are retained; cancellation does not
provide rollback. The Dispatcher exposes this through `$/cancelRequest` and
`QUERY_CANCELLED`.

Disconnect rejects new Session work, cancels and drains outstanding work, then
closes the Adapter. Once closing starts, cancelling disconnect does not reverse
it: lifecycle cleanup finishes and retains its normal outcome. End of input uses
one bounded grace period for all cleanup.
After the deadline, a driver that still ignores interruption is abandoned: its
daemon Lane cannot keep the process alive, pending awaiters are released, and
incomplete connection cleanup is logged. Driver close is attempted if the worker
later returns, but cannot be guaranteed if it remains stuck.
Profile operations remain synchronous on the loop because their files are small.

Plain worker orchestration would solve today's responsiveness, but native async
drivers and future transports would require a second migration. A default thread
pool cannot guarantee driver thread affinity or FIFO execution. Per-Session
processes add serialization and lifecycle cost without a current isolation need.

## Consequences and revisit trigger

The native-driver revisit trigger is met. The optional MySQL Adapter implements
the contract using aiomysql, verified against MySQL 8.4; see
[backlog 019](../backlog/019-mysql-adapter.md) and
[ADR-0004](0004-mysql-interruption.md). Native async Adapters must never let task
cancellation reach driver I/O. MySQL shields its reader tasks and interrupts
server statements through a separate control connection. Once interruption is
issued, a subsequently received result is cancelled even when MySQL reports
normal completion. The boundary is the Adapter receiving the result, not the
database finishing work remotely.

This decision does not choose streaming, pagination, transactions, pooling, or
network transport behavior. Result fetching now retains at most one row beyond
the response cap. MySQL `CALL` and multi-statement requests drain remaining rows
to preserve later effects, as recorded in the query-results contract.
DuckDB and MySQL metadata may observe a different transaction context
from the query connection; clients wait for an execute reply before requesting
metadata that must reflect its changes.

Driver interruption semantics and concurrency ordering require regression tests.
Revisit lane count with pooling/idle expiry and loop work if measured parsing or
output backpressure affects responsiveness. The implementation and verification
are tracked in [the change](../../openspec/changes/archive/2026-09-24-adopt-async-orchestration/proposal.md).
