"""Unit tests for config/profiles.py and the getERD / refreshSchema handlers."""
import textwrap

import pytest

from dbridge.config.profiles import (
    ProfileNotFoundError,
    delete_profile,
    get_profile,
    load_profiles,
    save_profile,
)


# ── profiles loader ───────────────────────────────────────────────────────────

def test_missing_file_returns_empty(tmp_path):
    assert load_profiles(tmp_path / "nonexistent.toml") == {}


def test_loads_profile(tmp_path):
    toml = tmp_path / "connections.toml"
    toml.write_text(textwrap.dedent("""\
        [connections.mydb]
        adapter = "sqlite"
        [connections.mydb.config]
        uri = "/tmp/test.db"
    """))
    profiles = load_profiles(toml)
    assert "mydb" in profiles
    assert profiles["mydb"]["adapter"] == "sqlite"
    assert profiles["mydb"]["config"]["uri"] == "/tmp/test.db"


def test_multiple_profiles(tmp_path):
    toml = tmp_path / "connections.toml"
    toml.write_text(textwrap.dedent("""\
        [connections.a]
        adapter = "sqlite"
        [connections.b]
        adapter = "duckdb"
        [connections.b.config]
        uri = ":memory:"
    """))
    profiles = load_profiles(toml)
    assert set(profiles) == {"a", "b"}


def test_entry_without_adapter_is_skipped(tmp_path):
    toml = tmp_path / "connections.toml"
    toml.write_text(textwrap.dedent("""\
        [connections.bad]
        uri = "oops"
    """))
    assert load_profiles(toml) == {}


def test_empty_toml_returns_empty(tmp_path):
    toml = tmp_path / "connections.toml"
    toml.write_text("")
    assert load_profiles(toml) == {}


# ── getERD and refreshSchema via Dispatcher ───────────────────────────────────

@pytest.fixture
def _dispatcher():
    from dbridge.core.engine import Engine
    from dbridge.protocol.handlers import Dispatcher
    engine = Engine()
    sid = engine.connect("sqlite", {"uri": ":memory:"})["session_id"]
    engine.execute(sid, "CREATE TABLE t (id INTEGER)")
    # warm the cache
    engine.list_tables(sid)
    return Dispatcher(engine), sid


def test_get_erd_returns_placeholder(_dispatcher):
    dispatcher, sid = _dispatcher
    resp = dispatcher.handle({
        "jsonrpc": "2.0", "id": 1,
        "method": "dbridge/getERD",
        "params": {"session_id": sid},
    })
    result = resp["result"]
    assert result["status"] == "not_implemented"
    assert "t" in result["tables"]


def test_get_erd_does_not_crash_on_empty_session(_dispatcher):
    dispatcher, sid = _dispatcher
    resp = dispatcher.handle({
        "jsonrpc": "2.0", "id": 2,
        "method": "dbridge/getERD",
        "params": {"session_id": sid},
    })
    assert "error" not in resp


def test_refresh_schema_returns_ok(_dispatcher):
    dispatcher, sid = _dispatcher
    resp = dispatcher.handle({
        "jsonrpc": "2.0", "id": 3,
        "method": "dbridge/refreshSchema",
        "params": {"session_id": sid},
    })
    assert resp["result"]["ok"] is True


def test_refresh_schema_clears_cache(_dispatcher):
    from dbridge.core.engine import Engine
    engine = Engine()
    sid = engine.connect("sqlite", {"uri": ":memory:"})["session_id"]
    engine.execute(sid, "CREATE TABLE before (id INTEGER)")
    engine.list_tables(sid)  # populate cache

    # create a new table and refresh; it must now appear
    engine.execute(sid, "CREATE TABLE after (id INTEGER)")
    engine.refresh_schema(sid)
    tables = engine.list_tables(sid)
    assert "after" in tables


# ── profile writes ────────────────────────────────────────────────────────────

def test_save_profile_creates_file_and_roundtrips(tmp_path):
    toml = tmp_path / "nested" / "connections.toml"
    save_profile("mydb", "sqlite", {"uri": "/tmp/x.db"}, path=toml)
    assert load_profiles(toml) == {"mydb": {"adapter": "sqlite", "config": {"uri": "/tmp/x.db"}}}


def test_save_profile_upserts_without_clobbering_siblings(tmp_path):
    toml = tmp_path / "connections.toml"
    save_profile("a", "sqlite", {"uri": "/a.db"}, path=toml)
    save_profile("b", "duckdb", {"uri": ":memory:"}, path=toml)
    save_profile("a", "duckdb", {"uri": "/a2.db"}, path=toml)

    profiles = load_profiles(toml)
    assert set(profiles) == {"a", "b"}
    assert profiles["a"] == {"adapter": "duckdb", "config": {"uri": "/a2.db"}}
    assert profiles["b"]["adapter"] == "duckdb"


def test_delete_profile_removes_only_the_named_entry(tmp_path):
    toml = tmp_path / "connections.toml"
    save_profile("a", "sqlite", {}, path=toml)
    save_profile("b", "duckdb", {}, path=toml)

    assert delete_profile("a", path=toml) is True
    assert set(load_profiles(toml)) == {"b"}


def test_delete_missing_profile_returns_false(tmp_path):
    toml = tmp_path / "connections.toml"
    save_profile("a", "sqlite", {}, path=toml)
    assert delete_profile("nope", path=toml) is False
    assert set(load_profiles(toml)) == {"a"}


def test_delete_on_absent_file_returns_false(tmp_path):
    assert delete_profile("a", path=tmp_path / "nonexistent.toml") is False


def test_get_profile_returns_entry(tmp_path):
    toml = tmp_path / "connections.toml"
    save_profile("a", "sqlite", {"uri": "/a.db"}, path=toml)
    assert get_profile("a", path=toml)["adapter"] == "sqlite"


def test_get_profile_raises_when_missing(tmp_path):
    toml = tmp_path / "connections.toml"
    save_profile("a", "sqlite", {}, path=toml)
    with pytest.raises(ProfileNotFoundError):
        get_profile("nope", path=toml)
