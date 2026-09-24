# 005 - Extract DuckDB primary and foreign keys

- Repo: dbridge, dbridge.nvim
- Status: planned
- Change: [server](../../openspec/changes/extract-table-key-constraints/proposal.md), [client](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/adopt-table-key-constraints)
- Origin: Legacy backlog 1.5; retained from revision `80d71d4`.

## Problem / opportunity

DuckDB get_table_schema returns empty primary_keys and foreign_keys even when constraints exist. This limits schema browsing and future ERDs.

## Desired outcome

Extract real constraint metadata, including correct schema/catalog scoping and composite-key ordering.

## Notes and references

Inspect [DuckDBAdapter](../../src/dbridge/adapters/duckdb.py). Investigate duckdb_constraints() when implementing. Supports [ERD extraction](011-erd-extraction.md).
