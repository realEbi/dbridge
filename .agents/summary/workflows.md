# Workflows: dbridge

## 1. Server Startup

```mermaid
sequenceDiagram
    participant User
    participant app.py
    participant Settings
    participant ServiceConfig
    participant FastAPI

    User->>app.py: python -m dbridge.server.app
    app.py->>Settings: load from env (dbridge_*)
    app.py->>ServiceConfig: init → mkdir data_path, touch YAML
    app.py->>FastAPI: instantiate app + Connections()
    app.py->>app.py: uvicorn.run(app, host, port=3695)
    FastAPI-->>User: server ready
```

---

## 2. Creating a Connection

```mermaid
sequenceDiagram
    participant Client
    participant POST /connections
    participant Connections
    participant YAML

    Client->>POST /connections: {adapter, connection_config, name}
    POST /connections->>YAML: add_connection(ConnectionConfig)
    note over YAML: skips if already present
    POST /connections->>Connections: set_connection(params)
    note over Connections: creates DBAdapter, stores in memory dict
    POST /connections-->>Client: {connection_id, name}
```

The `connection_id` is deterministic — calling POST again with the same config returns the same ID without creating a duplicate.

---

## 3. Executing a Cached Query

```mermaid
sequenceDiagram
    participant Client
    participant Route Handler
    participant cache_value()
    participant Connections
    participant DBAdapter

    Client->>Route Handler: GET /get_dbs_schemas_tables?connection_id=...
    Route Handler->>cache_value(): lambda + cache key args
    cache_value()->>cache_value(): sha256(args) → lookup in cache dict
    alt hit and age < 120s
        cache_value()-->>Route Handler: cached result
    else miss or expired
        cache_value()->>Connections: get_connection(connection_id)
        Connections-->>cache_value(): DBAdapter
        cache_value()->>DBAdapter: show_tables_schema_dbs()
        DBAdapter-->>cache_value(): list[DbCatalog]
        cache_value()->>cache_value(): store (result, now) in cache
        cache_value()-->>Route Handler: result
    end
    Route Handler-->>Client: JSON
```

---

## 4. Running an Arbitrary Query (not cached)

```mermaid
sequenceDiagram
    participant Client
    participant POST /run_query
    participant Connections
    participant DBAdapter

    Client->>POST /run_query: {connection_id, query, connection_name?}
    POST /run_query->>Connections: get_connection(connection_id, connection_name)
    note over Connections: may load from YAML if not in memory
    Connections-->>POST /run_query: DBAdapter
    POST /run_query->>DBAdapter: run_query(query)
    DBAdapter-->>POST /run_query: list[dict]
    POST /run_query-->>Client: JSON rows
```

---

## 5. Connection Lookup (Connections.get_connection)

```mermaid
flowchart TD
    A[get_connection called] --> B{hash in memory?}
    B -- yes --> C{name in sub-dict?}
    C -- yes --> D[return existing adapter]
    C -- no --> E[_create_new_connection]
    E --> F{is_single_connection?}
    F -- yes --> G[return first adapter]
    F -- no --> H[create new adapter instance]
    B -- no --> I[load YAML connections]
    I --> J{matching hash found?}
    J -- yes --> K[create adapter, store in memory]
    J -- no --> L[return None]
```

---

## 6. Adding a New Database Adapter

To add a new adapter:

1. Create `src/dbridge/adapters/dbs/<name>.py` implementing `DBAdapter`.
2. Implement all abstract methods: `show_columns`, `get_all_columns`, `show_tables_schema_dbs`, `run_query`, `is_single_connection`.
3. Optionally override `get_capabilities()` to return `USE_DB` / `USE_SCHEMA`.
4. Register in `server/config.py` → `create_adapter_connection()` factory function.
5. Add optional dep to `pyproject.toml` under `[project.optional-dependencies]`.
6. Add adapter name to `INSTALLED_ADAPTERS` in `adapters/dbs/models.py` if it should be a core dep.

---

## 7. CI / Release Workflow

```mermaid
flowchart LR
    A[git push tag] --> B[GitHub Actions: publish-pypi.yml]
    B --> C[build wheel + sdist]
    C --> D[publish to TestPyPI]
    C --> E[publish to PyPI\nvia trusted publishing]
    E --> F[sign with Sigstore]
    F --> G[create GitHub Release\nwith signed artifacts]
```

Tags follow the pattern `alpha_X.Y.Z` (e.g. `alpha_0.2.10`). Any tag push triggers the workflow.
