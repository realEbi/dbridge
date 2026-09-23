## MODIFIED Requirements

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
