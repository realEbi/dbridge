# dbridge Phase 1 Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Note:** Per the project owner, this plan does **not** use TDD. Each task implements code first, then adds/runs verification, then commits.

**Goal:** Restructure dbridge from a synchronous FastAPI REST server into a three-layer (Transport / Core Engine / Adapters) JSON-RPC server speaking over stdio, targeting Neovim.

**Architecture:** A synchronous core engine sits behind a transport-agnostic boundary. The only Phase 1 transport is stdio using LSP-style `Content-Length` framing and JSON-RPC 2.0. The core engine owns a SessionManager, a thin query executor, a hot-only in-memory schema registry, a tier-1 SQL completion engine, and a placeholder ERD module. Adapters (sqlite, duckdb only) implement a single ABC; the engine never imports a driver directly.

**Tech Stack:** Python 3.11+, pydantic v2, sqlglot, duckdb, sqlite3 (stdlib), tomllib (stdlib), pytest. Packaging via uv. src layout (`src/dbridge/`).

## Global Constraints

- Package lives under `src/dbridge/` (src layout retained; do not move to repo root).
- Synchronous only — no `asyncio`, no `async def`, no `AsyncIterator` (see `docs/adr/0001-sync-core-for-phase-1.md`).
- No streaming, no query cancellation, no transactions in Phase 1.
- Core engine modules must never `import duckdb`, `import sqlite3`, or any driver — only adapters may.
- JSON-RPC 2.0 with method namespace `dbridge/`. Framing: `Content-Length: <n>\r\n\r\n<utf-8 json>`.
- DSP error codes: `-32700` parse, `-32600` invalid request, `-32601` method not found, `-32001` connection failed, `-32002` query error, `-32003` session not found, `-32005` adapter not supported.
- Adapters ported in Phase 1: **sqlite, duckdb only**. mysql/postgres/snowflake source stays on disk but is NOT registered and NOT imported at module load.
- Connection profiles persist to `connections.toml`; server settings read from env vars (prefix `dbridge_`).
- Result rows are materialized and capped (default 100, env `dbridge_max_rows`); truncation surfaced via `QueryResult.warnings`.
- `dbridge/getERD` is a placeholder that returns a structured "not implemented" payload, never crashes.
- Run all commands with `uv run` (e.g. `uv run pytest`).

---

## File Structure

```
src/dbridge/
├── __init__.py
├── server.py                      # entry point: build engine, run stdio transport
├── protocol/
│   ├── __init__.py
│   ├── messages.py                # pydantic JSON-RPC + DSP param/result models
│   ├── errors.py                  # DspError + error codes
│   ├── handlers.py                # method-name → handler dispatch over the engine
│   └── transport/
│       ├── __init__.py
│       ├── base.py                # Transport ABC
│       └── stdio.py               # Content-Length framed stdio loop
├── core/
│   ├── __init__.py
│   ├── engine.py                  # Engine: owns SessionManager + registry + completion + erd
│   ├── session.py                 # Session + SessionManager
│   ├── executor.py                # execute(): timing + row cap + truncation warning
│   ├── schema_registry.py         # hot TTL cache over adapter introspection
│   ├── completion.py              # tier-1 SQL completion (absorbs extract_table.py)
│   └── erd.py                     # placeholder
├── adapters/
│   ├── __init__.py
│   ├── base.py                    # DBAdapter ABC + dataclasses
│   ├── registry.py                # adapter_name → class (sqlite, duckdb)
│   ├── sqlite.py                  # ported
│   ├── duckdb.py                  # ported
│   └── _parked/                   # mysql.py, postgres.py, snowflake.py (not imported)
├── config/
│   ├── __init__.py
│   ├── connections.py             # connections.toml loader/writer
│   └── settings.py                # env-var settings (pydantic-settings)
└── logging/__init__.py            # unchanged (get_logger)

tests/
├── conftest.py
├── adapters/
│   ├── test_sqlite.py
│   └── test_duckdb.py
├── core/
│   ├── test_session.py
│   ├── test_schema_registry.py
│   └── test_completion.py
├── protocol/
│   └── test_framing.py
└── test_e2e_stdio.py              # spawn server.py subprocess, drive over stdin/stdout
```

**Removed:** `src/dbridge/server/__init__.py` (FastAPI routes), `server/app.py`, `server/config.py`, `server/caching.py`, `scripts/extract_table.py` (logic absorbed into `core/completion.py`). `config.py` is replaced by the `config/` package.

---

## Task 1: Layer skeleton & FastAPI teardown

**Files:**
- Create: `src/dbridge/core/__init__.py`, `src/dbridge/protocol/__init__.py`, `src/dbridge/protocol/transport/__init__.py`, `src/dbridge/config/__init__.py`
- Create: `src/dbridge/adapters/_parked/__init__.py`
- Move: `src/dbridge/adapters/dbs/mysql.py` → `src/dbridge/adapters/_parked/mysql.py` (same for `postgres.py`, `snowflake.py`)
- Delete: `src/dbridge/server/` (whole dir), `src/dbridge/scripts/extract_table.py`, `src/dbridge/config.py`, `src/dbridge/server/caching.py`
- Modify: `pyproject.toml` (drop FastAPI/uvicorn deps and the server entry point; add `sqlglot` if absent)
- Modify: `src/dbridge/adapters/dbs/__init__.py` (stop re-exporting parked adapters)

**Interfaces:**
- Produces: empty package dirs that later tasks fill. No public API yet.

- [ ] **Step 1: Create the new package directories** with empty `__init__.py` files at the paths listed above.

- [ ] **Step 2: Move parked adapters.** `git mv src/dbridge/adapters/dbs/mysql.py src/dbridge/adapters/_parked/mysql.py` and likewise for postgres, snowflake. These files will not import or be imported until a later phase; leave their content untouched.

- [ ] **Step 3: Delete FastAPI surface.** `git rm -r src/dbridge/server` and `git rm src/dbridge/scripts/extract_table.py`. Keep `src/dbridge/logging/` and `src/dbridge/exceptions/`.

- [ ] **Step 4: Replace `config.py`.** `git rm src/dbridge/config.py`. (Constants like `NO_COLS_FETCH` move to `config/settings.py` in Task 11; for now nothing imports it because adapters are rewritten in Tasks 9–10.)

- [ ] **Step 5: Update `pyproject.toml`.** Remove `fastapi` and `uvicorn` from dependencies. Ensure `sqlglot` and `pydantic>=2` are present. Remove any `[project.scripts]` entry pointing at the old server; leave the package installable.

- [ ] **Step 6: Verify the tree compiles.** Run: `uv run python -c "import dbridge"`
  Expected: no ImportError. (It is fine that most subpackages are empty.)

- [ ] **Step 7: Commit.**
```bash
git add -A
git commit -m "refactor: tear down FastAPI server, scaffold three-layer package skeleton"
```

---

## Task 2: Adapter base — dataclasses & ABC

**Files:**
- Create: `src/dbridge/adapters/base.py`

