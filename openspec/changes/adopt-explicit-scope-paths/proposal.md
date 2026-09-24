## Why

Introspection results cannot express where a table lives. `listTables` returns bare
strings, so a DuckDB Session with two attached catalogs lists `orders` twice with
nothing to distinguish the entries, completion offers both as identical items, and
a table listed from a non-default catalog completes to text that fails to execute
(`Catalog Error: Table with name shipments does not exist!`). Meanwhile
`getTableSchema` already speaks structured identity after
[qualified table identifiers](../archive/2026-09-23-qualify-generated-table-identifiers/proposal.md),
so listing and resolution now disagree about what an unscoped call means.

The fixed `database`/`schema` pair is the root cause. SQLite has one namespace level
and must fill both fields with the same value, so its structured metadata claims two
levels while its `sql_identifier` uses one, and clients render a redundant
`main/main` tier. Replacing that pair with an explicit, adapter-declared scope path
resolves four backlog items that are all the same seam viewed from different sides.

## What Changes

- **BREAKING** Introduce the **Scope Path**: an ordered sequence of container names
  locating a table inside an Adapter's declared hierarchy (`("main")` for SQLite,
  `("memory", "main")` for DuckDB). It replaces the fixed `database`/`schema` pair in
  `TableRef`, `TableSchema`, and the DSP request/response shapes.
- **BREAKING** Adapters declare their own **Scope Levels** — how many tiers exist and
  each tier's client-facing label. SQLite declares one level; DuckDB declares two.
  A client renders what the Adapter declares instead of assuming two tiers, which
  removes the `main/main` duplication at the data model rather than hiding it.
- **BREAKING** Every metadata operation takes an explicit Scope Path. Unscoped
  introspection is removed: `listSchemas`, `listTables`, `getTableSchema`, `getERD`,
  and `complete` all require one. The server holds no active scope; clients own that
  state and send it per request.
- **BREAKING** `dbridge/getTableSchema` drops the legacy dot-separated `fqn` string.
  One input shape remains, addressed by Scope Path plus table name.
- **BREAKING** `dbridge/connect` returns the Adapter's hierarchy (levels and a
  default Scope Path) and its SQL dialect alongside `session_id`, so a client can
  issue scoped calls immediately without a discovery round trip.
- **BREAKING** `dbridge/refreshSchema` re-delivers the hierarchy in its response and
  invalidates every cached introspection result, including database and schema
  listings that previously bypassed the cache.
- `listDatabases` and `listSchemas` entries gain a marker distinguishing
  engine-internal containers (DuckDB's `system`/`temp`, `information_schema`,
  `pg_catalog`) from user containers. They are flagged, not filtered.
- `listTables` entries carry an executable `sql_identifier`, removing a
  `getTableSchema` round trip per table and letting completion insert text that runs.
- Completion bounds table suggestions to the requested Scope Path, ending duplicate
  indistinguishable items. Explicitly qualified sources still resolve on their own
  terms; a source outside the requested scope inserts its qualified identifier.
- `Session.active_database` and `Session.active_schema` are removed. Nothing reads
  them today and `tests/core/test_session.py` pins them as permanently `None`.

## Capabilities

### New Capabilities

- `scope-addressing`: Addressing database metadata by explicit adapter-declared
  Scope Paths — hierarchy description and default scope, required scope on every
  introspection operation, engine-internal container marking, and unified cache
  and refresh semantics across all introspection results.
- `session-dialect`: Reporting a Session's SQL dialect to clients so they can apply
  dialect-specific syntax handling without inferring it from the Adapter name.

### Modified Capabilities

- `table-identifiers`: *Preserve compatibility and structured identity* is retired.
  Its two guarantees — that `listTables` continues returning strings and that
  `getTableSchema` continues accepting `fqn` — are both deliberately broken. Cached
  identity separation and `refreshSchema` invalidation survive, restated in terms of
  Scope Paths. *Return executable table identifiers* keeps its guarantee but its
  structured shape becomes a Scope Path, ending the SQLite arity contradiction.
- `sql-completion`: `dbridge/complete` gains a required Scope Path. Table
  suggestions become scope-bounded, and insertion text for a source outside the
  requested scope becomes its qualified identifier. Cursor offset handling,
  completion item fields, and SELECT-scope isolation are unchanged.

## Impact

**Repositories.** This change owns server behavior and the DSP contract. It breaks
6 of the 13 documented RPCs, so `dbridge.nvim` must move in lockstep with a linked
client change; the client reads `.database`/`.schema` and calls the affected methods
today. Nothing here authorizes editing that repository — the client change is its
own proposal, and the shared flow needs integration verification against a DuckDB
Session with an attached catalog and a SQLite Session with an attached namespace.

**Protocol compatibility.** No compatibility shims and no versioned fallback. The
`dbridge-2.0` line accepts breaking protocol changes, and the additive dual-input
path added for `getTableSchema` is itself part of the confusion being removed.

**Code.** `adapters/base.py` (`TableRef`, `TableSchema`, new hierarchy declaration),
both shipped adapters, `core/engine.py`, `core/schema_registry.py` (cache keys become
scope tuples; listings move into the registry), `core/session.py` (fields removed),
`protocol/handlers.py`, and `core/completion.py`. Roughly 103 test call sites across
9 files. `adapters/_parked/` stays parked and unregistered.

**Documentation.** README method table, `docs/architecture.md`, `CONTEXT.md` (Scope
Path and Scope Level are new vocabulary), `docs/roadmap.md` milestone 1, and backlog
statuses.

**Backlog and roadmap.** Closes [003](../../../docs/backlog/003-database-hierarchy.md)
(hierarchy), [004](../../../docs/backlog/004-introspection-cache-coverage.md) (cache
coverage), and [008](../../../docs/backlog/008-session-dialect.md) (dialect).
Resolves [048](../../../docs/backlog/048-session-scope-selection.md) by deletion:
server-side active scope is removed rather than implemented, so that item closes as
dropped with its reasoning recorded. Advances roadmap milestone 1, *Reliable daily
use*, which stays open on [001](../../../docs/backlog/001-profile-rename.md) and
[005](../../../docs/backlog/005-duckdb-constraints.md).

**Explicitly out of scope.** Automatic invalidation after DDL remains
[043](../../../docs/backlog/043-ddl-cache-invalidation.md), which inherits a new
consequence: a client that runs `ATTACH` and never refreshes holds a stale hierarchy
until it does. That is bounded — every metadata call carries its own explicit Scope
Path, so nothing resolves against stale hierarchy — and classifying schema-changing
SQL deserves its own design. Scoped (rather than whole-Session) refresh granularity
stays with [024](../../../docs/backlog/024-remote-cache-policy.md). `getERD` is
rescoped because it calls `list_tables()` unscoped, but keeps returning its
`not_implemented` stub; real extraction remains
[011](../../../docs/backlog/011-erd-extraction.md), gated on
[005](../../../docs/backlog/005-duckdb-constraints.md). The synchronous execution
model and [ADR-0001](../../../docs/adr/0001-sync-core-for-phase-1.md) are untouched.
