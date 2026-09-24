import io

import pytest

from dbridge.protocol.transport.stdio import FrameError, read_message, write_message


def test_round_trip():
    buf = io.BytesIO()
    write_message(buf, {"jsonrpc": "2.0", "id": 1, "method": "dbridge/ping", "params": {}})
    buf.seek(0)
    msg = read_message(buf)
    assert msg["method"] == "dbridge/ping"


def test_eof_returns_none():
    buf = io.BytesIO(b"")
    assert read_message(buf) is None


def test_content_length_is_byte_length_not_character_length():
    """Framing is byte-based: a multi-byte body must declare its encoded length."""
    buf = io.BytesIO()
    write_message(buf, {"jsonrpc": "2.0", "id": 1, "method": "dbridge/execute",
                        "params": {"sql": "SELECT 'né'"}})
    raw = buf.getvalue()
    header, body = raw.split(b"\r\n\r\n", 1)
    declared = int(header.split(b":", 1)[1])
    assert declared == len(body)
    buf.seek(0)
    assert read_message(buf)["params"]["sql"] == "SELECT 'né'"


def test_other_headers_before_content_length_are_skipped():
    """The reader loops over header lines; only Content-Length is significant."""
    body = b'{"jsonrpc":"2.0","id":7,"method":"dbridge/ping","params":{}}'
    raw = (
        b"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"\r\n" + body
    )
    assert read_message(io.BytesIO(raw))["id"] == 7


def test_content_length_header_is_matched_case_insensitively():
    body = b'{"jsonrpc":"2.0","id":8,"method":"dbridge/ping","params":{}}'
    raw = b"CONTENT-LENGTH: " + str(len(body)).encode() + b"\r\n\r\n" + body
    assert read_message(io.BytesIO(raw))["id"] == 8


def test_header_block_without_content_length_is_fatal():
    """Headers that end without a Content-Length yield None rather than hanging."""
    raw = b"Content-Type: application/json\r\n\r\n"
    assert read_message(io.BytesIO(raw)) == FrameError("missing Content-Length", True)


def test_truncated_body_is_fatal():
    raw = b'Content-Length: 100\r\n\r\n' + b'{"jsonrpc"'
    assert read_message(io.BytesIO(raw)) == FrameError("truncated frame body", True)


@pytest.mark.parametrize("length", [b"nope", b"-1", b"1.5"])
def test_invalid_content_length_is_fatal(length):
    error = read_message(io.BytesIO(b"Content-Length: " + length + b"\r\n\r\n"))
    assert isinstance(error, FrameError) and error.fatal


@pytest.mark.parametrize("body", [b"{", b"\xff"])
def test_unparseable_body_preserves_next_frame(body):
    stream = io.BytesIO(b"Content-Length: 1\r\n\r\n" + body)
    stream.seek(0, 2)
    write_message(stream, {"id": 7, "result": "café"})
    stream.seek(0)
    assert read_message(stream) == FrameError("frame body is not valid UTF-8 JSON", False)
    assert read_message(stream)["result"] == "café"


def test_short_reads_are_accumulated_by_byte_length():
    class ShortReads(io.BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 2))
    body = '{"result":"☕"}'.encode()
    stream = ShortReads(b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
    assert read_message(stream) == {"result": "☕"}


def test_two_messages_read_sequentially_from_one_stream():
    buf = io.BytesIO()
    write_message(buf, {"jsonrpc": "2.0", "id": 1, "method": "a", "params": {}})
    write_message(buf, {"jsonrpc": "2.0", "id": 2, "method": "b", "params": {}})
    buf.seek(0)
    assert read_message(buf)["method"] == "a"
    assert read_message(buf)["method"] == "b"
    assert read_message(buf) is None
