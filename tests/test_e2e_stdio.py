import subprocess
import sys

from dbridge.protocol.transport.stdio import read_message, write_message


def _request(proc, payload):
    write_message(proc.stdin, payload)
    return read_message(proc.stdout)


def _spawn():
    return subprocess.Popen(
        [sys.executable, "-m", "dbridge.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )


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
            "params": {"session_id": sid},
        })
        assert "t" in resp["result"]

        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 6, "method": "dbridge/getTableSchema",
            "params": {"session_id": sid, "fqn": "t"},
        })
        assert [c["name"] for c in resp["result"]["columns"]] == ["id", "name"]

        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 7, "method": "dbridge/disconnect",
            "params": {"session_id": sid},
        })
        assert resp["result"]["ok"] is True
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)


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
            "params": {"session_id": sid, "sql": "SELECT * FROM "},
        })
        items = resp["result"]
        kinds = {i["kind"] for i in items}
        labels = [i["label"] for i in items]
        assert kinds == {"table"}
        assert "users" in labels
        assert "orders" in labels

        # WHERE context → columns in scope
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 5, "method": "dbridge/complete",
            "params": {"session_id": sid, "sql": "SELECT id FROM users WHERE "},
        })
        items = resp["result"]
        assert any(i["kind"] == "column" for i in items)
        assert any(i["label"] == "name" for i in items)

        # Keyword fallback
        resp = _request(proc, {
            "jsonrpc": "2.0", "id": 6, "method": "dbridge/complete",
            "params": {"session_id": sid, "sql": ""},
        })
        items = resp["result"]
        assert any(i["kind"] == "keyword" for i in items)
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)


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
        proc.stdin.close()
        proc.wait(timeout=5)
