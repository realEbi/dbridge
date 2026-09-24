## Context

See proposal.md for motivation and specs/table-keys/spec.md for the contract.

`TableSchema` in `adapters/base.py` carries `primary_keys: list[str]` and
`foreign_keys: list[ForeignKey]`, where `ForeignKey` is one column pair. The Engine
serializes the dataclass with `asdict`. SQLite builds keys from `PRAGMA table_info`
and `PRAGMA foreign_key_list`; DuckDB returns empty lists. Under
[ADR-0003](../../../docs/adr/0003-async-orchestration.md), DuckDB reads catalog
metadata on its metadata Lane cursor and answers temporary tables from a snapshot
taken on the query connection after each statement.

Probes against the pinned drivers (SQLite 3.50.4, DuckDB 1.1.3) established:

- `duckdb_constraints()` returns one row per constraint, with
  `constraint_column_names` and `referenced_column_names` in key order, a
  `constraint_name` (DuckDB generates one when the DDL names none), and
  `constraint_index`. A reference that omits columns is already resolved to the
  parent's primary key.
- DuckDB rejects foreign keys across schemas or catalogs ("Creating foreign keys
  across different schemas or catalogs is not supported"). Keys inside an attached
  catalog work and are reported with that `database_name`.
- A DuckDB cursor does not see the connection's temporary constraints:
  `duckdb_constraints()` on a cursor reports no `temp` rows that the query
  connection reports.
- SQLite `table_info.pk` is the column's 1-based position in the primary key, so
  `PRIMARY KEY (b, a)` reports `b` as 1 and `a` as 2. The current code reads rows in
  column order and reports `[a, b]`.
- SQLite `foreign_key_list` reports one row per column pair, grouped by `id` and
  ordered by `seq`. `id` is not declaration order. A shorthand `REFERENCES r`
  reports `to` as NULL. SQLite exposes no constraint names through these pragmas.

## Goals / Non-Goals

**Goals:**

- One key model in `adapters/base.py` that every Adapter fills, including future
  engines whose foreign keys cross schemas.
- Key metadata for DuckDB catalog and temporary tables with no extra round trip
  through the query Lane for catalog tables.

**Non-Goals:**

- No `getERD` implementation, relationship traversal, or reverse lookup of the
  tables that reference a given table.
- No unique, check, or not-null constraint reporting, and no referential actions
  (`ON DELETE`, `ON UPDATE`).
- No parsing of SQL DDL text.

## Decisions

### D1. Key dataclasses mirror the wire shape

Add `PrimaryKey(name: str | None, columns: list[str])` and replace `ForeignKey` with
`ForeignKey(name, columns, referenced_path: ScopePath, referenced_table,
referenced_columns)`. `TableSchema.primary_keys` becomes `primary_key: PrimaryKey |
None = None`. The Engine keeps serializing with `asdict` and converts
`referenced_path` to a list, as it already does for `scope`.

*Alternatives:* Keep internal pair records and reshape them in the Engine. That
leaves every Adapter free to lose grouping before the Engine sees it; one shared
model makes the Adapter responsible for the grouping it knows.

### D2. DuckDB catalog tables read `duckdb_constraints()` on the metadata Lane

`_get_table_schema` runs a second query on the same metadata cursor, filtered by
`database_name`, `schema_name`, and `table_name` and by the constraint types
`PRIMARY KEY` and `FOREIGN KEY`, ordered by `constraint_index`. Each row becomes one
`PrimaryKey` or `ForeignKey`. Because DuckDB forbids cross-schema and cross-catalog
foreign keys, `referenced_path` is the table's own path.

*Alternatives:* `information_schema.table_constraints` and
`referential_constraints` exist, but joining them to key columns needs
`key_column_usage` and reconstructs what `duckdb_constraints()` already returns in
order.

### D3. DuckDB temporary keys join the query-connection snapshot

`_capture_session_metadata` already reads temporary tables on the query connection.
It also reads `duckdb_constraints()` for `database_name = 'temp'` there and stores the
keys in the snapshotted `TableSchema`. A cursor cannot see them, so the metadata Lane
cannot answer this.

### D4. SQLite primary key follows the `pk` ordinal

Sort `table_info` rows with a nonzero `pk` by that value. `name` is null: the
pragmas expose no constraint name, and D6 rejects parsing DDL to find one.

### D5. SQLite foreign keys group by `id` and resolve shorthand targets

Group `foreign_key_list` rows by `id`, order entries by `id` and columns by `seq`.
When `to` is NULL, read `PRAGMA <namespace>.table_info(<parent>)` in the same
namespace and use its primary-key columns ordered by D4. A missing parent yields an
empty `referenced_columns`. SQLite resolves a parent in the child's own database, so
`referenced_path` is the table's own one-component path.

### D6. Report engine names; do not synthesize or parse

`name` is the engine's constraint name or null. SQLite names could be recovered by
parsing `sqlite_master.sql`, but quoted identifiers, comments, and column-level
constraints make that a small SQL parser for a field no client uses yet.
Synthesizing names like DuckDB's would present an invented name as the engine's.

### D7. Stable engine order, not declaration order

Entries follow the engine's constraint identifier (`constraint_index` for DuckDB,
`id` for SQLite). SQLite ids are not declaration order, so the spec promises only a
stable order. Column order inside an entry is always key order.

## Risks / Trade-offs

- [`duckdb_constraints()` columns change in a later DuckDB release] → Adapter tests
  cover the key shape against the pinned driver, so an upgrade that changes the
  function fails there first.
- [An unknown client reads `primary_keys` or the old foreign-key pairs] → No known
  consumer exists: dbridge.nvim asserts `primary_keys` only in a test, and no Lua
  code reads either field. The README records the new shape, and the proposal marks
  the change as breaking.
- [`getTableSchema` on DuckDB now runs two metadata queries] → Both run on the
  metadata Lane and the result is cached by the schema registry, so the cost applies
  once per table per refresh.
- [SQLite never reports constraint names] → Stated in the spec as null when the
  engine reports none; revisit only if a client needs names.

## Migration Plan

Merge this server change first. The linked dbridge.nvim change
`adopt-table-key-constraints` then updates its transport test to assert
`primary_key` and runs against the merged server. Rolling back means reverting both
changes; neither alters persisted data.
