# sql-completion Specification

## Purpose

Provide useful alias-qualified SQL column suggestions through DSP while preserving
cursor offsets, query scope, and completion item compatibility for editor clients.

## Requirements

### Requirement: Complete qualified physical-table columns

`dbridge/complete` SHALL offer columns of a physical table selected in the current
SELECT scope when an unquoted qualifier before the cursor refers to that table's
alias, or its name when unaliased. This SHALL work in SELECT expressions including
after commas and in WHERE and JOIN ON expressions for SQLite and DuckDB Sessions.
Alias matching and optional column-prefix filtering SHALL be case-insensitive.
Physical source lookup SHALL retain schema/catalog qualifiers, including SQLite
attached database namespaces and DuckDB catalog/schema scopes.

#### Scenario: Complete either selected product column
- **WHEN** SQL is `SELECT p.name, p.category FROM products p LIMIT 100` and the
  cursor is immediately after either `p.`
- **THEN** the result contains the columns of products, in schema order
- **AND** it contains no keyword suggestions or columns from other tables

#### Scenario: Incomplete column or prefix
- **WHEN** SQL is `SELECT p.na FROM products AS p` and the cursor follows `p.na`
- **THEN** the result contains only product columns whose names begin with `na`
- **AND** an unfinished `p.` before the FROM clause still resolves products

#### Scenario: Joined tables
- **WHEN** the current query selects products as p and orders as o and completion
  is requested after `p.` in a WHERE or JOIN ON expression
- **THEN** only product columns are offered

#### Scenario: Same table name in different DuckDB schemas
- **WHEN** two DuckDB schemas contain products with different columns and the
  current query selects one explicitly as p
- **THEN** qualified completion returns only that schema's product columns

#### Scenario: SQLite attached database source
- **WHEN** products exists in main and an attached SQLite namespace and the query selects the attached table as p
- **THEN** qualified completion returns only the attached table's columns

### Requirement: Preserve scope and tolerate unresolved SQL

Qualified completion SHALL resolve only sources selected by the SELECT containing
the cursor. It MUST NOT borrow aliases from other statements, sibling or nested
queries, or UNION branches. Unknown or ambiguous qualifiers, unavailable metadata,
and unresolvable SQL SHALL return an empty list without raising an RPC error.
CTE/derived-table projections and outer correlated references are not supported
by this initial contract and SHALL NOT produce guessed physical-table columns.

#### Scenario: Nested alias shadows another alias
- **WHEN** an inner SELECT aliases orders as p and the outer SELECT aliases
  products as p and the cursor is after `p.` in the inner SELECT
- **THEN** only orders columns are offered

#### Scenario: No source in the current scope
- **WHEN** the qualifier is unknown in the cursor's SELECT or belongs only to a
  different statement or scope
- **THEN** completion returns an empty list

#### Scenario: Derived or CTE source
- **WHEN** p names a derived table or CTE in the cursor's SELECT
- **THEN** qualified completion returns an empty list

#### Scenario: Dot occurs in a literal or comment
- **WHEN** the text immediately before the cursor ends with `p.` inside a SQL
  string or comment
- **THEN** it does not return product columns

### Requirement: Keep cursor and item compatibility

Completion SHALL continue accepting full SQL with an optional UTF-8 byte offset
`position`, defaulting to the end. Column suggestions SHALL retain the existing
`label`, `kind`, `detail`, `insert_text`, and `sort_key` fields, with only the
unqualified column name as insertion text so the existing qualifier remains once.
Existing unqualified table, column, and keyword completion SHALL remain available.

#### Scenario: Multibyte text before the cursor
- **WHEN** SQL contains multibyte text before `p.` and position is its UTF-8 byte
  offset immediately after the dot
- **THEN** the appropriate physical table's columns are returned

#### Scenario: Cursor inside an existing identifier
- **WHEN** the cursor follows `p.na` inside `p.name`
- **THEN** completion resolves the same table and filters by `na`
- **AND** the suggestion inserts `name`, not `p.name`
