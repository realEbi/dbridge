# Current architecture

This document describes the implemented server. The [roadmap](roadmap.md)
describes its intended evolution; [ADRs](adr/) explain architectural decisions.
Use the [glossary](../CONTEXT.md) for domain terminology and the
[README](../README.md#json-rpc-methods) for the supported method surface.

## Execution model

The server is synchronous. It supports multiple live Sessions in one process,
but handles one request at a time. A long query blocks subsequent requests in
that process until it returns.

```text
Client
  |
  | stdin/stdout, Content-Length framing, UTF-8 JSON
  v
StdioTransport.serve
  --> Dispatcher.handle
        --> Engine
              --> Session / SchemaRegistry / completion / executor
                    --> DBAdapter
                          --> sqlite3 or duckdb
  <-- one response after the handler finishes
```

The evidence is the direct call in
[`StdioTransport.serve`](../src/dbridge/protocol/transport/stdio.py), ordinary
methods in [`Engine`](../src/dbridge/core/engine.py), and blocking `fetchall()`
in the [SQLite](../src/dbridge/adapters/sqlite.py) and
[DuckDB](../src/dbridge/adapters/duckdb.py) adapters. The runtime has no async
event loop or background query executor. [ADR-0001](adr/0001-sync-core-for-phase-1.md)
records this decision and remains applicable until superseded.

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

Profiles are persisted data. Loading, saving, or deleting a Profile does not
create or close a Session. Clients manage Profiles through the Profile RPCs.
The server owns `connections.toml`, under `$XDG_CONFIG_HOME/dbridge` (default
`~/.config/dbridge`) on Unix-like systems or `%APPDATA%\dbridge` on Windows.
Settings are read from environment variables; there is no settings.toml loader.
See the [README](../README.md#profiles) for the file shape and settings.

## Queries and adapters

Only SQLite and DuckDB are registered. The MySQL, PostgreSQL, and Snowflake code
in `adapters/_parked/` uses an older interface and is neither registered nor
imported by the registry. DuckDB execution uses native fetch methods without
pandas; this does not imply pandas has been removed from package dependencies.

Both shipped adapters fully materialize query results. The executor then limits
the returned rows to `max_rows` (default 100), sets `row_count` to the returned
count, and adds a truncation warning when the result exceeds the cap. The cap is
therefore a response limit, not a bound on database fetching or server memory.
Results contain ordered `columns`, positional `rows`, `row_count`,
`execution_time_ms`, and `warnings`.

SQLite connects in autocommit mode so writes survive disconnect/reconnect. The
protocol exposes no explicit begin/commit/rollback methods. Streaming, query
cancellation, server-side cursors, and server-to-client notifications are not
implemented.

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
or shared cache.

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

Completion uses an optional UTF-8 byte offset `position`, which defaults to the
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
