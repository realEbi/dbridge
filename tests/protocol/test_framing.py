import io
import json

import pytest

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


def test_header_block_without_content_length_returns_none():
    """Headers that end without a Content-Length yield None rather than hanging."""
    raw = b"Content-Type: application/json\r\n\r\n"
    assert read_message(io.BytesIO(raw)) is None


def test_truncated_body_currently_raises():
    """A frame whose body is shorter than its Content-Length raises.

    This pins *current* behavior, not desired behavior: the JSONDecodeError
    propagates out of read_message and through StdioTransport.serve, ending the
    server loop. Recorded as a backlog item; when that is addressed, this test
    changes with it.
    """
    raw = b"Content-Length: 100\r\n\r\n" + b'{"jsonrpc"'
    with pytest.raises(json.JSONDecodeError):
        read_message(io.BytesIO(raw))


def test_two_messages_read_sequentially_from_one_stream():
    buf = io.BytesIO()
    write_message(buf, {"jsonrpc": "2.0", "id": 1, "method": "a", "params": {}})
    write_message(buf, {"jsonrpc": "2.0", "id": 2, "method": "b", "params": {}})
    buf.seek(0)
    assert read_message(buf)["method"] == "a"
    assert read_message(buf)["method"] == "b"
    assert read_message(buf) is None
