"""The optional MySQL driver must never prevent other Adapters from serving."""

import subprocess
import sys

import pytest

from dbridge.protocol import errors
from dbridge.protocol.handlers import Dispatcher


@pytest.mark.parametrize("dependency", ["aiomysql", "cryptography"])
async def test_missing_mysql_extra_returns_error_and_sqlite_still_connects(
    engine, monkeypatch, dependency,
):
    # Simulate an absent extra even when the local MySQL test environment has it.
    monkeypatch.delitem(sys.modules, "dbridge.adapters.mysql", raising=False)
    monkeypatch.setitem(sys.modules, dependency, None)
    dispatcher = Dispatcher(engine)
    response = await dispatcher.handle({
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
        "params": {"adapter": "mysql", "config": {"user": "test"}},
    })
    assert response["error"]["code"] == errors.ADAPTER_NOT_SUPPORTED
    assert "dbridge[mysql]" in response["error"]["message"]
    assert engine.sessions.ids() == ()

    response = await dispatcher.handle({
        "jsonrpc": "2.0", "id": 2, "method": "dbridge/connect",
        "params": {"adapter": "sqlite", "config": {"uri": ":memory:"}},
    })
    assert response["result"]["dialect"] == "sqlite"


def test_registry_loads_without_importing_mysql_driver():
    # A fresh interpreter catches accidental eager imports despite pytest's cache.
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
from dbridge.adapters.registry import INSTALLED_ADAPTERS
assert 'mysql' in INSTALLED_ADAPTERS
assert 'dbridge.adapters.mysql' not in sys.modules
assert 'aiomysql' not in sys.modules
assert 'cryptography' not in sys.modules
"""],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