**Interfaces:**
- Produces:
  - `@dataclass ColumnDef(name: str, data_type: str, nullable: bool, default: str | None, comment: str | None)`
  - `@dataclass ForeignKey(column: str, referenced_table: str, referenced_column: str)`
  - `@dataclass TableSchema(name: str, schema: str | None, database: str | None, columns: list[ColumnDef], primary_keys: list[str], foreign_keys: list[ForeignKey])`
  - `@dataclass QueryResult(columns: list[str], rows: list[list], row_count: int, execution_time_ms: float, warnings: list[str])`
  - `class DBAdapter(ABC)` with `adapter_name: str` and abstract methods: `connect()`, `disconnect()`, `execute(sql) -> QueryResult`, `list_databases() -> list[str]`, `list_schemas(database) -> list[str]`, `list_tables(database, schema) -> list[str]`, `get_table_schema(fqn) -> TableSchema`, `dialect_name() -> str`, `get_keywords() -> list[str]`.

- [ ] **Step 1: Write `base.py`.**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from dbridge.logging import get_logger


@dataclass
class ColumnDef:
    name: str
    data_type: str
    nullable: bool = True
    default: str | None = None
    comment: str | None = None


@dataclass
class ForeignKey:
    column: str
    referenced_table: str
    referenced_column: str


@dataclass
class TableSchema:
    name: str
    schema: str | None
    database: str | None
    columns: list[ColumnDef] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    row_count: int
    execution_time_ms: float
    warnings: list[str] = field(default_factory=list)


class DBAdapter(ABC):
    adapter_name: str

    def __init__(self, config: dict[str, str]) -> None:
        self.logger = get_logger()
        self.config = config

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def execute(self, sql: str) -> QueryResult: ...

    @abstractmethod
    def list_databases(self) -> list[str]: ...

    @abstractmethod
    def list_schemas(self, database: str | None = None) -> list[str]: ...

    @abstractmethod
    def list_tables(self, database: str | None = None, schema: str | None = None) -> list[str]: ...

    @abstractmethod
    def get_table_schema(self, fqn: str) -> TableSchema: ...

    @abstractmethod
    def dialect_name(self) -> str: ...

    @abstractmethod
    def get_keywords(self) -> list[str]: ...
```

- [ ] **Step 2: Verify import.** Run: `uv run python -c "from dbridge.adapters.base import DBAdapter, QueryResult, TableSchema, ColumnDef, ForeignKey"`
  Expected: no error.

- [ ] **Step 3: Commit.**
```bash
git add src/dbridge/adapters/base.py
git commit -m "feat: add DBAdapter ABC and core adapter dataclasses"
```

---

## Task 3: Adapter exceptions

**Files:**
- Modify: `src/dbridge/exceptions/__init__.py`

**Interfaces:**
- Produces: `AdapterError`, `AdapterConnectionError(AdapterError)`, `AdapterQueryError(AdapterError)`.

- [ ] **Step 1: Add exception classes** to `src/dbridge/exceptions/__init__.py`:
```python
class AdapterError(Exception):
    """Base for adapter-raised errors."""


class AdapterConnectionError(AdapterError):
    """Raised when an adapter cannot connect."""


class AdapterQueryError(AdapterError):
    """Raised when query execution fails inside an adapter."""
```

- [ ] **Step 2: Verify.** Run: `uv run python -c "from dbridge.exceptions import AdapterConnectionError, AdapterQueryError"`
  Expected: no error.

- [ ] **Step 3: Commit.**
```bash
git add src/dbridge/exceptions/__init__.py
git commit -m "feat: add typed adapter exceptions"
```

---

## Task 4: SQLite adapter (ported)

**Files:**
- Create: `src/dbridge/adapters/sqlite.py`
- Test: `tests/adapters/test_sqlite.py`

**Interfaces:**
- Consumes: `DBAdapter`, `QueryResult`, `TableSchema`, `ColumnDef`, `ForeignKey` from `adapters/base.py`; `AdapterConnectionError`, `AdapterQueryError`.
- Produces: `class SqliteAdapter(DBAdapter)` with `adapter_name = "sqlite"`. Config key: `uri` (file path or `:memory:`).

- [ ] **Step 1: Implement `sqlite.py`.**
```python
import sqlite3
import time

from dbridge.adapters.base import ColumnDef, DBAdapter, ForeignKey, QueryResult, TableSchema
from dbridge.exceptions import AdapterConnectionError, AdapterQueryError

# A small dialect keyword set is enough for tier-1 completion.
_SQLITE_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "INNER", "OUTER", "ON", "GROUP",
    "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "INSERT", "INTO", "VALUES",
    "UPDATE", "SET", "DELETE", "CREATE", "TABLE", "DROP", "DISTINCT", "AS",
    "AND", "OR", "NOT", "NULL", "IS", "IN", "LIKE", "BETWEEN", "UNION", "ALL",
]


class SqliteAdapter(DBAdapter):
    adapter_name = "sqlite"

    def __init__(self, config: dict[str, str]) -> None:
        super().__init__(config)
        self.uri = self.config.get("uri")
        if not self.uri:
            raise AdapterConnectionError("sqlite adapter requires a 'uri' config key")
        self.con: sqlite3.Connection | None = None

    def connect(self) -> None:
        try:
            self.con = sqlite3.connect(self.uri)
        except sqlite3.Error as e:
            raise AdapterConnectionError(str(e)) from e

    def disconnect(self) -> None:
        if self.con is not None:
            self.con.close()
            self.con = None

    def _cur(self) -> sqlite3.Cursor:
        assert self.con is not None, "adapter not connected"
        return self.con.cursor()

    def execute(self, sql: str) -> QueryResult:
        start = time.perf_counter()
        try:
            cur = self._cur()
            cur.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
        except sqlite3.Error as e:
            raise AdapterQueryError(str(e)) from e
        elapsed = (time.perf_counter() - start) * 1000
        return QueryResult(columns=columns, rows=rows, row_count=len(rows),
                           execution_time_ms=elapsed, warnings=[])

    def list_databases(self) -> list[str]:
        # SQLite has a single database namespace.
        return ["main"]

    def list_schemas(self, database: str | None = None) -> list[str]:
        return ["main"]

    def list_tables(self, database: str | None = None, schema: str | None = None) -> list[str]:
        cur = self._cur()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [r[0] for r in cur.fetchall()]

    def get_table_schema(self, fqn: str) -> TableSchema:
        table = fqn.split(".")[-1]
        cur = self._cur()
        cur.execute(f"PRAGMA table_info('{table}')")
        columns, pks = [], []
        for _cid, name, ctype, notnull, dflt, pk in cur.fetchall():
            columns.append(ColumnDef(name=name, data_type=ctype or "",
                                     nullable=not notnull, default=dflt, comment=None))
            if pk:
                pks.append(name)
        fks: list[ForeignKey] = []
        cur.execute(f"PRAGMA foreign_key_list('{table}')")
        for row in cur.fetchall():
            # row: id, seq, table, from, to, on_update, on_delete, match
            fks.append(ForeignKey(column=row[3], referenced_table=row[2], referenced_column=row[4]))
        return TableSchema(name=table, schema="main", database="main",
                           columns=columns, primary_keys=pks, foreign_keys=fks)

    def dialect_name(self) -> str:
        return "sqlite"

    def get_keywords(self) -> list[str]:
        return list(_SQLITE_KEYWORDS)
