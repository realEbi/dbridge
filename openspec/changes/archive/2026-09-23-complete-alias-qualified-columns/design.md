## Context

The direct SQLite subprocess reproduction returns only keywords at both `p.`
positions in the reported SQL. The current regex accepts word prefixes but no
dots, and table extraction discards aliases. Merely extending the regex also
fails: an unfinished `SELECT p. FROM ...` lets the parser consume FROM as a column.
See proposal.md for scope and backlog ownership.

## Goals / Non-Goals

**Goals:** Resolve unquoted physical-table qualifiers in the current SELECT,
including incomplete SQL, multiple sources, nested scopes, and UTF-8 offsets.

**Non-Goals:** Projection inference for CTEs/derived tables, correlated outer
references, dialect-specific quoted qualifier syntax, broader unqualified comma
completion, ranking, or new dependencies. Client UI work is owned by the linked
dbridge.nvim change
[`trigger-qualified-column-completion`](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-trigger-qualified-column-completion).

## Decisions

- Add a qualified completion path before the existing context classifier. A
  regex identifies a potential qualifier/partial column only; the AST confirms
  it is a column expression, excluding comments, literals, and table positions.
- Reuse `_prefix_at` for byte offsets; replace only the partial column token and
  any remaining token suffix after the cursor with a unique placeholder before
  parsing. Parse all statements with the existing error-tolerant sqlglot API.
- Locate the placeholder column's nearest SELECT, then use sqlglot's selected
  sources for that exact scope. Introspect only an unambiguous matching physical
  Table, preserving its schema/catalog parts for Adapter lookup. Account for
  case-insensitive CTE names before treating a source as physical. A whole-tree
  alias map would leak across subqueries and statements;
  source inference for derived or correlated expressions is deferred.
- Preserve the existing completion item shape and schema order. Filter typed
  column prefixes case-insensitively and return bare column insertion text.
- Keep driver calls in Adapters and the synchronous execution model from
  ADR-0001. No ADR is superseded; no transport/protocol migration is needed.

## Risks / Trade-offs

- Incomplete SQL can remain unparseable → return no qualified suggestions and
  assert graceful behavior in tests; never guess a schema from an unrelated scope.
- Neovim's source lacks an explicit dot trigger → the companion client change
  registers triggering and checks the shared nvim-cmp/server flow. Retain direct
  server regression tests so client triggering and SQL resolution stay distinct.
- Broader SQL source types remain unsupported → document and track follow-up
  scope instead of exposing incorrect physical-table columns.

## Migration Plan

Run existing clients against the updated server and restart their server process.
No Profile or database changes are required. Reverting the completion change
restores the prior suggestions without a protocol version change.
