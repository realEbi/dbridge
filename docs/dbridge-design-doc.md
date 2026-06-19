# dbridge — Design Document

> **Status:** Draft  
> **Version:** 0.1.0  
> **Author(s):** realEbi  
> **Last Updated:** 19.06.2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [System Architecture](#3-system-architecture)
4. [Transport Layer](#4-transport-layer)
5. [Core Engine](#5-core-engine)
6. [Database Adapter Interface](#6-database-adapter-interface)
7. [Adapter Implementations](#7-adapter-implementations)
8. [Protocol Specification (DSP)](#8-protocol-specification-dsp)
9. [Schema Registry & Caching](#9-schema-registry--caching)
10. [Completion Engine](#10-completion-engine)
11. [ERD Extractor](#11-erd-extractor)
12. [Session Management](#12-session-management)
13. [Configuration](#13-configuration)
14. [Use Cases](#14-use-cases)
15. [Project Structure](#15-project-structure)
16. [Technology Choices](#16-technology-choices)
17. [Testing Strategy](#17-testing-strategy)
18. [Open Questions](#18-open-questions)
19. [Future Work](#19-future-work)

---

## 1. Overview

**dbridge** is a backend service that acts as a universal bridge between database engines and developer-facing clients. It is conceptually similar to DBeaver but designed as a protocol-driven server rather than a monolithic GUI application.

Clients (Neovim plugins, TUI applications, web UIs, CLI tools) connect to dbridge over a well-defined protocol and gain a uniform interface for:

- Executing queries against any supported database
- Browsing schemas, tables, columns, and indexes
- Autocompleting SQL with dialect-aware suggestions
- Extracting Entity-Relationship Diagrams (ERDs)
- Managing multiple simultaneous database connections

The backend is implemented in **Python**, using `asyncio` for concurrency, and exposes a **JSON-RPC 2.0** protocol modeled after the Language Server Protocol (LSP).

---

## 2. Goals & Non-Goals

### Goals

- **Protocol-first**: any client that speaks JSON-RPC 2.0 can integrate with dbridge
- **Adapter-based extensibility**: adding a new database requires only implementing a single abstract class
- **Dialect-aware SQL completion**: completions respect the target database's SQL syntax
- **Streaming results**: large result sets are streamed row-by-row, not buffered in memory
- **Multi-session**: a single server process handles multiple concurrent client sessions
- **LSP-compatible transport**: Neovim and other editors can use dbridge as a language server

### Non-Goals

- dbridge is **not** a query builder or ORM
- dbridge is **not** a migration tool
- dbridge does **not** manage database user permissions
- dbridge does **not** provide a built-in GUI — that is always the client's responsibility
- dbridge does **not** support write-heavy batch operations (bulk load, ETL pipelines)

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTENDS                            │
│   Neovim/Lua      Textual TUI      Web UI      CLI          │
└────────┬──────────────┬───────────────┬──────────┬──────────┘
         │              │               │          │
         └──────────────┴───────────────┴──────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Transport Layer      │
                    │  JSON-RPC 2.0          │
                    │  stdio / socket / TCP  │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │     Core Engine        │
                    │  Session Manager       │
                    │  Query Executor        │
                    │  Schema Registry       │
                    │  Completion Engine     │
                    │  ERD Extractor         │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   DBAdapter (ABC)      │
                    └───────────┬───────────┘
                                │
          ┌──────────┬──────────┼──────────┬──────────┐
     ┌────▼───┐ ┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐
     │ MySQL  │ │DuckDB  │ │Snowflk │ │Postgres│ │SQLite  │
     └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

The architecture separates three concerns cleanly:

| Layer | Responsibility |
|---|---|
| Transport | How frontends talk to dbridge (protocol, serialization, I/O) |
| Core Engine | Business logic: sessions, queries, completions, ERD |
| Adapters | How dbridge talks to each specific database |

---

## 4. Transport Layer

### 4.1 Protocol

dbridge uses **JSON-RPC 2.0** as its wire protocol, extended with server-push notifications — the same model used by LSP. This makes the Neovim frontend trivial to implement using `vim.lsp` utilities, and every other client can implement a thin JSON-RPC client.

Message types:

| Type | Direction | Description |
|---|---|---|
| Request | Client → Server | Calls a named method, expects a response |
| Response | Server → Client | Result or error for a request |
| Notification | Server → Client | Push event (progress, log, schema change) |

### 4.2 Transport Modes

| Mode | Use Case | Notes |
|---|---|---|
| `stdio` | Neovim, CLI tools | Server is a child process; simplest model |
| Unix socket | Local TUI (Textual) | Low latency, same machine only |
| TCP | Remote clients, testing | Enables multi-machine setups |
| WebSocket | Web UI | HTTP upgrade; enables browser clients |

The transport mode is selected at server startup via CLI flag or config. The core engine is completely agnostic to transport.

### 4.3 Message Framing

For stream-based transports (stdio, TCP, Unix socket), messages are framed with an HTTP-style header for compatibility with LSP clients:

```
Content-Length: <byte_length>\r\n
\r\n
<json_payload>
```

---

## 5. Core Engine

The core engine sits between the transport layer and the adapters. It owns:

- **Session lifecycle**: create, track, terminate sessions
- **Query dispatch**: route execute requests to the right adapter, manage cancellation
- **Schema registry**: maintain a cached view of the connected DB's metadata
- **Completion**: parse partial SQL, consult schema registry, return ranked completions
- **ERD**: build a relationship graph from schema metadata

The engine is fully async (`asyncio`) and never blocks the event loop. All adapter calls are `await`-ed.

---

## 6. Database Adapter Interface

All database-specific logic lives behind a single abstract base class. The core engine never imports driver libraries directly.

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass

@dataclass
class ColumnDef:
    name: str
    data_type: str
    nullable: bool
    default: str | None
    comment: str | None

@dataclass
class ForeignKey:
    column: str
    referenced_table: str
    referenced_column: str

@dataclass
class TableSchema:
    name: str
    schema: str
    database: str
    columns: list[ColumnDef]
    primary_keys: list[str]
    foreign_keys: list[ForeignKey]

@dataclass
class QueryResult:
    query_id: str
    columns: list[str]
    rows: AsyncIterator[list]   # streaming
    row_count: int | None       # None if unknown before completion
    execution_time_ms: float
    warnings: list[str]

class DBAdapter(ABC):
    # --- Lifecycle ---
    @abstractmethod
    async def connect(self, config: dict) -> None: ...
    @abstractmethod
    async def disconnect(self) -> None: ...
    @abstractmethod
    async def ping(self) -> bool: ...

    # --- Query ---
    @abstractmethod
    async def execute(self, sql: str, params: list = []) -> QueryResult: ...
    @abstractmethod
    async def cancel(self, query_id: str) -> None: ...
    @abstractmethod
    async def begin(self) -> None: ...
    @abstractmethod
    async def commit(self) -> None: ...
    @abstractmethod
    async def rollback(self) -> None: ...

    # --- Schema introspection ---
    @abstractmethod
    async def list_databases(self) -> list[str]: ...
    @abstractmethod
    async def list_schemas(self, database: str) -> list[str]: ...
    @abstractmethod
    async def list_tables(self, database: str, schema: str) -> list[str]: ...
    @abstractmethod
    async def get_table_schema(self, fqn: str) -> TableSchema: ...
    @abstractmethod
    async def get_function_signatures(self) -> list[str]: ...

    # --- Dialect ---
    @abstractmethod
    def dialect_name(self) -> str: ...
    @abstractmethod
    def get_keywords(self) -> list[str]: ...
```

### Design Principles

- Adapters are **stateless** with respect to sessions — the session manager holds state
- Adapters may maintain an internal **connection pool** (e.g. `asyncpg` pool for Postgres)
- Adapters raise typed exceptions (`AdapterConnectionError`, `AdapterQueryError`) that the engine maps to JSON-RPC error codes
- Adapters declare their **dialect name** so the completion engine can load the correct SQL grammar

---

## 7. Adapter Implementations

### Planned Adapters

| Database | Driver | Notes |
|---|---|---|
| PostgreSQL | `asyncpg` | Async native; full type mapping |
| MySQL / MariaDB | `aiomysql` | Async native |
| SQLite | `aiosqlite` | File-based; useful for local dev/testing |
| DuckDB | `duckdb` (sync, run in executor) | In-process OLAP; wrap with `asyncio.run_in_executor` |
| Snowflake | `snowflake-connector-python` (sync) | Wrap in executor; token auth support |
| BigQuery | `google-cloud-bigquery` (async) | Long-running jobs, polling required |

### Adding a New Adapter

1. Create `dbridge/adapters/<name>.py`
2. Subclass `DBAdapter` and implement all abstract methods
3. Register the adapter in `dbridge/adapters/registry.py` under a string key (e.g. `"duckdb"`)
4. Add integration tests in `tests/adapters/test_<name>.py` using testcontainers (or a local binary for DuckDB/SQLite)

---

## 8. Protocol Specification (DSP)

> **dbridge Server Protocol (DSP)** — version 1.0

### 8.1 Method Namespace

All methods are namespaced under `dbridge/`:

| Method | Direction | Description |
|---|---|---|
| `dbridge/connect` | C→S | Open a named connection profile |
| `dbridge/disconnect` | C→S | Close session |
| `dbridge/execute` | C→S | Run a SQL statement |
| `dbridge/cancel` | C→S | Cancel a running query |
| `dbridge/listDatabases` | C→S | List available databases |
| `dbridge/listSchemas` | C→S | List schemas in a database |
| `dbridge/listTables` | C→S | List tables in a schema |
| `dbridge/getTableSchema` | C→S | Get full schema for a table |
| `dbridge/complete` | C→S | Request SQL completions |
| `dbridge/getERD` | C→S | Get ERD for a set of tables |
| `dbridge/progress` | S→C | Streaming query progress notification |
| `dbridge/logMessage` | S→C | Server log / diagnostic message |

### 8.2 Example: Execute Request

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "dbridge/execute",
  "params": {
    "session_id": "sess-abc123",
    "sql": "SELECT * FROM orders LIMIT 100",
    "stream": true
  }
}
```

### 8.3 Example: Execute Response (streaming)

Progress notifications arrive before the final response:

```json
// notification (no id)
{
  "jsonrpc": "2.0",
  "method": "dbridge/progress",
  "params": {
    "query_id": "qry-001",
    "rows_fetched": 1000,
    "done": false
  }
}

// final response
{
  "jsonrpc": "2.0",
  "id": 42,
  "result": {
    "query_id": "qry-001",
    "columns": ["id", "customer_id", "total"],
    "rows": [...],
    "row_count": 100,
    "execution_time_ms": 42.3
  }
}
```

### 8.4 Error Codes

| Code | Meaning |
|---|---|
| -32700 | Parse error |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32001 | Connection failed |
| -32002 | Query execution error |
| -32003 | Session not found |
| -32004 | Query cancelled |
| -32005 | Adapter not supported |

---

## 9. Schema Registry & Caching

Schema introspection is expensive on remote databases (Snowflake, BigQuery). The registry manages two cache levels:

| Level | Storage | TTL | Scope |
|---|---|---|---|
| Hot | In-process dict | 60s | Per-session, active objects |
| Warm | SQLite on disk (`~/.cache/dbridge/`) | 10min | Shared across sessions |
| Cold | Live DB call | — | Cache miss fallback |

The registry is the single source of truth for the completion engine and the ERD extractor. Both consume it read-only.

Cache invalidation can be triggered explicitly via `dbridge/refreshSchema` or automatically on DDL detection (adapter-specific).

---

## 10. Completion Engine

### 10.1 Approach

SQL completion is context-aware. Given the cursor position within a partial SQL statement, the engine:

1. Tokenizes and partially parses the SQL using **sqlglot** (dialect-aware)
2. Determines the **completion context** (which part of the AST the cursor is in)
3. Queries the **schema registry** for relevant identifiers
4. Returns ranked `CompletionItem` objects

### 10.2 Completion Contexts

| Context | Example | Completions returned |
|---|---|---|
| `SELECT` target | `SELECT cu█` | Column names, `*`, functions |
| `FROM` clause | `FROM █` | Table names, views |
| `JOIN` target | `JOIN █` | Table names, views |
| `JOIN ON` column | `JOIN orders o ON o.█` | Columns of aliased table |
| `WHERE` column | `WHERE █` | Columns of all tables in scope |
| `WHERE` value | `WHERE status = '█'` | Enum/distinct values (if cached) |
| Keyword position | `SEL█` | SQL keywords for current dialect |

### 10.3 CompletionItem Shape

```python
@dataclass
class CompletionItem:
    label: str          # displayed text
    kind: str           # "table" | "column" | "keyword" | "function" | "alias"
    detail: str         # e.g. column data type, table schema
    insert_text: str    # text to insert (may differ from label)
    sort_key: str       # for ranking
```

The `kind` field maps directly to LSP `CompletionItemKind` values, so Neovim renders the correct icon automatically.

---

## 11. ERD Extractor

The ERD extractor builds a directed graph of foreign key relationships from schema metadata.

```python
@dataclass
class ERDNode:
    table: str
    schema: str
    columns: list[ColumnDef]
    primary_keys: list[str]

@dataclass
class ERDEdge:
    from_table: str
    from_column: str
    to_table: str
    to_column: str

@dataclass
class ERDGraph:
    nodes: dict[str, ERDNode]
    edges: list[ERDEdge]

    def to_mermaid(self) -> str: ...
    def to_dot(self) -> str: ...         # Graphviz
    def to_json(self) -> dict: ...       # for JS rendering (d3, mxGraph)
```

The client specifies which tables to include. The extractor can optionally **expand** the graph by following FK chains to related tables.

---

## 12. Session Management

Each connected client maps to a `Session`:

```python
@dataclass
class Session:
    id: str                              # UUID
    adapter: DBAdapter
    active_database: str
    active_schema: str
    query_history: deque[QueryRecord]    # last N queries
    running_queries: dict[str, Task]     # query_id → asyncio.Task
    schema_cache: SchemaCache            # session-local TTL cache
    transaction_state: TransactionState  # IDLE | IN_TRANSACTION | FAILED
    created_at: datetime
    last_active_at: datetime
```

A single dbridge server process holds multiple named sessions. Sessions are cleaned up after a configurable idle timeout.

---

## 13. Configuration

Connection profiles are stored in `~/.config/dbridge/connections.toml`:

```toml
[connections.local_pg]
adapter = "postgres"
host = "localhost"
port = 5432
database = "mydb"
user = "me"

[connections.analytics]
adapter = "duckdb"
path = "/data/analytics.duckdb"

[connections.warehouse]
adapter = "snowflake"
account = "myorg.us-east-1"
user = "ebi"
auth = "browser"   # or "password" | "key_pair"
warehouse = "COMPUTE_WH"
database = "PROD"
```

Server settings go in `~/.config/dbridge/settings.toml`:

```toml
[server]
transport = "stdio"       # stdio | socket | tcp
socket_path = "/tmp/dbridge.sock"
port = 9876               # for tcp transport
log_level = "info"

[cache]
ttl_hot_seconds = 60
ttl_warm_seconds = 600
cache_dir = "~/.cache/dbridge"

[session]
idle_timeout_seconds = 1800
max_query_history = 200
```

---

## 14. Use Cases

### UC1: Connect and Browse Schema (Neovim)

```
Neovim plugin                 dbridge                      DuckDB
     │                            │                           │
     │─── dbridge/connect ───────>│                           │
     │    {profile: "analytics"}  │── adapter.connect() ─────>│
     │                            │<─────────────────────────-│
     │<── {session_id: "abc"} ────│                           │
     │                            │                           │
     │─── dbridge/listTables ────>│                           │
     │                            │── schema_registry.get() ->│ (or cache)
     │<── {tables: ["orders"...]} │                           │
```

### UC2: SQL Autocomplete

```
Neovim (insert mode)          dbridge                     Schema Registry
     │                            │                           │
     │  user types: "SELECT cu"   │                           │
     │─── dbridge/complete ──────>│                           │
     │    {sql: "SELECT cu",      │── registry.get_cols() ───>│
     │     cursor: 9,             │<── [customer_id, ...]  ───│
     │     session_id: "abc"}     │                           │
     │<── {items: [               │                           │
     │      {label:"customer_id", │                           │
     │       kind:"column",       │                           │
     │       detail:"VARCHAR"}    │                           │
     │    ]} ─────────────────────│                           │
```

### UC3: Streaming Query Execution

```
Client                        dbridge                      Postgres
  │                               │                            │
  │─── dbridge/execute ──────────>│                            │
  │    {sql: "SELECT * FROM       │── cursor.fetchmany() ─────>│
  │     events", stream: true}    │<── [batch 1: 1000 rows] ───│
  │<── dbridge/progress ──────────│                            │
  │    {rows_fetched: 1000}       │── cursor.fetchmany() ─────>│
  │<── dbridge/progress ──────────│<── [batch 2: 1000 rows] ───│
  │    {rows_fetched: 2000}       │                            │
  │        ...                    │── cursor.fetchmany() ─────>│
  │<── result {total: 52000} ─────│<── [] (done) ──────────────│
```

### UC4: ERD Extraction

```
Client                        dbridge
  │                               │
  │─── dbridge/getERD ───────────>│
  │    {tables: ["orders",        │── schema_registry.get_schema(each table)
  │     "customers", "products"], │── erd_extractor.build_graph()
  │     format: "mermaid"}        │
  │<── {content: "erDiagram\n     │
  │     orders ||--o{ customers"} │
```

### UC5: Multi-DB Power User (Textual TUI)

A single dbridge server holds two simultaneous sessions — one for a production Postgres DB and one for a local DuckDB file. The TUI shows split panes, each bound to a different session, with separate query history and transaction state.

### UC6: Cancel Long-Running Query

```
Client                        dbridge                      Snowflake
  │                               │                            │
  │─── dbridge/execute ──────────>│── long query running ─────>│
  │    {query_id: "qry-007"}      │                            │
  │   (10 seconds pass)           │                            │
  │─── dbridge/cancel ───────────>│                            │
  │    {query_id: "qry-007"}      │── adapter.cancel() ───────>│
  │<── {cancelled: true} ─────────│<── query killed ───────────│
```

---

## 15. Project Structure

```
dbridge/
├── dbridge/
│   ├── __init__.py
│   ├── server.py                  # Entry point; wires transport → engine
│   ├── protocol/
│   │   ├── messages.py            # Pydantic models for all JSON-RPC messages
│   │   ├── handlers.py            # Method dispatch: method name → handler fn
│   │   ├── errors.py              # DSP error codes and exception mapping
│   │   └── transport/
│   │       ├── base.py            # Transport ABC
│   │       ├── stdio.py
│   │       ├── socket.py
│   │       └── websocket.py
│   ├── core/
│   │   ├── engine.py              # Wires together all core subsystems
│   │   ├── session.py             # Session dataclass + manager
│   │   ├── executor.py            # Async query dispatch + cancellation
│   │   ├── completion.py          # SQL parser + completion logic
│   │   ├── erd.py                 # ERD graph builder + formatters
│   │   └── schema_registry.py     # Two-level cache + introspection
│   ├── adapters/
│   │   ├── base.py                # DBAdapter ABC + shared types
│   │   ├── registry.py            # str → adapter class mapping
│   │   ├── postgres.py
│   │   ├── mysql.py
│   │   ├── sqlite.py
│   │   ├── duckdb.py
│   │   └── snowflake.py
│   └── config/
│       ├── connections.py         # Connection profile loader
│       └── settings.py            # Server settings loader
├── tests/
│   ├── conftest.py
│   ├── adapters/
│   │   ├── test_postgres.py       # Integration (testcontainers)
│   │   ├── test_mysql.py
│   │   ├── test_duckdb.py
│   │   └── test_sqlite.py
│   ├── core/
│   │   ├── test_completion.py
│   │   ├── test_erd.py
│   │   └── test_session.py
│   └── protocol/
│       └── test_handlers.py
├── clients/
│   └── neovim/                    # Lua plugin lives here
│       ├── lua/dbridge/
│       │   ├── init.lua
│       │   ├── client.lua         # JSON-RPC transport (stdio)
│       │   ├── completion.lua     # nvim-cmp source
│       │   └── ui.lua             # Result pane, ERD float
│       └── plugin/dbridge.lua
├── docs/
│   ├── DESIGN.md                  # This document
│   ├── PROTOCOL.md                # Full DSP specification
│   └── ADAPTERS.md                # Guide for writing new adapters
├── pyproject.toml
├── README.md
└── CHANGELOG.md
```

---

## 16. Technology Choices

| Concern | Choice | Rationale |
|---|---|---|
| Async runtime | `asyncio` + `anyio` | Compatible with all async DB drivers |
| Message validation | `pydantic v2` | Fast validation; auto-generates JSON Schema for protocol docs |
| SQL parsing / completion | `sqlglot` | Multi-dialect; tolerates partial / invalid SQL |
| Config format | TOML + `pydantic-settings` | Human-friendly; standard in Python tooling |
| Schema cache (warm) | `diskcache` or SQLite | Zero infrastructure; fast enough for metadata |
| Logging | `structlog` | Structured JSON logs; easy to grep |
| Testing | `pytest-asyncio` + `testcontainers` | Real DB integration tests in CI |
| Packaging | `uv` + `pyproject.toml` | Fast installs; modern Python tooling |

---

## 17. Testing Strategy

### Unit Tests

- Completion engine: given partial SQL + mock schema, assert correct completions
- ERD builder: given mock `TableSchema` objects, assert correct graph edges
- Session manager: lifecycle, idle timeout, query cancellation

### Integration Tests

- Each adapter has a test suite that spins up a real database (via testcontainers or local binary)
- Tests cover: connect, execute (simple + streaming), schema introspection, cancel
- DuckDB and SQLite tests run without containers (in-process / in-memory)

### Protocol Tests

- JSON-RPC handler dispatch: valid requests, malformed requests, unknown methods
- Error mapping: adapter exceptions → correct DSP error codes

### End-to-End

- Start server in stdio mode as subprocess
- Python client sends JSON-RPC messages over stdin/stdout
- Assert correct responses for connect → list tables → execute → disconnect flow

---

## 18. Open Questions

| # | Question | Owner | Priority |
|---|---|---|---|
| 1 | Should the server support multiple transport modes simultaneously, or one per process? | — | High |
| 2 | How should we handle very large result sets — client-side pagination or server-side cursors? | — | High |
| 3 | Should connection profiles support secret managers (e.g. AWS Secrets Manager, 1Password CLI)? | — | Medium |
| 4 | What is the right TTL strategy for Snowflake schema cache (introspection is very slow)? | — | Medium |
| 5 | Should the ERD extractor follow FK chains automatically, or always require explicit table list? | — | Low |
| 6 | Do we want a plugin system for custom completion providers (e.g. dbt model awareness)? | — | Low |
| 7 | What authentication model does the WebSocket transport need? | — | Medium |

---

## 19. Future Work

- **dbt integration**: resolve `{{ ref(...) }}` and `{{ source(...) }}` in SQL completion
- **Query history persistence**: store history to SQLite, searchable across sessions
- **EXPLAIN visualization**: parse `EXPLAIN` output and return a structured plan tree
- **SSH tunneling**: built-in support for DB connections through an SSH jump host
- **Notebook mode**: multi-statement execution with per-statement result blocks
- **Web UI client**: React/TypeScript frontend connecting over WebSocket
- **VS Code extension**: same protocol, different client
- **Telemetry / observability**: OpenTelemetry traces for query execution spans
