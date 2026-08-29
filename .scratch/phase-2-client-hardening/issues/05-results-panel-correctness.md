# 05 — Results panel: column order and truncation

Status: done (dbridge.nvim 69e1b26)
Repo: `dbridge.nvim`

## Parent

`.scratch/phase-2-client-hardening/PRD.md`

## What to build

Two correctness bugs in `results.lua`, both user-visible.

- **Column order is nondeterministic.** `render_page` builds its column list
  with `for k in pairs(slice[1])` over a hash table. Verified: the server sent
  `{id, name, email}` and the panel rendered `{name, id, email}`. Use
  `query_result.columns` — it is already ordered — as the column list, and stop
  round-tripping rows through a keyed record just to read the keys back out.
- **Truncation is invisible.** The server caps results at `max_rows` (default
  100) and reports it in `QueryResult.warnings` as
  `"result truncated to N rows"`. `M.render` drops `warnings` entirely, so a
  capped result shows a confident "page 5/5" and looks complete. Surface
  warnings in the panel — the statusline already carries the page counter, so
  it is a natural home.
- While here: the statusline says `rows X-Y of Z` where `Z` is the *fetched*
  count, not the table's real count. Make it honest about being a capped view.

Keep the client-side pagination as-is; server-side cursors are out of scope
(design doc open question #2).

## Acceptance criteria

- [x] Rendered column order matches `query_result.columns` exactly, asserted in
      an integration test with a table whose column names do not sort
      alphabetically
- [x] A query exceeding `max_rows` shows the truncation warning in the panel
- [x] A query returning no rows still renders `(no results)` without error
- [x] A query whose columns include duplicates or NULL values does not crash

## Blocked by

- `.scratch/phase-2-client-hardening/issues/02-lua-integration-harness.md`
