# 03 — Cursor-aware completion (`position` param)

Status: ready-for-agent
Repo: `dbridge`

## Parent

`.scratch/phase-2-client-hardening/PRD.md`

## What to build

Close the DSP gap that makes SELECT-position column completion impossible.

Today `complete()` receives only `sql` and assumes the cursor sits at the end.
`_FROM_JOIN_RE` is anchored at `$`, so `"SELECT  FROM users"` matches
`FROM users` and returns **tables** — regardless of where the user actually is.

- `dbridge/complete` accepts an **optional** `position`: a byte offset into
  `sql`. Absent → end of string, so every existing caller is unaffected.
- `core/completion.complete()` takes `position` and classifies context from
  `sql[:position]`, while still parsing the **full** `sql` for tables in scope —
  that is what lets `SELECT ␣ FROM users` see `users` and offer its columns.
- Restore `tests/core/test_completion.py::test_select_returns_columns_of_referenced_tables`
  to actually assert the SELECT case. Remove the orphaned `items` local (the
  ruff `F841`); it is the fossil of the assertion that was dropped when it
  failed.
- Update the method tables in `README.md` and `AGENTS.md`.

Keep the tier-1 contract otherwise unchanged: deferred contexts
(alias-qualified `JOIN ON`, value/enum completion, ranking) still return
empty/flat rather than crash.

## Acceptance criteria

- [ ] `complete("SELECT  FROM users", position=7)` returns `users`' columns with
      kind `column`
- [ ] `complete("SELECT * FROM ")` with no `position` behaves exactly as before
- [ ] `complete("SELECT \nFROM users", position=7)` returns columns — the
      multi-line case that currently yields nothing
- [ ] The restored SELECT-position test asserts on labels and fails if the
      classification regresses
- [ ] `ruff check src/ tests/core/test_completion.py` is clean

## Blocked by

Nothing — server-side only, can run in parallel with 01/02.