```

- [ ] **Step 2: Write tests** in `tests/adapters/test_sqlite.py`:
```python
import pytest

from dbridge.adapters.sqlite import SqliteAdapter


@pytest.fixture
def adapter():
    a = SqliteAdapter({"uri": ":memory:"})
    a.connect()
    a.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    a.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id))")
    a.execute("INSERT INTO users (id, name) VALUES (1, 'ada')")
    yield a
    a.disconnect()


def test_list_tables(adapter):
    assert set(adapter.list_tables()) == {"users", "orders"}


def test_execute_returns_rows(adapter):
    result = adapter.execute("SELECT id, name FROM users")
    assert result.columns == ["id", "name"]
    assert result.rows == [[1, "ada"]]
    assert result.row_count == 1


def test_get_table_schema(adapter):
    schema = adapter.get_table_schema("users")
    assert [c.name for c in schema.columns] == ["id", "name"]
    assert schema.primary_keys == ["id"]
    name_col = next(c for c in schema.columns if c.name == "name")
    assert name_col.nullable is False


def test_foreign_keys(adapter):
    schema = adapter.get_table_schema("orders")
    assert schema.foreign_keys[0].referenced_table == "users"
```

- [ ] **Step 3: Run tests.** Run: `uv run pytest tests/adapters/test_sqlite.py -v`
  Expected: 4 passed.

- [ ] **Step 4: Commit.**
```bash
git add src/dbridge/adapters/sqlite.py tests/adapters/test_sqlite.py
git commit -m "feat: port sqlite adapter to new DBAdapter interface"
```

---

## Task 5: DuckDB adapter (ported)

**Files:**
- Create: `src/dbridge/adapters/duckdb.py`
- Test: `tests/adapters/test_duckdb.py`

**Interfaces:**
- Consumes: `DBAdapter`, `QueryResult`, `TableSchema`, `ColumnDef`, `ForeignKey`.
- Produces: `class DuckdbAdapter(DBAdapter)` with `adapter_name = "duckdb"`. Config key: `uri` (`:memory:` or file path). No pandas dependency — use native fetch.

- [ ] **Step 1: Implement `duckdb.py`** (mirror sqlite's structure; introspect via `information_schema`):
```python
import time

import duckdb

from dbridge.adapters.base import ColumnDef, DBAdapter, ForeignKey, QueryResult, TableSchema
from dbridge.exceptions import AdapterConnectionError, AdapterQueryError

_DUCKDB_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "INNER", "OUTER", "ON", "GROUP",
    "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "INSERT", "INTO", "VALUES",
    "UPDATE", "SET", "DELETE", "CREATE", "TABLE", "DROP", "DISTINCT", "AS",
    "AND", "OR", "NOT", "NULL", "IS", "IN", "LIKE", "BETWEEN", "UNION", "ALL",
    "QUALIFY", "PIVOT", "UNPIVOT",
]


class DuckdbAdapter(DBAdapter):
    adapter_name = "duckdb"

    def __init__(self, config: dict[str, str]) -> None:
        super().__init__(config)
        self.uri = self.config.get("uri", ":memory:")
        self.con = None

    def connect(self) -> None:
        try:
            self.con = duckdb.connect(self.uri)
        except duckdb.Error as e:
            raise AdapterConnectionError(str(e)) from e

    def disconnect(self) -> None:
        if self.con is not None:
            self.con.close()
            self.con = None

    def _exec(self, sql: str, params=None):
        assert self.con is not None, "adapter not connected"
        return self.con.execute(sql, params) if params else self.con.execute(sql)

    def execute(self, sql: str) -> QueryResult:
        start = time.perf_counter()
        try:
            rel = self._exec(sql)
            columns = [c for c in rel.columns] if rel.description else []
            rows = [list(r) for r in rel.fetchall()]
        except duckdb.Error as e:
            raise AdapterQueryError(str(e)) from e
        elapsed = (time.perf_counter() - start) * 1000
        return QueryResult(columns=columns, rows=rows, row_count=len(rows),
                           execution_time_ms=elapsed, warnings=[])

    def list_databases(self) -> list[str]:
        rows = self._exec("SELECT DISTINCT table_catalog FROM information_schema.tables").fetchall()
        return [r[0] for r in rows]

    def list_schemas(self, database: str | None = None) -> list[str]:
        rows = self._exec("SELECT DISTINCT table_schema FROM information_schema.tables").fetchall()
        return [r[0] for r in rows]

    def list_tables(self, database: str | None = None, schema: str | None = None) -> list[str]:
        q = "SELECT table_name FROM information_schema.tables"
        if schema:
            rows = self._exec(q + " WHERE table_schema = ?", [schema]).fetchall()
        else:
            rows = self._exec(q).fetchall()
        return [r[0] for r in rows]

    def get_table_schema(self, fqn: str) -> TableSchema:
        parts = fqn.split(".")
        table = parts[-1]
        schema = parts[-2] if len(parts) >= 2 else None
        rows = self._exec(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_name = ?", [table]
        ).fetchall()
        columns = [
            ColumnDef(name=r[0], data_type=r[1], nullable=(r[2] == "YES"),
                      default=r[3], comment=None)
            for r in rows
        ]
        # PK / FK extraction is best-effort in Phase 1; return empty lists.
        return TableSchema(name=table, schema=schema, database=None,
                           columns=columns, primary_keys=[], foreign_keys=[])

    def dialect_name(self) -> str:
        return "duckdb"

    def get_keywords(self) -> list[str]:
        return list(_DUCKDB_KEYWORDS)
```

- [ ] **Step 2: Write tests** in `tests/adapters/test_duckdb.py`:
```python
import pytest

from dbridge.adapters.duckdb import DuckdbAdapter


@pytest.fixture
def adapter():
    a = DuckdbAdapter({"uri": ":memory:"})
    a.connect()
    a.execute("CREATE TABLE items (id INTEGER, label VARCHAR)")
    a.execute("INSERT INTO items VALUES (1, 'a'), (2, 'b')")
    yield a
    a.disconnect()


def test_list_tables(adapter):
    assert "items" in adapter.list_tables()


def test_execute(adapter):
    result = adapter.execute("SELECT id, label FROM items ORDER BY id")
    assert result.columns == ["id", "label"]
    assert result.rows == [[1, "a"], [2, "b"]]
    assert result.row_count == 2


def test_get_table_schema(adapter):
    schema = adapter.get_table_schema("items")
    assert [c.name for c in schema.columns] == ["id", "label"]
```

- [ ] **Step 3: Run tests.** Run: `uv run pytest tests/adapters/test_duckdb.py -v`
  Expected: 3 passed.

- [ ] **Step 4: Commit.**
```bash
git add src/dbridge/adapters/duckdb.py tests/adapters/test_duckdb.py
git commit -m "feat: port duckdb adapter to new DBAdapter interface (drop pandas)"
```

---

## Task 6: Adapter registry

**Files:**
- Create: `src/dbridge/adapters/registry.py`
- Modify: `src/dbridge/adapters/dbs/__init__.py` (or remove if now empty)

**Interfaces:**
- Consumes: `SqliteAdapter`, `DuckdbAdapter`, `DBAdapter`.
- Produces: `INSTALLED_ADAPTERS: list[str]`, `create_adapter(adapter_name: str, config: dict) -> DBAdapter`.

- [ ] **Step 1: Implement `registry.py`.**
```python
from dbridge.adapters.base import DBAdapter
from dbridge.adapters.duckdb import DuckdbAdapter
from dbridge.adapters.sqlite import SqliteAdapter
from dbridge.exceptions import AdapterError

