# Phase 1 Restructure — MVP

Migrate dbridge from a synchronous FastAPI REST server into the three-layer
architecture from the design doc (`docs/dbridge-design-doc.md`): **Transport /
Core Engine / Adapters**. Phase 1 ships a single transport (stdio JSON-RPC,
LSP-style framing) targeting Neovim.

## Scope (Phase 1 decisions)

- **Synchronous** core and adapters — no asyncio, streaming, cancel, or
  transactions (see `docs/adr/0001-sync-core-for-phase-1.md`).
- **stdio-only** JSON-RPC 2.0; FastAPI removed.
- **Multi-session** manager; thin `Session`; connection *profiles* persisted to
  `connections.toml`, live adapter instances are not persisted.
- Adapter interface: granular `list_*`, enriched `get_table_schema`
  (types + PK, FK best-effort); drop `is_single_connection`/`get_capabilities`.
- Adapters ported: **sqlite + duckdb only**; mysql/postgres/snowflake parked.
- **Tier-1** completion (FROM/JOIN tables, SELECT/WHERE columns, keywords).
- **Hot-only** in-memory schema registry; disk cache dropped.
- `dbridge/getERD` is a non-crashing placeholder.
- `execute` returns materialized `QueryResult`, configurable row cap, truncation
  surfaced via `warnings`.

## Acceptance

A Python end-to-end test spawns the stdio server as a subprocess and drives
`connect → listTables → getTableSchema → execute → complete → disconnect`
against in-memory sqlite and a duckdb database, with all unit tests passing.

## Reference

- Plan: `docs/superpowers/plans/2026-06-19-dbridge-phase-1-restructure.md`
- Glossary: `CONTEXT.md`
- Design: `docs/dbridge-design-doc.md`
