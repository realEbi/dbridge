# dbridge

[![actions status](https://img.shields.io/github/actions/workflow/status/realebi/dbridge/publish-pypi.yml?logo=github&style=)](https://github.com/realebi/dbridge/actions)
[![PyPI - Version](https://img.shields.io/pypi/v/dbridge.svg)](https://pypi.org/project/dbridge)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dbridge.svg)](https://pypi.org/project/dbridge)

---

A unified database management server that bridges client applications to multiple
database engines via a **stdio JSON-RPC 2.0** interface (LSP-style framing).
Designed to back editor plugins and TUI clients like
[dbridge.nvim](https://github.com/realebi/dbridge.nvim).

The server keeps accepting requests while queries run, supports cancellation, and
returns replies in completion order. See the [current architecture](docs/architecture.md)
and the separate [roadmap](docs/roadmap.md) for the planned evolution.

## Table of Contents

- [Installation](#installation)
- [Run the Server](#run-the-server)
- [Profiles](#profiles)
- [JSON-RPC Methods](#json-rpc-methods)
- [Development](#development)
- [Documentation](#documentation)
- [UIs](#uis)
- [License](#license)

## Installation

```console
pip install dbridge
```

## Run the Server

The server reads LSP-framed JSON-RPC messages from stdin and writes responses to
stdout.

```console
python -m dbridge.server
```

With uv:

```console
uv run python -m dbridge.server
```

## Profiles

Named Profiles are stored by the server in
`~/.config/dbridge/connections.toml` (Linux/macOS) or
`%APPDATA%\dbridge\connections.toml` (Windows). On Linux/macOS,
`XDG_CONFIG_HOME` can override the base configuration directory. File format:

```toml
[connections.mydb]
adapter = "sqlite"
[connections.mydb.config]
uri = "/path/to/database.db"

[connections.analytics]
adapter = "duckdb"
[connections.analytics.config]
uri = "/path/to/data.duckdb"
```

A missing file is not an error — profiles are data only and do not create live
connections. The server owns this file: clients should manage profiles through
`dbridge/listProfiles` / `dbridge/saveProfile` / `dbridge/deleteProfile` rather
than editing the TOML themselves.

`dbridge/saveProfile` creates or replaces a Profile under `name`. To rename and
edit an existing Profile together, send its old name as `previous_name`:

```json
{"name": "analytics", "previous_name": "warehouse", "adapter": "duckdb", "config": {"uri": "/path/to/data.duckdb"}}
```

When the names differ, the server replaces the old entry in one file update,
preserving its position among other Profiles. It rejects an existing destination
with `PROFILE_ALREADY_EXISTS` (-32007) or a missing source with
`PROFILE_NOT_FOUND` (-32006), leaving the file unchanged. A supplied
`previous_name` must be a nonempty string or the request returns
`INVALID_REQUEST` (-32600). Omitting it, or setting it equal to `name`, keeps the
create-or-replace behavior. Saving or renaming a Profile does not change any live
Session. The file update still uses an in-place write; interrupted writes are a
[separate known limitation](docs/backlog/059-crash-safe-profile-writes.md).

## JSON-RPC Methods

All requests follow JSON-RPC 2.0 with LSP framing (`Content-Length` counts UTF-8
body bytes). Replies may arrive out of request order; clients correlate them by
`id`. A request id must stay unique until its reply arrives.

| Method | Params | Description |
|---|---|---|
| `dbridge/connect` | `profile` **or** `adapter` + `config?` | Open a Session → `{session_id, levels, default_path, dialect}` |
| `dbridge/disconnect` | `session_id` | Cancel the Session's outstanding work, then close it → `{ok}` |
| `dbridge/execute` | `session_id`, `sql` | Run SQL → `{columns, rows, row_count, …}` |
| `dbridge/listDatabases` | `session_id` | First-level containers → `[{name, internal}]`; rejects `path` |
| `dbridge/listSchemas` | `session_id`, `path` | Child containers under a one-component path → `[{name, internal}]`; SQLite returns `[]` |
| `dbridge/listTables` | `session_id`, `path` | Tables in a full path → `[{name, sql_identifier}]` |
| `dbridge/getTableSchema` | `session_id`, `path`, `name` | `{name, scope, columns, primary_keys, foreign_keys, sql_identifier}` |
| `dbridge/complete` | `session_id`, `path`, `sql`, `position?` | SQL completion items; `position` is the cursor's UTF-8 byte offset into `sql` (default: end) |
| `dbridge/getERD` | `session_id`, `path` | Placeholder → `{status: "not_implemented", tables: [{name, sql_identifier}]}` |
| `dbridge/refreshSchema` | `session_id` | Clear all metadata caches → `{ok, levels, default_path}` |
| `dbridge/listProfiles` | — | Saved profiles → `{name: {adapter, config}}` |
| `dbridge/saveProfile` | `name`, `adapter`, `config?`, `previous_name?` | Upsert a Profile, or rename and replace `previous_name` → `{ok}` |
| `dbridge/deleteProfile` | `name` | Remove a profile → `{ok}` (false if absent) |
| `$/cancelRequest` | `id` | Notification: cancel an outstanding request; no reply to the notification |

**Supported adapters:** `sqlite`, `duckdb`

`connect` reports the hierarchy before the first scoped request. For SQLite, its
result has this shape:

```json
{
  "session_id": "<session-id>",
  "levels": [{"name": "namespace", "label": "Namespace"}],
  "default_path": ["main"],
  "dialect": "sqlite"
}
```

DuckDB declares `[{"name": "catalog", "label": "Catalog"},
{"name": "schema", "label": "Schema"}]` and reports its current catalog and
schema as `default_path`, for example `["memory", "main"]`. `dialect` is `duckdb`.
Clients use `levels` for hierarchy and `dialect` for SQL syntax. `refreshSchema`
returns the authoritative current `levels` and `default_path`, plus `ok: true`.

`path` is a required array of nonempty literal strings. Table listing, table
metadata, ERD, and completion require a full path: one component for SQLite and
two for DuckDB. `listSchemas` takes one first-level component; SQLite has no
second tier. Missing paths, malformed components, and wrong arity return
`INVALID_REQUEST`. `listDatabases` accepts no path. Containers are returned with
an `internal` boolean; internal namespaces/catalogs and schemas remain visible.

To inspect a literal table name, send `getTableSchema` params such as
`{"session_id": "<session-id>", "path": ["main"], "name": "order.items"}`.
The response reports `scope: ["main"]`; neither path components nor the name
are split on dots. The legacy `fqn`, `table`, `database`, and `schema` inputs are
rejected on scoped metadata requests. This is a breaking DSP change requiring
clients to migrate together with the server.

Both `listTables` entries and resolved `getTableSchema` results include an
executable `sql_identifier`. It quotes every path component followed by the table
name, doubling embedded double quotes: SQLite uses namespace/table and DuckDB
uses catalog/schema/table. An unresolved table returns no columns and
`sql_identifier: null`; clients should not generate a query from that result.
All four metadata listings/lookups share the Session cache. Refresh after DDL or
`ATTACH` to invalidate cached listings and metadata and re-read the hierarchy;
execution does not invalidate them automatically.

The server stores no selected metadata scope. Each request's `path` controls its
own metadata lookup. `execute` takes SQL without a path and uses the database
engine's SQL resolution rules; selecting a metadata path does not issue `USE` or
otherwise alter those rules.

SQL completion lists tables only from the request's full Scope Path. Table
suggestions display the literal name and insert the executable fully qualified
`sql_identifier`, including for tables inside that path. A partly qualified SQL
source fills its missing leading containers from the request's path; an explicitly
qualified source keeps its own containers.

Column completion supports unquoted physical-table qualifiers in the current SELECT
scope. For `SELECT p.name, p.category FROM products p LIMIT 100`, send the path, full
SQL and a cursor `position` immediately after either `p.` to receive product
columns. Typing `p.na` filters to matching names; insertion text is the column
name alone. Unqualified SELECT targets also offer columns from physical sources
in that SELECT, including after commas and inside expressions; `SELECT id, na`
before `FROM products` filters to `name`. A bare `SELECT ` or a SELECT without a
resolvable physical source offers dialect keywords. CTE/derived-table columns and
outer correlated references remain deferred. See the
[manual guide](docs/manual-testing-guide.md) for interactive checks.

### Concurrent requests and cancellation

Different Sessions can run queries concurrently. On one Session, `execute`
requests keep arrival order. DuckDB can answer metadata and completion while a
query runs on that Session; SQLite queues database work behind the query, but
cached completion remains available. Wait for an execute reply before requesting
metadata that must reflect its changes. A refresh prevents older in-flight
introspection from repopulating the cache.

Cancel an outstanding request by sending its id in a notification with no outer
`id`:

```json
{"jsonrpc": "2.0", "method": "$/cancelRequest", "params": {"id": 42}}
```

The interrupted request replies with `QUERY_CANCELLED` (-32004), and the Session
remains usable. Queued work is removed before it runs. Cancellation affects only
the named request and is best effort: work that already finished or cannot be
interrupted keeps its normal result. Earlier statements' effects in a cancelled
multi-statement execute remain; cancellation does not roll them back. Unknown,
completed, or malformed cancel ids are ignored without a reply.

Disconnect rejects new work for that Session with `SESSION_NOT_FOUND`, cancels
and drains its outstanding work, then closes its Adapter. Cancelling a disconnect
after closing has started waits for cleanup and keeps the disconnect's normal
outcome. Closing stdin also
cancels outstanding work and closes Sessions within a fixed shutdown grace period.
A driver that cannot stop is abandoned when that period expires; cleanup can be
incomplete, but the process still exits successfully and reports it on stderr.

### Errors and framing

Errors use the JSON-RPC `error` object. The main codes are:

| Code | Name | Meaning |
|---|---|---|
| -32700 | `PARSE_ERROR` | A complete frame body is not valid UTF-8 JSON; reply id is null and the next frame is still accepted |
| -32600 | `INVALID_REQUEST` | Invalid request shape or parameters, including an id still in use |
| -32601 | `METHOD_NOT_FOUND` | Unknown request method |
| -32603 | `INTERNAL_ERROR` | An unexpected request failure |
| -32001 | `CONNECTION_FAILED` | The Adapter could not connect |
| -32002 | `QUERY_ERROR` | The Adapter could not execute SQL or read metadata |
| -32003 | `SESSION_NOT_FOUND` | Unknown or closing Session |
| -32004 | `QUERY_CANCELLED` | The named request was cancelled |
| -32005 | `ADAPTER_NOT_SUPPORTED` | The requested Adapter is not registered |
| -32006 | `PROFILE_NOT_FOUND` | The named Profile does not exist |
| -32007 | `PROFILE_ALREADY_EXISTS` | A Profile rename would replace another Profile |

A truncated body or an invalid/missing `Content-Length` cannot be safely
resynchronized. The server logs the framing failure to stderr and follows its
normal shutdown path. stdout remains reserved for complete protocol frames.

**Environment variables** (prefix `dbridge_`):

| Variable | Default | Description |
|---|---|---|
| `dbridge_logging_level` | `INFO` | Log level |
| `dbridge_max_rows` | `100` | Row cap per query |
| `dbridge_cache_ttl_seconds` | `60` | Schema cache TTL |

## Development

Clone the repo and install dependencies with [uv](https://docs.astral.sh/uv/):

```console
uv sync
```

Run tests:

```console
uv run --group test pytest
```

New work follows OpenSpec. See the [development guide](docs/development.md) for
workflow commands, type/lint checks, verification, and release details.

## Documentation

- [Current architecture](docs/architecture.md) — implemented structure and limits
- [Roadmap](docs/roadmap.md) — future direction and dependencies
- [Backlog](docs/backlog/README.md) — individual deferred ideas and defects
- [Manual testing](docs/manual-testing-guide.md) — sample preparation and interactive checks
- [Domain vocabulary](CONTEXT.md) and [architectural decisions](docs/adr/)
- [Agent workflow and document ownership](AGENTS.md)
- [Capability specs](openspec/specs/) and [OpenSpec changes](openspec/changes/)

## UIs

- [dbridge.nvim](https://github.com/realebi/dbridge.nvim) — Neovim plugin
- [dbridge.tui](https://github.com/realebi/dbridge.tui) — Terminal UI built with [Textual](https://textual.textualize.io/)

## License

`dbridge` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
