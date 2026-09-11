"""Fixtures shared across the suite.

Every fixture here isolates state: Profile files go to tmp_path rather than the
real ~/.config/dbridge, and Sessions use in-memory SQLite so no test touches a
database on disk.
"""
import pytest

from dbridge.config import profiles
from dbridge.core.engine import Engine


@pytest.fixture
def isolated_profiles(tmp_path, monkeypatch):
    """Point the profiles module at a temp connections.toml instead of ~/.config."""
    toml = tmp_path / "connections.toml"
    monkeypatch.setattr(profiles, "_profiles_path", lambda: toml)
    return toml


@pytest.fixture
def engine():
    """A bare Engine with no Session."""
    return Engine()


@pytest.fixture
def engine_session(engine):
    """An Engine plus a connected in-memory SQLite Session id."""
    session_id = engine.connect("sqlite", {"uri": ":memory:"})["session_id"]
    return engine, session_id
