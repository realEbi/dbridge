"""Engine methods driven directly.

These paths are exercised end-to-end through a spawned server, so they are
proven but unmeasured. Calling them in process also lets each assertion target
one method rather than a whole protocol exchange.
"""
import pytest

from dbridge.core.schema_registry import SchemaRegistry
from dbridge.core.session import SessionNotFoundError
from dbridge.exceptions import InvalidRequestError


def test_connect_returns_a_session_id(engine):
    result = engine.connect("sqlite", {"uri": ":memory:"})
    assert isinstance(result["session_id"], str) and result["session_id"]


def test_connect_without_adapter_or_profile_is_invalid(engine):
    with pytest.raises(InvalidRequestError):
        engine.connect()


def test_connect_registers_a_schema_registry(engine_session):
    engine, session_id = engine_session
    assert isinstance(engine._registries[session_id], SchemaRegistry)


def test_disconnect_removes_session_and_registry(engine_session):
    engine, session_id = engine_session

    assert engine.disconnect(session_id) == {"ok": True}

    assert session_id not in engine._registries
    with pytest.raises(SessionNotFoundError):
        engine.sessions.get(session_id)


def test_disconnect_is_idempotent(engine_session):
    """Disconnecting twice is a silent no-op: SessionManager.close pops with a
    default, so a client that retries a disconnect does not get an error."""
    engine, session_id = engine_session
    assert engine.disconnect(session_id) == {"ok": True}
    assert engine.disconnect(session_id) == {"ok": True}


def test_list_databases(engine_session):
    engine, session_id = engine_session
    assert engine.list_databases(session_id) == ["main"]


def test_list_schemas(engine_session):
    engine, session_id = engine_session
    assert engine.list_schemas(session_id) == ["main"]


def test_list_schemas_with_explicit_database(engine_session):
    engine, session_id = engine_session
    assert engine.list_schemas(session_id, "main") == ["main"]


def test_list_tables_reflects_created_tables(engine_session):
    engine, session_id = engine_session
    engine.execute(session_id, "CREATE TABLE users (id INTEGER)")
    assert engine.list_tables(session_id) == ["users"]


def test_get_table_schema_returns_columns(engine_session):
    engine, session_id = engine_session
    engine.execute(session_id, "CREATE TABLE users (id INTEGER, name TEXT)")

    schema = engine.get_table_schema(session_id, "users")

    assert schema["name"] == "users"
    assert [c["name"] for c in schema["columns"]] == ["id", "name"]


def test_get_erd_reports_not_implemented_with_tables(engine_session):
    engine, session_id = engine_session
    engine.execute(session_id, "CREATE TABLE t (id INTEGER)")

    erd = engine.get_erd(session_id)

    assert erd["status"] == "not_implemented"
    assert "t" in erd["tables"]


def test_refresh_schema_clears_the_cache(engine_session):
    engine, session_id = engine_session
    engine.execute(session_id, "CREATE TABLE before (id INTEGER)")
    engine.list_tables(session_id)

    engine.execute(session_id, "CREATE TABLE after (id INTEGER)")
    assert engine.refresh_schema(session_id) == {"ok": True}

    assert "after" in engine.list_tables(session_id)


def test_complete_returns_tables_in_a_from_position(engine_session):
    engine, session_id = engine_session
    engine.execute(session_id, "CREATE TABLE users (id INTEGER)")

    items = engine.complete(session_id, "SELECT * FROM ")

    assert {i["kind"] for i in items} == {"table"}
    assert "users" in [i["label"] for i in items]


def test_complete_returns_columns_at_a_cursor_position(engine_session):
    engine, session_id = engine_session
    engine.execute(session_id, "CREATE TABLE users (id INTEGER, name TEXT)")

    items = engine.complete(session_id, "SELECT  FROM users", position=7)

    assert {i["kind"] for i in items} == {"column"}
    assert [i["label"] for i in items] == ["id", "name"]


def test_complete_falls_back_to_keywords(engine_session):
    engine, session_id = engine_session
    items = engine.complete(session_id, "")
    assert {i["kind"] for i in items} == {"keyword"}


@pytest.mark.parametrize("call", [
    lambda e, s: e.execute(s, "SELECT 1"),
    lambda e, s: e.list_databases(s),
    lambda e, s: e.list_schemas(s),
    lambda e, s: e.list_tables(s),
    lambda e, s: e.get_table_schema(s, "t"),
    lambda e, s: e.get_erd(s),
    lambda e, s: e.refresh_schema(s),
    lambda e, s: e.complete(s, "SELECT"),
])
def test_unknown_session_raises_before_touching_the_cache(engine, call):
    """Every session-scoped method must reject an unknown id, not KeyError."""
    with pytest.raises(SessionNotFoundError):
        call(engine, "no-such-session")


def test_profile_roundtrip_through_the_engine(engine, isolated_profiles):
    assert engine.list_profiles() == {}

    assert engine.save_profile("mem", "sqlite", {"uri": ":memory:"}) == {"ok": True}
    assert engine.list_profiles() == {"mem": {"adapter": "sqlite", "config": {"uri": ":memory:"}}}

    assert engine.delete_profile("mem") == {"ok": True}
    assert engine.delete_profile("mem") == {"ok": False}


def test_connect_by_profile_name(engine, isolated_profiles):
    engine.save_profile("mem", "sqlite", {"uri": ":memory:"})
    session_id = engine.connect(profile="mem")["session_id"]
    assert engine.list_databases(session_id) == ["main"]
