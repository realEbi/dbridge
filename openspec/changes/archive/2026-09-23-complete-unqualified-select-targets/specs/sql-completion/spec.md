## ADDED Requirements

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
