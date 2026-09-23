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
creates a fresh Adapter, connects it, and returns a UUID `session_id`. Each Session
owns one Adapter; the Engine also creates a SchemaRegistry for it. Disconnect
closes the Adapter and removes the Session and registry. The active database and
schema fields exist on Session, but there is no method to select them today.

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

## Schema browsing and completion

Each Session has an in-memory TTL cache (default 60 seconds) for `listTables` and
`getTableSchema`, keyed by their arguments. `refreshSchema` clears it. Database
and schema listings bypass this cache; query execution does not automatically
invalidate it after DDL. There is no persistent or shared cache.

SQLite reports column metadata, primary keys, and foreign keys. DuckDB reports
columns but currently returns empty primary/foreign key lists. `getERD` returns
`{"status": "not_implemented", "tables": [...]}`.

Completion classifies the text before an optional UTF-8 byte offset `position`,
which defaults to the end of `sql`. It parses the full SQL with sqlglot to find
tables in scope. FROM/JOIN contexts offer tables; SELECT/WHERE/AND/OR/ON contexts
offer columns; other contexts fall back to dialect keywords. It tolerates partial
SQL, but alias-qualified columns, values, richer ranking, and some SELECT contexts
are deferred. See the [backlog](backlog/README.md).

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
