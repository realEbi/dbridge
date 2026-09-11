# 040 - Serve local clients over Unix sockets

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Original design 4; retained from revision `80d71d4`.

## Problem / opportunity

The original design proposed Unix sockets for local clients; only stdio currently exists.

## Desired outcome

Add a local socket transport with explicit ownership, permissions, connection lifecycle, and framing.

## Notes and references

Depends on decisions in [transport selection](022-transport-selection.md). Preserve the transport-independent Core Engine.
