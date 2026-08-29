# Phase 2 Client Hardening — MVP

Phase 1 delivered a working stdio JSON-RPC server. A Neovim client
(`~/Projects/dbms/dbridge.nvim`) has since been migrated to speak it, but the
migration is **uncommitted, untested, and carries four verified defects** — one
of which is a gap in DSP itself. Phase 2 lands that migration, closes the gap,
and puts a real test suite under the client.

Phase 2 spans two repos. This PRD is the single source of truth; each issue
names the repo it touches.

## Scope (Phase 2 decisions)

- **Cursor-aware completion.** `dbridge/complete` gains an **optional**
  `position` (byte offset into `sql`), defaulting to end-of-string so existing
  callers keep working. Without it the server cannot distinguish
  `SELECT ␣ FROM users` (cursor after SELECT) from `SELECT  FROM users` (cursor
  at end), which makes SELECT-position column completion impossible.
- **Land the client migration** as-is, then delete the orphaned REST island
  (`api`, `config`, `dbconnection`, `dbexplorer`, `node_utils`, `query_editor`,
  `query_result`, `file_utils`, `sql_extractor`, `help`, `cmp_format`). The
  module graph is already disjoint — nothing reachable from `init.lua` or
  `plugin/dbridge.lua` requires any of them.
- **Integration-first Lua testing**: `mini.test` spawning the real dbridge
  server as a subprocess. Unit tests with a stubbed client are explicitly not
  the primary strategy — they would not have caught any of the four defects.
- **Still synchronous, still stdio-only.** No asyncio, streaming, or cancel
  (ADR-0001 stands). No new adapters. ERD stays a placeholder.
- Deferred features from `dbridge.nvim/TODO.md` (saved queries) stay deferred.

## The defects

1. `dbridge/complete` has no cursor position, so SELECT-position column
   completion is structurally impossible. `tests/core/test_completion.py:46`
   claims to cover this but never asserts on the SELECT case — the orphaned
   `items` local (ruff `F841`) is the fossil of the dropped assertion.
   **Issue 04's acceptance criterion was never met.**
2. `cmp.lua` sends `params.context.cursor_before_line`, so multi-line
   statements yield zero completions.
3. `results.lua` derives columns via `pairs()` on a hash table, so column order
   is nondeterministic (`{id,name,email}` renders as `{name,id,email}`).
4. `results.lua` ignores `QueryResult.warnings`, so a result silently capped at
   `max_rows` looks complete.

5. **Closing any panel hangs Neovim.** `init.lua`'s `BufUnload` handler calls
   `open()`, which mounts new panels and registers new `BufUnload` handlers, so
   teardown re-enters forever. `:q` in a panel, and `:qa!` with the layout open,
   both hang. Found while verifying issue 01; see issue 06.

Defects 1-4 were reproduced live against the real server before this PRD was
written; defect 5 was found while verifying issue 01's acceptance criteria.

## Acceptance

`make test` in `dbridge.nvim` runs a `mini.test` suite that spawns the real
server and covers: framing across chunked reads, profile CRUD round-trip,
connect-by-profile, execute with correct column order, truncation surfaced to
the user, and SELECT-position column completion returning columns. The
server-side suite still passes, with the restored SELECT-position test now
asserting for real.

## Reference

- Plan: `docs/superpowers/plans/2026-08-29-dbridge-phase-2-client-hardening.md`
- Phase 1 PRD: `.scratch/phase-1-restructure/PRD.md`
- Glossary: `CONTEXT.md`
- Design: `docs/dbridge-design-doc.md`
- Client repo: `~/Projects/dbms/dbridge.nvim`
