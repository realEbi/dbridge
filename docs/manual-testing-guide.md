# dbridge Manual Testing Guide

This walkthrough exercises the current synchronous server over real stdio RPCs
against SQLite and DuckDB. It creates temporary databases and temporary Profile
configuration, then removes them on exit. Run it from the repository root after
`uv sync`. No saved user Profiles are read or modified.

The example fixes the row cap at 100 and cache TTL at 60 seconds so its checks
are reproducible. See the [README](../README.md#json-rpc-methods) for settings and
[development guide](development.md) for automated checks.

## Run the walkthrough

```bash
uv run python - <<'PY'
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from dbridge.protocol.transport.stdio import read_message, write_message

with TemporaryDirectory(prefix="dbridge-manual-") as directory:
    env = os.environ.copy()
    env.update(
        XDG_CONFIG_HOME=directory,
        APPDATA=directory,
        dbridge_max_rows="100",
        dbridge_cache_ttl_seconds="60",
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "dbridge.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        env=env,
    )
    request_id = 0

    def rpc(method, params=None):
        global request_id
        request_id += 1
        write_message(proc.stdin, {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "dbridge/" + method,
            "params": {} if params is None else params,
        })
        response = read_message(proc.stdout)
        assert response is not None, "server exited before responding"
        assert response["id"] == request_id
        if "error" in response:
            raise RuntimeError(response["error"])
        return response["result"]

    try:
        assert rpc("listProfiles") == {}
        for adapter in ("sqlite", "duckdb"):
            name = "manual-" + adapter
            uri = str(Path(directory) / (name + ".db"))
            assert rpc("saveProfile", {
                "name": name, "adapter": adapter, "config": {"uri": uri},
            })["ok"]
            assert name in rpc("listProfiles")
            sid = rpc("connect", {"profile": name})["session_id"]

            def query(sql):
                return rpc("execute", {"session_id": sid, "sql": sql})

            query("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT)")
            query("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id))")
            query("INSERT INTO users VALUES (1, 'alice', 'alice@example.com')")
            query("INSERT INTO orders VALUES (1, 1)")

            assert rpc("listDatabases", {"session_id": sid})
            assert rpc("listSchemas", {"session_id": sid})
            assert set(rpc("listTables", {"session_id": sid})) == {"users", "orders"}
            schema = rpc("getTableSchema", {"session_id": sid, "fqn": "users"})
            assert [c["name"] for c in schema["columns"]] == ["id", "name", "email"]
            if adapter == "sqlite":
                assert schema["primary_keys"] == ["id"]
                orders = rpc("getTableSchema", {"session_id": sid, "fqn": "orders"})
                assert orders["foreign_keys"][0]["referenced_table"] == "users"

            result = query("SELECT id, name FROM users ORDER BY id")
            assert result["columns"] == ["id", "name"]
            assert result["rows"] == [[1, "alice"]]

            items = rpc("complete", {"session_id": sid, "sql": "SELECT * FROM "})
            assert any(i["kind"] == "table" and i["label"] == "users" for i in items)
            items = rpc("complete", {
                "session_id": sid, "sql": "SELECT \nFROM users", "position": 7,
            })
            assert {i["label"] for i in items} == {"id", "name", "email"}
            assert all(i["kind"] == "column" for i in items)
            assert any(i["kind"] == "keyword" for i in rpc("complete", {
                "session_id": sid, "sql": "",
            }))

            result = query(
                "WITH RECURSIVE s(n) AS "
                "(SELECT 1 UNION ALL SELECT n+1 FROM s WHERE n<150) SELECT n FROM s"
            )
            assert result["row_count"] == 100
            assert any("truncated" in warning for warning in result["warnings"])
            assert rpc("getERD", {"session_id": sid})["status"] == "not_implemented"

            query("CREATE TABLE products (id INTEGER)")
            assert rpc("refreshSchema", {"session_id": sid})["ok"]
            assert "products" in rpc("listTables", {"session_id": sid})
            assert rpc("disconnect", {"session_id": sid})["ok"]

            sid = rpc("connect", {"profile": name})["session_id"]
            assert query("SELECT id, name FROM users ORDER BY id")["rows"] == [[1, "alice"]]
            assert rpc("disconnect", {"session_id": sid})["ok"]
            assert rpc("deleteProfile", {"name": name})["ok"]
            assert name not in rpc("listProfiles")
            print(adapter + ": Profile, Session, schema, query, completion, cap, and persistence checks passed")
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise
        proc.stdout.close()
    assert proc.returncode == 0
PY
```

## What this verifies

- Profile CRUD and connect-by-Profile use the public RPCs and isolated config.
- Each adapter can create, query, and introspect a file-backed database.
- Columns retain their requested order and writes survive reconnecting.
- Table completion, multiline SELECT completion with a byte offset, and keyword
  fallback operate through the server process.
- A result larger than the configured cap carries a truncation warning.
- Refresh happens after DDL and makes new metadata visible.
- The ERD endpoint remains an explicit placeholder; DuckDB constraint extraction
  is not assumed to be implemented.
- Closing stdin lets the server exit cleanly.

This is a smoke check, not exhaustive protocol validation. For additional manual
cases, follow the same temporary-data and subprocess-cleanup pattern.
