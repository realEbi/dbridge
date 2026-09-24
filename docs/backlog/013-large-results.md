# 013 - Retrieve large results with bounded fetching

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.2 and question 2; original design streaming goals; retained from revision `80d71d4`.

## Problem / opportunity

SQLite and DuckDB now fetch at most one row beyond the response cap, and the
executor returns only the capped result. Client pagination only pages through
that truncated result, not the full query. There is no protocol for retrieving
rows beyond the cap.

## Desired outcome

Choose streaming batches, server-side cursors, pagination, or a combination. Define ordering, row-count meaning, backpressure, resource lifetime, truncation, and cancellation.

## Notes and references

Open question retained: client pagination versus server-side cursors.
Bounded fetching without changing the wire shape shipped in
[056](056-bounded-result-fetch.md), through
[bound-result-fetch](../../openspec/changes/archive/2026-09-24-bound-result-fetch/proposal.md).
It reads at most `max_rows + 1` rows to detect truncation and releases capped
statements before replying. This item keeps the undecided delivery model for
rows beyond the cap. Coordinate [concurrency](012-concurrent-execution.md),
[notifications](010-server-notifications.md), and [cancellation](009-query-cancellation.md).

The execution model is decided in [ADR-0003](../adr/0003-async-orchestration.md):
async orchestration with Adapter-owned database concurrency. Cancellation now
exists; future delivery must preserve its request isolation and per-Session
ordering. Neither that decision nor bounded fetching chooses streaming,
server-side cursors, or pagination.
