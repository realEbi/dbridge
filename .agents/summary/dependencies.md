# Dependencies: dbridge

## Runtime Dependencies (always installed)

| Package | Version | Used for |
|---|---|---|
| `fastapi` | 0.115.6 | HTTP framework, route definitions, request/response models |
| `uvicorn` | 0.34.0 | ASGI server, runs the FastAPI app |
| `pydantic` | 2.10.4 | Data models (`BaseModel`), validation, serialization |
| `pydantic-settings` | 2.7.0 | `Settings` and `ServiceConfig` from env vars |
| `duckdb` | 1.1.3 | DuckDB adapter (also a core adapter) |
| `pandas` | 2.2.3 | DuckDB result processing (`fetch_df`, `fetch_df_chunk`) |
| `numpy` | 2.2.1 | Transitive dep of pandas |
| `pyyaml` | 6.0.2 | Persisting/loading connections list YAML |
| `sqlparse` | 0.5.3 | `extract_table.py` script — SQL parsing |

## Optional Dependencies

| Extra | Package | Adapter |
|---|---|---|
| `dbridge[mysql]` | `pymysql` | `MySqlAdapter` |
| `dbridge[postgres]` | `psycopg2` | `PostgresAdapter` |
| `dbridge[snowflake]` | `snowflake-connector-python` | `SnowflakeAdapter` |

SQLite is provided by Python's stdlib (`sqlite3`) — no extra install needed.

## Development Dependencies (hatch `dev` env)

| Package | Purpose |
|---|---|
| `ruff` | Linting |
| `black` | Formatting |
| `isort` | Import sorting |
| `pyright` | Static type checking |
| `pytest` | Test runner |
| `ipython` | Interactive development |
| `mysql-connector-python` | MySQL dev/test |

## Test Dependencies (hatch `test` env)

| Package | Purpose |
|---|---|
| `pytest` | Test runner |
| `pytest-cov` | Coverage reporting |
| `pytest-mock` | Mocking |
| `coverage[toml]` | Coverage config via pyproject.toml |

## Type Checking (hatch `types` env)

| Package | Purpose |
|---|---|
| `mypy` | Static type checking |

## Build System

| Tool | Role |
|---|---|
| `hatchling` | Build backend (PEP 517) |
| `hatch` | Project manager, env manager, version management |

Version is read dynamically from `src/dbridge/__about__.py` via `[tool.hatch.version]`.

## Dependency Notes

- `pandas` and `numpy` are heavy deps pulled in solely for DuckDB result processing (`fetch_df_chunk`). If DuckDB is not used, these are still installed.
- `duckdb` is a core dep even though it's an optional database — it ships as a built-in adapter.
- Optional adapters (`mysql`, `postgres`, `snowflake`) are imported at the top of `server/config.py` unconditionally. If the package is not installed, importing the server will raise an `ImportError` unless the optional dep is installed.
