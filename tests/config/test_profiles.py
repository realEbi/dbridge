"""Unit tests for config/profiles.py and the getERD / refreshSchema handlers."""
import textwrap
from pathlib import Path

import pytest

from dbridge.config.profiles import load_profiles


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
