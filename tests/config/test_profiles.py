"""Unit tests for config/profiles.py and the getERD / refreshSchema handlers."""
import sys
import textwrap
from pathlib import Path

import pytest

from dbridge.config import profiles
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
async def _dispatcher(engine):
    from dbridge.protocol.handlers import Dispatcher
    sid = (await engine.connect("sqlite", {"uri": ":memory:"}))["session_id"]
    await engine.execute(sid, "CREATE TABLE t (id INTEGER)")
    # warm the cache
    await engine.list_tables(sid, ("main",))
    return Dispatcher(engine), sid


async def test_get_erd_returns_placeholder(_dispatcher):
    dispatcher, sid = _dispatcher
    resp = await dispatcher.handle({
        "jsonrpc": "2.0", "id": 1,
        "method": "dbridge/getERD",
        "params": {"session_id": sid, "path": ["main"]},
    })
    result = resp["result"]
    assert result["status"] == "not_implemented"
    assert "t" in [entry["name"] for entry in result["tables"]]


async def test_get_erd_does_not_crash_on_empty_session(_dispatcher):
    dispatcher, sid = _dispatcher
    resp = await dispatcher.handle({
        "jsonrpc": "2.0", "id": 2,
        "method": "dbridge/getERD",
        "params": {"session_id": sid, "path": ["main"]},
    })
    assert "error" not in resp


async def test_refresh_schema_returns_ok(_dispatcher):
    dispatcher, sid = _dispatcher
    resp = await dispatcher.handle({
        "jsonrpc": "2.0", "id": 3,
        "method": "dbridge/refreshSchema",
        "params": {"session_id": sid},
    })
    assert resp["result"]["ok"] is True


async def test_refresh_schema_clears_cache(engine):
    sid = (await engine.connect("sqlite", {"uri": ":memory:"}))["session_id"]
    await engine.execute(sid, "CREATE TABLE before (id INTEGER)")
    await engine.list_tables(sid, ("main",))  # populate cache

    # create a new table and refresh; it must now appear
    await engine.execute(sid, "CREATE TABLE after (id INTEGER)")
    await engine.refresh_schema(sid)
    tables = await engine.list_tables(sid, ("main",))
    assert "after" in [entry["name"] for entry in tables]


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


def test_non_table_config_is_normalized(tmp_path):
    """An early client wrote `config = []`; it must not reach the adapter."""
    toml = tmp_path / "connections.toml"
    toml.write_text(textwrap.dedent("""\
        [connections.legacy]
        adapter = "sqlite"
        config = []
    """))
    assert load_profiles(toml) == {"legacy": {"adapter": "sqlite", "config": {}}}


# ── config directory resolution ───────────────────────────────────────────────
# These exercise _config_dir/_profiles_path without ever reading or writing the
# real ~/.config/dbridge: every case patches the environment or sys.platform.

def test_config_dir_honours_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert profiles._config_dir() == tmp_path / "dbridge"


def test_config_dir_falls_back_to_dot_config(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert profiles._config_dir() == tmp_path / ".config" / "dbridge"


def test_config_dir_uses_appdata_on_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert profiles._config_dir() == tmp_path / "dbridge"


def test_config_dir_falls_back_to_home_on_windows_without_appdata(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert profiles._config_dir() == tmp_path / "dbridge"


def test_profiles_path_is_connections_toml_in_the_config_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert profiles._profiles_path() == tmp_path / "dbridge" / "connections.toml"


def test_default_path_functions_are_used_when_no_path_is_given(monkeypatch, tmp_path):
    """load/save/delete with no explicit path go through _profiles_path()."""
    toml = tmp_path / "connections.toml"
    monkeypatch.setattr(profiles, "_profiles_path", lambda: toml)

    assert load_profiles() == {}
    save_profile("mem", "sqlite", {"uri": ":memory:"})
    assert load_profiles() == {"mem": {"adapter": "sqlite", "config": {"uri": ":memory:"}}}
    assert get_profile("mem")["adapter"] == "sqlite"
    assert delete_profile("mem") is True
    assert load_profiles() == {}


def test_entry_without_an_adapter_is_skipped(tmp_path):
    """A hand-edited file missing the adapter key must not yield a broken Profile."""
    toml = tmp_path / "connections.toml"
    toml.write_text(textwrap.dedent("""\
        [connections.broken]
        note = "no adapter here"
        [connections.fine]
        adapter = "sqlite"
    """))
    assert set(load_profiles(toml)) == {"fine"}
