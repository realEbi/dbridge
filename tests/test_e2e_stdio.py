import os
import subprocess
import sys

import pytest

from dbridge.protocol.transport.stdio import read_message, write_message


def _request(proc, payload):
    write_message(proc.stdin, payload)
    return read_message(proc.stdout)


def _spawn(env=None):
    return subprocess.Popen(
        [sys.executable, "-m", "dbridge.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        env=env,
    )


def _stop(proc):
    try:
        proc.stdin.close()
    finally:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        finally:
            proc.stdout.close()


def test_e2e_connect_execute_disconnect():
    proc = _spawn()
    try:
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
            "params": {"adapter": "sqlite", "config": {"uri": ":memory:"}},
        })
        sid = resp["result"]["session_id"]

        _request(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "dbridge/execute",
            "params": {"session_id": sid, "sql": "CREATE TABLE t (id INTEGER, name TEXT)"},
        })
        _request(proc, {
            "jsonrpc": "2.0", "id": 3, "method": "dbridge/execute",
            "params": {"session_id": sid, "sql": "INSERT INTO t VALUES (1, 'a')"},
        })

        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 4, "method": "dbridge/execute",
            "params": {"session_id": sid, "sql": "SELECT id, name FROM t"},
        })
        assert resp["result"]["columns"] == ["id", "name"]
        assert resp["result"]["rows"] == [[1, "a"]]

        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 5, "method": "dbridge/listTables",
            "params": {"path": ["main"], "session_id": sid},
        })
        assert "t" in [entry["name"] for entry in resp["result"]]

        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 6, "method": "dbridge/getTableSchema",
            "params": {"path": ["main"], "session_id": sid, "name": "t"},
        })
        assert [c["name"] for c in resp["result"]["columns"]] == ["id", "name"]

        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 7, "method": "dbridge/disconnect",
            "params": {"session_id": sid},
        })
        assert resp["result"]["ok"] is True
    finally:
        _stop(proc)


def test_e2e_complete():
    proc = _spawn()
    try:
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
            "params": {"adapter": "sqlite", "config": {"uri": ":memory:"}},
        })
        sid = resp["result"]["session_id"]

        _request(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "dbridge/execute",
            "params": {"session_id": sid, "sql": "CREATE TABLE users (id INTEGER, name TEXT)"},
        })
        _request(proc, {
            "jsonrpc": "2.0", "id": 3, "method": "dbridge/execute",
            "params": {"session_id": sid, "sql": "CREATE TABLE orders (id INTEGER, user_id INTEGER)"},
        })

        # FROM context → table names
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 4, "method": "dbridge/complete",
            "params": {"path": ["main"], "session_id": sid, "sql": "SELECT * FROM "},
        })
        items = resp["result"]
        kinds = {i["kind"] for i in items}
        labels = [i["label"] for i in items]
        assert kinds == {"table"}
        assert "users" in labels
        assert "orders" in labels

        # SELECT position (cursor before FROM) → columns of tables in scope
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 7, "method": "dbridge/complete",
            "params": {"path": ["main"], "session_id": sid, "sql": "SELECT  FROM users", "position": 7},
        })
        items = resp["result"]
        assert {i["kind"] for i in items} == {"column"}
        assert [i["label"] for i in items] == ["id", "name"]

        # WHERE context → columns in scope
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 5, "method": "dbridge/complete",
            "params": {"path": ["main"], "session_id": sid, "sql": "SELECT id FROM users WHERE "},
        })
        items = resp["result"]
        assert any(i["kind"] == "column" for i in items)
        assert any(i["label"] == "name" for i in items)

        # Keyword fallback
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 6, "method": "dbridge/complete",
            "params": {"path": ["main"], "session_id": sid, "sql": ""},
        })
        items = resp["result"]
        assert any(i["kind"] == "keyword" for i in items)
    finally:
        _stop(proc)


