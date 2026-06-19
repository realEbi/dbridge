# 03 — Schema introspection over stdio

Status: ready-for-agent

## Parent

`.scratch/phase-1-restructure/PRD.md`

## What to build

Add schema browsing to the running stdio server, backed by a hot-tier cache.

- **Adapter layer:** implement the introspection methods on the sqlite adapter —
  `list_databases`, `list_schemas`, `list_tables`, and `get_table_schema`.
  `get_table_schema` returns columns **with data types**, nullability, and
  primary keys; foreign keys are best-effort (sqlite can read
  `PRAGMA foreign_key_list`).
- **Core layer:** a `SchemaRegistry` wrapping an adapter with a per-call-signature
  in-memory TTL cache (default 60s) and a `refresh()` that clears it; the engine
  creates one registry per session and routes `listTables`/`getTableSchema`
  through it (other `list_*` may call the adapter directly).
- **Protocol layer:** dispatch `dbridge/listDatabases`, `dbridge/listSchemas`,
  `dbridge/listTables`, `dbridge/getTableSchema`.

No disk cache (explicitly out of scope for Phase 1).

## Acceptance criteria

- [ ] E2E: after creating a table, `dbridge/listTables` returns it and
      `dbridge/getTableSchema` returns its columns (with types) and primary keys
- [ ] `SchemaRegistry` serves a second identical call from cache within TTL and
      re-queries after `refresh()` or TTL expiry (unit-tested with a fake adapter)
- [ ] sqlite `get_table_schema` reports `nullable` correctly for NOT NULL columns
      and lists declared foreign keys

## Blocked by

- `.scratch/phase-1-restructure/issues/02-tracer-connect-execute-stdio.md`