_REGISTRY: dict[str, type[DBAdapter]] = {
    "sqlite": SqliteAdapter,
    "duckdb": DuckdbAdapter,
}

INSTALLED_ADAPTERS = list(_REGISTRY.keys())


def create_adapter(adapter_name: str, config: dict[str, str]) -> DBAdapter:
    cls = _REGISTRY.get(adapter_name)
    if cls is None:
        raise AdapterError(f"adapter '{adapter_name}' is not supported")
    return cls(config)
```

- [ ] **Step 2: Verify.** Run: `uv run python -c "from dbridge.adapters.registry import create_adapter, INSTALLED_ADAPTERS; print(INSTALLED_ADAPTERS)"`
  Expected: `['sqlite', 'duckdb']`.

- [ ] **Step 3: Commit.**
```bash
git add src/dbridge/adapters/registry.py src/dbridge/adapters/dbs/__init__.py
git commit -m "feat: add adapter registry (sqlite, duckdb)"
```

---

## Task 7: Session & SessionManager

**Files:**
- Create: `src/dbridge/core/session.py`
- Test: `tests/core/test_session.py`

**Interfaces:**
- Consumes: `DBAdapter`, `create_adapter`.
- Produces:
  - `@dataclass Session(id: str, adapter: DBAdapter, active_database: str | None, active_schema: str | None)`
  - `class SessionManager` with `create(adapter_name: str, config: dict) -> Session`, `get(session_id: str) -> Session`, `close(session_id: str) -> None`. `get` on unknown id raises `SessionNotFoundError`.
- Produces exception: `SessionNotFoundError(Exception)` (define here).

- [ ] **Step 1: Implement `session.py`.**
```python
import uuid
from dataclasses import dataclass

from dbridge.adapters.base import DBAdapter
from dbridge.adapters.registry import create_adapter


class SessionNotFoundError(Exception):
    pass


