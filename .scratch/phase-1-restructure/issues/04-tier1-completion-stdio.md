# 04 — Tier-1 SQL completion over stdio

Status: ready-for-agent

## Parent

`.scratch/phase-1-restructure/PRD.md`

## What to build

A working (partial) context-aware SQL completion path exposed as
`dbridge/complete`. Not the full design matrix — three contexts only:

- **FROM / JOIN position** → table names from the schema registry.
- **SELECT / WHERE position** → column names of the tables in scope (parse the
  partial SQL with sqlglot to find tables already referenced).
- **Otherwise (keyword position)** → dialect keywords from the adapter.

Returns `CompletionItem`s with `label`, `kind` (`table` | `column` | `keyword`,
mapping to LSP `CompletionItemKind` client-side), `detail`, `insert_text`, and a
`sort_key`. Deferred contexts (alias-qualified `JOIN ON` columns, `WHERE` value /
enum completion, sophisticated ranking) must return empty/flat rather than crash.
Absorb the old `extract_table` table-extraction logic into the completion module.

## Acceptance criteria

- [ ] E2E: `dbridge/complete` on `"SELECT * FROM "` returns existing table names
      with kind `table`
- [ ] Completion at a SELECT/WHERE position returns columns of tables in scope
      with kind `column`
- [ ] Completion at a bare keyword position returns dialect keywords
- [ ] Malformed/partial SQL does not raise — completion degrades gracefully
- [ ] Unit tests cover the three contexts with a fake registry

## Blocked by

- `.scratch/phase-1-restructure/issues/03-schema-introspection-stdio.md`
