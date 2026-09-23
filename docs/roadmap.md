# Roadmap

This is the intended evolution of dbridge. It preserves the direction of the
original design while leaving implementation choices to scoped OpenSpec changes.
The [current architecture](architecture.md) describes what exists today.

The sections below are proposed milestones, not release commitments or an
approved execution queue. Work can proceed independently where dependencies
allow it. Detailed problems, open questions, ownership, and status live in
[individual backlog files](backlog/README.md); active tasks live in OpenSpec.

## Product direction

Provide a uniform database server for editor, terminal, and browser clients:
queries, schema browsing, SQL assistance, and relationship exploration through
one protocol. Keep the Transport / Core Engine / Adapters boundaries, put
database-specific behavior in Adapters, and keep presentation in clients.

The intended execution model supports responsive, concurrent work and bounded
result delivery. Async orchestration is a candidate from the original vision;
the driver strategy and migration design still need a decision. The stdio client
path should remain supported as the system evolves.

dbridge remains a query and introspection tool. ORM/query-builder behavior,
database migrations, database permission administration, and bulk ETL are outside
this direction. Clients continue to live in their own repositories.

## 1. Reliable daily use

Make the existing server/client path predictable: target the right Session and
table, preserve Profiles, refresh metadata, and execute the intended statement.

Key work includes [Profile renames](backlog/001-profile-rename.md),
[database hierarchies](backlog/003-database-hierarchy.md),
[cache coverage](backlog/004-introspection-cache-coverage.md),
[DuckDB constraints](backlog/005-duckdb-constraints.md),
[statement selection](backlog/006-statement-under-cursor.md), and
[Session dialect](backlog/008-session-dialect.md). The backlog also carries
completion and client presentation defects.

Progress is demonstrated by actual protocol and client scenarios, including
cross-repository integration when a user-visible flow spans both.

Local verification tooling now provides `make manual-prepare` for reusable sample
databases and `make test` / `make test-cov` for automated checks. See the
[manual guide](manual-testing-guide.md). Type and lint checks are clean and run
through `make check` and the existing CI matrix; repeated Adapter construction
also preserves one diagnostic handler. See the verified
[quality-check maintenance change](../openspec/changes/archive/2026-09-23-restore-server-quality-checks/).
Generated table queries now use server-provided quoted identifiers, preserving
SQLite namespaces and DuckDB catalog/schema identity, including literal dots and
quotes. See [002](backlog/002-qualified-identifiers.md) for both repository changes.
The remaining daily-use outcomes above remain open; dialect reporting and hierarchy
presentation are still separate work.

## 2. Responsive queries and larger results

Choose and implement the [concurrent execution model](backlog/012-concurrent-execution.md),
then introduce [large-result delivery](backlog/013-large-results.md),
[notifications](backlog/010-server-notifications.md), and
[cancellation](backlog/009-query-cancellation.md) with explicit resource lifetimes.
Resolve cursors versus pagination/streaming before standardizing the wire shape.

[Transactions](backlog/014-transactions.md),
[bound parameters](backlog/049-query-parameters.md), and
[active database/schema selection](backlog/048-session-scope-selection.md)
extend query control. They need their own behavioral decisions and do not all
depend on adopting asyncio. Revisit [ADR-0001](adr/0001-sync-core-for-phase-1.md)
when the execution model changes.

## 3. Broader database support

Bring [MySQL](backlog/019-mysql-adapter.md),
[PostgreSQL](backlog/020-postgres-adapter.md), and
[Snowflake](backlog/021-snowflake-adapter.md) onto the supported Adapter interface;
evaluate [BigQuery](backlog/042-bigquery-adapter.md) separately. Each adapter needs
real integration evidence, clear type/metadata limits, and dependency isolation.

Extend metadata where useful through [indexes](backlog/047-index-introspection.md)
and [functions](backlog/044-function-completion.md). Consider
[pooling](backlog/046-adapter-pooling.md) as driver/resource needs become concrete.

## 4. Richer SQL assistance

Completion now resolves [physical-table aliases](backlog/015-alias-completion.md)
within the cursor's SELECT scope, including after a SELECT comma. Extend it with
[derived and correlated sources](backlog/055-completion-derived-and-correlated-sources.md),
[unqualified SELECT targets](backlog/018-select-comma-completion.md),
[values](backlog/016-value-completion.md), and
[ranking](backlog/017-completion-ranking.md). Explore
[custom providers](backlog/025-completion-providers.md) using real needs such as
[dbt models](backlog/030-dbt-completion.md).

Build [ERDs](backlog/011-erd-extraction.md) from reliable constraint metadata,
choosing explicit table selection versus bounded FK expansion. Add
[structured EXPLAIN plans](backlog/032-explain-plans.md) for client visualization.

## 5. Additional transports and clients

First resolve [one versus multiple transports per process](backlog/022-transport-selection.md)
and client/Session ownership. Then add [Unix sockets](backlog/040-unix-socket-transport.md),
[TCP](backlog/041-tcp-transport.md), or [WebSocket](backlog/026-websocket-transport.md)
as a client needs them. Network exposure requires an authentication and protection
model; the WebSocket authentication question remains open.

The existing Neovim and TUI clients can evolve alongside prospective
[browser](backlog/035-web-client.md) and [VS Code](backlog/036-vscode-client.md)
clients. [Saved queries](backlog/007-saved-queries.md),
[history](backlog/031-query-history.md), and
[notebook-style execution](backlog/034-notebook-execution.md) are client-facing
opportunities whose server responsibilities must be explicit.

## 6. Remote operation and resource management

Resolve [secret-manager integration](backlog/023-secret-managers.md) and
[SSH tunnels](backlog/033-ssh-tunnels.md) as remote database use grows. Establish
a measured [remote introspection cache policy](backlog/024-remote-cache-policy.md),
then decide on [persistent caching](backlog/038-persistent-schema-cache.md) and
[DDL invalidation](backlog/043-ddl-cache-invalidation.md).

[Idle Session expiry](backlog/039-session-idle-timeout.md),
[persistent settings](backlog/045-settings-file.md), and
[observability](backlog/037-observability.md) complete the operational direction.
Original library choices and default values are candidates to reassess, not
promises about the current implementation.

## Keeping the roadmap current

When priorities or dependencies change, update the affected milestone and its
backlog links. When an outcome ships, update current architecture and behavior
specs, resolve its backlog item, and revise this document to show the remaining
direction. Mark a milestone complete only when its stated outcome is met; a
finished task or proposal alone is insufficient. Follow the document ownership
and completion rules in [AGENTS.md](../AGENTS.md#documentation-ownership).
