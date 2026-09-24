# table-keys Specification

## Purpose

Describe the primary and foreign keys `dbridge/getTableSchema` reports, so clients
and future relationship features can rely on complete, ordered, scope-aware key
metadata from every registered Adapter.

## Requirements

### Requirement: Report the table's primary key as one ordered constraint

A `dbridge/getTableSchema` reply SHALL contain `primary_key`, either null or an
object `{name, columns}`. `columns` SHALL list the key's column names in key order,
which is the order the constraint declares them and not necessarily the table's
column order. `name` SHALL be the constraint name the engine reports, or null when
the engine reports none. A table with no declared primary key, and an unresolved
table, SHALL report `primary_key: null`. The reply SHALL NOT contain `primary_keys`.

#### Scenario: Composite primary key declared out of column order
- **WHEN** a table declares columns `a, b` and `PRIMARY KEY (b, a)` on a SQLite or
  DuckDB Session and a client requests its schema
- **THEN** `primary_key.columns` is `["b", "a"]`

#### Scenario: Column-level primary key
- **WHEN** a SQLite table is created as `users (id INTEGER PRIMARY KEY, name TEXT)`
- **THEN** `primary_key` is `{name: null, columns: ["id"]}`

#### Scenario: DuckDB reports its constraint name
- **WHEN** a DuckDB table declares a primary key
- **THEN** `primary_key.name` is the name DuckDB reports for that constraint

#### Scenario: No primary key
- **WHEN** a table declares no primary key, or the requested table does not exist
- **THEN** `primary_key` is null

### Requirement: Report each foreign key as one constraint with paired columns

A reply SHALL contain `foreign_keys`, a list with one entry per foreign-key
constraint. Each entry SHALL be `{name, columns, referenced_path, referenced_table,
referenced_columns}`. `columns` SHALL list the referencing columns in declared key
order, and `columns[i]` SHALL refer to `referenced_columns[i]`. `referenced_path`
SHALL be the referenced table's full Scope Path, with one component per declared
Scope Level, and `referenced_table` SHALL be its literal name, so that a client can
request that table's schema with them. `name` SHALL be the engine's constraint name
or null when the engine reports none. The list order SHALL be stable across repeated
requests for an unchanged table. A table without foreign keys, and an unresolved
table, SHALL report an empty list.

#### Scenario: Composite foreign key stays one entry
- **WHEN** a table declares `FOREIGN KEY (x, y) REFERENCES p (b, a)` on a SQLite or
  DuckDB Session
- **THEN** `foreign_keys` contains one entry with `columns` `["x", "y"]`,
  `referenced_table` `"p"`, and `referenced_columns` `["b", "a"]`

#### Scenario: Two composite keys to the same table
- **WHEN** a table declares two composite foreign keys that both reference table `p`
- **THEN** `foreign_keys` contains two entries, each with only its own column pairs

#### Scenario: Referenced path locates the parent table
- **WHEN** a client requests a child table's schema in a DuckDB schema other than
  the default, or in an attached SQLite namespace
- **THEN** each entry's `referenced_path` names that same catalog and schema, or
  that namespace, and requesting `getTableSchema` with `referenced_path` and
  `referenced_table` returns the parent table

#### Scenario: Temporary DuckDB tables
- **WHEN** a DuckDB Session creates a temporary table with a primary key and another
  temporary table that references it
- **THEN** both tables' schemas report those keys under their `temp` Scope Paths

### Requirement: Resolve an omitted referenced column list

When a foreign-key declaration names the parent table without columns, the entry's
`referenced_columns` SHALL be the parent table's primary-key columns in key order.
If the parent table has no primary key or does not exist, `referenced_columns`
SHALL be an empty list and the entry SHALL still report its `columns`, Scope Path,
and table name. An entry SHALL NOT contain null column names.

#### Scenario: SQLite shorthand reference
- **WHEN** a SQLite table declares `z INTEGER REFERENCES r` and `r` has primary key
  `id`
- **THEN** the entry has `columns` `["z"]` and `referenced_columns` `["id"]`

#### Scenario: SQLite reference to a missing table
- **WHEN** a SQLite table declares `REFERENCES missing` and no table `missing` exists
- **THEN** the entry has `referenced_table` `"missing"` and empty `referenced_columns`

### Requirement: Report key metadata consistently with schema refresh

Key metadata SHALL follow the same caching as the rest of `getTableSchema`: after a
key is added or dropped, `dbridge/refreshSchema` SHALL make the next request report
the current keys. Unique, check, and not-null constraints SHALL NOT be reported as
primary or foreign keys.

#### Scenario: Table recreated with keys after its schema was cached
- **WHEN** a client requests the schema of a table without keys, then the table is
  dropped and recreated with a primary key and a foreign key, and the client calls
  `dbridge/refreshSchema` and requests the schema again
- **THEN** the reply reports the recreated table's primary key and foreign key

#### Scenario: Unique constraint is not a primary key
- **WHEN** a table declares `UNIQUE (a, b)` and no primary key
- **THEN** `primary_key` is null
