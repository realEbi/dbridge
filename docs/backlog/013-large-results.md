# 013 - Retrieve large results with bounded fetching

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.2 and question 2; original design streaming goals; retained from revision `80d71d4`.

## Problem / opportunity

Adapters fetch all rows before the executor caps the response. Client pagination only pages through the truncated result, not the full query.

## Desired outcome

Choose streaming batches, server-side cursors, pagination, or a combination. Define ordering, row-count meaning, backpressure, resource lifetime, truncation, and cancellation.

## Notes and references

Open question retained: client pagination versus server-side cursors.
Fetching no more than the row cap, without changing the wire shape, is split out
to [056](056-bounded-result-fetch.md); this item keeps the delivery model for rows
beyond the cap. Coordinate [concurrency](012-concurrent-execution.md), [notifications](010-server-notifications.md), and [cancellation](009-query-cancellation.md).

The execution model is decided in [ADR-0003](../adr/0003-async-orchestration.md):
async orchestration with Adapter-owned database concurrency. Cancellation now
exists; future delivery must preserve its request isolation and per-Session
ordering. The current row cap still applies after full materialization. This
decision does not choose streaming, server-side cursors, or pagination.