@dataclass
class Session:
    id: str
    adapter: DBAdapter
    active_database: str | None = None
    active_schema: str | None = None


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, adapter_name: str, config: dict[str, str]) -> Session:
        adapter = create_adapter(adapter_name, config)
        adapter.connect()
        session = Session(id=str(uuid.uuid4()), adapter=adapter)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def close(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            session.adapter.disconnect()
```

- [ ] **Step 2: Write tests** `tests/core/test_session.py`:
```python
import pytest

from dbridge.core.session import SessionManager, SessionNotFoundError


def test_create_and_get():
    mgr = SessionManager()
    s = mgr.create("sqlite", {"uri": ":memory:"})
    assert mgr.get(s.id) is s


def test_unknown_session_raises():
    mgr = SessionManager()
    with pytest.raises(SessionNotFoundError):
        mgr.get("nope")


def test_close_removes_session():
    mgr = SessionManager()
    s = mgr.create("sqlite", {"uri": ":memory:"})
    mgr.close(s.id)
    with pytest.raises(SessionNotFoundError):
        mgr.get(s.id)
```

- [ ] **Step 3: Run tests.** Run: `uv run pytest tests/core/test_session.py -v`
  Expected: 3 passed.

- [ ] **Step 4: Commit.**
```bash
git add src/dbridge/core/session.py tests/core/test_session.py
git commit -m "feat: add Session and SessionManager"
```

---

## Task 8: Schema registry (hot TTL cache)

**Files:**
- Create: `src/dbridge/core/schema_registry.py`
- Test: `tests/core/test_schema_registry.py`

**Interfaces:**
- Consumes: `DBAdapter`, `TableSchema`.
- Produces: `class SchemaRegistry(adapter: DBAdapter, ttl_seconds: float = 60)` with `list_tables(database=None, schema=None) -> list[str]`, `get_table_schema(fqn) -> TableSchema`, `refresh() -> None`. Caches per call-signature; `refresh()` clears the cache.

- [ ] **Step 1: Implement `schema_registry.py`.**
```python
import time

from dbridge.adapters.base import DBAdapter, TableSchema


class SchemaRegistry:
    def __init__(self, adapter: DBAdapter, ttl_seconds: float = 60) -> None:
        self._adapter = adapter
        self._ttl = ttl_seconds
        self._cache: dict[tuple, tuple[float, object]] = {}

    def _get(self, key: tuple, producer):
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit is not None and (now - hit[0]) < self._ttl:
            return hit[1]
        value = producer()
        self._cache[key] = (now, value)
        return value

    def list_tables(self, database: str | None = None, schema: str | None = None) -> list[str]:
        return self._get(("tables", database, schema),
                         lambda: self._adapter.list_tables(database, schema))

    def get_table_schema(self, fqn: str) -> TableSchema:
        return self._get(("schema", fqn), lambda: self._adapter.get_table_schema(fqn))

    def refresh(self) -> None:
        self._cache.clear()
```

- [ ] **Step 2: Write tests** `tests/core/test_schema_registry.py` (use a fake adapter to assert caching):
```python
from dbridge.core.schema_registry import SchemaRegistry


class FakeAdapter:
    def __init__(self):
        self.table_calls = 0

    def list_tables(self, database=None, schema=None):
        self.table_calls += 1
        return ["a", "b"]

    def get_table_schema(self, fqn):
        return None


def test_caches_within_ttl():
    fake = FakeAdapter()
    reg = SchemaRegistry(fake, ttl_seconds=60)
    assert reg.list_tables() == ["a", "b"]
    assert reg.list_tables() == ["a", "b"]
    assert fake.table_calls == 1


def test_refresh_clears_cache():
    fake = FakeAdapter()
    reg = SchemaRegistry(fake, ttl_seconds=60)
    reg.list_tables()
    reg.refresh()
    reg.list_tables()
    assert fake.table_calls == 2


def test_ttl_expiry():
    fake = FakeAdapter()
    reg = SchemaRegistry(fake, ttl_seconds=0)
    reg.list_tables()
    reg.list_tables()
    assert fake.table_calls == 2
```

- [ ] **Step 3: Run tests.** Run: `uv run pytest tests/core/test_schema_registry.py -v`
  Expected: 3 passed.

- [ ] **Step 4: Commit.**
```bash
git add src/dbridge/core/schema_registry.py tests/core/test_schema_registry.py
git commit -m "feat: add hot-tier schema registry"
```

---

## Task 9: Executor

**Files:**
- Create: `src/dbridge/core/executor.py`
- Test: folded into the engine test (Task 12) — no standalone test needed.

**Interfaces:**
- Consumes: `Session`, `QueryResult`.
- Produces: `execute(session: Session, sql: str, max_rows: int) -> QueryResult`. Caps `rows` to `max_rows`, sets `row_count` to returned length, appends a truncation warning when capped.

- [ ] **Step 1: Implement `executor.py`.**
```python
from dbridge.adapters.base import QueryResult
from dbridge.core.session import Session


def execute(session: Session, sql: str, max_rows: int) -> QueryResult:
    result = session.adapter.execute(sql)
    if len(result.rows) > max_rows:
        truncated = result.rows[:max_rows]
        result = QueryResult(
            columns=result.columns,
            rows=truncated,
            row_count=len(truncated),
            execution_time_ms=result.execution_time_ms,
            warnings=[*result.warnings, f"result truncated to {max_rows} rows"],
        )
    return result
```

- [ ] **Step 2: Verify import.** Run: `uv run python -c "from dbridge.core.executor import execute"`
  Expected: no error.

- [ ] **Step 3: Commit.**
```bash
git add src/dbridge/core/executor.py
git commit -m "feat: add query executor with row cap and truncation warning"
```

---

## Task 10: Completion engine (tier-1)

**Files:**
- Create: `src/dbridge/core/completion.py`
- Test: `tests/core/test_completion.py`

**Interfaces:**
- Consumes: `SchemaRegistry`, `DBAdapter.get_keywords`, `sqlglot`.
- Produces:
  - `@dataclass CompletionItem(label: str, kind: str, detail: str, insert_text: str, sort_key: str)`
  - `complete(sql: str, cursor: int, registry: SchemaRegistry, keywords: list[str]) -> list[CompletionItem]`
  - Internal `_context_at(sql, cursor) -> str` returning one of `"table"`, `"column"`, `"keyword"`.

- [ ] **Step 1: Implement `completion.py`** (tier-1: FROM/JOIN→tables, SELECT/WHERE→columns, else keywords):
```python
from dataclasses import dataclass

import sqlglot

# kind strings map to LSP CompletionItemKind on the client side.
KIND_TABLE = "table"
KIND_COLUMN = "column"
KIND_KEYWORD = "keyword"


@dataclass
class CompletionItem:
    label: str
    kind: str
    detail: str
    insert_text: str
    sort_key: str


def _preceding_keyword(sql: str, cursor: int) -> str:
    head = sql[:cursor]
    tokens = head.replace("\n", " ").split()
    # find the last SQL keyword token before the cursor
    keywords = {"SELECT", "FROM", "WHERE", "JOIN", "ON", "GROUP", "ORDER", "HAVING"}
    for tok in reversed(tokens):
        up = tok.upper().strip(",();")
        if up in keywords:
            return up
    return ""


def _context_at(sql: str, cursor: int) -> str:
    kw = _preceding_keyword(sql, cursor)
    if kw in ("FROM", "JOIN"):
        return KIND_TABLE
    if kw in ("SELECT", "WHERE"):
        return KIND_COLUMN
    return KIND_KEYWORD


def _tables_in_scope(sql: str, dialect: str) -> list[str]:
    try:
        expr = sqlglot.parse_one(sql, read=dialect, error_level=sqlglot.ErrorLevel.IGNORE)
    except Exception:
        return []
    if expr is None:
        return []
    return [t.name for t in expr.find_all(sqlglot.exp.Table)]


def complete(sql: str, cursor: int, registry, keywords: list[str], dialect: str = "") -> list[CompletionItem]:
    ctx = _context_at(sql, cursor)
    if ctx == KIND_KEYWORD:
        return [CompletionItem(k, KIND_KEYWORD, "keyword", k, f"2_{k}") for k in keywords]
    if ctx == KIND_TABLE:
        tables = registry.list_tables()
        return [CompletionItem(t, KIND_TABLE, "table", t, f"0_{t}") for t in tables]
    # KIND_COLUMN: gather columns from tables already in scope
    items: list[CompletionItem] = []
    for table in _tables_in_scope(sql, dialect):
        try:
            schema = registry.get_table_schema(table)
        except Exception:
            continue
        for col in schema.columns:
            items.append(CompletionItem(col.name, KIND_COLUMN, col.data_type, col.name, f"1_{col.name}"))
    return items
```

- [ ] **Step 2: Write tests** `tests/core/test_completion.py`:
```python
from dbridge.adapters.base import ColumnDef, TableSchema
from dbridge.core.completion import complete, KIND_TABLE, KIND_COLUMN, KIND_KEYWORD


class FakeRegistry:
    def list_tables(self, database=None, schema=None):
        return ["users", "orders"]

    def get_table_schema(self, fqn):
        return TableSchema(name=fqn, schema=None, database=None,
                           columns=[ColumnDef("id", "INTEGER"), ColumnDef("name", "TEXT")],
                           primary_keys=["id"], foreign_keys=[])


KEYWORDS = ["SELECT", "FROM", "WHERE"]


def test_from_position_returns_tables():
    sql = "SELECT * FROM "
    items = complete(sql, len(sql), FakeRegistry(), KEYWORDS)
    assert {i.label for i in items} == {"users", "orders"}
    assert all(i.kind == KIND_TABLE for i in items)


def test_select_position_returns_columns():
    sql = "SELECT  FROM users"
    items = complete(sql, len("SELECT "), FakeRegistry(), KEYWORDS)
    assert {i.label for i in items} == {"id", "name"}
    assert all(i.kind == KIND_COLUMN for i in items)


def test_keyword_position():
    sql = "SEL"
    items = complete(sql, 3, FakeRegistry(), KEYWORDS)
    assert all(i.kind == KIND_KEYWORD for i in items)
```

- [ ] **Step 3: Run tests.** Run: `uv run pytest tests/core/test_completion.py -v`
  Expected: 3 passed.

- [ ] **Step 4: Commit.**
```bash
git add src/dbridge/core/completion.py tests/core/test_completion.py
git commit -m "feat: add tier-1 SQL completion engine"
```

---

## Task 11: ERD placeholder & config

**Files:**
- Create: `src/dbridge/core/erd.py`
- Create: `src/dbridge/config/settings.py`
- Create: `src/dbridge/config/connections.py`
- Test: `tests/config/test_connections.py`

**Interfaces:**
- Produces (`erd.py`): `build_erd(tables: list[str], registry) -> dict` returning `{"status": "not_implemented", "tables": tables}`.
- Produces (`settings.py`): `class Settings(BaseSettings)` with `logging_level: str = "INFO"`, `max_rows: int = 100`, `cache_ttl_seconds: int = 60`, env prefix `dbridge_`; module-level `settings = Settings()`.
- Produces (`connections.py`): `load_connections(path: Path | None = None) -> dict[str, dict]` reading `[connections.<name>]` tables from `connections.toml`; `connections_path() -> Path`.

- [ ] **Step 1: Implement `erd.py`.**
```python
def build_erd(tables: list[str], registry) -> dict:
    # Placeholder for Phase 1; real graph extraction comes later.
    return {"status": "not_implemented", "tables": list(tables)}
```

- [ ] **Step 2: Implement `settings.py`.**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="dbridge_")
    logging_level: str = "INFO"
    max_rows: int = 100
    cache_ttl_seconds: int = 60


settings = Settings()
```

- [ ] **Step 3: Implement `connections.py`.**
```python
import os
import tomllib
from pathlib import Path


def config_dir() -> Path:
    if os.name == "nt":
        return Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")) / "dbridge"
    return Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "dbridge"


def connections_path() -> Path:
    return config_dir() / "connections.toml"


def load_connections(path: Path | None = None) -> dict[str, dict]:
    path = path or connections_path()
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    return data.get("connections", {})
```

- [ ] **Step 4: Write test** `tests/config/test_connections.py`:
```python
from dbridge.config.connections import load_connections


def test_load_connections(tmp_path):
    f = tmp_path / "connections.toml"
    f.write_text(
        "[connections.local]\n"
        'adapter = "duckdb"\n'
        'uri = ":memory:"\n'
    )
    conns = load_connections(f)
    assert conns["local"]["adapter"] == "duckdb"
    assert conns["local"]["uri"] == ":memory:"


def test_missing_file_returns_empty(tmp_path):
    assert load_connections(tmp_path / "nope.toml") == {}
```

- [ ] **Step 5: Run tests.** Run: `uv run pytest tests/config/test_connections.py -v`
  Expected: 2 passed.

- [ ] **Step 6: Commit.**
```bash
git add src/dbridge/core/erd.py src/dbridge/config/settings.py src/dbridge/config/connections.py tests/config/test_connections.py
git commit -m "feat: add ERD placeholder, settings, and connections.toml loader"
```

---

## Task 12: Engine

**Files:**
- Create: `src/dbridge/core/engine.py`
- Test: `tests/core/test_engine.py`

**Interfaces:**
- Consumes: `SessionManager`, `SchemaRegistry`, `executor.execute`, `completion.complete`, `erd.build_erd`, `settings`.
- Produces: `class Engine` with methods mirroring the DSP surface, each taking plain dicts/strings and returning JSON-serializable results:
  - `connect(adapter_name, config) -> dict` → `{"session_id": str}`
  - `disconnect(session_id) -> dict` → `{"ok": True}`
  - `execute(session_id, sql) -> dict` (QueryResult as dict)
  - `list_databases(session_id) -> list[str]`, `list_schemas(session_id, database=None) -> list[str]`, `list_tables(session_id, database=None, schema=None) -> list[str]`
  - `get_table_schema(session_id, fqn) -> dict`
  - `complete(session_id, sql, cursor) -> list[dict]`
  - `refresh_schema(session_id) -> dict`
  - `get_erd(session_id, tables) -> dict`
  - Holds one `SchemaRegistry` per session (created on connect).

- [ ] **Step 1: Implement `engine.py`.**
```python
from dataclasses import asdict

from dbridge.config.settings import settings
from dbridge.core import erd, executor
from dbridge.core.completion import complete as complete_sql
from dbridge.core.schema_registry import SchemaRegistry
from dbridge.core.session import SessionManager


class Engine:
    def __init__(self) -> None:
        self.sessions = SessionManager()
        self._registries: dict[str, SchemaRegistry] = {}

    def connect(self, adapter_name: str, config: dict) -> dict:
        session = self.sessions.create(adapter_name, config)
        self._registries[session.id] = SchemaRegistry(
            session.adapter, ttl_seconds=settings.cache_ttl_seconds
        )
        return {"session_id": session.id}

    def disconnect(self, session_id: str) -> dict:
        self.sessions.close(session_id)
        self._registries.pop(session_id, None)
        return {"ok": True}

    def execute(self, session_id: str, sql: str) -> dict:
        session = self.sessions.get(session_id)
        result = executor.execute(session, sql, settings.max_rows)
        return asdict(result)

    def list_databases(self, session_id: str) -> list[str]:
        return self.sessions.get(session_id).adapter.list_databases()

    def list_schemas(self, session_id: str, database: str | None = None) -> list[str]:
        return self.sessions.get(session_id).adapter.list_schemas(database)

    def list_tables(self, session_id: str, database=None, schema=None) -> list[str]:
        return self._registries[session_id].list_tables(database, schema)

    def get_table_schema(self, session_id: str, fqn: str) -> dict:
        return asdict(self._registries[session_id].get_table_schema(fqn))

    def complete(self, session_id: str, sql: str, cursor: int) -> list[dict]:
        session = self.sessions.get(session_id)
        registry = self._registries[session_id]
        items = complete_sql(sql, cursor, registry,
                             session.adapter.get_keywords(),
                             session.adapter.dialect_name())
        return [asdict(i) for i in items]

    def refresh_schema(self, session_id: str) -> dict:
        self._registries[session_id].refresh()
        return {"ok": True}

    def get_erd(self, session_id: str, tables: list[str]) -> dict:
        return erd.build_erd(tables, self._registries[session_id])
```

- [ ] **Step 2: Write integration test** `tests/core/test_engine.py`:
```python
from dbridge.core.engine import Engine


def test_full_flow():
    engine = Engine()
    sid = engine.connect("sqlite", {"uri": ":memory:"})["session_id"]
    engine.execute(sid, "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    engine.execute(sid, "INSERT INTO t VALUES (1, 'x')")

    assert "t" in engine.list_tables(sid)
    schema = engine.get_table_schema(sid, "t")
    assert schema["primary_keys"] == ["id"]

    result = engine.execute(sid, "SELECT id, name FROM t")
    assert result["columns"] == ["id", "name"]
    assert result["rows"] == [[1, "x"]]

    items = engine.complete(sid, "SELECT * FROM ", len("SELECT * FROM "))
    assert any(i["label"] == "t" for i in items)

    engine.disconnect(sid)
```

- [ ] **Step 3: Run tests.** Run: `uv run pytest tests/core/test_engine.py -v`
  Expected: 1 passed.

- [ ] **Step 4: Commit.**
```bash
git add src/dbridge/core/engine.py tests/core/test_engine.py
git commit -m "feat: wire core engine over session/registry/executor/completion"
```

---

## Task 13: Protocol — messages & errors

**Files:**
- Create: `src/dbridge/protocol/errors.py`
- Create: `src/dbridge/protocol/messages.py`

**Interfaces:**
- Produces (`errors.py`): error-code int constants (`PARSE_ERROR=-32700`, `INVALID_REQUEST=-32600`, `METHOD_NOT_FOUND=-32601`, `CONNECTION_FAILED=-32001`, `QUERY_ERROR=-32002`, `SESSION_NOT_FOUND=-32003`, `ADAPTER_NOT_SUPPORTED=-32005`); `class DspError(Exception)` carrying `code: int` and `message: str`.
- Produces (`messages.py`): pydantic models `JsonRpcRequest(jsonrpc, id, method, params)`, `JsonRpcResponse(jsonrpc, id, result)`, `JsonRpcError(jsonrpc, id, error)`, with `make_response(id, result)` and `make_error(id, code, message)` helpers returning dicts.

- [ ] **Step 1: Implement `errors.py`.**
```python
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
CONNECTION_FAILED = -32001
QUERY_ERROR = -32002
SESSION_NOT_FOUND = -32003
ADAPTER_NOT_SUPPORTED = -32005


class DspError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
```

- [ ] **Step 2: Implement `messages.py`.**
```python
from typing import Any

from pydantic import BaseModel


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] = {}


def make_response(req_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def make_error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
```

- [ ] **Step 3: Verify.** Run: `uv run python -c "from dbridge.protocol.messages import JsonRpcRequest, make_error; from dbridge.protocol.errors import DspError, METHOD_NOT_FOUND"`
  Expected: no error.

- [ ] **Step 4: Commit.**
```bash
git add src/dbridge/protocol/errors.py src/dbridge/protocol/messages.py
git commit -m "feat: add JSON-RPC message models and DSP error codes"
```

---

## Task 14: Protocol — handlers (method dispatch)

**Files:**
- Create: `src/dbridge/protocol/handlers.py`
- Test: `tests/protocol/test_handlers.py`

**Interfaces:**
- Consumes: `Engine`, `JsonRpcRequest`, `make_response`, `make_error`, error codes, `DspError`, `SessionNotFoundError`, `AdapterError`/`AdapterConnectionError`/`AdapterQueryError`.
- Produces: `class Dispatcher(engine: Engine)` with `handle(request: dict) -> dict | None`. Maps `dbridge/<method>` to engine calls; translates exceptions to DSP error codes; returns `None` for notifications (no `id`).

- [ ] **Step 1: Implement `handlers.py`.**
```python
from dbridge.adapters.base import DBAdapter  # noqa: F401 (type context)
from dbridge.core.engine import Engine
from dbridge.core.session import SessionNotFoundError
from dbridge.exceptions import AdapterConnectionError, AdapterError, AdapterQueryError
from dbridge.protocol import errors
from dbridge.protocol.messages import JsonRpcRequest, make_error, make_response


class Dispatcher:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._methods = {
            "dbridge/connect": lambda p: engine.connect(p["adapter"], p.get("config", {})),
            "dbridge/disconnect": lambda p: engine.disconnect(p["session_id"]),
            "dbridge/execute": lambda p: engine.execute(p["session_id"], p["sql"]),
            "dbridge/listDatabases": lambda p: engine.list_databases(p["session_id"]),
            "dbridge/listSchemas": lambda p: engine.list_schemas(p["session_id"], p.get("database")),
            "dbridge/listTables": lambda p: engine.list_tables(p["session_id"], p.get("database"), p.get("schema")),
            "dbridge/getTableSchema": lambda p: engine.get_table_schema(p["session_id"], p["fqn"]),
            "dbridge/complete": lambda p: engine.complete(p["session_id"], p["sql"], p["cursor"]),
            "dbridge/refreshSchema": lambda p: engine.refresh_schema(p["session_id"]),
            "dbridge/getERD": lambda p: engine.get_erd(p["session_id"], p.get("tables", [])),
        }

    def handle(self, request: dict) -> dict | None:
        try:
            req = JsonRpcRequest.model_validate(request)
        except Exception:
            return make_error(request.get("id"), errors.INVALID_REQUEST, "invalid request")

        if req.id is None:  # notification
            return None

        fn = self._methods.get(req.method)
        if fn is None:
            return make_error(req.id, errors.METHOD_NOT_FOUND, f"unknown method: {req.method}")

        try:
            return make_response(req.id, fn(req.params))
        except SessionNotFoundError as e:
            return make_error(req.id, errors.SESSION_NOT_FOUND, str(e))
        except AdapterConnectionError as e:
            return make_error(req.id, errors.CONNECTION_FAILED, str(e))
        except AdapterQueryError as e:
            return make_error(req.id, errors.QUERY_ERROR, str(e))
        except AdapterError as e:
            return make_error(req.id, errors.ADAPTER_NOT_SUPPORTED, str(e))
        except KeyError as e:
            return make_error(req.id, errors.INVALID_REQUEST, f"missing param: {e}")
```

- [ ] **Step 2: Write tests** `tests/protocol/test_handlers.py`:
```python
from dbridge.core.engine import Engine
from dbridge.protocol import errors
from dbridge.protocol.handlers import Dispatcher


def make_dispatcher():
    return Dispatcher(Engine())


def test_connect_and_list_tables():
    d = make_dispatcher()
    resp = d.handle({"jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
                     "params": {"adapter": "sqlite", "config": {"uri": ":memory:"}}})
    sid = resp["result"]["session_id"]
    d.handle({"jsonrpc": "2.0", "id": 2, "method": "dbridge/execute",
              "params": {"session_id": sid, "sql": "CREATE TABLE t (id INTEGER)"}})
    resp = d.handle({"jsonrpc": "2.0", "id": 3, "method": "dbridge/listTables",
                     "params": {"session_id": sid}})
    assert "t" in resp["result"]


def test_unknown_method():
    d = make_dispatcher()
    resp = d.handle({"jsonrpc": "2.0", "id": 1, "method": "dbridge/nope", "params": {}})
    assert resp["error"]["code"] == errors.METHOD_NOT_FOUND


def test_session_not_found():
    d = make_dispatcher()
    resp = d.handle({"jsonrpc": "2.0", "id": 1, "method": "dbridge/execute",
                     "params": {"session_id": "bad", "sql": "SELECT 1"}})
    assert resp["error"]["code"] == errors.SESSION_NOT_FOUND


def test_notification_returns_none():
    d = make_dispatcher()
    assert d.handle({"jsonrpc": "2.0", "method": "dbridge/getERD", "params": {}}) is None
```

- [ ] **Step 3: Run tests.** Run: `uv run pytest tests/protocol/test_handlers.py -v`
  Expected: 4 passed.

- [ ] **Step 4: Commit.**
```bash
git add src/dbridge/protocol/handlers.py tests/protocol/test_handlers.py
git commit -m "feat: add JSON-RPC method dispatcher with DSP error mapping"
```

---

## Task 15: Transport — base & stdio framing

**Files:**
- Create: `src/dbridge/protocol/transport/base.py`
- Create: `src/dbridge/protocol/transport/stdio.py`
- Test: `tests/protocol/test_framing.py`

**Interfaces:**
- Produces (`base.py`): `class Transport(ABC)` with `serve(dispatcher) -> None`.
- Produces (`stdio.py`): module functions `read_message(stream) -> dict | None` and `write_message(stream, payload: dict) -> None` (Content-Length framing); `class StdioTransport(Transport)` that loops reading requests from `sys.stdin.buffer`, dispatching, and writing responses to `sys.stdout.buffer`. Exposed for testing as `read_message`/`write_message`.

- [ ] **Step 1: Implement `base.py`.**
```python
from abc import ABC, abstractmethod


class Transport(ABC):
    @abstractmethod
    def serve(self, dispatcher) -> None: ...
```

- [ ] **Step 2: Implement `stdio.py`.**
```python
import json
import sys

from dbridge.protocol.transport.base import Transport


def write_message(stream, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    stream.write(header)
    stream.write(body)
    stream.flush()


def read_message(stream) -> dict | None:
    content_length = None
    while True:
        line = stream.readline()
        if not line:
            return None  # EOF
        line = line.strip()
        if line == b"":
            break  # end of headers
        if line.lower().startswith(b"content-length:"):
            content_length = int(line.split(b":", 1)[1].strip())
    if content_length is None:
        return None
    body = stream.read(content_length)
    return json.loads(body.decode("utf-8"))


class StdioTransport(Transport):
    def serve(self, dispatcher) -> None:
        stdin = sys.stdin.buffer
        stdout = sys.stdout.buffer
        while True:
            request = read_message(stdin)
            if request is None:
                break
            response = dispatcher.handle(request)
            if response is not None:
                write_message(stdout, response)
```

- [ ] **Step 3: Write framing test** `tests/protocol/test_framing.py` (round-trip via BytesIO):
```python
import io

from dbridge.protocol.transport.stdio import read_message, write_message


def test_round_trip():
    buf = io.BytesIO()
    write_message(buf, {"jsonrpc": "2.0", "id": 1, "method": "dbridge/ping", "params": {}})
    buf.seek(0)
    msg = read_message(buf)
    assert msg["method"] == "dbridge/ping"


def test_eof_returns_none():
    buf = io.BytesIO(b"")
    assert read_message(buf) is None
```

- [ ] **Step 4: Run tests.** Run: `uv run pytest tests/protocol/test_framing.py -v`
  Expected: 2 passed.

- [ ] **Step 5: Commit.**
```bash
git add src/dbridge/protocol/transport/base.py src/dbridge/protocol/transport/stdio.py tests/protocol/test_framing.py
git commit -m "feat: add stdio transport with Content-Length framing"
```

---

## Task 16: Server entry point

**Files:**
- Create: `src/dbridge/server.py`
- Modify: `pyproject.toml` (add `[project.scripts] dbridge = "dbridge.server:main"`)

**Interfaces:**
- Consumes: `Engine`, `Dispatcher`, `StdioTransport`.
- Produces: `main() -> None` that builds the engine, dispatcher, and stdio transport and serves.

- [ ] **Step 1: Implement `server.py`.**
```python
from dbridge.core.engine import Engine
from dbridge.protocol.handlers import Dispatcher
from dbridge.protocol.transport.stdio import StdioTransport


def main() -> None:
    engine = Engine()
    dispatcher = Dispatcher(engine)
    StdioTransport().serve(dispatcher)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add script entry** to `pyproject.toml`:
```toml
[project.scripts]
dbridge = "dbridge.server:main"
```

- [ ] **Step 3: Verify it starts and exits on EOF.** Run: `printf "" | uv run python -m dbridge.server`
  Expected: clean exit, no traceback.

- [ ] **Step 4: Commit.**
```bash
git add src/dbridge/server.py pyproject.toml
git commit -m "feat: add stdio server entry point"
```

---

## Task 17: End-to-end stdio test

**Files:**
- Create: `tests/test_e2e_stdio.py`

**Interfaces:**
- Consumes: the built server via `python -m dbridge.server`, `read_message`/`write_message` helpers.

- [ ] **Step 1: Write the E2E test** `tests/test_e2e_stdio.py`:
```python
import subprocess
import sys

from dbridge.protocol.transport.stdio import read_message, write_message


def _request(proc, payload):
    write_message(proc.stdin, payload)
    return read_message(proc.stdout)


def test_e2e_connect_execute_complete_disconnect():
    proc = subprocess.Popen(
        [sys.executable, "-m", "dbridge.server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    try:
        resp = _request(proc, {"jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
                               "params": {"adapter": "sqlite", "config": {"uri": ":memory:"}}})
        sid = resp["result"]["session_id"]

        _request(proc, {"jsonrpc": "2.0", "id": 2, "method": "dbridge/execute",
                        "params": {"session_id": sid, "sql": "CREATE TABLE t (id INTEGER, name TEXT)"}})
        _request(proc, {"jsonrpc": "2.0", "id": 3, "method": "dbridge/execute",
                        "params": {"session_id": sid, "sql": "INSERT INTO t VALUES (1, 'a')"}})

        resp = _request(proc, {"jsonrpc": "2.0", "id": 4, "method": "dbridge/listTables",
                               "params": {"session_id": sid}})
        assert "t" in resp["result"]

        resp = _request(proc, {"jsonrpc": "2.0", "id": 5, "method": "dbridge/execute",
                               "params": {"session_id": sid, "sql": "SELECT id, name FROM t"}})
        assert resp["result"]["rows"] == [[1, "a"]]

        resp = _request(proc, {"jsonrpc": "2.0", "id": 6, "method": "dbridge/complete",
                               "params": {"session_id": sid, "sql": "SELECT * FROM ", "cursor": 14}})
        assert any(i["label"] == "t" for i in resp["result"])

        resp = _request(proc, {"jsonrpc": "2.0", "id": 7, "method": "dbridge/disconnect",
                               "params": {"session_id": sid}})
        assert resp["result"]["ok"] is True
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)
```

- [ ] **Step 2: Run the E2E test.** Run: `uv run pytest tests/test_e2e_stdio.py -v`
  Expected: 1 passed.

- [ ] **Step 3: Run the full suite.** Run: `uv run pytest -v`
  Expected: all tests pass.

- [ ] **Step 4: Commit.**
```bash
git add tests/test_e2e_stdio.py
git commit -m "test: add end-to-end stdio JSON-RPC integration test"
```

---

## Task 18: Docs sync

**Files:**
- Modify: `AGENTS.md` (replace REST/FastAPI description with the new three-layer JSON-RPC architecture; update directory overview, subsystems, env vars; remove `/adapters`, `/run_query` etc. route table)
- Modify: `README.md` (update run instructions: `uv run python -m dbridge.server`, JSON-RPC over stdio)

**Interfaces:** docs only.

- [ ] **Step 1: Rewrite the AGENTS.md "Directory Overview", "Key Subsystems", and "REST API" sections** to reflect: Transport (stdio JSON-RPC) / Core Engine / Adapters; methods table from the DSP surface; `connections.toml` + env vars; sqlite/duckdb only.

- [ ] **Step 2: Update README** run/usage section to the stdio server and the JSON-RPC method list.

- [ ] **Step 3: Commit.**
```bash
git add AGENTS.md README.md
git commit -m "docs: update AGENTS.md and README for three-layer JSON-RPC architecture"
```

---

## Self-Review Notes

- **Spec coverage:** Transport (Tasks 13–16), Core Engine — session (7), executor (9), schema registry (8), completion (10), ERD placeholder (11), engine wiring (12). Adapter interface (2) + sqlite/duckdb ports (4–5) + registry (6). Config TOML + settings (11). E2E acceptance (17). FastAPI teardown + parked adapters (1). Docs (18). All Phase 1 decisions from the grilling map to a task.
- **Deliberately dropped (per decisions):** async, streaming, `dbridge/cancel`, `dbridge/progress`, transactions, warm disk cache, mysql/postgres/snowflake ports, the Lua client.
- **Type consistency check:** `QueryResult` fields (`columns/rows/row_count/execution_time_ms/warnings`) consistent across adapters → executor → engine `asdict`. `CompletionItem` fields consistent between `completion.py` and tests. `create_adapter`/`INSTALLED_ADAPTERS` names consistent between registry and session manager. `Dispatcher.handle` return contract (`dict | None`) consistent between handlers, stdio loop, and E2E test.
- **Ordering:** adapters (2–6) precede core (7–12) precede protocol/transport (13–16) precede E2E (17), so each task's `Consumes` is satisfied by an earlier task.
```
