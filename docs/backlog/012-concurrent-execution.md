# 012 - Evolve the synchronous core for concurrent work

- Repo: dbridge
- Status: done
- Change: [server](../../openspec/changes/archive/2026-09-24-adopt-async-orchestration/proposal.md)
- Origin: Legacy backlog 4.2; original design 3-6; retained from revision `80d71d4`.

## Problem / opportunity

The Phase 1 server blocked the stdio request loop during each query even though
multiple Sessions could exist. The original vision called for an async,
transport-independent Core Engine.

## Desired outcome

Choose async orchestration, worker isolation, or another justified model; define per-Session ordering, driver/thread ownership, responsiveness, and shutdown. Preserve a compatible stdio path.

## Notes and references

[ADR-0003](../adr/0003-async-orchestration.md) now supersedes ADR-0001.
Async orchestration, Adapter-owned lanes, per-Session execute ordering, request
cancellation, and bounded shutdown are implemented. DuckDB uses a sibling
metadata cursor; SQLite uses one Lane and serves cache hits directly on the loop.
Verified by 519 server tests on Python 3.11 and 3.12 (96.58% coverage) and the
linked client integration. The archived change records scenario-by-scenario evidence.

[Transport selection](022-transport-selection.md) and
[large-result delivery](013-large-results.md) remain separate work.
