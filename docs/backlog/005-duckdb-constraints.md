# 005 - Extract DuckDB primary and foreign keys

- Repo: dbridge, dbridge.nvim
- Status: done
- Change: [server](../../openspec/changes/archive/2026-09-24-extract-table-key-constraints/proposal.md), [client](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-24-adopt-table-key-constraints)
- Origin: Legacy backlog 1.5; retained from revision `80d71d4`.

## Problem / opportunity

DuckDB previously returned empty primary and foreign keys even when constraints
existed, limiting schema browsing and future ERDs.

## Desired outcome

Extract real constraint metadata, including correct schema/catalog scoping and composite-key ordering.

## Notes and references

Implemented in [DuckDBAdapter](../../src/dbridge/adapters/duckdb.py) using
`duckdb_constraints()` for catalog tables and the query-connection metadata
snapshot for temporary tables. SQLite now preserves composite ordering and
resolves shorthand references. The [table-keys contract](../../openspec/specs/table-keys/spec.md)
defines both engines' constraint shape. Adapter, stdio refresh, and paired client
transport checks verify the behavior. Supports [ERD extraction](011-erd-extraction.md),
which remains deferred.
