# dbridge Backlog

Known defects, deferred work, and open questions that outlive any single phase.

Phase-scoped work lives in `.scratch/phase-N-*/` and disappears from view once
the phase closes; this file is the durable record. Most entries below were found
while verifying Phase 2 end to end and, until now, existed only in commit
messages.

**Conventions.** Each entry says what is wrong or missing, why it matters, and
where to look. `dbridge` = this repo (server); `dbridge.nvim` = the Neovim
client at `../dbridge.nvim`. When you pick something up, move it into a phase
PRD rather than fixing it inline — that is how the cross-references stay useful.

---

## 1. Correctness gaps

### 1.1 Editing a profile's name orphans the old one
**Repo:** `dbridge.nvim` · `lua/dbridge/explorer.lua` `handle_edit_profile`

`create_interactive` saves under whatever name the user types, and
`handle_edit_profile` then updates the tree node in place. If the name changed,
the original entry is still in `connections.toml` — so a rename silently leaves
a duplicate behind, and the explorer shows only the new one.

Fix: capture the old name before prompting and `deleteProfile` it when the name
changed. Guard against deleting when the save failed.

### 1.2 Generated SQL uses a bare table name
**Repo:** `dbridge.nvim` · `lua/dbridge/init.lua` (the `<CR>` handler)

`SELECT * FROM <table>` resolves against the default search path, so it can hit
the wrong table when two schemas share a name. It is bare because correct
qualification is dialect-specific and the client does not know the dialect:
sqlite has no catalog level (`main.main.customers` fails to parse) while duckdb
wants `catalog.schema.table`.

Fix properly by having the server hand back a ready-to-use identifier — either a
`qualify` responsibility on `DBAdapter`, or a qualified name on the
`getTableSchema` response. Related to §3.1.

### 1.3 sqlite's tree has a redundant level
**Repo:** `dbridge` · `src/dbridge/adapters/sqlite.py`

`list_databases()` and `list_schemas()` both return `["main"]`, so the explorer
renders `main → main → tables`. Cosmetic, but it implies a hierarchy sqlite does
not have. The tree shape probably needs to be adapter-driven rather than always
three levels deep.

### 1.4 `list_databases` / `list_schemas` bypass the schema cache
**Repo:** `dbridge` · `src/dbridge/core/engine.py:46,49`

`list_tables` and `get_table_schema` go through the `SchemaRegistry`, but
`list_databases` and `list_schemas` call the adapter directly. They are therefore
uncached, and `dbridge/refreshSchema` does not affect them. Inconsistent, and it
matters more for a slow backend (Snowflake — see §5, open question #4).

### 1.5 duckdb reports no primary or foreign keys
**Repo:** `dbridge` · `src/dbridge/adapters/duckdb.py` `get_table_schema`

Returns `primary_keys=[]` and `foreign_keys=[]` unconditionally. Documented as
best-effort in Phase 1, but the ERD extractor (§4.1) needs real FK data, and
sqlite already provides it via `PRAGMA foreign_key_list`. duckdb exposes
constraints through `duckdb_constraints()`.

---

## 2. Capability regressions

### 2.1 No "run the statement under the cursor"
**Repo:** `dbridge.nvim` · `lua/dbridge/editor.lua` `get_sql`

`<leader>r` sends the entire buffer in normal mode, or the visual selection.
The pre-stdio client had `sql_extractor.lua`, which did cursor-aware statement
boundary detection; it was deleted with the REST island in `c4720f8` because
nothing reachable required it any more.

This is the most-missed thing in day-to-day use: a scratch buffer with several
queries cannot run just one. Worth restoring, ideally via treesitter rather than
the old hand-rolled scanner.

### 2.2 Saved queries
**Repo:** `dbridge.nvim` · see `TODO.md` in that repo

Per-connection `.sql` files under `stdpath("data")`, with tree nodes to create,
open, and delete them. Fully specified there; purely client-side, no server
change needed.

---

## 3. Protocol gaps

### 3.1 The client cannot learn the dialect
Adapters implement `dialect_name()`, but it is not exposed over DSP. The client
therefore cannot qualify identifiers (§1.2), pick dialect-appropriate quoting, or
adjust generated SQL. Cheapest fix: return it from `dbridge/connect` alongside
`session_id`.

### 3.2 `dbridge/cancel` is reserved but unimplemented
`QUERY_CANCELLED = -32004` exists in `src/dbridge/protocol/errors.py`; no method
uses it. Blocked on the async core (§4.2) — a synchronous executor has nothing to
cancel.

### 3.3 No server→client notifications
The design doc specifies `dbridge/progress` and `dbridge/logMessage` as server
pushes. The stdio transport is strictly request/response today, and
`client.lua`'s `dispatch_response` drops any message without an `id`. Needed
before streaming (§4.2) can report progress.

---

## 4. Deferred by design

These were scoped out deliberately. See `docs/adr/0001-sync-core-for-phase-1.md`.

### 4.1 ERD extraction
`dbridge/getERD` returns `{"status": "not_implemented", "tables": [...]}`. Needs
§1.5 first, plus a decision on open question #5 (follow FK chains automatically,
or require an explicit table list?).

