# AGENTS.md

dbridge is a **stdio JSON-RPC 2.0 server** (LSP-style framing) that bridges
database clients to multiple database engines via a three-layer architecture:
**Transport / Core Engine / Adapters**. Entry point: `python -m dbridge.server`.

## Directory Overview

```
src/dbridge/
├── server.py              # Entry point: wires StdioTransport → Dispatcher → Engine
├── config/
│   ├── settings.py        # Global settings (pydantic-settings, env prefix dbridge_)
│   └── profiles.py        # Load connection profiles from connections.toml
├── adapters/
│   ├── base.py            # DBAdapter ABC, ColumnDef, TableSchema, QueryResult
│   ├── registry.py        # INSTALLED_ADAPTERS + create_adapter()
│   ├── sqlite.py          # SQLite adapter
│   ├── duckdb.py          # DuckDB adapter (no pandas)
│   └── _parked/           # mysql, postgres, snowflake (Phase 2)
├── core/
│   ├── engine.py          # Engine: top-level orchestrator (connect/execute/complete/…)
│   ├── session.py         # SessionManager + Session
│   ├── executor.py        # execute() with row-cap + truncation warnings
│   ├── schema_registry.py # In-memory TTL cache for list_tables / get_table_schema
│   └── completion.py      # Tier-1 SQL completion (FROM/JOIN → tables, SELECT/WHERE → columns)
├── protocol/
│   ├── handlers.py        # Dispatcher: JSON-RPC method → Engine call
│   ├── messages.py        # make_response / make_error helpers
│   ├── errors.py          # JSON-RPC error codes
│   └── transport/
│       └── stdio.py       # StdioTransport: LSP-framed stdin/stdout loop
├── exceptions/            # AdapterError, AdapterConnectionError, AdapterQueryError
└── logging/__init__.py    # get_logger() factory
tests/
├── adapters/              # test_sqlite.py, test_duckdb.py
├── config/                # test_profiles.py
├── core/                  # test_completion.py, test_schema_registry.py, test_session.py
├── protocol/              # test_handlers.py, test_framing.py
└── test_e2e_stdio.py      # End-to-end subprocess tests
```

## Key Subsystems

### Transport (`protocol/transport/stdio.py`)
- Reads LSP-framed messages from stdin (`Content-Length: N\r\n\r\n{json}`).
- Passes each parsed dict to `Dispatcher.handle()`, writes the response back.
- Runs synchronously in a `while True` loop; EOF exits cleanly.

### Core Engine (`core/engine.py`)
- `Engine` owns a `SessionManager` (live adapter instances) and a per-session `SchemaRegistry` (TTL cache).
- All public methods map 1-to-1 to JSON-RPC methods in the Dispatcher.
- `executor.execute()` enforces `max_rows` and appends a truncation warning when hit.

### Adapters (`adapters/`)
- `DBAdapter` ABC (`adapters/base.py`) defines: `connect`, `disconnect`, `execute`, `list_databases`, `list_schemas`, `list_tables`, `get_table_schema`, `dialect_name`, `get_keywords`.
- To add an adapter: subclass `DBAdapter`, register in `adapters/registry.py`, add optional dep to `pyproject.toml`.
- `INSTALLED_ADAPTERS` in `adapters/registry.py` lists currently registered adapters (`sqlite`, `duckdb`). mysql/postgres/snowflake are parked in `adapters/_parked/`.

### Schema Registry (`core/schema_registry.py`)
- Per-session hot-only in-memory TTL cache (default 60 s).
- Caches `list_tables()` and `get_table_schema(fqn)` results.
- `refresh()` clears all cached entries (used by `dbridge/refreshSchema`).

### Completion (`core/completion.py`)
- `complete(sql, list_tables_fn, get_columns_fn, get_keywords_fn)` — regex dispatch:
  - `FROM`/`JOIN` position → table names (kind: `table`)
  - `SELECT`/`WHERE`/`AND`/`OR`/`ON` position → columns of in-scope tables (kind: `column`)
  - otherwise → dialect keywords (kind: `keyword`)
- Uses `sqlglot` to extract referenced tables from partial SQL; degrades gracefully on errors.

### Connection Profiles (`config/profiles.py`)
- Loads `~/.config/dbridge/connections.toml` (Linux/macOS) or `%APPDATA%\dbridge\connections.toml` (Windows).
- Format: `[connections.<name>]` with `adapter` and optional `[connections.<name>.config]`.
- Missing file returns `{}` — not an error. Profiles are data only; loading does not create a live adapter.

### JSON-RPC Method Surface (`protocol/handlers.py`)
| Method | Params | Description |
|---|---|---|
| `dbridge/connect` | `adapter`, `config` | Create session → `{session_id}` |
| `dbridge/disconnect` | `session_id` | Close session → `{ok}` |
| `dbridge/execute` | `session_id`, `sql` | Run SQL → `QueryResult` |
| `dbridge/listDatabases` | `session_id` | List databases |
| `dbridge/listSchemas` | `session_id`, `database?` | List schemas |
| `dbridge/listTables` | `session_id`, `database?`, `schema?` | List tables (cached) |
| `dbridge/getTableSchema` | `session_id`, `fqn` | Column/PK/FK info (cached) |
| `dbridge/complete` | `session_id`, `sql` | Tier-1 completion items |
| `dbridge/getERD` | `session_id` | Placeholder → `{status, tables}` |
| `dbridge/refreshSchema` | `session_id` | Clear schema cache → `{ok}` |

## Repo-Specific Patterns

- **src layout**: package lives under `src/dbridge/`, not at root. Tests import `dbridge` directly.
- **Synchronous**: no asyncio; all adapters and the transport loop are sync (Phase 1 decision, see `docs/adr/0001-sync-core-for-phase-1.md`).
- **DuckDB — no pandas**: `execute()` uses native `duckdb` fetch; introspection via `information_schema`.
- **Row cap**: `executor.execute()` truncates to `max_rows` and appends a warning string to `QueryResult.warnings`.
- **uv scripts**: `uv run python -m dbridge.server` to start; `uv run --group test pytest` for tests.

## CI / Release
- Workflow: `.github/workflows/publish-pypi.yml`
- Trigger: any tag push (pattern `*`)
- Steps: build wheel + sdist → publish to TestPyPI → publish to PyPI (trusted publishing) → sign with Sigstore → create GitHub Release
- Tags follow `alpha_X.Y.Z` convention (e.g. `alpha_0.2.10`)

## Environment Variables (prefix `dbridge_`)

| Variable | Default | Description |
|---|---|---|
| `dbridge_logging_level` | `INFO` | Log level |
| `dbridge_max_rows` | `100` | Row cap for `execute` (truncation warning added when hit) |
| `dbridge_cache_ttl_seconds` | `60` | Schema registry TTL |

## Agent skills

### Issue tracker

Issues and PRDs live as markdown files under `.scratch/<feature>/` in this repo. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical triage roles, using the default label strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Custom Instructions
<!-- This section is for human and agent-maintained operational knowledge.
     Add repo-specific conventions, gotchas, and workflow rules here.
     This section is preserved exactly as-is when re-running codebase-summary. -->
