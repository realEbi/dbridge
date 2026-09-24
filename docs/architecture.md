# Current architecture

This document describes the implemented server. The [roadmap](roadmap.md)
describes its intended evolution; [ADRs](adr/) explain architectural decisions.
Use the [glossary](../CONTEXT.md) for domain terminology and the
[README](../README.md#json-rpc-methods) for the supported method surface.

## Execution model

Transport, Dispatcher, and Core Engine run on one asyncio event loop. A blocking
reader thread continues accepting framed input while request tasks await database
work. Replies carry their request id and are written on the loop in completion
order, so a fast request can overtake an earlier slow one without interleaving
frames. An outstanding id cannot be reused until its reply is written.

```text
Client stdin --> reader thread --> asyncio loop: Dispatcher request tasks
                                      --> Engine / SchemaRegistry / completion
                                            --> async DBAdapter
                                                  --> Adapter-owned lanes
Client stdout <-- complete replies on the loop     --> sqlite3 or duckdb
```

A Lane is one daemon thread and FIFO job queue owning a driver connection. SQLite
uses one Lane and retains its driver same-thread check. DuckDB uses a query Lane
and a metadata Lane whose sibling cursor comes from the query connection, so
attached catalogs remain visible. Different Sessions run independently. Executes
on one Session keep arrival order; uncached SQLite metadata queues behind its
queries, while DuckDB metadata can run alongside them. Clients wait for an execute
reply before requesting metadata that must reflect that statement's effects.
DuckDB's sibling cursor does not share the query connection's `USE` state or
temporary objects. The query Lane publishes replacement snapshots of its default
Scope Path and temporary-table metadata after connecting and after execute,
including effects of earlier statements when a later statement fails or is
cancelled. Metadata reads use those snapshots for temporary objects, preserving
Session-local state without accessing the busy query connection. Snapshot
discovery after SQL has finished is protected from late cancellation, so it
cannot replace an already-established query outcome.

Database-touching Adapter methods are coroutines; `scope_levels`, `dialect_name`,
and `get_keywords` remain synchronous declarations. Cache hits, completion parsing,
and small Profile file operations run directly on the loop. A cache hit does not
wait for database work. The Core Engine owns no driver threads or interrupts.

`$/cancelRequest` cancels the task registered under its JSON-RPC id. Adapter lanes
remove queued work or interrupt the currently running job while holding the same
lock used to change the current job, so a late cancel cannot reach the next job.
Interrupted work replies with `QUERY_CANCELLED`; completed or non-interruptible
work keeps its normal result. Cancels for unknown/completed ids or malformed
params are ignored. The Session remains usable after cancellation; effects of
earlier completed statements are retained.

Disconnect marks a Session closing, rejects new work with `SESSION_NOT_FOUND`,
cancels and drains its outstanding requests, then closes its Adapter. Once
disconnect starts closing, cancellation of the disconnect request does not
reverse the lifecycle change: it finishes cleanup and returns its normal outcome.
Concurrent disconnects share that cleanup. End of input
and fatal framing errors start the same bounded shutdown: cancel all requests,
drain them, and close Sessions within `SHUTDOWN_GRACE_SECONDS` (currently one
second, a module constant). If a driver ignores interruption past the deadline,
the server logs incomplete cleanup, abandons its daemon lanes, releases awaiters,
and exits successfully. Driver connection cleanup is attempted if that worker
later returns; it cannot be guaranteed for a driver that never returns. Replies
produced during shutdown are written only while the output pipe remains usable.

A complete body containing invalid UTF-8 JSON returns `PARSE_ERROR` with a null id,
and the next frame is still accepted. A truncated body or invalid/missing
`Content-Length` logs a diagnostic and shuts down cleanly. Framing continues to
count encoded bytes, and diagnostics stay off stdout.

[ADR-0003](adr/0003-async-orchestration.md) supersedes the Phase 1 synchronous
execution decision in [ADR-0001](adr/0001-sync-core-for-phase-1.md). The async Adapter
contract remains provisional until a native async MySQL driver validates it.
Implementation lives in [Transport](../src/dbridge/protocol/transport/stdio.py),
[Dispatcher](../src/dbridge/protocol/handlers.py), [Engine](../src/dbridge/core/engine.py),
and the shared [Lane](../src/dbridge/adapters/lane.py) and
[thread-backed Adapter base](../src/dbridge/adapters/threaded.py).

## Boundaries and source map

| Area | Responsibility | Source |
|---|---|---|
| Entry point | Wire Transport, Dispatcher, and Engine | [server.py](../src/dbridge/server.py) |
| Transport | Read/write frames and serve requests over stdio | [protocol/transport/](../src/dbridge/protocol/transport/) |
| Protocol | Validate request shape, dispatch methods, map recognized errors | [protocol/handlers.py](../src/dbridge/protocol/handlers.py) |
| Core Engine | Coordinate Sessions, execution, introspection, and completion | [core/](../src/dbridge/core/) |
| Adapters | Own driver calls and database-specific behavior | [adapters/](../src/dbridge/adapters/) |
| Configuration | Persist Profiles and read environment settings | [config/](../src/dbridge/config/) |

The package uses the `src/dbridge/` layout. The Core Engine is independent of
transport I/O and accesses databases through the Adapter interface. Clients live
in separate repositories and own presentation and editor interactions.

## Sessions and Profiles

`dbridge/connect` resolves a saved Profile or accepts inline adapter/config data,
creates a fresh Adapter, connects it, and returns a UUID `session_id`, the Adapter's
ordered Scope Levels, a default Scope Path, and its SQL dialect. Each Session owns
one Adapter; the Engine also creates a SchemaRegistry for it. Disconnect closes
the Adapter and removes the Session and registry. Session holds no active metadata
scope. Clients send a Scope Path with every scoped metadata request, so one
request's selection cannot change another request's lookup.
[ADR-0002](adr/0002-explicit-scope-paths.md) records this decision.

Profiles are persisted data. Loading, saving, renaming, or deleting a Profile
does not create, change, or close a Session: each live Session keeps the Adapter
and configuration it connected with. Clients manage Profiles through the Profile RPCs.
The server owns `connections.toml`, under `$XDG_CONFIG_HOME/dbridge` (default
`~/.config/dbridge`) on Unix-like systems or `%APPDATA%\dbridge` on Windows.
Settings are read from environment variables; there is no settings.toml loader.
See the [README](../README.md#profiles) for the file shape and settings.

`saveProfile` accepts an optional `previous_name`. When it differs from `name`,
storage checks that the source exists and the destination is unused, then replaces
the source entry with the new name and definition in its original position. The
rename is one read-modify-write and one file write; rejected missing-source and
name-collision requests leave the file unchanged. Omitting `previous_name`, or
using the same name, retains the existing upsert behavior. These synchronous
operations run on the event loop without yielding, so Profile requests from this
server cannot interleave the read and write. They do not coordinate with other
processes. Saves and deletes still rewrite the file in place rather than replacing
it through a temporary file; crash-safe persistence remains
[backlog 059](backlog/059-crash-safe-profile-writes.md).

## Queries and adapters

Only SQLite and DuckDB are registered. The MySQL, PostgreSQL, and Snowflake code
in `adapters/_parked/` uses an older interface and is neither registered nor
imported by the registry. DuckDB execution uses native fetch methods without
pandas; this does not imply pandas has been removed from package dependencies.

The executor asks both shipped Adapters for at most `max_rows + 1` rows, using
native bounded fetches on the query Lane. The extra row detects truncation: the
executor returns at most `max_rows` rows (default 100), sets `row_count` to the
returned count, and adds `result truncated to <max_rows> rows` only when the
result exceeds the cap. A result exactly at the cap has no truncation warning.
Results contain ordered `columns`, positional `rows`, `row_count`,
`execution_time_ms`, and `warnings`; they do not report a total result count.

Capped statements release their database resources before the reply. SQLite
closes the cursor in `finally`, releasing its read lock; DuckDB's existing Session
metadata snapshot queries replace the pending result. Writes with `RETURNING`
apply every modification even when their returned rows are capped. The cap bounds
rows read into Python, not work the database performs before producing its first
row. Sorts and aggregates over large inputs still run to completion unless
cancelled, and database-internal memory use is not bounded by this fetch limit.

SQLite connects in autocommit mode so writes survive disconnect/reconnect. The
protocol exposes no explicit begin/commit/rollback methods. Streaming, server-side cursors, and server-to-client notifications remain
unimplemented. Request cancellation is described above.

Execution accepts SQL without a Scope Path and retains the database engine's SQL
resolution rules. Sending a metadata Scope Path does not change the driver's
current catalog, schema, or search path. The default Scope Path is discovery data,
derived from the live Adapter, rather than an implicit scope for later requests.

## Schema browsing and completion

Adapters declare ordered Scope Levels with stable names and display labels:
SQLite has one namespace level, DuckDB has catalog then schema levels. A full
Scope Path has one literal component per level. SQLite therefore reports
`["main"]`, eliminating the old redundant `main/main` hierarchy. Attached SQLite
namespaces and DuckDB catalogs are first-level containers. `listDatabases`
enumerates this first level without a path. `listSchemas` takes a one-component
path and returns the next level; for SQLite it returns an empty list.

Container entries carry `name` and `internal`, retaining engine-internal entries
for clients to present as appropriate. SQLite marks its `temp` namespace when
present. DuckDB marks `system` and `temp` catalogs, their schemas, and
`information_schema`/`pg_catalog` in user catalogs. User catalogs and their
`main` schemas remain unmarked.

Each Session has an in-memory TTL cache (default 60 seconds) covering database,
schema, and table listings plus table metadata. Schema/table listings are keyed by
the full literal request path; metadata uses an immutable `TableRef(name, path)`.
`refreshSchema` clears every cached introspection result and returns current
Scope Levels and a default Scope Path. Its declaration is authoritative over the
connect-time copy. Query execution does not invalidate caches after DDL or
`ATTACH`; clients refresh to rebuild their metadata view. There is no persistent
or shared cache. Cache refresh increments a generation: a fetch started before
refresh can still return to its original requester, but cannot repopulate the
cache afterward. Cancelled fetches do not store results. Concurrent misses fetch
independently so cancelling one does not cancel another request's metadata.

`listTables` returns entries containing a literal `name` and an Adapter-owned
`sql_identifier`. `getTableSchema` requires top-level `path` and `name` parameters
and reports `scope` with the Adapter's exact arity. Legacy `fqn`, `table`,
`database`, and `schema` inputs are rejected on scoped metadata requests. Paths
must be arrays of nonempty strings with the operation's required arity; invalid
paths return `INVALID_REQUEST` without terminating the server. Each identifier
quotes the path components in order followed by the table name, doubling embedded
double quotes. Literal dots remain part of a component. Unresolved tables return
no columns and a null identifier. Metadata failures remain errors.

SQLite reports column metadata, primary keys, and foreign keys. DuckDB reports
columns but currently returns empty primary/foreign key lists. `getERD` requires a
full Scope Path and returns `{"status": "not_implemented", "tables": [...]}`
with that path's table entries.

Completion awaits table and column lookups; sqlglot parsing stays synchronous on
the event loop. Completion uses an optional UTF-8 byte offset `position`, which defaults to the
end of `sql`. Unquoted qualified column positions such as `p.` and `p.na` are
resolved against physical FROM/JOIN sources in the cursor's SELECT scope. A
temporary cursor marker lets sqlglot parse the unfinished column without losing
the following FROM clause. Resolution preserves nested-query and statement
boundaries; returned insertion text is the bare column name. Unresolvable
qualifiers and metadata failures return no qualified suggestions. Physical source
components travel as structured table identities through the schema registry, so
literal dots in quoted table/schema/catalog names cannot select a different
namespace. Missing leading source qualifiers come from the request's Scope Path;
explicit SQL qualifiers retain their own containers. Completion detail/sort text
remains separate from metadata identity.

Unqualified SELECT target expressions use the same cursor marker and exact SELECT
scope. They offer columns of that scope's physical FROM/JOIN sources, including
after commas, inside expressions, and for typed prefixes. Source order and schema
column order are preserved, with duplicate labels retaining physical table detail.
When no physical source resolves, including bare `SELECT `, completion returns
dialect keywords without introspecting other tables. Metadata failures skip the
affected source; no matching column prefix returns an empty list.

FROM/JOIN contexts offer tables only from the request's full Scope Path. Their
display labels are bare names; every table suggestion inserts its executable
fully qualified identifier, so attached-container selections execute without
changing driver scope. The legacy unqualified WHERE/AND/OR/ON
path still uses whole-statement table extraction; other contexts fall back to
dialect keywords. CTE/derived-table projections, outer correlated references,
quoted qualifier syntax, values, and richer ranking remain deferred. See the
[backlog](backlog/README.md).

## Diagnostics

Named server loggers reuse their existing direct handlers. If none is configured,
logger setup installs one console handler writing to stderr, preserving stdout
for protocol frames. Repeated Adapter construction does not multiply handlers or
diagnostic lines. Embedding applications retain handlers they configure explicitly;
the requested logger level can change without adding a new console handler.

## Verification evidence

Tests cover [stdio framing](../tests/protocol/test_framing.py),
[dispatch and Profiles](../tests/protocol/test_handlers.py),
[subprocess flows](../tests/test_e2e_stdio.py),
[completion](../tests/core/test_completion.py),
[cache behavior](../tests/core/test_schema_registry.py), and
[adapters](../tests/adapters/). Test presence does not imply every edge case is
covered. The [manual guide](manual-testing-guide.md) covers interactive checks
against reusable sample databases;
[development instructions](development.md) list the verification commands.
