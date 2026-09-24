## ADDED Requirements

### Requirement: Return executable table identifiers

getTableSchema SHALL add a server-owned sql_identifier for a resolved SQLite or DuckDB table. Adapters SHALL quote each literal component by wrapping it in double quotes and doubling embedded double quotes. SQLite identifiers SHALL use schema.table; DuckDB identifiers SHALL use catalog.schema.table. An unresolved table SHALL have a null identifier. SQLite introspection SHALL expose attached namespaces and scope table listings and metadata to the requested namespace.

#### Scenario: Literal punctuation and keywords
- **WHEN** a table name contains spaces, a keyword, embedded double quotes, or a literal dot
- **THEN** executing SELECT with its returned sql_identifier reads that exact table

#### Scenario: Attached SQLite namespace
- **WHEN** a SQLite database is attached with a literal namespace name
- **THEN** database/schema listings expose it and its table listing stays within that namespace

#### Scenario: Duplicate names in different scopes
- **WHEN** same-named tables exist in separate schemas or catalogs and one explicit identity is requested
- **THEN** its columns and sql_identifier refer only to the selected table

### Requirement: Preserve compatibility and structured identity

getTableSchema SHALL continue accepting the existing fqn string and SHALL additionally accept `table: {name, database?, schema?}` containing literal strings. Structured identity SHALL take precedence over fqn and invalid non-null shapes SHALL return INVALID_REQUEST. listTables SHALL continue returning strings. Cached schemas SHALL remain separated by full structured identity and refreshSchema SHALL invalidate them.

#### Scenario: New caller supplies literal components
- **WHEN** the request supplies both a legacy fqn and a structured table identity whose component contains a dot
- **THEN** the literal component is preserved without splitting it

#### Scenario: Existing caller
- **WHEN** the caller supplies only the existing fqn
- **THEN** table metadata remains available and the response adds sql_identifier

#### Scenario: Invalid structured identity
- **WHEN** table is not an object with a nonempty string name and optional nonempty string scope components
- **THEN** the request returns INVALID_REQUEST without terminating the server

#### Scenario: Refresh cached identity
- **WHEN** a scoped table schema changes and refreshSchema is called
- **THEN** the next structured lookup returns fresh metadata for that same identity
