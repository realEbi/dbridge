import io

from dbridge.protocol.transport.stdio import read_message, write_message


def test_round_trip():
    buf = io.BytesIO()
    write_message(buf, {"jsonrpc": "2.0", "id": 1, "method": "dbridge/ping", "params": {}})
    buf.seek(0)
    msg = read_message(buf)
    assert msg["method"] == "dbridge/ping"


def test_eof_returns_none():
    buf = io.BytesIO(b"")
    assert read_message(buf) is None
