# 022 - Choose transport and process topology

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design question 1 (high priority in the legacy backlog); retained from revision `80d71d4`.

## Problem / opportunity

Only stdio is implemented. The original design left one transport per process versus several simultaneous transports unresolved.

## Desired outcome

Choose process/client ownership, Session isolation, startup selection, and connection lifecycle before adding remote or multiple-client transport modes.

## Notes and references

Coordinate [concurrency](012-concurrent-execution.md), [Unix sockets](040-unix-socket-transport.md), [TCP](041-tcp-transport.md), and [WebSocket](026-websocket-transport.md).
