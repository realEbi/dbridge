# 06 — Closing a panel hangs Neovim (BufUnload re-entry)

Status: ready-for-agent
Priority: **highest in the phase** — this hangs the editor
Repo: `dbridge.nvim`

## Parent

`.scratch/phase-2-client-hardening/PRD.md`

## The bug

`lua/dbridge/init.lua` registers a `BufUnload` handler on each of the three
panels whose job is to tear the layout down and re-create it, so `:Dbridge`
keeps working after the user closes the UI:

```lua
p:on("BufUnload", function()
  vim.schedule(function()
    ...
    _layout:unmount()
    open()          -- re-enters
  end)
end)
```

`open()` mounts a new layout and registers `BufUnload` on the *new* panels.
Unmounting the old layout unloads its buffers, which fires their handlers, which
call `open()` again. The loop never terminates.

Reproduced headless: with the layout mounted, deleting a single panel buffer
(what `:q` or `:bd` does) never returns — Neovim was still spinning after two
minutes and had to be killed. The same hang occurs on `:qa!`, because quitting
unloads the panel buffers and re-enters `open()` during shutdown.

This predates Phase 2 — it came in with the migration and was committed as-is in
`7e3594e` so the work was preserved before being changed.

## What to build

Break the re-entry. Options, roughly in order of preference:

- Track teardown state and make `open()` a no-op while a teardown is in flight;
  detach the `BufUnload` handlers before calling `_layout:unmount()`.
- Or drop the re-create-on-close behaviour entirely and let `:Dbridge` build the
  layout on demand each time, which is what the command already does when
  `vim.g.dbridge_loaded ~= 1`.

Also guard the shutdown path: during `VimLeavePre` the handler must not try to
build UI at all, and the server job should be stopped so no process is orphaned.

## Acceptance criteria

- [ ] Closing one panel with `:q` does not hang; the remaining layout tears down
      cleanly
- [ ] `:qa!` with the layout open exits promptly
- [ ] `:Dbridge` still re-opens a working layout after the UI has been closed
- [ ] The server child process is stopped on exit, not orphaned
- [ ] Covered by a test in the issue-02 harness that mounts, closes a panel, and
      asserts Neovim is still responsive

## Blocked by

- `.scratch/phase-2-client-hardening/issues/02-lua-integration-harness.md`
  (for the regression test; the fix itself can land first)
