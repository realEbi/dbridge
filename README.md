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
| `dbridge/connect` | `profile` **or** `adapter` + `config` | Open a session → `{session_id}` |
| `dbridge/disconnect` | `session_id` | Close a session → `{ok}` |
| `dbridge/execute` | `session_id`, `sql` | Run SQL → `{columns, rows, row_count, …}` |
| `dbridge/listDatabases` | `session_id` | List databases |
| `dbridge/listSchemas` | `session_id`, `database?` | List schemas |
| `dbridge/listTables` | `session_id`, `database?`, `schema?` | List tables |
| `dbridge/getTableSchema` | `session_id`, `fqn` | Column/PK/FK info |
| `dbridge/complete` | `session_id`, `sql`, `position?` | SQL completion items; `position` is the cursor's byte offset into `sql` (default: end) |
| `dbridge/getERD` | `session_id` | ERD placeholder |
| `dbridge/refreshSchema` | `session_id` | Clear schema cache |
| `dbridge/listProfiles` | — | Saved profiles → `{name: {adapter, config}}` |
| `dbridge/saveProfile` | `name`, `adapter`, `config?` | Upsert a profile → `{ok}` |
| `dbridge/deleteProfile` | `name` | Remove a profile → `{ok}` (false if absent) |

**Supported adapters:** `sqlite`, `duckdb`

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
