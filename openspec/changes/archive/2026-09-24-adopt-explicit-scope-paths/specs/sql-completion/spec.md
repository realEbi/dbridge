## MODIFIED Requirements

### Requirement: Complete qualified physical-table columns

`dbridge/complete` SHALL offer columns of a physical table selected in the current
SELECT scope when an unquoted qualifier before the cursor refers to that table's
alias, or its name when unaliased. This SHALL work in SELECT expressions including
after commas and in WHERE and JOIN ON expressions for SQLite and DuckDB Sessions.
Alias matching and optional column-prefix filtering SHALL be case-insensitive.
Physical source lookup SHALL retain the qualifiers written in the SQL. A source whose
qualifiers name fewer containers than the Adapter declares SHALL have its missing
leading components taken from the request's Scope Path, not from the Adapter's own
current catalog or schema. Literal dots, spaces, and embedded quotes in a source name
or qualifier SHALL remain part of that identifier component and MUST NOT resolve a
different physical table.

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

#### Scenario: Quoted physical source contains a literal dot
- **WHEN** the current query reads the literal table `"sales.products"` as p and
  a different table products exists in the sales namespace
- **THEN** qualified completion offers only the literal table's columns
- **AND** the same holds when the source uses the server-generated qualified identifier

#### Scenario: Partly qualified source resolves against the request Scope Path
- **WHEN** a DuckDB query selects `sales.products` as p, the request's Scope Path names
  an attached catalog, and a different products table exists in the `sales` schema of
  another catalog
- **THEN** only the columns of the table in the requested catalog's `sales` schema are
  offered

### Requirement: Keep cursor and item compatibility

Completion SHALL continue accepting full SQL with an optional UTF-8 byte offset
`position`, defaulting to the end, and SHALL additionally require the request's
Scope Path. Column suggestions SHALL retain the existing `label`, `kind`, `detail`,
`insert_text`, and `sort_key` fields, with only the unqualified column name as
insertion text so the existing qualifier remains once. Unqualified table, column, and
keyword completion SHALL remain available. Table suggestions SHALL come only from the
request's Scope Path, so the same table name SHALL NOT appear twice for one request
from containers the client did not ask about. Every table suggestion SHALL insert its Adapter-provided executable qualified
`sql_identifier`, including tables inside the requested Scope Path. Table labels
SHALL remain literal bare names. Metadata scope does not change SQL execution scope.

#### Scenario: Multibyte text before the cursor
- **WHEN** SQL contains multibyte text before `p.` and position is its UTF-8 byte
  offset immediately after the dot
- **THEN** the appropriate physical table's columns are returned

#### Scenario: Cursor inside an existing identifier
- **WHEN** the cursor follows `p.na` inside `p.name`
- **THEN** completion resolves the same table and filters by `na`
- **AND** the suggestion inserts `name`, not `p.name`

#### Scenario: Same-named tables in two containers
- **WHEN** same-named tables exist in two DuckDB catalogs and completion is requested
  after `FROM ` with a Scope Path naming one of them
- **THEN** that table name is offered once, for the requested catalog only

#### Scenario: Completed table name executes
- **WHEN** a client executes a statement built from the insertion text of a table
  suggestion, without editing it
- **THEN** the statement reads the intended table rather than failing to resolve it

#### Scenario: Scope Path missing from a completion request
- **WHEN** `dbridge/complete` is called without a Scope Path
- **THEN** the request returns `INVALID_REQUEST` and the server stays available
