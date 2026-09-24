# 052 - Survive a malformed or truncated protocol frame

- Repo: dbridge
- Status: done
- Change: [server](../../openspec/changes/archive/2026-09-24-adopt-async-orchestration/proposal.md)
- Origin: Observed while raising test coverage ([archived change](../../openspec/changes/archive/2026-09-12-raise-test-coverage/proposal.md)).

## Problem / opportunity

Before this change, `read_message` in
[transport/stdio.py](../../src/dbridge/protocol/transport/stdio.py) read exactly
`Content-Length` bytes and called `json.loads` without a guard. A frame whose
body was shorter than its declared length, or whose body was not valid JSON,
raised `json.JSONDecodeError`. It propagated out of `read_message` and
`StdioTransport.serve`, terminating the server process. The client saw its child
exit rather than an error response.

Historical reproduction before the fix:

```console
$ python -c "
import io
from dbridge.protocol.transport.stdio import read_message
read_message(io.BytesIO(b'Content-Length: 100\r\n\r\n{\"jsonrpc\"'))"
json.decoder.JSONDecodeError: Expecting ':' delimiter: line 1 column 11 (char 10)
```

`Dispatcher.handle` already returned `INVALID_REQUEST` for well-framed but
semantically invalid requests. The missing handling was one layer below, in
framing. `PARSE_ERROR` (-32700) was defined for exactly this case
but was not emitted (see [050](050-unused-dsp-error.md)).

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
The old `test_truncated_body_currently_raises` regression is replaced by explicit
recoverable/fatal framing tests. Complete invalid UTF-8 JSON receives
`PARSE_ERROR` and the next request is served; invalid or missing lengths and
truncated bodies log a diagnostic and take the bounded shutdown path. stdout
remains reserved for framed replies. In-process and subprocess checks verify
recovery, diagnostics, complete frames, and clean exit; the linked change is archived.
The same distinction remains relevant to future
[network transports](022-transport-selection.md).