### 4.2 Async core, streaming, cancel, transactions
ADR-0001 chose a synchronous core for Phase 1. Revisiting it affects every layer
and is the single largest piece of remaining work. Note that
`SqliteAdapter.connect` now passes `isolation_level=None` for autocommit
(`a6897f9`) — any transaction feature must revisit that, since it was chosen
precisely because nothing could ever issue a commit.

### 4.3 Tier-2 completion
Currently: FROM/JOIN → tables, SELECT/WHERE → columns of tables in scope,
otherwise keywords. Not yet handled:
- alias-qualified columns in `JOIN ... ON`
- value / enum completion in `WHERE`
- meaningful ranking (`sort_key` is just the lowercased label)
- a trailing comma (`SELECT id, `) falls through to keywords instead of columns

### 4.4 Parked adapters
`src/dbridge/adapters/_parked/` holds mysql, postgres, and snowflake against the
old interface. They are neither imported nor registered. Porting them to the
current `DBAdapter` is mechanical but each needs its own introspection queries.

---

## 5. Design-doc open questions

Still open, from `docs/dbridge-design-doc.md` §18. Reproduced here so this file
is the single place to look:

| # | Question | Priority |
|---|---|---|
| 1 | One transport per process, or several simultaneously? | High |
| 2 | Large result sets: client-side pagination or server-side cursors? | High |
| 3 | Should profiles support secret managers (1Password, AWS Secrets Manager)? | Medium |
| 4 | Right TTL strategy for Snowflake, where introspection is very slow? | Medium |
| 5 | Should the ERD extractor follow FK chains, or take an explicit table list? | Low |
| 6 | A plugin system for custom completion providers (e.g. dbt awareness)? | Low |
| 7 | What authentication model does a WebSocket transport need? | Medium |

Question #2 is the one that keeps surfacing: results are capped at
`max_rows` (default 100) and the client paginates within that cap, so the user
sees "page 1/5" for a table with 220 rows. The truncation warning makes it
honest, but it is not a real answer.

---

## 6. Housekeeping

- Two pre-existing ruff `F401`s: `operator.mul` in
  `src/dbridge/adapters/_parked/mysql.py` and `ForeignKey` in
  `src/dbridge/adapters/duckdb.py`. The parked one will resolve with §4.4.
- No visual indicator of which connection is active. `get_active_session` now
  tracks the last-touched connection (`dbridge.nvim` `1cea404`), but nothing in
  the UI shows which one that is, so `<leader>r`'s target is invisible.
- The explorer's `R` (refresh) disconnects and reconnects the profile to rebuild
  the subtree, rather than just clearing the cache and re-querying.
