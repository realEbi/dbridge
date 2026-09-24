# 010 - Deliver server-to-client notifications

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Legacy backlog 3.3; retained from revision `80d71d4`.

## Problem / opportunity

The server emits request responses only. The legacy client report says dispatch_response drops messages without an id.

## Desired outcome

Define and handle progress and log notifications, including correlation, ordering, and schema-change events if adopted.

## Notes and references

Inspect [stdio transport](../../src/dbridge/protocol/transport/stdio.py) and each affected client. Supports [large results](013-large-results.md).

[ADR-0003](../adr/0003-async-orchestration.md) decides the execution model: one
asyncio loop keeps intake responsive while Adapter-owned work runs. Server replies
can arrive out of order and remain correlated by request id. `$/cancelRequest` is
a client-to-server notification; it adds no server-to-client progress or log
messages and does not resolve this item.
