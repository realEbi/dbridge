# 05 — DuckDB adapter parity

Status: ready-for-agent

## Parent

`.scratch/phase-1-restructure/PRD.md`

## What to build

Port the DuckDB adapter to the new `DBAdapter` interface and register it, so a
client can connect to duckdb and run the same connect/execute/introspect path as
sqlite. Independent of the introspection/completion slices — it only needs the
adapter interface and registry from the tracer slice, so it can run in parallel
with slices 03/04.

- Implement `connect`/`disconnect`/`execute`/`list_databases`/`list_schemas`/
  `list_tables`/`get_table_schema`/`dialect_name`/`get_keywords` against duckdb.
- **Drop the pandas dependency** — use duckdb's native fetch, not
  `fetch_df`/`to_dict`.
- Introspect via `information_schema`; columns carry data types and nullability.
  Primary/foreign keys are best-effort (may return empty in Phase 1).
- Register `"duckdb"` in the adapter registry alongside sqlite.

## Acceptance criteria

- [ ] `INSTALLED_ADAPTERS` includes both `sqlite` and `duckdb`
- [ ] E2E (or adapter integration test) connects to an in-memory duckdb, runs
      CREATE/INSERT/SELECT, and lists the created table
- [ ] `get_table_schema` returns columns with data types for a duckdb table
- [ ] No pandas import remains in the duckdb adapter

## Blocked by

- `.scratch/phase-1-restructure/issues/02-tracer-connect-execute-stdio.md`
