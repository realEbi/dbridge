# 048 - Select a Session's active database and schema

- Repo: dbridge, clients
- Status: dropped
- Change: [adopt-explicit-scope-paths](../../openspec/changes/archive/2026-09-24-adopt-explicit-scope-paths/proposal.md)
- Origin: Original design 12 and multi-database use cases; retained from revision `80d71d4`.

## Problem / opportunity

The previous Session model had unused `active_database` and `active_schema`
fields, with no protocol operations to set them.

## Desired outcome

Make metadata selection explicit and preserve fully qualified identity across
client operations.

## Resolution

Server-held active metadata scope was rejected, not deferred. The unused Session
fields are removed. Clients own their selected Scope Path and send it on each
scoped metadata request; neither metadata requests nor completions mutate another
request's scope. This avoids shared-Session contention and the inconsistent
implicit defaults that previously affected listing and lookup.

Connect supplies a default path for clients to use explicitly. SQL execution
retains the engine's resolution rules; a client metadata selection does not issue
`USE` or change a search path. Table suggestions insert executable fully qualified
identifiers, so queries generated for attached containers remain correctly
targeted.

See [ADR-0002](../adr/0002-explicit-scope-paths.md),
[database hierarchy](003-database-hierarchy.md), and
[qualified identifiers](002-qualified-identifiers.md).
