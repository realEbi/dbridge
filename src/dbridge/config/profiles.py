"""Load/save/delete connection profiles in connections.toml.

File format:
    [connections.mydb]
    adapter = "sqlite"
    [connections.mydb.config]
    uri = "/path/to/db.sqlite"

Returns a dict mapping profile name → {"adapter": str, "config": dict}.
A missing file yields an empty dict (not an error).
"""
from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

import tomli_w


class ProfileNotFoundError(Exception):
    """Raised when a named profile is not present in connections.toml."""


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", Path.home())
    else:
        base = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    return Path(base) / "dbridge"


def _profiles_path() -> Path:
    return _config_dir() / "connections.toml"


def _read_raw(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text())
    except FileNotFoundError:
        return {}


def load_profiles(path: Path | None = None) -> dict[str, dict]:
    """Return {name: {adapter, config}} from connections.toml; {} if file absent."""
    if path is None:
        path = _profiles_path()
    connections = _read_raw(path).get("connections", {})
    profiles = {}
    for name, entry in connections.items():
        if "adapter" not in entry:
            continue
        config = entry.get("config", {})
        # A hand-edited or legacy file can carry a non-table config — an early
        # client wrote `config = []` for an empty config, because Lua encodes an
        # empty table as a JSON array. Normalize rather than hand a list to an
        # adapter that expects a mapping.
        if not isinstance(config, dict):
            config = {}
        profiles[name] = {"adapter": entry["adapter"], "config": config}
    return profiles


def save_profile(name: str, adapter: str, config: dict, path: Path | None = None) -> None:
    """Upsert a profile entry in connections.toml."""
    if path is None:
        path = _profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_raw(path)
    data.setdefault("connections", {})[name] = {"adapter": adapter, "config": config}
    path.write_bytes(tomli_w.dumps(data).encode())


def delete_profile(name: str, path: Path | None = None) -> bool:
    """Remove a profile by name. Returns True if it existed."""
    if path is None:
        path = _profiles_path()
    data = _read_raw(path)
    connections = data.get("connections", {})
    if name not in connections:
        return False
    del connections[name]
    data["connections"] = connections
    path.write_bytes(tomli_w.dumps(data).encode())
    return True


def get_profile(name: str, path: Path | None = None) -> dict:
    """Return a single profile by name, or raise ProfileNotFoundError."""
    profiles = load_profiles(path)
    if name not in profiles:
        raise ProfileNotFoundError(name)
    return profiles[name]
