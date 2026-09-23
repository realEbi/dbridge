# sql-completion Specification

## Purpose

Provide useful SQL column and keyword suggestions through DSP while preserving
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

### Requirement: Complete unqualified SELECT target expressions

`dbridge/complete` SHALL offer columns from physical FROM/JOIN sources selected in
the cursor's SELECT for an unquoted unqualified column position in its target
expressions. This SHALL include the first target, targets after commas, and
columns inside target expressions for SQLite and DuckDB Sessions. The server SHALL
filter a typed column prefix case-insensitively, preserve source and schema column
order, and retain bare insertion text and the existing completion item fields.
Identical names from different physical sources SHALL retain their table detail;
this change does not establish a new ranking or deduplication policy.

#### Scenario: Complete after a comma before the FROM clause
- **WHEN** SQL is `SELECT id,  FROM products` and the cursor follows the comma and space
- **THEN** product columns are offered, including name and category
- **AND** the result contains columns rather than dialect keywords

#### Scenario: Partial identifier in a multiline expression
- **WHEN** SQL is `SELECT 'café',\n COALESCE(na, '') FROM products` and the UTF-8
  byte cursor position follows `na`
- **THEN** only product columns beginning with `na` are offered
- **AND** a cursor inside the existing identifier `name` has the same result

#### Scenario: Columns from joined physical sources
- **WHEN** the cursor is at an unqualified SELECT target with products and orders
  selected by FROM/JOIN in that SELECT
- **THEN** available columns from both physical sources are offered in source order
- **AND** their detail identifies the physical table, including schema qualification

#### Scenario: No matching prefix or unavailable metadata
- **WHEN** physical sources resolve but no available column matches the typed prefix
- **THEN** the result is empty without an RPC error
- **AND** unavailable metadata for one source does not prevent other physical
  sources from contributing matching columns

### Requirement: Isolate unqualified SELECT sources and use a keyword fallback

Unqualified SELECT completion SHALL NOT borrow physical tables from another
statement, a nested or sibling SELECT, a UNION branch, or the body of a CTE or
derived source. It SHALL NOT infer projected or outer correlated columns. When
no physical source can be resolved in the current SELECT, including a bare
`SELECT `, it SHALL return the Session dialect's keyword suggestions without
listing every table or introspecting unrelated columns. A SELECT-like token in
a string, comment, table name, or output alias SHALL NOT cause SELECT column
suggestions. Parse failures SHALL not propagate as RPC errors.

#### Scenario: Bare SELECT without a FROM clause
- **WHEN** completion is requested after `SELECT ` or `SELECT id, ` without a FROM
- **THEN** dialect keywords are returned and no database tables are introspected

#### Scenario: Nested scope and statement boundaries
- **WHEN** the cursor is in an inner SELECT that selects orders while an outer,
  sibling, or separate SELECT selects products
- **THEN** only orders columns are offered

#### Scenario: Derived or CTE sources without a physical source
- **WHEN** the cursor's SELECT reads only CTEs or derived tables
- **THEN** dialect keywords are returned without exposing columns from their bodies

#### Scenario: Physical and derived sources together
- **WHEN** the cursor's SELECT joins a physical products table with a derived source
- **THEN** product columns are offered without guessed columns from the derived source

#### Scenario: Cursor within a literal or comment
- **WHEN** the cursor follows a comma or a SELECT-like token inside a SQL literal or comment
- **THEN** it does not receive physical-table column suggestions
