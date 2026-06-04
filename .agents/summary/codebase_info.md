# Codebase Info: dbridge

## Project Identity
- **Name**: dbridge
- **Language**: Python (3.11+)
- **Type**: HTTP API server (library + server)
- **License**: MIT
- **PyPI**: `pip install dbridge`
- **Entry point**: `python -m dbridge.server.app`

## Directory Layout

```
dbridge/
├── src/dbridge/               # Main package (src layout)
│   ├── __init__.py
│   ├── __about__.py           # Version string
│   ├── config.py              # Global settings (pydantic-settings)
│   ├── adapters/
│   │   ├── interfaces.py      # DBAdapter abstract base class
│   │   ├── capabilities.py    # CapabilityEnums (USE_DB, USE_SCHEMA)
│   │   └── dbs/
│   │       ├── models.py      # DbCatalog, SchemaCatalog, INSTALLED_ADAPTERS
│   │       ├── sqllite.py     # SQLite adapter
│   │       ├── duckdb.py      # DuckDB adapter
│   │       ├── mysql.py       # MySQL adapter
│   │       ├── postgres.py    # PostgreSQL adapter
│   │       └── snowflake.py   # Snowflake adapter
│   ├── server/
│   │   ├── __init__.py        # FastAPI app + all route handlers
│   │   ├── app.py             # Uvicorn entry point
│   │   ├── config.py          # Connection management + persistence
│   │   └── caching.py         # In-memory TTL cache
│   ├── scripts/
│   │   └── extract_table.py   # SQL parsing utility (sqlparse)
│   ├── logging/
│   │   └── __init__.py        # Logger factory (get_logger)
│   ├── exceptions/            # Reserved (empty)
│   └── output_formatters/     # Reserved (empty)
├── tests/
│   ├── adapters/
│   │   ├── sqlite_test.py
│   │   └── duckdb_test.py
│   ├── config_test.py
│   ├── logging_test.py
│   └── server.py
├── pyproject.toml             # Hatch build, deps, envs
└── .github/workflows/
    └── publish-pypi.yml       # CI: build + publish on tag push
```

## Technology Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI 0.115 |
| ASGI server | Uvicorn 0.34 |
| Settings | pydantic-settings 2.7 |
| Data models | Pydantic 2.10 |
| Data processing | pandas 2.2, numpy 2.2 |
| SQL parsing | sqlparse 0.5 |
| Config persistence | PyYAML 6.0 |
| Build tool | Hatch |

## Database Adapters

| Adapter | Install | Single connection |
|---|---|---|
| SQLite | core | yes |
| DuckDB | core | yes |
| MySQL | `pip install dbridge[mysql]` | no |
| PostgreSQL | `pip install dbridge[postgres]` | no |
| Snowflake | `pip install dbridge[snowflake]` | no |

## Configuration (env vars, prefix `dbridge_`)

| Variable | Default | Description |
|---|---|---|
| `dbridge_logging_level` | `INFO` | Log level |
| `dbridge_host` | `0.0.0.0` | Server bind host |
| `dbridge_port` | `3695` | Server port |
| `dbridge_expiration_seconds` | `120` | Cache TTL |
| `dbridge_no_cols_fetch` | `1000` | Max columns fetched |

## Persistent Storage
Connections are persisted to `~/.config/dbridge/connections_list.yml` (Linux/macOS) or `%APPDATA%\dbridge\connections_list.yml` (Windows).
