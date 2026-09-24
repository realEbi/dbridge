# 011 - Return an actual entity-relationship graph

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.1; original design 11 and question 5; retained from revision `80d71d4`.

## Problem / opportunity

getERD currently returns a not_implemented status and table names.

## Desired outcome

Build nodes and FK edges from real metadata and define JSON, Mermaid, or DOT output as needed. Decide whether callers select tables explicitly or the server follows FK chains, with bounds for expansion.

## Notes and references

SQLite and DuckDB constraint metadata is available through the
[table-keys contract](../../openspec/specs/table-keys/spec.md), including ordered
composite keys and referenced Scope Paths; see [005](005-duckdb-constraints.md).
Graph construction and traversal remain deferred. Other adapters can be supported
incrementally; missing metadata must be explicit.
