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


# ── profile management over the protocol ──────────────────────────────────────
# `isolated_profiles` comes from tests/conftest.py.

def _rpc(d, _id, method, params):
    return d.handle({"jsonrpc": "2.0", "id": _id, "method": method, "params": params})


def test_save_list_delete_profile_roundtrip(isolated_profiles):
    d = make_dispatcher()

    assert _rpc(d, 1, "dbridge/listProfiles", {})["result"] == {}

    resp = _rpc(d, 2, "dbridge/saveProfile", {
        "name": "mem", "adapter": "sqlite", "config": {"uri": ":memory:"},
    })
    assert resp["result"]["ok"] is True

    listed = _rpc(d, 3, "dbridge/listProfiles", {})["result"]
    assert listed == {"mem": {"adapter": "sqlite", "config": {"uri": ":memory:"}}}

    assert _rpc(d, 4, "dbridge/deleteProfile", {"name": "mem"})["result"]["ok"] is True
    assert _rpc(d, 5, "dbridge/listProfiles", {})["result"] == {}


def test_delete_unknown_profile_reports_not_ok(isolated_profiles):
    d = make_dispatcher()
    assert _rpc(d, 1, "dbridge/deleteProfile", {"name": "ghost"})["result"]["ok"] is False


def test_save_profile_requires_name_and_adapter(isolated_profiles):
    d = make_dispatcher()
    resp = _rpc(d, 1, "dbridge/saveProfile", {"adapter": "sqlite"})
    assert resp["error"]["code"] == errors.INVALID_REQUEST


def test_connect_by_profile_name(isolated_profiles):
    d = make_dispatcher()
    _rpc(d, 1, "dbridge/saveProfile", {
        "name": "mem", "adapter": "sqlite", "config": {"uri": ":memory:"},
    })

    sid = _rpc(d, 2, "dbridge/connect", {"profile": "mem"})["result"]["session_id"]
    _rpc(d, 3, "dbridge/execute", {"session_id": sid, "sql": "CREATE TABLE t (id INTEGER)"})
    assert _rpc(d, 4, "dbridge/listTables", {"session_id": sid})["result"] == ["t"]


def test_connect_with_unknown_profile_returns_profile_not_found(isolated_profiles):
    d = make_dispatcher()
    resp = _rpc(d, 1, "dbridge/connect", {"profile": "ghost"})
    assert resp["error"]["code"] == errors.PROFILE_NOT_FOUND


def test_connect_without_profile_or_adapter_is_invalid_request():
    d = make_dispatcher()
    resp = _rpc(d, 1, "dbridge/connect", {})
    assert resp["error"]["code"] == errors.INVALID_REQUEST


def test_get_erd_with_unknown_session_returns_session_not_found():
    d = make_dispatcher()
    resp = _rpc(d, 1, "dbridge/getERD", {"session_id": "no-such-session"})
    assert resp["error"]["code"] == errors.SESSION_NOT_FOUND


# ── error mapping ─────────────────────────────────────────────────────────────

def test_malformed_request_returns_invalid_request():
    """A payload that fails JsonRpcRequest validation is reported, not raised."""
    d = make_dispatcher()
    resp = d.handle({"jsonrpc": "2.0", "id": 1})  # no method
    assert resp["error"]["code"] == errors.INVALID_REQUEST


def test_malformed_request_preserves_the_request_id():
    d = make_dispatcher()
    resp = d.handle({"jsonrpc": "2.0", "id": 42, "params": {}})
    assert resp["id"] == 42


def test_malformed_request_without_an_id_still_responds():
    """Validation fails before the notification check, so an error still comes back."""
    d = make_dispatcher()
    resp = d.handle({"not": "a request"})
    assert resp["error"]["code"] == errors.INVALID_REQUEST
    assert resp["id"] is None


def test_connection_failure_maps_to_connection_failed():
    """sqlite without a uri raises AdapterConnectionError inside connect."""
    d = make_dispatcher()
    resp = _rpc(d, 1, "dbridge/connect", {"adapter": "sqlite", "config": {}})
    assert resp["error"]["code"] == errors.CONNECTION_FAILED


def test_query_failure_maps_to_query_error():
    d = make_dispatcher()
    sid = _rpc(d, 1, "dbridge/connect", {
        "adapter": "sqlite", "config": {"uri": ":memory:"},
    })["result"]["session_id"]

    resp = _rpc(d, 2, "dbridge/execute", {"session_id": sid, "sql": "SELECT * FROM nope"})
    assert resp["error"]["code"] == errors.QUERY_ERROR


def test_missing_param_maps_to_invalid_request():
    """A KeyError from a method lambda is reported as a missing param."""
    d = make_dispatcher()
    resp = _rpc(d, 1, "dbridge/execute", {"session_id": "whatever"})  # no sql
    assert resp["error"]["code"] == errors.INVALID_REQUEST
    assert "sql" in resp["error"]["message"]


def test_successful_response_shape():
    d = make_dispatcher()
    resp = _rpc(d, 7, "dbridge/connect", {
        "adapter": "sqlite", "config": {"uri": ":memory:"},
    })
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 7
    assert "error" not in resp
