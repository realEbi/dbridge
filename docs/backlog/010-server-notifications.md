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
