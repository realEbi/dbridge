# 041 - Serve remote clients over TCP

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Original design 4; retained from revision `80d71d4`.

## Problem / opportunity

The original design proposed TCP for remote clients and testing; only stdio currently exists.

## Desired outcome

Define authenticated, protected network access and Session ownership before adding the transport.

## Notes and references

Coordinate [transport selection](022-transport-selection.md) and [concurrent execution](012-concurrent-execution.md).
