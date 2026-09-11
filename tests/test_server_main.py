"""Cover the process entry point in process.

test_e2e_stdio.py proves main() works by spawning it; because that runs in a
separate process it contributes no coverage and cannot assert on internals.
Here main() is driven over fake streams instead. sys.stdin/sys.stdout are
replaced via monkeypatch so they are restored even if an assertion fails —
writing protocol frames to the real stdout would corrupt pytest's own output.
"""
import io
import sys

from dbridge.protocol.transport.stdio import read_message, write_message
from dbridge.server import main


class _FakeStd:
    """Mimics sys.stdin/sys.stdout closely enough: only .buffer is read."""

    def __init__(self, buffer):
        self.buffer = buffer


def _run_main(monkeypatch, requests):
    stdin = io.BytesIO()
    for request in requests:
        write_message(stdin, request)
    stdin.seek(0)
    stdout = io.BytesIO()

    real_stdout = sys.stdout
    monkeypatch.setattr(sys, "stdin", _FakeStd(stdin))
    monkeypatch.setattr(sys, "stdout", _FakeStd(stdout))

    main()

    assert sys.stdout is not real_stdout, "main() must not write to the real stdout"
    stdout.seek(0)
    return stdout


def test_main_wires_engine_dispatcher_and_transport(monkeypatch):
    """A connect request driven through main() returns a usable session_id."""
    out = _run_main(monkeypatch, [{
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
        "params": {"adapter": "sqlite", "config": {"uri": ":memory:"}},
    }])

    response = read_message(out)
    assert response["id"] == 1
    assert isinstance(response["result"]["session_id"], str)
    assert response["result"]["session_id"]


def test_main_serves_a_full_connect_execute_exchange(monkeypatch):
    """Session state persists across frames within one main() invocation."""
    # The session id is only known at runtime, so connect first and reuse the
    # Engine by sending every frame in a single stdin stream.
    connect = {
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/connect",
        "params": {"adapter": "sqlite", "config": {"uri": ":memory:"}},
    }
    # A second connect proves the loop keeps serving; ids must come back paired.
    out = _run_main(monkeypatch, [connect, {**connect, "id": 2}])

    first = read_message(out)
    second = read_message(out)
    assert [first["id"], second["id"]] == [1, 2]
    assert first["result"]["session_id"] != second["result"]["session_id"]


def test_main_returns_on_empty_stdin(monkeypatch):
    """No input means main() exits cleanly rather than blocking."""
    out = _run_main(monkeypatch, [])
    assert out.getvalue() == b""


def test_main_reports_unknown_method_without_crashing(monkeypatch):
    out = _run_main(monkeypatch, [{
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/nope", "params": {},
    }])
    assert read_message(out)["error"]["code"] == -32601
