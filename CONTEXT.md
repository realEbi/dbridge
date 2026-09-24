# dbridge

dbridge is a protocol-driven backend that bridges database engines to developer clients (Neovim first), exposing a uniform interface for queries, schema browsing, and SQL completion over JSON-RPC.

This file owns domain terminology. See [current architecture](docs/architecture.md)
for implemented behavior and the [roadmap](docs/roadmap.md) for future direction.

## Language

**DSP (dbridge Server Protocol)**:
The dbridge-specific methods and request/result contracts carried over JSON-RPC
2.0. The current stdio Transport uses LSP-style framing; that does not make DSP
the full Language Server Protocol.

**Adapter**:
The database-engine-specific implementation behind a single interface. The core engine never talks to a driver directly — only through an Adapter (e.g. the DuckDB adapter, the Postgres adapter).
_Avoid_: driver, connector, backend

**Session**:
A live, server-side binding to one instantiated Adapter, identified by a `session_id`. Created fresh by `dbridge/connect` from a saved Profile or inline adapter/config data; not persisted. A Session holds no active metadata scope: clients send a Scope Path with each scoped metadata request. Multiple Sessions do not imply concurrent query execution.
_Avoid_: connection (ambiguous — say Profile for the config, Session for the live object)

**Scope Path**:
An ordered sequence of nonempty literal container names locating metadata within an
Adapter's declared hierarchy. A full path has one component per Scope Level:
`["main"]` for SQLite and `["memory", "main"]` for an in-memory DuckDB catalog's
main schema. A table is addressed by its full path plus a literal table name.
Scope Paths are immutable tuples internally and arrays in DSP. They are independent
of sqlglot's SELECT `Scope`, which describes SQL name visibility inside a query.
_Avoid_: active scope, current scope, fqn, database/schema pair, SELECT scope

**Scope Level**:
One container tier in an Adapter's ordered hierarchy, declared with a stable `name`
and a display `label`. SQLite declares a namespace level; DuckDB declares catalog
then schema levels. Clients use these declarations to interpret Scope Paths and
render hierarchy without inferring its shape from the SQL dialect.
_Avoid_: fixed database tier, fixed schema tier, dialect hierarchy

**Transport**:
The layer that moves JSON-RPC messages between a client and the core engine over a specific channel (currently stdio). The core engine is transport-agnostic.
_Avoid_: protocol (the protocol is JSON-RPC/DSP; the transport is the channel)

**Core Engine**:
The transport-agnostic business-logic layer sitting between Transport and Adapters: session management, query dispatch, schema registry, completion. Owns no driver code.
_Avoid_: backend, service

**Profile**:
A named, persisted configuration describing *how* to reach a database (adapter name + config dict). It is data, never a live object. Persisted to `~/.config/dbridge/connections.toml` and owned by the server: clients read and write profiles through `dbridge/listProfiles`, `dbridge/saveProfile`, and `dbridge/deleteProfile`, never by touching the TOML file. `dbridge/connect` accepts either a profile name or an inline adapter + config.
_Avoid_: connection, connection profile, datasource

> The TOML sections are spelled `[connections.<name>]` for historical reasons. In prose, code, and protocol methods the term is **Profile**.

**Neovim Client**:
The Lua plugin (`dbridge.nvim`) that spawns the dbridge server as a stdio child process and communicates with it over JSON-RPC 2.0 with LSP framing. Lives in a separate repo. Owns no database logic.
_Avoid_: frontend (too generic), extension
