# 052 - Survive a malformed or truncated protocol frame

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Observed while raising test coverage ([archived change](../../openspec/changes/archive/2026-09-12-raise-test-coverage/proposal.md)).

## Problem / opportunity

`read_message` in
[transport/stdio.py](../../src/dbridge/protocol/transport/stdio.py) reads exactly
`Content-Length` bytes and calls `json.loads` on the result with no guard. A
frame whose body is shorter than its declared length, or whose body is not valid
JSON, raises `json.JSONDecodeError`. Nothing catches it: it propagates out of
`read_message`, out of `StdioTransport.serve`'s loop, and terminates the server
process. The client sees its child exit rather than an error response.

Evidence:

```console
$ python -c "
import io
from dbridge.protocol.transport.stdio import read_message
read_message(io.BytesIO(b'Content-Length: 100\r\n\r\n{\"jsonrpc\"'))"
json.decoder.JSONDecodeError: Expecting ':' delimiter: line 1 column 11 (char 10)
```

`Dispatcher.handle` already degrades gracefully for a well-formed frame carrying
a semantically invalid request, returning `INVALID_REQUEST`. The gap is one
layer below, in framing. `PARSE_ERROR` (-32700) is defined for exactly this case
and is currently never emitted (see [050](050-unused-dsp-error.md)).

## Desired outcome

A malformed or truncated frame is reported rather than fatal. Decide the
behavior deliberately, since the options differ for a stream client: emit a
`PARSE_ERROR` response and attempt to resynchronize, or log and close the
connection cleanly. Resynchronization after a wrong `Content-Length` is not
generally possible — the stream offset is already lost — so "close cleanly with
a diagnostic" may be the honest answer.

Whatever is chosen must preserve byte-based framing and keep stdout reserved for
protocol frames.

## Notes and references

[transport/stdio.py](../../src/dbridge/protocol/transport/stdio.py),
[protocol/errors.py](../../src/dbridge/protocol/errors.py) (`PARSE_ERROR`).
`tests/protocol/test_framing.py::test_truncated_body_currently_raises` pins the
current behavior and changes with the fix. Low practical urgency while the only
client is a trusted local child process; it matters more for
[network transports](022-transport-selection.md).
