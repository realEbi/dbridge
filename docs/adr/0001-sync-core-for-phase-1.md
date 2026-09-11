# Synchronous core engine and adapters for Phase 1

Status: accepted; still applicable until superseded by a new ADR.

## Decision and rationale

The original vision called for an async core and streaming results. Phase 1
deliberately chose a synchronous Core Engine and synchronous Adapters. Its only
Transport was stdio serving one client process; the shipped sqlite3 and duckdb
calls were blocking. Async orchestration would have added wrapping or driver
changes before concurrent work was in scope.

Streaming, query cancellation, and explicit transaction APIs were also deferred
to keep that release small. These are scope decisions, not a claim that every
feature requires asyncio. In particular, explicit transactions can be implemented
with synchronous adapters. SQLite currently uses autocommit; a transaction API
must define how it interacts with that behavior.

## Consequences and revisit trigger

Multiple Sessions can exist, but the process handles requests sequentially. The
[current architecture](../architecture.md) documents the implemented call path.

Revisit this decision when concurrent queries, cancellation, or additional client
transports are selected from the [roadmap](../roadmap.md). Record the chosen
execution model and migration strategy in an OpenSpec change and a superseding
ADR before describing that model as the current architecture.
