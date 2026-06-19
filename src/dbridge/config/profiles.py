"""Load connection profiles from connections.toml.

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


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", Path.home())
    else:
        base = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    return Path(base) / "dbridge"


def load_profiles(path: Path | None = None) -> dict[str, dict]:
    """Return {name: {adapter, config}} from connections.toml; {} if file absent."""
    if path is None:
        path = _config_dir() / "connections.toml"
    try:
        data = tomllib.loads(path.read_text())
    except FileNotFoundError:
        return {}
    connections = data.get("connections", {})
    return {
        name: {"adapter": entry["adapter"], "config": entry.get("config", {})}
        for name, entry in connections.items()
        if "adapter" in entry
    }
