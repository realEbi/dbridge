# dbridge

[![actions status](https://img.shields.io/github/actions/workflow/status/realebi/dbridge/publish-pypi.yml?logo=github&style=)](https://github.com/realebi/dbridge/actions)
[![PyPI - Version](https://img.shields.io/pypi/v/dbridge.svg)](https://pypi.org/project/dbridge)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dbridge.svg)](https://pypi.org/project/dbridge)

---

A unified database management server that bridges client applications to multiple
database engines via a **stdio JSON-RPC 2.0** interface (LSP-style framing).
Designed to back editor plugins and TUI clients like
[dbridge.nvim](https://github.com/realebi/dbridge.nvim).

The current server executes requests synchronously. See the
[current architecture](docs/architecture.md) and the separate
[roadmap](docs/roadmap.md) for the planned evolution.

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

## JSON-RPC Methods

All requests follow JSON-RPC 2.0 with LSP framing (`Content-Length` header).

| Method | Params | Description |
|---|---|---|
| `dbridge/connect` | `profile` **or** `adapter` + `config?` | Open a Session → `{session_id, levels, default_path, dialect}` |
| `dbridge/disconnect` | `session_id` | Close a session → `{ok}` |
| `dbridge/execute` | `session_id`, `sql` | Run SQL → `{columns, rows, row_count, …}` |
| `dbridge/listDatabases` | `session_id` | First-level containers → `[{name, internal}]`; rejects `path` |
| `dbridge/listSchemas` | `session_id`, `path` | Child containers under a one-component path → `[{name, internal}]`; SQLite returns `[]` |
| `dbridge/listTables` | `session_id`, `path` | Tables in a full path → `[{name, sql_identifier}]` |
| `dbridge/getTableSchema` | `session_id`, `path`, `name` | `{name, scope, columns, primary_keys, foreign_keys, sql_identifier}` |
| `dbridge/complete` | `session_id`, `path`, `sql`, `position?` | SQL completion items; `position` is the cursor's UTF-8 byte offset into `sql` (default: end) |
| `dbridge/getERD` | `session_id`, `path` | Placeholder → `{status: "not_implemented", tables: [{name, sql_identifier}]}` |
| `dbridge/refreshSchema` | `session_id` | Clear all metadata caches → `{ok, levels, default_path}` |
| `dbridge/listProfiles` | — | Saved profiles → `{name: {adapter, config}}` |
| `dbridge/saveProfile` | `name`, `adapter`, `config?` | Upsert a profile → `{ok}` |
| `dbridge/deleteProfile` | `name` | Remove a profile → `{ok}` (false if absent) |

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
