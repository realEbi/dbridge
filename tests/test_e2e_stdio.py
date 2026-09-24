import os
import io
import select
import time
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


def test_e2e_table_key_constraints_and_refresh(tmp_path):
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path), "APPDATA": str(tmp_path)}
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
        sid = rpc("connect", adapter="sqlite", config={"uri": ":memory:"})["session_id"]
        rpc("execute", session_id=sid,
            sql="CREATE TABLE parent (a INTEGER, b INTEGER, PRIMARY KEY (b, a))")
        rpc("execute", session_id=sid, sql="CREATE TABLE child (x INTEGER, y INTEGER)")
        schema = rpc("getTableSchema", session_id=sid, path=["main"], name="child")
        assert schema["primary_key"] is None
        assert schema["foreign_keys"] == []
        assert "primary_keys" not in schema

        rpc("execute", session_id=sid, sql="DROP TABLE child")
        rpc("execute", session_id=sid, sql=(
            "CREATE TABLE child (x INTEGER, y INTEGER, PRIMARY KEY (y, x), "
            "FOREIGN KEY (y, x) REFERENCES parent (b, a))"
        ))
        assert rpc("getTableSchema", session_id=sid, path=["main"], name="child") == schema
        assert rpc("refreshSchema", session_id=sid)["ok"] is True
        refreshed = rpc("getTableSchema", session_id=sid, path=["main"], name="child")
        assert refreshed["primary_key"] == {"name": None, "columns": ["y", "x"]}
        assert refreshed["foreign_keys"] == [{
            "name": None, "columns": ["y", "x"], "referenced_path": ["main"],
            "referenced_table": "parent", "referenced_columns": ["b", "a"],
        }]
        assert "primary_keys" not in refreshed
        assert rpc("disconnect", session_id=sid) == {"ok": True}
    finally:
        _stop(proc)
    assert proc.returncode == 0


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


@pytest.mark.parametrize("adapter", ["sqlite", "duckdb"])
@pytest.mark.parametrize("max_rows", [3, 100])
def test_e2e_result_truncation(adapter, max_rows, tmp_path):
    env = {
        **os.environ, "XDG_CONFIG_HOME": str(tmp_path), "APPDATA": str(tmp_path),
        "DBRIDGE_MAX_ROWS": str(max_rows),
    }
    proc = _spawn(env=env)
    try:
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
            "params": {"adapter": adapter, "config": {"uri": ":memory:"}},
        })
        sid = resp["result"]["session_id"]
        # Recursive CTE generating 150 rows.
        sql = (
            "WITH RECURSIVE seq(n) AS "
            "(SELECT 1 UNION ALL SELECT n+1 FROM seq WHERE n < 150) "
            "SELECT n AS b, -n AS a FROM seq"
        )
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "dbridge/execute",
            "params": {"session_id": sid, "sql": sql},
        })
        result = resp["result"]
        assert set(result) == {"columns", "rows", "row_count", "execution_time_ms", "warnings"}
        assert result["columns"] == ["b", "a"]
        assert result["rows"] == [[n, -n] for n in range(1, max_rows + 1)]
        assert result["row_count"] == max_rows
        assert result["warnings"] == [f"result truncated to {max_rows} rows"]
        assert result["execution_time_ms"] >= 0
    finally:
        _stop(proc)
    assert proc.returncode == 0


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


def _read_bounded(proc, timeout=5):
    assert select.select([proc.stdout], [], [], timeout)[0], "server reply timed out"
    return read_message(proc.stdout)


def test_e2e_truncated_frame_exits_cleanly_with_diagnostic(tmp_path):
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path), "APPDATA": str(tmp_path)}
    proc = subprocess.Popen([sys.executable, "-m", "dbridge.server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        stdout, stderr = proc.communicate(b'Content-Length: 100\r\n\r\n{', timeout=5)
        assert proc.returncode == 0
        assert b'truncated frame body' in stderr
        assert b'Traceback' not in stderr
        assert read_message(io.BytesIO(stdout)) is None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()


def test_e2e_invalid_json_reply_then_valid_request(tmp_path):
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path), "APPDATA": str(tmp_path)}
    proc = _spawn(env)
    try:
        proc.stdin.write(b'Content-Length: 1\r\n\r\n{')
        proc.stdin.flush()
        response = _read_bounded(proc)
        assert response['id'] is None and response['error']['code'] == -32700
        write_message(proc.stdin, {'jsonrpc': '2.0', 'id': 2, 'method': 'dbridge/listProfiles'})
        assert _read_bounded(proc) == {'jsonrpc': '2.0', 'id': 2, 'result': {}}
    finally:
        _stop(proc)
    assert proc.returncode == 0


def test_e2e_close_input_during_long_duckdb_query_exits_promptly(tmp_path):
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path), "APPDATA": str(tmp_path)}
    proc = subprocess.Popen([sys.executable, "-m", "dbridge.server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        write_message(proc.stdin, {'jsonrpc': '2.0', 'id': 1, 'method': 'dbridge/connect', 'params': {'adapter': 'duckdb'}})
        sid = _read_bounded(proc)['result']['session_id']
        write_message(proc.stdin, {'jsonrpc': '2.0', 'id': 2, 'method': 'dbridge/execute', 'params': {'session_id': sid, 'sql': 'SELECT sum(hash(i)) FROM range(20000000000) t(i)'}})
        # A fast later response proves intake continues while execute is outstanding.
        write_message(proc.stdin, {'jsonrpc': '2.0', 'id': 3, 'method': 'dbridge/listProfiles'})
        assert _read_bounded(proc)['id'] == 3
        started = time.monotonic()
        proc.stdin.close()
        proc.stdin = None
        stdout, stderr = proc.communicate(timeout=4)
        assert proc.returncode == 0
        assert time.monotonic() - started < 3
        assert b'Traceback' not in stderr
        frames = io.BytesIO(stdout)
        while (frame := read_message(frames)) is not None:
            assert isinstance(frame, dict)
            assert frame['id'] == 2 and frame['error']['code'] == -32004
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
