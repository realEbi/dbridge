# Architecture: dbridge

## Overview

dbridge is a single-process HTTP API server that acts as a bridge between UI database clients and multiple database engines. It exposes a unified REST API so clients never need to know which database they are talking to.

## High-Level Architecture

```mermaid
graph TB
    subgraph Clients
        A[dbridge.nvim]
        B[dbridge.tui]
        C[Any HTTP client]
    end

    subgraph dbridge Server
        D[FastAPI app\nsrc/dbridge/server/__init__.py]
        E[Connections manager\nserver/config.py]
        F[TTL Cache\nserver/caching.py]
        G[ServiceConfig\nserver/config.py]
    end

    subgraph Adapters
        H[DBAdapter ABC\nadapters/interfaces.py]
        I[SqliteAdapter]
        J[DuckdbAdapter]
        K[MySqlAdapter]
        L[PostgresAdapter]
        M[SnowflakeAdapter]
    end

    subgraph Storage
        N[In-memory dict\nconnections]
        O[YAML file\nconnections_list.yml]
        P[Database files / servers]
    end

    A & B & C -->|HTTP REST| D
    D --> E
    D --> F
    E --> G
    E --> N
    G --> O
    E --> H
    H --> I & J & K & L & M
    I & J --> P
    K & L & M --> P
```

## Layered Design

```mermaid
graph LR
    A[HTTP Layer\nFastAPI routes] --> B[Service Layer\nConnections + Cache]
    B --> C[Adapter Layer\nDBAdapter implementations]
    C --> D[Database Layer\nSQLite / DuckDB / MySQL / Postgres / Snowflake]
    E[Config Layer\npydantic-settings] -.->|settings| A & B & C
```

## Request Lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Cache
    participant Connections
    participant DBAdapter
    participant Database

    Client->>FastAPI: GET /get_dbs_schemas_tables?connection_id=...
    FastAPI->>Cache: check cache key
    alt cache hit and not expired
        Cache-->>FastAPI: cached result
    else cache miss or expired
        FastAPI->>Connections: get_connection(connection_id)
        Connections-->>FastAPI: DBAdapter instance
        FastAPI->>DBAdapter: show_tables_schema_dbs()
        DBAdapter->>Database: SQL query
        Database-->>DBAdapter: rows
        DBAdapter-->>FastAPI: list[DbCatalog]
        FastAPI->>Cache: store result with timestamp
    end
    FastAPI-->>Client: JSON response
```

## Connection Identity

Connection IDs are deterministic: `md5(adapter + connection_config) + "--" + connection_name`. This means the same physical connection config always maps to the same hash, enabling connection reuse across requests.

## Single vs Multi Connection

Adapters declare `is_single_connection()`:
- **True** (SQLite, DuckDB): all named connections sharing the same hash reuse the same underlying connection object.
- **False** (MySQL, PostgreSQL, Snowflake): each named connection gets its own connection object, enabling concurrent queries.

## Deployment

The server is started via `python -m dbridge.server.app`, which calls `uvicorn.run(app, host=settings.host, port=settings.port)`. Default port is **3695**.
