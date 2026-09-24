## Why

Explorer-generated SELECT statements use bare names, so duplicate table names can select the wrong table and names containing spaces or SQL punctuation fail. This implements [server backlog 002](../../../../docs/backlog/002-qualified-identifiers.md) and the reliable-daily-use roadmap outcome with a linked Neovim change.

## What Changes

- Add server-owned `sql_identifier` to the existing getTableSchema object response.
- Accept optional structured table identity alongside legacy `fqn`, preserving raw name components.
- Quote and qualify identifiers in SQLite/DuckDB Adapters; retain existing listTables string results.
- Verify generated identifiers through real SQLite/DuckDB queries and client activation.

## Capabilities

### New Capabilities
- `table-identifiers`: SQL identifiers and structured table metadata lookup.

### Modified Capabilities
- `sql-completion`: remove the attached SQLite metadata limitation now covered by scoped lookup.

## Impact

Server owns the additive DSP contract, Adapter metadata, and tests. Neovim owns retaining identifiers and generated SELECT behavior in [use-server-table-identifiers](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-use-server-table-identifiers). Existing fqn callers and table-list consumers remain supported. Session dialect RPC (008), hierarchy flattening (003), concurrency, and additional adapters are out of scope.
