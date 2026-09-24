# Explicit Scope Paths for metadata requests

Status: accepted.

## Decision and rationale

Each scoped metadata request carries an ordered literal Scope Path. An Adapter
declares the path's container levels: one namespace for SQLite, catalog then
schema for DuckDB. A table's identity is its full path plus its literal name.
Connect returns the levels, default path, and SQL dialect; refresh invalidates all
introspection caches and returns the authoritative current levels and default.

The Session holds no active metadata scope. Clients retain their selection and
send it explicitly. This removes inconsistent implicit defaults between listing
and lookup, represents SQLite without a redundant main/main tier, and prevents
one client's selection from changing another client's lookup if a Session is
shared. The default path is discovery data, not a fallback for omitted paths.

Keeping mutable Session scope would reduce request size but introduce hidden
state into metadata resolution. Keeping a fixed database/schema pair would force
Adapters with one container level to duplicate it. Both alternatives are rejected.
The full design and migration are recorded in the
[OpenSpec change](../../openspec/changes/archive/2026-09-24-adopt-explicit-scope-paths/design.md).

## Consequences and revisit trigger

Clients render the declared levels and send the appropriate path on metadata and
completion calls. There is no compatibility window for the removed `fqn` and
fixed-pair request shapes; the server and client migrations move together.
Metadata cache keys preserve full literal identity. Container listings retain
engine-internal entries with an explicit marker for client presentation.

SQL execution remains subject to the engine's SQL resolution rules. Selecting a
metadata path does not issue `USE` or change a search path. Table completion always
inserts a fully qualified Adapter-owned identifier so a suggestion executes in
the intended container without changing driver state.

Clients refresh after hierarchy changes; automatic invalidation remains
[backlog 043](../backlog/043-ddl-cache-invalidation.md). Revisit the path declaration
if a supported Adapter needs optional container levels. Any future proposal for
server-held metadata scope must explicitly supersede this decision and address
shared-Session behavior. [ADR-0001](0001-sync-core-for-phase-1.md) remains unchanged.
