# 02 — Tracer: connect → execute → disconnect over stdio (sqlite)

Status: ready-for-agent

## Parent

`.scratch/phase-1-restructure/PRD.md`

## What to build

The first complete end-to-end path through every layer: a client speaks
JSON-RPC over stdio to open a sqlite session, run a query, and close it. This is
the spine the rest of Phase 1 hangs off, so it stands up all the layers at once.

- **Adapter layer:** `DBAdapter` ABC plus the `ColumnDef` / `ForeignKey` /
  `TableSchema` / `QueryResult` dataclasses; typed adapter exceptions
  (`AdapterError`, `AdapterConnectionError`, `AdapterQueryError`); a sqlite
  adapter implementing `connect`/`disconnect`/`execute`/`dialect_name`/
  `get_keywords` (introspection methods can land in slice 03); an adapter
  registry exposing `create_adapter` and `INSTALLED_ADAPTERS`.
- **Core layer:** `Session` + `SessionManager` (UUID ids, `SessionNotFoundError`
  on unknown id); an `executor` that materializes rows, **caps to a configurable
  max (default 100)**, and appends a `"result truncated to N rows"` warning when
  capped; an `Engine` exposing `connect`/`disconnect`/`execute`.
- **Protocol/Transport layer:** pydantic JSON-RPC request model + DSP error codes
  and `DspError`; a `Dispatcher` mapping `dbridge/connect`, `dbridge/execute`,
  `dbridge/disconnect` to engine calls and translating exceptions to DSP error
  codes; a stdio transport using `Content-Length: <n>\r\n\r\n<json>` framing; a
  `server` entry point (`python -m dbridge.server`) that wires engine →
  dispatcher → stdio and exits cleanly on EOF.

`execute` returns a materialized result with `columns`, `rows`, `row_count`,
`execution_time_ms`, and `warnings`.

## Acceptance criteria

- [ ] An E2E test spawns `python -m dbridge.server` and drives connect → execute
      (CREATE/INSERT/SELECT) → disconnect over stdin/stdout, asserting returned
      columns and rows
- [ ] Unknown `session_id` yields DSP error `-32003`; unknown method yields `-32601`
- [ ] A query returning more than the configured cap is truncated and carries a
      truncation warning
- [ ] Server starts and exits cleanly on EOF with no traceback
- [ ] Unit tests pass for the sqlite adapter, session manager, and dispatcher

## Blocked by

- `.scratch/phase-1-restructure/issues/01-groundwork-skeleton.md`
