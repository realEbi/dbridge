import pytest

from dbridge.protocol import errors
from dbridge.protocol.handlers import Dispatcher


@pytest.fixture
def make_dispatcher(engine):
    return lambda: Dispatcher(engine)


async def test_connect_and_execute(make_dispatcher):
    d = make_dispatcher()
    resp = (await d.handle({
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
        "params": {"adapter": "sqlite", "config": {"uri": ":memory:"}},
    }))
    sid = resp["result"]["session_id"]
    (await d.handle({
        "jsonrpc": "2.0", "id": 2, "method": "dbridge/execute",
        "params": {"session_id": sid, "sql": "CREATE TABLE t (id INTEGER)"},
    }))
    (await d.handle({
        "jsonrpc": "2.0", "id": 3, "method": "dbridge/execute",
        "params": {"session_id": sid, "sql": "INSERT INTO t VALUES (1)"},
    }))
    resp = (await d.handle({
        "jsonrpc": "2.0", "id": 4, "method": "dbridge/execute",
        "params": {"session_id": sid, "sql": "SELECT id FROM t"},
    }))
    assert resp["result"]["rows"] == [[1]]


async def test_unknown_method(make_dispatcher):
    d = make_dispatcher()
    resp = (await d.handle({"jsonrpc": "2.0", "id": 1, "method": "dbridge/nope", "params": {}}))
    assert resp["error"]["code"] == errors.METHOD_NOT_FOUND


async def test_session_not_found(make_dispatcher):
    d = make_dispatcher()
    resp = (await d.handle({
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/execute",
        "params": {"session_id": "bad", "sql": "SELECT 1"},
    }))
    assert resp["error"]["code"] == errors.SESSION_NOT_FOUND


async def test_unsupported_adapter(make_dispatcher):
    d = make_dispatcher()
    resp = (await d.handle({
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
        "params": {"adapter": "oracle", "config": {}},
    }))
    assert resp["error"]["code"] == errors.ADAPTER_NOT_SUPPORTED


async def test_notification_returns_none(make_dispatcher):
    d = make_dispatcher()
    assert (await d.handle({"jsonrpc": "2.0", "method": "dbridge/execute", "params": {}})) is None


# ── profile management over the protocol ──────────────────────────────────────
# `isolated_profiles` comes from tests/conftest.py.

async def _rpc(d, _id, method, params):
    return (await d.handle({"jsonrpc": "2.0", "id": _id, "method": method, "params": params}))


async def test_save_list_delete_profile_roundtrip(make_dispatcher, isolated_profiles):
    d = make_dispatcher()

    assert (await _rpc(d, 1, "dbridge/listProfiles", {}))["result"] == {}

    resp = (await _rpc(d, 2, "dbridge/saveProfile", {
        "name": "mem", "adapter": "sqlite", "config": {"uri": ":memory:"},
    }))
    assert resp["result"]["ok"] is True

    listed = (await _rpc(d, 3, "dbridge/listProfiles", {}))["result"]
    assert listed == {"mem": {"adapter": "sqlite", "config": {"uri": ":memory:"}}}

    assert (await _rpc(d, 4, "dbridge/deleteProfile", {"name": "mem"}))["result"]["ok"] is True
    assert (await _rpc(d, 5, "dbridge/listProfiles", {}))["result"] == {}


async def test_delete_unknown_profile_reports_not_ok(make_dispatcher, isolated_profiles):
    d = make_dispatcher()
    assert (await _rpc(d, 1, "dbridge/deleteProfile", {"name": "ghost"}))["result"]["ok"] is False


async def test_rename_profile_replaces_definition(make_dispatcher, isolated_profiles):
    d = make_dispatcher()
    await _rpc(d, 1, "dbridge/saveProfile", {
        "name": "old", "adapter": "sqlite", "config": {"uri": ":memory:"},
    })
    response = await _rpc(d, 2, "dbridge/saveProfile", {
        "name": "new", "previous_name": "old", "adapter": "duckdb",
    })
    assert response["result"] == {"ok": True}
    assert (await _rpc(d, 3, "dbridge/listProfiles", {}))["result"] == {
        "new": {"adapter": "duckdb", "config": {}},
    }


@pytest.mark.parametrize("extra", [{}, {"previous_name": "mem"}])
async def test_save_profile_still_upserts(make_dispatcher, isolated_profiles, extra):
    d = make_dispatcher()
    for request_id, config in enumerate([{"uri": ":memory:"}, {}], start=1):
        response = await _rpc(d, request_id, "dbridge/saveProfile", {
            "name": "mem", "adapter": "sqlite", "config": config, **extra,
        })
        assert response["result"] == {"ok": True}
        assert (await _rpc(d, 3, "dbridge/listProfiles", {}))["result"] == {
            "mem": {"adapter": "sqlite", "config": config},
        }


