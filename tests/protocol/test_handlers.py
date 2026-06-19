from dbridge.core.engine import Engine
from dbridge.protocol import errors
from dbridge.protocol.handlers import Dispatcher


def make_dispatcher():
    return Dispatcher(Engine())


def test_connect_and_execute():
    d = make_dispatcher()
    resp = d.handle({
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
        "params": {"adapter": "sqlite", "config": {"uri": ":memory:"}},
    })
    sid = resp["result"]["session_id"]
    d.handle({
        "jsonrpc": "2.0", "id": 2, "method": "dbridge/execute",
        "params": {"session_id": sid, "sql": "CREATE TABLE t (id INTEGER)"},
    })
    d.handle({
        "jsonrpc": "2.0", "id": 3, "method": "dbridge/execute",
        "params": {"session_id": sid, "sql": "INSERT INTO t VALUES (1)"},
    })
    resp = d.handle({
        "jsonrpc": "2.0", "id": 4, "method": "dbridge/execute",
        "params": {"session_id": sid, "sql": "SELECT id FROM t"},
    })
    assert resp["result"]["rows"] == [[1]]


def test_unknown_method():
    d = make_dispatcher()
    resp = d.handle({"jsonrpc": "2.0", "id": 1, "method": "dbridge/nope", "params": {}})
    assert resp["error"]["code"] == errors.METHOD_NOT_FOUND


def test_session_not_found():
    d = make_dispatcher()
    resp = d.handle({
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/execute",
        "params": {"session_id": "bad", "sql": "SELECT 1"},
    })
    assert resp["error"]["code"] == errors.SESSION_NOT_FOUND


def test_unsupported_adapter():
    d = make_dispatcher()
    resp = d.handle({
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
        "params": {"adapter": "oracle", "config": {}},
    })
    assert resp["error"]["code"] == errors.ADAPTER_NOT_SUPPORTED


def test_notification_returns_none():
    d = make_dispatcher()
    assert d.handle({"jsonrpc": "2.0", "method": "dbridge/execute", "params": {}}) is None
