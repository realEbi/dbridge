## Why

Typing `p.` in `SELECT p.name, p.category FROM products p LIMIT 100` returns
keywords instead of product columns, even through a direct SQLite RPC. The
server's completion classifier and table extraction do not resolve qualifiers.

## What Changes

- Complete columns for unquoted physical-table aliases in SELECT expressions,
  including after commas, and WHERE/JOIN conditions.
- Resolve the qualifier in the cursor's query scope using the full statement,
  tolerate an unfinished column after the dot, and preserve UTF-8 cursor offsets.
- Keep the existing item shape and insert only the column name after the dot.
- Document the supported behavior and remaining CTE/derived-column limitations.

## Capabilities

### New Capabilities

- `sql-completion`: Alias-qualified physical-table column completion, scope
  isolation, partial identifiers, and compatible completion items/cursor offsets.

### Modified Capabilities

None. The only existing capability spec is test-coverage, whose requirements stay
unchanged.

## Impact

Owner: dbridge server, primarily Core Engine completion and its tests. No driver,
dependency, or wire-shape changes. The companion dbridge.nvim change
[`trigger-qualified-column-completion`](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-trigger-qualified-column-completion)
owns automatic dot triggering and verifies
the shared UI flow. Neovim continues sending full SQL and the cursor byte offset
through the existing `dbridge/complete` contract. Both repositories' changes are
needed for automatic alias completion with the updated server.

Selects backlog [015](../../../../docs/backlog/015-alias-completion.md) for roadmap
milestone 4 (Richer SQL assistance). Unqualified completion after a comma (018),
bare SELECT fallback (053), dialect-specific identifier quoting (002), and CTE or
derived-table projection inference remain outside this change.
