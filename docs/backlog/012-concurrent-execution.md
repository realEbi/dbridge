# 012 - Evolve the synchronous core for concurrent work

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.2; original design 3-6; retained from revision `80d71d4`.

## Problem / opportunity

One query blocks the stdio request loop even though multiple Sessions may exist. The original vision called for an async, transport-independent Core Engine.

## Desired outcome

Choose async orchestration, worker isolation, or another justified model; define per-Session ordering, driver/thread ownership, responsiveness, and shutdown. Preserve a compatible stdio path.

## Notes and references

Revisit [ADR-0001](../adr/0001-sync-core-for-phase-1.md) through a superseding ADR. Coordinate [transport selection](022-transport-selection.md), cancellation, and large results.
