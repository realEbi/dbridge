# 035 - Build a browser client

- Repo: New client repository
- Status: deferred
- Change: none
- Origin: Original design 19; retained from revision `80d71d4`.

## Problem / opportunity

The original vision included a web UI, with React/TypeScript suggested as an implementation option.

## Desired outcome

Provide a browser-based database client using the server protocol, keeping database behavior in the server.

## Notes and references

Depends on a suitable authenticated transport, such as [WebSocket](026-websocket-transport.md). The UI stack remains a design choice.
