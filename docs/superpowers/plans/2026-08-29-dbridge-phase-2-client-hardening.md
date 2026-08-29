# dbridge Phase 2 Client Hardening Implementation Plan

> **For agentic workers:** implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.
>
> **Note:** Per the project owner, this plan does **not** use TDD — except in
> issue 03, where a test already exists and is wrong. Each task implements code
> first, then adds/runs verification, then commits.

**Goal:** Land the uncommitted Neovim client migration, close the DSP gap that
makes SELECT-position completion impossible, fix two user-visible result-panel
bugs, and put a real integration test suite under the client.

**Architecture:** Unchanged from Phase 1 — synchronous core, stdio-only
transport, JSON-RPC 2.0 with `Content-Length` framing. Phase 2 adds exactly one
protocol change (an optional `position` on `dbridge/complete`) and otherwise
works on the client side of the wire.

**Tech Stack:** Server — Python 3.11+, pydantic v2, sqlglot, pytest, uv.
Client — Lua, Neovim 0.12+, `nui.nvim` for panels, `nvim-cmp` as the completion
host, `mini.test` for tests.

## Repos

| Repo | Path | Issues |
|---|---|---|
| `dbridge` (server) | `~/Projects/dbms/dbridge` | 03 |
| `dbridge.nvim` (client) | `~/Projects/dbms/dbridge.nvim` | 01, 02, 04, 05 |

This plan and its PRD live in the server repo and are the single source of
truth for both.

## Global Constraints

- ADR-0001 stands: synchronous only, no asyncio, no streaming, no cancel.
- Transport stays stdio-only. No new adapters. ERD stays a placeholder.
- The `position` param on `dbridge/complete` is **optional** and defaults to
  end-of-string — no existing caller may break.
- The client never reads or writes `connections.toml` directly; profiles go
  through `dbridge/listProfiles` / `saveProfile` / `deleteProfile`.
- Glossary discipline (`CONTEXT.md`): **Profile** for the saved config,
  **Session** for the live binding. Do not reintroduce "connection" for either.
- Lua tests spawn the real server. Point them at a temp `connections.toml` via
  the `dbridge_`-prefixed env so they never touch `~/.config/dbridge/`.
- Run server commands with `uv run`; run client tests with `make test`.

## Sequencing

```
01 land client migration  --+--> 02 integration harness --+--> 04 client sends cursor
                            |                             +--> 05 results panel
03 cursor-aware completion -+-----------------------------+
   (server-side, parallel from the start)
```

- **01 is urgent and blocking**: ~470 lines of finished client work are
  untracked. Nothing else should start until it is in git.
- **03 is independent** of the client work and can run in parallel from day one.
- **04 needs both** 03 (the server accepts `position`) and 02 (a test to prove
  the multi-line case).
- **05 needs only** 02.

## Evidence base

Every defect this plan fixes was reproduced live against the running server, not
inferred from reading code:

| Defect | Observed |
|---|---|
| No cursor in `complete` | `complete("SELECT  FROM users")` returns `users:table`, never columns |
| `cursor_before_line` | `"SELECT "` gives 0 items; `"SELECT \nFROM users"` gives 1 |
| Column order | server `{id,name,email}` rendered as `{name,id,email}` |
| Silent truncation | 250 rows inserted, `row_count=100`, `warnings=["result truncated to 100 rows"]`, panel shows none of it |
| Panel close hangs | deleting one panel buffer never returns; `:qa!` with the layout open also hangs |

The completion defect also invalidates a Phase 1 acceptance criterion: issue 04
required "completion at a SELECT/WHERE position returns columns of tables in
scope", and the test that claims to cover it
(`tests/core/test_completion.py:46`) asserts only on the `WHERE` case. The
orphaned `items` local that ruff flags as `F841` is the fossil of the SELECT
assertion, dropped because it did not pass.

## Tasks

See `.scratch/phase-2-client-hardening/issues/` — each issue is independently
grabbable and carries its own acceptance criteria:

- [ ] `01-land-client-migration.md` — commit the rewrite, delete the REST island
- [ ] `02-lua-integration-harness.md` — `mini.test` against a real server
- [ ] `03-cursor-aware-completion.md` — optional `position` on `dbridge/complete`
- [ ] `04-client-sends-cursor.md` — send buffer + byte offset from `cmp.lua`
- [ ] `05-results-panel-correctness.md` — column order + truncation warnings
- [ ] `06-panel-close-hangs-neovim.md` — BufUnload re-entry hangs the editor

## Out of scope

Carried forward, not started in Phase 2:

- Async core, streaming, server-side cursors, `dbridge/cancel` (design doc open
  questions #1, #2)
- Un-parking the mysql / postgres / snowflake adapters
- Real ERD extraction (still `{"status": "not_implemented"}`)
- Tier-2 completion: alias-qualified `JOIN ON` columns, value/enum completion,
  ranking
- Saved queries (`dbridge.nvim/TODO.md`)
- Secret-manager backed profiles (open question #3)
