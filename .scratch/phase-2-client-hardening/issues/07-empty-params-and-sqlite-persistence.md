# 07 — Empty params rejected + sqlite writes rolled back

Status: done (dbridge.nvim 74e0640, dbridge a6897f9)
Repo: both

## Parent

`.scratch/phase-2-client-hardening/PRD.md`

Two defects found while verifying the client end to end. Both were silent, and
neither was anticipated by the plan. Recorded here so the phase history is
complete.

## Empty params were rejected (`dbridge.nvim`)

Lua cannot distinguish an empty list from an empty map, so `vim.fn.json_encode({})`
emits `[]`. DSP params are always an object and the server types them as a dict,
so **any** request sent with empty params failed validation with `-32600`.

`dbridge/listProfiles` is the only no-param method, and `explorer.init()` calls
it to populate the tree — so saved profiles never appeared when opening the UI.
The callback discarded the error, so nothing was reported.

Fixed by substituting `vim.empty_dict()` for nil/empty params in
`client.request`, which covers any future no-param method.

## sqlite writes were rolled back on disconnect (`dbridge`)

`SqliteAdapter.execute()` never committed, and `disconnect()` closes the
connection. Python's `sqlite3` opens an implicit transaction before every
INSERT/UPDATE/DELETE under the default `isolation_level`, so closing discarded
them. The writes were visible for the rest of the session — an open transaction
sees its own uncommitted rows — so this only surfaced on reconnect. `CREATE TABLE`
survived because DDL runs outside the implicit transaction, which made
persistence look like it worked.

Reproduced: 150 rows inserted into a file-backed database returned 0 rows after
reconnecting, with the table intact.

Fixed by connecting with `isolation_level=None` (autocommit). Phase 1 exposes no
transaction control (ADR-0001), so nothing would ever have issued the commit.
duckdb was checked and already persists correctly.

## Acceptance criteria

- [x] `dbridge/listProfiles` succeeds from the Lua client
- [x] Saved profiles populate the explorer tree on `:Dbridge`
- [x] sqlite INSERT/UPDATE/DELETE survive disconnect/reconnect, covered by tests
- [x] duckdb persistence confirmed unaffected
