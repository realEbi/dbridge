# 003 - Represent each database's browsing hierarchy accurately

- Repo: dbridge, dbridge.nvim
- Status: done
- Change: [server](../../openspec/changes/archive/2026-09-24-adopt-explicit-scope-paths/proposal.md), [dbridge.nvim](../../../dbridge.nvim/openspec/changes/archive/2026-09-24-adopt-explicit-scope-paths/proposal.md)
- Origin: Legacy backlog 1.3; retained from revision `80d71d4`.

## Problem / opportunity

The previous fixed database/schema model reported SQLite's main namespace twice,
producing a redundant main/main level in the client tree.

## Desired outcome

Define a browsing contract that accommodates different catalog/schema hierarchies and lets clients render them consistently.

## Resolution

The server now declares one SQLite namespace level and two DuckDB catalog/schema
levels. Connect and refresh return these declarations and a default Scope Path.
All scoped metadata calls require literal paths, table metadata reports the same
arity, and table listings carry executable identifiers. Attached containers remain
distinct, including when they contain same-named tables.

The linked client renders the declared tiers and retains per-buffer paths. Real
Neovim integration verified attached DuckDB catalogs, single-tier SQLite browsing,
and unedited execution of completed identifiers in each selected scope. See
[ADR-0002](../adr/0002-explicit-scope-paths.md) for the accepted scope decision.
