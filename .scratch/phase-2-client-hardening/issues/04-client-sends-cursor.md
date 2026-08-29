# 04 — Client sends buffer + cursor to completion

Status: done (dbridge.nvim b2b96d8)
Repo: `dbridge.nvim`

## Parent

`.scratch/phase-2-client-hardening/PRD.md`

## What to build

Use the new `position` param so completion works on real, multi-line SQL.

`cmp.lua` currently sends `params.context.cursor_before_line` — only the text
before the cursor **on the current line**. Any statement spanning lines gives
the server no FROM clause, so it returns zero items. Verified: `"SELECT "` → 0
items, `"SELECT \nFROM users"` → 1 item.

- Send the full editor buffer as `sql` plus the cursor's **byte offset** as
  `position`. Mind the units: Neovim's column from `nvim_win_get_cursor` is a
  byte index into the line, and offsets must account for the newlines joining
  lines — get this wrong and completion silently misclassifies.
- Keep `is_available()` gated on `filetype == "sql"` and a running client.
- Debounce or cancel in-flight completion requests so fast typing does not
  queue stale callbacks against `_pending`.

## Acceptance criteria

- [x] Completion after `SELECT ` on line 1 with `FROM users` on line 2 returns
      `users`' columns
- [x] Completion after `FROM ` still returns table names
- [x] Byte offset is correct for a buffer containing multi-byte characters
- [x] Integration test in the suite from issue 02 covers the multi-line case

## Blocked by

- `.scratch/phase-2-client-hardening/issues/03-cursor-aware-completion.md`
- `.scratch/phase-2-client-hardening/issues/02-lua-integration-harness.md`
