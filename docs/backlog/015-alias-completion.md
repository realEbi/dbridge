# 015 - Complete alias-qualified columns

- Repo: dbridge
- Status: done
- Change: [complete-alias-qualified-columns](../../openspec/changes/archive/2026-09-23-complete-alias-qualified-columns/)
- Origin: Legacy backlog 4.3; original design 10; retained from revision `80d71d4`.

## Problem / opportunity

The original Tier-1 completion did not resolve alias-qualified positions such as
`JOIN orders o ON o.`. The reported `SELECT p.name, p.category FROM products p
LIMIT 100` likewise returned only keywords when the cursor followed either `p.`.

## Desired outcome

Resolve aliases and query scope to offer the appropriate columns in SELECT, WHERE, and JOIN conditions.

## Notes and references

Inspect [completion](../../src/dbridge/core/completion.py). Include partial SQL and multiple table scopes in the change's scenarios.

## Resolution

Completion now resolves unquoted physical-table qualifiers in the cursor's
SELECT, including SELECT lists after commas, WHERE expressions, and JOIN ON
conditions. It preserves UTF-8 offsets, column order, bare insertion text, and
schema/catalog parts for Adapter lookup. Real SQLite/DuckDB and stdio tests pass.
Derived/CTE projections, outer correlated references, and identifier limitations
remain in [055](055-completion-derived-and-correlated-sources.md). Client popup
triggering and identifier replacement are owned by the companion dbridge.nvim
[`trigger-qualified-column-completion`](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-trigger-qualified-column-completion)
change, which verifies actual nvim-cmp interaction against this server.
