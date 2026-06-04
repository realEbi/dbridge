# AGENTS.md

dbridge is a FastAPI HTTP server that bridges UI database clients to multiple database engines via a unified REST API. Default port: **3695**. Entry point: `python -m dbridge.server.app`.

## Directory Overview

```
src/dbridge/
├── config.py              # Global settings (pydantic-settings, env prefix dbridge_)
├── adapters/
│   ├── interfaces.py      # DBAdapter ABC — all adapters implement this
│   ├── capabilities.py    # CapabilityEnums: USE_DB, USE_SCHEMA
│   └── dbs/
│       ├── models.py      # DbCatalog, SchemaCatalog, INSTALLED_ADAPTERS
│       ├── sqllite.py     # SQLite (core)
│       ├── duckdb.py      # DuckDB (core)
│       ├── mysql.py       # MySQL (optional: pip install dbridge[mysql])
│       ├── postgres.py    # PostgreSQL (optional: pip install dbridge[postgres])
│       └── snowflake.py   # Snowflake (optional: pip install dbridge[snowflake])
├── server/
│   ├── __init__.py        # All FastAPI routes + module-level Connections() instance
│   ├── app.py             # uvicorn.run entry point
│   ├── config.py          # Connections manager, ConnectionParam/Config models, YAML persistence
│   └── caching.py         # In-memory SHA-256 keyed TTL cache (default 120s)
├── scripts/
│   └── extract_table.py   # CLI: parses SQL → prints table name (used for autocomplete)
└── logging/__init__.py    # get_logger() factory with module-level logger cache
tests/
├── adapters/              # sqlite_test.py, duckdb_test.py
└── config_test.py, logging_test.py, server.py
```

## Key Subsystems

### Adapters
- `DBAdapter` (ABC in `adapters/interfaces.py`) defines: `show_columns`, `get_all_columns`, `show_tables_schema_dbs`, `run_query`, `is_single_connection`, `get_capabilities`.
- To add an adapter: implement `DBAdapter`, register in `server/config.py → create_adapter_connection()`, add optional dep to `pyproject.toml`.
- `INSTALLED_ADAPTERS` in `adapters/dbs/models.py` controls what `/adapters` returns.

### Connection Management (`server/config.py`)
- `Connections` holds an in-memory `dict[hash_uri → dict[name → DBAdapter]]`.
- Connection ID format: `md5(adapter + str(connection_config)) + "--" + name` (deterministic).
- On `get_connection`, falls back to loading from YAML if hash not in memory.
- `is_single_connection() = True` (SQLite, DuckDB): all named connections sharing a hash reuse one adapter instance. `False` (MySQL, PostgreSQL, Snowflake): each name gets its own instance.
- Connections are persisted to `~/.config/dbridge/connections_list.yml` (Linux/macOS) or `%APPDATA%\dbridge\connections_list.yml` (Windows).

### Caching (`server/caching.py`)
- Applied to: `GET /get_columns`, `GET /get_all_columns`, `GET /query_table`, `GET /get_dbs_schemas_tables`.
- Not applied to: `POST /run_query` (always live).
- TTL: `dbridge_expiration_seconds` env var (default 120).

### REST API (all routes in `server/__init__.py`)
| Route | Method | Description |
|---|---|---|
| `/adapters` | GET | List installed adapters |
| `/connections` | GET | List persisted connections |
| `/connections` | POST | Register connection → returns `{connection_id, name}` |
| `/get_dbs_schemas_tables` | GET | Full catalog (db → schema → tables) |
| `/get_columns` | GET | Columns for a table |
| `/get_all_columns` | GET | All columns (autocomplete) |
| `/query_table` | GET | `SELECT *` from table (cached) |
| `/run_query` | POST | Arbitrary SQL (not cached) |

## Repo-Specific Patterns

- **src layout**: package lives under `src/dbridge/`, not at root. Tests import `dbridge` directly.
- **Optional adapter imports are unconditional**: `server/config.py` imports `MySqlAdapter`, `PostgresAdapter`, `SnowflakeAdapter` at module level. If optional deps are missing, the server fails to start even if only SQLite/DuckDB is needed.
- **DuckDB uses pandas**: `run_query` returns `fetch_df_chunk(limit).to_dict("records")`. `get_all_columns` returns `"table_name.column_name"` formatted strings.
- **SQLite `run_query` limit**: hardcoded `fetchmany(100)`.
- **`query_table` builds SQL from capabilities**: adapters declare `USE_DB`/`USE_SCHEMA` to control whether `dbname.` or `schema_name.` is prepended.
- **uv scripts**: run `uv run python -m dbridge.server.app` to start the server and `uv run python -m dbridge.scripts.extract_table` for the extract_table helper.

## CI / Release
- Workflow: `.github/workflows/publish-pypi.yml`
- Trigger: any tag push (pattern `*`)
- Steps: build wheel + sdist → publish to TestPyPI → publish to PyPI (trusted publishing) → sign with Sigstore → create GitHub Release
- Tags follow `alpha_X.Y.Z` convention (e.g. `alpha_0.2.10`)

## Environment Variables (prefix `dbridge_`)

| Variable | Default | Description |
|---|---|---|
| `dbridge_logging_level` | `INFO` | Log level |
| `dbridge_host` | `0.0.0.0` | Bind host |
| `dbridge_port` | `3695` | HTTP port |
| `dbridge_expiration_seconds` | `120` | Cache TTL |
| `dbridge_no_cols_fetch` | `1000` | Max columns in DuckDB `get_all_columns` |

## Detailed Documentation

Full documentation is in `.agents/summary/`:
- `index.md` — navigation guide and quick-reference facts
- `architecture.md` — system diagrams and request lifecycle
- `components.md` — per-component details
- `interfaces.md` — full REST API reference
- `data_models.md` — all Pydantic models
- `workflows.md` — process flows and how to add an adapter
- `dependencies.md` — all deps with versions and caveats

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
