## Why

`dbridge/getTableSchema` returns empty key metadata for every DuckDB table, and
its key shape cannot describe what the next Adapters need. A foreign key is one
`{column, referenced_table, referenced_column}` pair, so a composite key is split
into unrelated entries and a referenced table outside the referencing table's
Scope Path cannot be named. SQLite also reports composite primary-key columns in
table order instead of key order, and reports a null referenced column when a
declaration names only the parent table. Fixing the contract now, while no client
reads foreign keys, keeps MySQL, PostgreSQL, and Snowflake from inheriting a lossy
shape. See [backlog 005](../../../docs/backlog/005-duckdb-constraints.md).

## What Changes

- **BREAKING** `getTableSchema` replaces `primary_keys: [string]` with
  `primary_key: {name, columns} | null`. `columns` is in key order; `name` is the
  engine's constraint name or null.
- **BREAKING** Each `foreign_keys` entry becomes one constraint:
  `{name, columns, referenced_path, referenced_table, referenced_columns}`.
  `columns[i]` refers to `referenced_columns[i]`, and `referenced_path` is the
  referenced table's full Scope Path.
- DuckDB reports primary and foreign keys for catalog tables and temporary tables.
- SQLite reports composite primary-key columns in key order, groups a composite
  foreign key into one entry, and resolves an omitted referenced column list to
  the parent table's primary key.
- A table without a declared primary key reports `primary_key: null`. Unique,
  check, and not-null constraints stay out of scope.

## Capabilities

### New Capabilities

- `table-keys`: The primary-key and foreign-key metadata `getTableSchema` returns,
  its ordering and pairing guarantees, and how a missing or unresolvable key is
  reported.

### Modified Capabilities

None. `table-identifiers` keeps its `sql_identifier` requirement, and
`scope-addressing` keeps its Scope Path request rules; `referenced_path` follows
them without changing them.

## Impact

**Roadmap and backlog.** Resolves [005](../../../docs/backlog/005-duckdb-constraints.md),
one of the two remaining items of milestone 1 (*Reliable daily use*). The other,
[001](../../../docs/backlog/001-profile-rename.md), is planned separately in
`rename-profiles-atomically`. Supplies the constraint metadata
[ERD extraction (011)](../../../docs/backlog/011-erd-extraction.md) depends on
without implementing `getERD`. Sets the key shape milestone 3 Adapters implement.

**Repositories.** dbridge owns the contract and Adapter changes. dbridge.nvim has a
linked change, `adopt-table-key-constraints`, which updates its real-server
transport test. The client reads neither field in production code.

**Protocol compatibility.** Breaking for `getTableSchema` key fields only; columns,
`scope`, and `sql_identifier` are unchanged. No other client is known to read
these fields. The server change merges first; the client test then targets it.

**Code.** `adapters/base.py` key dataclasses; SQLite and DuckDB `_get_table_schema`;
DuckDB's temporary-table snapshot. No dependency changes.

**Documentation.** README `getTableSchema` row and an example of the key shape;
current architecture's metadata section; backlog 005 and 011; the milestone 1
roadmap text.