@pytest.mark.parametrize("previous_name,name,code,message", [
    ("old", "taken", errors.PROFILE_ALREADY_EXISTS, "taken"),
    ("ghost", "new", errors.PROFILE_NOT_FOUND, "ghost"),
    ("ghost", "taken", errors.PROFILE_NOT_FOUND, "ghost"),
])
async def test_rejected_profile_rename_preserves_file(
    make_dispatcher, isolated_profiles, previous_name, name, code, message,
):
    d = make_dispatcher()
    for request_id, profile in enumerate(["old", "taken"], start=1):
        await _rpc(d, request_id, "dbridge/saveProfile", {
            "name": profile, "adapter": "sqlite", "config": {"uri": profile + ".db"},
        })
    before = isolated_profiles.read_bytes()
    response = await _rpc(d, 3, "dbridge/saveProfile", {
        "name": name, "previous_name": previous_name, "adapter": "duckdb",
    })
    assert response["error"]["code"] == code
    assert message in response["error"]["message"]
    assert isolated_profiles.read_bytes() == before


@pytest.mark.parametrize("previous_name", [None, "", 0, False, [], {}])
async def test_previous_name_requires_nonempty_string(
    make_dispatcher, isolated_profiles, previous_name,
):
    d = make_dispatcher()
    await _rpc(d, 1, "dbridge/saveProfile", {"name": "old", "adapter": "sqlite"})
    before = isolated_profiles.read_bytes()
    response = await _rpc(d, 2, "dbridge/saveProfile", {
        "name": "old", "previous_name": previous_name, "adapter": "duckdb",
    })
    assert response["error"]["code"] == errors.INVALID_REQUEST
    assert "previous_name" in response["error"]["message"]
    assert isolated_profiles.read_bytes() == before


async def test_save_profile_requires_name_and_adapter(make_dispatcher, isolated_profiles):
    d = make_dispatcher()
    resp = (await _rpc(d, 1, "dbridge/saveProfile", {"adapter": "sqlite"}))
    assert resp["error"]["code"] == errors.INVALID_REQUEST


async def test_connect_by_profile_name(make_dispatcher, isolated_profiles):
    d = make_dispatcher()
    (await _rpc(d, 1, "dbridge/saveProfile", {
        "name": "mem", "adapter": "sqlite", "config": {"uri": ":memory:"},
    }))

    sid = (await _rpc(d, 2, "dbridge/connect", {"profile": "mem"}))["result"]["session_id"]
    (await _rpc(d, 3, "dbridge/execute", {"session_id": sid, "sql": "CREATE TABLE t (id INTEGER)"}))
    assert (await _rpc(d, 4, "dbridge/listTables", {"session_id": sid, "path": ["main"]}))["result"] == [
        {"name": "t", "sql_identifier": '"main"."t"'},
    ]


async def test_connect_with_unknown_profile_returns_profile_not_found(make_dispatcher, isolated_profiles):
    d = make_dispatcher()
    resp = (await _rpc(d, 1, "dbridge/connect", {"profile": "ghost"}))
    assert resp["error"]["code"] == errors.PROFILE_NOT_FOUND


async def test_connect_without_profile_or_adapter_is_invalid_request(make_dispatcher):
    d = make_dispatcher()
    resp = (await _rpc(d, 1, "dbridge/connect", {}))
    assert resp["error"]["code"] == errors.INVALID_REQUEST


async def test_get_erd_with_unknown_session_returns_session_not_found(make_dispatcher):
    d = make_dispatcher()
    resp = (await _rpc(d, 1, "dbridge/getERD", {"session_id": "no-such-session"}))
    assert resp["error"]["code"] == errors.SESSION_NOT_FOUND


# ── error mapping ─────────────────────────────────────────────────────────────

async def test_malformed_request_returns_invalid_request(make_dispatcher):
    """A payload that fails JsonRpcRequest validation is reported, not raised."""
    d = make_dispatcher()
    resp = (await d.handle({"jsonrpc": "2.0", "id": 1}))  # no method
    assert resp["error"]["code"] == errors.INVALID_REQUEST


async def test_malformed_request_preserves_the_request_id(make_dispatcher):
    d = make_dispatcher()
    resp = (await d.handle({"jsonrpc": "2.0", "id": 42, "params": {}}))
    assert resp["id"] == 42


async def test_malformed_request_without_an_id_still_responds(make_dispatcher):
    """Validation fails before the notification check, so an error still comes back."""
    d = make_dispatcher()
    resp = (await d.handle({"not": "a request"}))
    assert resp["error"]["code"] == errors.INVALID_REQUEST
    assert resp["id"] is None


async def test_connection_failure_maps_to_connection_failed(make_dispatcher):
    """sqlite without a uri raises AdapterConnectionError inside connect."""
    d = make_dispatcher()
    resp = (await _rpc(d, 1, "dbridge/connect", {"adapter": "sqlite", "config": {}}))
    assert resp["error"]["code"] == errors.CONNECTION_FAILED


