# 018 - Offer columns after a SELECT comma

- Repo: dbridge; dbridge.nvim owns completion acceptance
- Status: done
- Change: [complete-unqualified-select-targets](../../openspec/changes/archive/2026-09-23-complete-unqualified-select-targets/)
- Origin: Legacy backlog 4.3; retained from revision `80d71d4`.

## Problem / opportunity

Before this change, a trailing comma in a SELECT list, such as SELECT id,
followed by a cursor, fell through to keyword suggestions.

## Desired outcome

Keep column completion active at subsequent SELECT targets, including multiline SQL and explicit cursor offsets.

## Notes and references

Inspect [completion](../../src/dbridge/core/completion.py) and [completion tests](../../tests/core/test_completion.py).

## Resolution

Unqualified SELECT target expressions now resolve physical sources in the cursor's
SELECT, including after commas, inside expressions, and with case-insensitive
prefix filtering. Multiline SQL and UTF-8 byte positions are covered by core and
real SQLite/DuckDB Engine/stdio tests. Other statements and nested/derived scopes
do not leak columns. Projected and correlated source inference remains in [055](055-completion-derived-and-correlated-sources.md).

The companion [client change](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-replace-unqualified-column-completions)
replaces unqualified identifier suffixes correctly with default nvim-cmp Insert
acceptance; real client tests verify the shared flow against both Adapters.
