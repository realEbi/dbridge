# 009 - Cancel an in-flight query

- Repo: dbridge, clients
- Status: done
- Change: [server](../../openspec/changes/archive/2026-09-24-adopt-async-orchestration/proposal.md); [dbridge.nvim](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-24-cancel-outstanding-query)
- Origin: Legacy backlog 3.2 and 4.2; retained from revision `80d71d4`.

## Problem / opportunity

The Phase 1 server reserved QUERY_CANCELLED (-32004) without a cancel method or
outstanding-request tracking. Its synchronous transport could not read a cancel
while executing a query.

## Desired outcome

Define query identity, cancellation races, adapter interruption, cleanup, and client feedback; provide a control path that stays responsive during execution.

## Notes and references

The server now accepts `$/cancelRequest`, isolates cancellation by request id,
removes queued work, and interrupts running SQLite/DuckDB jobs. Cancelled work
returns `QUERY_CANCELLED`; Sessions remain usable and earlier statements' effects
are retained. The linked client change owns `:DbridgeCancel` and its presentation.
Verified with the Neovim Client on SQLite and DuckDB: `:DbridgeCancel` reports
cancellation without replacing displayed results, the same Session executes again,
and DuckDB completion remains responsive during a long query. Both linked changes
are archived; the client suite passed 176 cases.

[Notifications](010-server-notifications.md) and
[large results](013-large-results.md) remain separate work.