@pytest.mark.parametrize("adapter", ["sqlite", "duckdb"])
def test_e2e_complete_alias_columns(adapter, tmp_path):
    env = os.environ.copy()
    env.update(XDG_CONFIG_HOME=str(tmp_path), APPDATA=str(tmp_path))
    proc = _spawn(env=env)
    request_id = 0

    def rpc(method, **params):
        nonlocal request_id
        request_id += 1
        response = _request(proc, {
            "jsonrpc": "2.0", "id": request_id, "method": "dbridge/" + method,
            "params": params,
        })
        assert response is not None, "server exited before responding"
        assert response["id"] == request_id
        assert "error" not in response, response.get("error")
        return response["result"]

    try:
        connected = rpc("connect", adapter=adapter, config={"uri": ":memory:"})
        session_id = connected["session_id"]
        scope_path = connected["default_path"]
        rpc(
            "execute", session_id=session_id,
            sql="CREATE TABLE products (id INTEGER, name TEXT, category TEXT)",
        )
        rpc(
            "execute", session_id=session_id,
            sql="CREATE TABLE orders (id INTEGER, product_id INTEGER, order_reference TEXT)",
        )
        cases = [
            ("SELECT p.|name, p.category FROM products p LIMIT 100",
             ["id", "name", "category"]),
            ("SELECT p.name, p.|category FROM products p LIMIT 100",
             ["id", "name", "category"]),
            ("SELECT p.name, p.ca|tegory FROM products p LIMIT 100", ["category"]),
            ("SELECT p.|name FROM products p JOIN orders o ON p.id = o.product_id",
             ["id", "name", "category"]),
            ("SELECT p.name FROM products p JOIN orders o ON p.id = o.|product_id",
             ["id", "product_id", "order_reference"]),
            ("SELECT 'café', p.|name FROM products p", ["id", "name", "category"]),
        ]
        for marked_sql, columns in cases:
            before, _, after = marked_sql.partition("|")
            items = rpc(
                "complete", path=scope_path, session_id=session_id, sql=before + after,
                position=len(before.encode("utf-8")),
            )
            assert [item["label"] for item in items] == columns, marked_sql
            assert {item["kind"] for item in items} == {"column"}, marked_sql
            assert [item["insert_text"] for item in items] == columns, marked_sql

        assert rpc("disconnect", session_id=session_id) == {"ok": True}
    finally:
        _stop(proc)
    assert proc.returncode == 0


def test_e2e_result_truncation():
    # Default max_rows is 100; a 150-row generated result must be capped and warned.
    proc = _spawn()
    try:
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
            "params": {"adapter": "sqlite", "config": {"uri": ":memory:"}},
        })
        sid = resp["result"]["session_id"]
        # Recursive CTE generating 150 rows.
        sql = (
            "WITH RECURSIVE seq(n) AS "
            "(SELECT 1 UNION ALL SELECT n+1 FROM seq WHERE n < 150) "
            "SELECT n FROM seq"
        )
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "dbridge/execute",
            "params": {"session_id": sid, "sql": sql},
        })
        assert resp["result"]["row_count"] == 100
        assert any("truncated" in w for w in resp["result"]["warnings"])
    finally:
        _stop(proc)


