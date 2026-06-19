# dbridge Manual Testing Guide

A hands-on walkthrough for testing the stdio JSON-RPC server locally.

---

## Prerequisites

```bash
cd /path/to/dbridge
uv sync
```

---

## 1. Create a test database

```bash
python3 -c "
import sqlite3
con = sqlite3.connect('/tmp/test.db')
con.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT)')
con.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), total REAL)')
con.execute(\"INSERT INTO users VALUES (1, 'alice', 'alice@example.com')\")
con.execute(\"INSERT INTO users VALUES (2, 'bob', 'bob@example.com')\")
con.execute(\"INSERT INTO orders VALUES (1, 1, 49.99)\")
con.commit()
print('created /tmp/test.db')
"
```

---

## 2. Create the test client

Save as `scripts/manual_test.py`:

```python
import json
import subprocess
import sys

sys.path.insert(0, 'src')
from dbridge.protocol.transport.stdio import read_message, write_message

proc = subprocess.Popen(
    [sys.executable, '-m', 'dbridge.server'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
)

_id = 0
def rpc(method, params):
    global _id
    _id += 1
    write_message(proc.stdin, {'jsonrpc': '2.0', 'id': _id, 'method': method, 'params': params})
    resp = read_message(proc.stdout)
    result = resp.get('result', resp.get('error'))
    print(f'\n[{method}]')
    print(json.dumps(result, indent=2))
    return result

# ── connect ──────────────────────────────────────────────────────────────────
result = rpc('dbridge/connect', {'adapter': 'sqlite', 'config': {'uri': '/tmp/test.db'}})
sid = result['session_id']

# ── introspection ─────────────────────────────────────────────────────────────
rpc('dbridge/listDatabases', {'session_id': sid})
rpc('dbridge/listSchemas',   {'session_id': sid})
rpc('dbridge/listTables',    {'session_id': sid})
rpc('dbridge/getTableSchema', {'session_id': sid, 'fqn': 'users'})
rpc('dbridge/getTableSchema', {'session_id': sid, 'fqn': 'orders'})

# ── execute ───────────────────────────────────────────────────────────────────
rpc('dbridge/execute', {'session_id': sid, 'sql': 'SELECT * FROM users'})
rpc('dbridge/execute', {'session_id': sid, 'sql':
    'SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id'})

# ── row cap (generates 150 rows, expect truncation warning) ───────────────────
rpc('dbridge/execute', {'session_id': sid, 'sql':
    'WITH RECURSIVE s(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM s WHERE n<150) SELECT n FROM s'})

# ── completion ────────────────────────────────────────────────────────────────
rpc('dbridge/complete', {'session_id': sid, 'sql': 'SELECT * FROM '})          # → tables
rpc('dbridge/complete', {'session_id': sid, 'sql': 'SELECT id FROM users WHERE '})  # → columns
rpc('dbridge/complete', {'session_id': sid, 'sql': ''})                         # → keywords

# ── ERD placeholder ───────────────────────────────────────────────────────────
rpc('dbridge/getERD', {'session_id': sid})

# ── refresh schema cache ──────────────────────────────────────────────────────
rpc('dbridge/refreshSchema', {'session_id': sid})
# After refresh, new tables created in the session will appear:
rpc('dbridge/execute',   {'session_id': sid, 'sql': 'CREATE TABLE products (id INTEGER, name TEXT)'})
rpc('dbridge/listTables', {'session_id': sid})  # products should now appear

# ── disconnect ────────────────────────────────────────────────────────────────
rpc('dbridge/disconnect', {'session_id': sid})

proc.stdin.close()
proc.wait()
```

---

## 3. Run it

```bash
uv run python scripts/manual_test.py
```

---

## 4. Expected output highlights

| Call | What to check |
|---|---|
| `dbridge/connect` | `session_id` is a non-empty string |
| `dbridge/listTables` | `["users", "orders"]` |
| `dbridge/getTableSchema` (users) | columns `id`, `name`, `email`; `primary_keys: ["id"]` |
| `dbridge/getTableSchema` (orders) | `foreign_keys` referencing `users` |
| `dbridge/execute` (SELECT) | `columns`, `rows`, `row_count` populated |
| `dbridge/execute` (150-row CTE) | `row_count: 100` and `warnings` contains `"truncated"` |
| `dbridge/complete` (FROM) | items with `kind: "table"` — `users`, `orders` |
| `dbridge/complete` (WHERE) | items with `kind: "column"` — `id`, `name`, `email` |
| `dbridge/complete` (empty) | items with `kind: "keyword"` — `SELECT`, `FROM`, … |
| `dbridge/getERD` | `{"status": "not_implemented", "tables": [...]}` |
| `dbridge/refreshSchema` | `{"ok": true}` |
| `dbridge/listTables` (after refresh) | `products` now in list |
| `dbridge/disconnect` | `{"ok": true}` |

---

## 5. Testing DuckDB

Change the connect call to use DuckDB (`:memory:` or a file path):

```python
result = rpc('dbridge/connect', {'adapter': 'duckdb', 'config': {'uri': ':memory:'}})
sid = result['session_id']
rpc('dbridge/execute', {'session_id': sid, 'sql': 'CREATE TABLE events (id INTEGER, ts TIMESTAMP, value DOUBLE)'})
rpc('dbridge/listTables', {'session_id': sid})
rpc('dbridge/getTableSchema', {'session_id': sid, 'fqn': 'events'})
```

---

## 6. Using connection profiles

Add to `~/.config/dbridge/connections.toml`:

```toml
[connections.testdb]
adapter = "sqlite"
[connections.testdb.config]
uri = "/tmp/test.db"
```

Load it in your script:

```python
from dbridge.config.profiles import load_profiles
profile = load_profiles()['testdb']
result = rpc('dbridge/connect', profile)
```

---

## 7. Env var overrides

```bash
# lower the row cap to 10
dbridge_max_rows=10 uv run python scripts/manual_test.py

# shorten the schema cache TTL
dbridge_cache_ttl_seconds=5 uv run python scripts/manual_test.py
```
