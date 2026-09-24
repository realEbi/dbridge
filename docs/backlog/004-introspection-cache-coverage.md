# 004 - Cache database and schema listings consistently

- Repo: dbridge
- Status: done
- Change: [adopt-explicit-scope-paths](../../openspec/changes/archive/2026-09-24-adopt-explicit-scope-paths/proposal.md)
- Origin: Legacy backlog 1.4; retained from revision `80d71d4`.

## Problem / opportunity

The previous Engine cached table listings and table schemas while calling
Adapters directly for database and schema listings. Refresh therefore cleared
only part of the metadata view.

## Desired outcome

Decide which introspection operations share the Session cache, cache their scope arguments, and make refresh behavior explicit.

## Resolution

[SchemaRegistry](../../src/dbridge/core/schema_registry.py) now caches all four
introspection results. Schema and table listings use literal Scope Path keys;
table metadata additionally keys on the literal table name. Refresh clears all
entries for the Session and re-delivers its hierarchy and default path. DDL still
requires explicit refresh or TTL expiry, tracked in
[043](043-ddl-cache-invalidation.md).

Verified cache separation, TTL expiry, and refresh of catalogs, schemas, tables,
and columns in the server suite. Scoped refresh and remote-cache policy remain separate work in
[024](024-remote-cache-policy.md).