@pytest.mark.parametrize("adapter", ["sqlite", "duckdb"])
def test_e2e_complete_unqualified_select(adapter, tmp_path):
    env = os.environ.copy()
    env.update(XDG_CONFIG_HOME=str(tmp_path), APPDATA=str(tmp_path))
    proc = _spawn(env=env)
    request_id = 0

    def rpc(method, **params):
        nonlocal request_id
        request_id += 1
        response = _request(proc, {
            "jsonrpc": "2.0", "id": request_id, "method": "dbridge/" + method,
            "params": params,
        })
        assert response is not None, "server exited before responding"
        assert response["id"] == request_id
        assert "error" not in response, response.get("error")
        return response["result"]

    try:
        connected = rpc("connect", adapter=adapter, config={"uri": ":memory:"})
        session_id = connected["session_id"]
        scope_path = connected["default_path"]
        rpc(
            "execute", session_id=session_id,
            sql="CREATE TABLE products (id INTEGER, name TEXT, category TEXT)",
        )
        rpc(
            "execute", session_id=session_id,
            sql="CREATE TABLE orders (id INTEGER, product_id INTEGER, order_reference TEXT)",
        )
        for marked_sql, columns in [
            ("SELECT id, | FROM products", ["id", "name", "category"]),
            ("SELECT id, na|me FROM products", ["name"]),
            ("SELECT 'café ☕',\n COALESCE(ca|tegory, '') FROM products", ["category"]),
            (
                "SELECT (SELECT | FROM orders) FROM products",
                ["id", "product_id", "order_reference"],
            ),
            (
                "SELECT id FROM products; SELECT | FROM orders",
                ["id", "product_id", "order_reference"],
            ),
        ]:
            before, after = marked_sql.split("|")
            items = rpc(
                "complete", path=scope_path, session_id=session_id, sql=before + after,
                position=len(before.encode("utf-8")),
            )
            assert [item["label"] for item in items] == columns, marked_sql
            assert [item["insert_text"] for item in items] == columns, marked_sql
            assert {item["kind"] for item in items} == {"column"}, marked_sql

        for sql in ["SELECT ", "SELECT id, "]:
            items = rpc("complete", path=scope_path, session_id=session_id, sql=sql)
            assert {item["kind"] for item in items} == {"keyword"}
            assert "FROM" in [item["label"] for item in items]
        assert rpc("disconnect", session_id=session_id) == {"ok": True}
    finally:
        _stop(proc)
    assert proc.returncode == 0


@pytest.mark.parametrize("adapter", ["sqlite", "duckdb"])
def test_e2e_explicit_scope_contract_and_recovery(adapter, tmp_path):
    env = os.environ.copy()
    env.update(XDG_CONFIG_HOME=str(tmp_path), APPDATA=str(tmp_path))
    proc = _spawn(env=env)
    request_id = 0

    def rpc(method, params):
        nonlocal request_id
        request_id += 1
        response = _request(proc, {
            "jsonrpc": "2.0", "id": request_id, "method": "dbridge/" + method,
            "params": params,
        })
        assert response is not None
        assert response["id"] == request_id
        return response

    try:
        connected = rpc("connect", {"adapter": adapter, "config": {
            "uri": str(tmp_path / ("sample.db" if adapter == "sqlite" else "sample.duckdb")),
        }})["result"]
        sid, path = connected["session_id"], connected["default_path"]
        assert connected["dialect"] == adapter
        assert [level["name"] for level in connected["levels"]] == (
            ["namespace"] if adapter == "sqlite" else ["catalog", "schema"]
        )
        assert len(path) == len(connected["levels"])
        assert all(level["label"] for level in connected["levels"])
        assert "error" not in rpc("execute", {"session_id": sid, "sql": "CREATE TABLE orders (id INTEGER)"})
        params = {"session_id": sid, "path": path}
        tables = rpc("listTables", params)["result"]
        assert [entry["name"] for entry in tables] == ["orders"]
        schema = rpc("getTableSchema", {**params, "name": "orders"})["result"]
        assert schema["scope"] == path
        assert schema["sql_identifier"] == tables[0]["sql_identifier"]
        assert [column["name"] for column in schema["columns"]] == ["id"]
        # Every malformed request responds, then the same subprocess still executes SQL.
        for method in ("listSchemas", "listTables", "getTableSchema", "getERD", "complete"):
            for invalid in ({}, {"path": [1]}, {"path": [""]}, {"path": ["a", "b", "c"]}):
                response = rpc(method, {"session_id": sid, "name": "orders", "sql": "SELECT ", **invalid})
                assert response["error"]["code"] == -32600
                assert rpc("execute", {"session_id": sid, "sql": "SELECT 1"})["result"]["rows"] == [[1]]
        refreshed = rpc("refreshSchema", {"session_id": sid})["result"]
        assert refreshed == {"ok": True, "levels": connected["levels"], "default_path": path}
        assert rpc("disconnect", {"session_id": sid})["result"] == {"ok": True}
    finally:
        _stop(proc)
    assert proc.returncode == 0
