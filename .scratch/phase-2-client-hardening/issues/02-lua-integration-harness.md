# 02 — Lua integration test harness against a real server

Status: done (dbridge.nvim 319cbf1)
Repo: `dbridge.nvim`

## Parent

`.scratch/phase-2-client-hardening/PRD.md`

## What to build

Replace the placeholder `1 + 1 == 2` test with a `mini.test` suite that spawns
the **real** dbridge server as a subprocess. This lands before the defect fixes
so those slices have a safety net — and because integration is the only level
that catches the class of bug this phase exists to fix.

- A test helper that starts `dbridge.server` via `client.start`, waits for
  readiness, and tears the job down between test sets. Make the server command
  overridable by env var so CI and local runs can differ.
- Cover the transport itself: a result set large enough to arrive across
  multiple `on_stdout` chunks must reassemble into one frame. (Insert a few
  hundred rows — this is the framing path, and it is the reason to test at this
  level at all.)
- Cover the protocol surface end-to-end: connect (inline adapter and by
  profile), execute, listTables, getTableSchema, complete, refreshSchema,
  getERD, disconnect, and the profile CRUD round-trip via `profiles.lua`.
- Point profile tests at a temp `connections.toml` via the `dbridge_`-prefixed
  env so they never touch the developer's real `~/.config/dbridge/`.
- Assert error paths surface: unknown session → `-32003`, unknown profile →
  `-32006`.

## Acceptance criteria

- [x] `make test` runs green and the placeholder test is gone
- [x] A multi-chunk result set round-trips with the correct row count
- [x] Profile CRUD round-trips without touching the real config directory
- [x] Unknown session and unknown profile assert on their DSP error codes
- [x] Suite tears down every spawned server; no orphaned processes

## Blocked by

- `.scratch/phase-2-client-hardening/issues/01-land-client-migration.md`

## Notes from implementation

Tests had to move into a **child Neovim**. The first in-process attempt failed
because the transport is async: driving it needs `vim.wait`, and a nested
`vim.wait` re-enters MiniTest's own scheduler, so one file's `pre_once` hook
executed another file's cases mid-request. `tests/child_env.lua` now runs in the
child and does the blocking; the parent drives it over RPC.

The Makefile also vendors `nui.nvim`, since the lifecycle/results/completion
tests mount the real UI.

40 cases, green on three consecutive runs with no orphaned processes.
Mutation-checked: reintroducing the empty-params and column-order bugs produces
7 failures.