async def test_query_failure_maps_to_query_error(make_dispatcher):
    d = make_dispatcher()
    sid = (await _rpc(d, 1, "dbridge/connect", {
        "adapter": "sqlite", "config": {"uri": ":memory:"},
    }))["result"]["session_id"]

    resp = (await _rpc(d, 2, "dbridge/execute", {"session_id": sid, "sql": "SELECT * FROM nope"}))
    assert resp["error"]["code"] == errors.QUERY_ERROR


async def test_missing_param_maps_to_invalid_request(make_dispatcher):
    """A KeyError from a method lambda is reported as a missing param."""
    d = make_dispatcher()
    resp = (await _rpc(d, 1, "dbridge/execute", {"session_id": "whatever"}))  # no sql
    assert resp["error"]["code"] == errors.INVALID_REQUEST
    assert "sql" in resp["error"]["message"]


async def test_successful_response_shape(make_dispatcher):
    d = make_dispatcher()
    resp = (await _rpc(d, 7, "dbridge/connect", {
        "adapter": "sqlite", "config": {"uri": ":memory:"},
    }))
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 7
    assert "error" not in resp


@pytest.mark.parametrize("method", ["listSchemas", "listTables", "getTableSchema", "getERD", "complete"])
@pytest.mark.parametrize("path_params", [{}, {"path": None}, {"path": "main"}, {"path": []},
                                         {"path": [1]}, {"path": [""]},
                                         {"path": ["main", "main"]}])
async def test_invalid_scope_path_returns_error_and_dispatcher_stays_available(
    engine_session, method, path_params,
):
    engine, sid = engine_session
    d = Dispatcher(engine)
    params = {"session_id": sid, "sql": "SELECT ", "name": "products", **path_params}
    assert (await _rpc(d, 1, "dbridge/" + method, params))["error"]["code"] == errors.INVALID_REQUEST
    assert (await _rpc(d, 2, "dbridge/execute", {"session_id": sid, "sql": "SELECT 1"}))[
        "result"
    ]["rows"] == [[1]]


@pytest.mark.parametrize("path", [None, [], ["main"]])
async def test_list_databases_rejects_any_supplied_path(engine_session, path):
    engine, sid = engine_session
    d = Dispatcher(engine)
    assert (await _rpc(d, 1, "dbridge/listDatabases", {"session_id": sid, "path": path}))[
        "error"
    ]["code"] == errors.INVALID_REQUEST
    assert (await _rpc(d, 2, "dbridge/listDatabases", {"session_id": sid}))["result"] == [
        {"name": "main", "internal": False},
    ]


@pytest.mark.parametrize("legacy", [{"fqn": "main.products"}, {"table": {"name": "products"}},
                                    {"database": "main"}, {"schema": "main"}])
async def test_legacy_identity_is_rejected_even_with_valid_path(engine_session, legacy):
    engine, sid = engine_session
    response = (await _rpc(Dispatcher(engine), 1, "dbridge/getTableSchema", {
        "session_id": sid, "path": ["main"], "name": "products", **legacy,
    }))
    assert response["error"]["code"] == errors.INVALID_REQUEST


@pytest.mark.parametrize("name", [None, "", 1, [], {"name": "products"}])
async def test_table_name_requires_nonempty_literal_string(engine_session, name):
    engine, sid = engine_session
    response = (await _rpc(Dispatcher(engine), 1, "dbridge/getTableSchema", {
        "session_id": sid, "path": ["main"], "name": name,
    }))
    assert response["error"]["code"] == errors.INVALID_REQUEST


async def test_duckdb_operation_arity_and_scoped_rpc_results(engine):
    d = Dispatcher(engine)
    connected = (await _rpc(d, 1, "dbridge/connect", {"adapter": "duckdb"}))["result"]
    sid = connected["session_id"]
    try:
        (await engine.execute(sid, "CREATE TABLE orders (id INTEGER)"))
        assert (await _rpc(d, 2, "dbridge/listTables", {"session_id": sid, "path": ["memory"]}))[
            "error"
        ]["code"] == errors.INVALID_REQUEST
        schemas = (await _rpc(d, 3, "dbridge/listSchemas", {"session_id": sid, "path": ["memory"]}))["result"]
        assert {"name": "main", "internal": False} in schemas
        assert (await _rpc(d, 4, "dbridge/listSchemas", {"session_id": sid, "path": ["memory", "main"]}))[
            "error"
        ]["code"] == errors.INVALID_REQUEST
        params = {"session_id": sid, "path": ["memory", "main"]}
        listed = (await _rpc(d, 5, "dbridge/listTables", params))["result"]
        assert listed == [{"name": "orders", "sql_identifier": '"memory"."main"."orders"'}]
        assert (await _rpc(d, 6, "dbridge/getERD", params))["result"] == {
            "status": "not_implemented", "tables": listed,
        }
        assert (await _rpc(d, 7, "dbridge/refreshSchema", {"session_id": sid}))["result"] == {
            "ok": True, "levels": connected["levels"], "default_path": connected["default_path"],
        }
    finally:
        (await engine.disconnect(sid))
