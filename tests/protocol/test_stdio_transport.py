"""Drive StdioTransport.serve in process.

The end-to-end tests exercise this loop through a spawned server, which proves
the real wiring but cannot reach cases like "EOF mid-stream" or "dispatcher
returns None". Those are covered here against controlled streams.
"""
import io

from dbridge.protocol.transport.stdio import StdioTransport, read_message, write_message


class _RecordingDispatcher:
    """Stands in for Dispatcher: records requests, returns a canned response."""

    def __init__(self, response=None):
        self.seen = []
        self._response = response

    def handle(self, request):
        self.seen.append(request)
        if self._response is None:
            return None
        return {**self._response, "id": request.get("id")}


def _serve(monkeypatch, payloads, dispatcher):
    """Run serve() over a stdin built from *payloads*; return captured stdout."""
    stdin = io.BytesIO()
    for payload in payloads:
        write_message(stdin, payload)
    stdin.seek(0)
    stdout = io.BytesIO()

    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": stdin})())
    monkeypatch.setattr("sys.stdout", type("S", (), {"buffer": stdout})())

    StdioTransport().serve(dispatcher)
    stdout.seek(0)
    return stdout


def test_request_gets_a_response_frame(monkeypatch):
    dispatcher = _RecordingDispatcher({"jsonrpc": "2.0", "result": {"ok": True}})
    out = _serve(
        monkeypatch,
        [{"jsonrpc": "2.0", "id": 1, "method": "dbridge/ping", "params": {}}],
        dispatcher,
    )

    response = read_message(out)
    assert response == {"jsonrpc": "2.0", "result": {"ok": True}, "id": 1}
    assert read_message(out) is None, "exactly one frame expected"
    assert [r["method"] for r in dispatcher.seen] == ["dbridge/ping"]


def test_notification_produces_no_output(monkeypatch):
    """A dispatcher returning None must write nothing, not an empty frame."""
    dispatcher = _RecordingDispatcher(None)
    out = _serve(
        monkeypatch,
        [{"jsonrpc": "2.0", "method": "dbridge/notify", "params": {}}],
        dispatcher,
    )

    assert out.getvalue() == b""
    assert len(dispatcher.seen) == 1


def test_multiple_requests_are_served_in_order(monkeypatch):
    dispatcher = _RecordingDispatcher({"jsonrpc": "2.0", "result": {}})
    out = _serve(
        monkeypatch,
        [
            {"jsonrpc": "2.0", "id": 1, "method": "a", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "b", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "c", "params": {}},
        ],
        dispatcher,
    )

    assert [read_message(out)["id"] for _ in range(3)] == [1, 2, 3]
    assert [r["method"] for r in dispatcher.seen] == ["a", "b", "c"]


def test_eof_ends_the_loop(monkeypatch):
    """serve() returns on EOF instead of spinning; an empty stdin serves nothing."""
    dispatcher = _RecordingDispatcher({"jsonrpc": "2.0", "result": {}})
    out = _serve(monkeypatch, [], dispatcher)

    assert out.getvalue() == b""
    assert dispatcher.seen == []


def test_mixed_requests_and_notifications(monkeypatch):
    """Only the request gets a frame back; the notification is silent."""

    class _Mixed:
        def handle(self, request):
            if request.get("id") is None:
                return None
            return {"jsonrpc": "2.0", "id": request["id"], "result": request["method"]}

    out = _serve(
        monkeypatch,
        [
            {"jsonrpc": "2.0", "method": "note", "params": {}},
            {"jsonrpc": "2.0", "id": 9, "method": "ask", "params": {}},
        ],
        _Mixed(),
    )

    assert read_message(out) == {"jsonrpc": "2.0", "id": 9, "result": "ask"}
    assert read_message(out) is None
