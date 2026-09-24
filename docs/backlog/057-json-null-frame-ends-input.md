# 057 - Distinguish a JSON null body from end of input

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Read-only protocol review during [adopt-async-orchestration](../../openspec/changes/archive/2026-09-24-adopt-async-orchestration/proposal.md); inherited from the preceding synchronous Transport.

## Problem / opportunity

`read_message` returns Python `None` both for end of input and for a complete
frame containing the valid JSON value `null`. The Transport uses `None` as its
end-of-input marker, so that body silently starts shutdown and discards following
requests. Although `null` is not a valid JSON-RPC request object, it is a fully
delimited JSON body and should not be confused with a closed channel.

Reproduced by sending `Content-Length: 4\r\n\r\nnull` followed by a framed
`dbridge/listProfiles` request with id 7, then closing stdin. The subprocess
exited with status 0, empty stdout, and no stderr diagnostic: neither the invalid
request nor the subsequent valid request received a reply. The previous
synchronous implementation used the same `None` sentinel, so this is an inherited
defect, separate from the async migration's framing recovery.

## Desired outcome

Use a distinct end-of-input result so every decoded JSON value reaches request
validation. A `null` frame should receive `INVALID_REQUEST` with a null id, and a
following valid request should still receive its normal response. Preserve EOF
shutdown, byte-based framing, and cancellation behavior.

## Notes and references

Inspect [stdio framing and Transport](../../src/dbridge/protocol/transport/stdio.py)
and [request validation](../../src/dbridge/protocol/handlers.py). Add a regression
covering `null` followed by a valid frame when this work is selected. Other invalid
JSON-RPC body shapes should likewise remain distinguishable from EOF.
