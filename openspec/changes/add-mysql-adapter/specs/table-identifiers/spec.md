## MODIFIED Requirements

### Requirement: Return executable table identifiers

getTableSchema SHALL add a server-owned sql_identifier for a resolved SQLite, DuckDB, or MySQL table. SQLite and DuckDB Adapters SHALL quote each literal component by wrapping it in double quotes and doubling embedded double quotes. The MySQL Adapter SHALL quote each literal component by wrapping it in backticks and doubling embedded backticks, so the identifier runs whether or not the Session's SQL mode treats double quotes as identifier quotes. An identifier SHALL name the table's Scope Path components in declared order followed by the table name, so a SQLite identifier has one container component, a DuckDB identifier has two, and a MySQL identifier has one. An unresolved table SHALL have a null identifier. SQLite introspection SHALL expose attached namespaces as first-level containers, and listings and metadata SHALL stay within the requested Scope Path.

#### Scenario: Literal punctuation and keywords
- **WHEN** a table name contains spaces, a keyword, embedded double quotes, or a literal dot
- **THEN** executing SELECT with its returned sql_identifier reads that exact table

#### Scenario: MySQL name with an embedded backtick
- **WHEN** a MySQL table name contains a backtick, a space, or a literal dot
- **THEN** its sql_identifier wraps each component in backticks with embedded backticks doubled
- **AND** executing SELECT with that identifier reads that exact table

#### Scenario: Attached SQLite namespace
- **WHEN** a SQLite database is attached with a literal namespace name
- **THEN** the database listing exposes it as a first-level container and its table listing stays within that namespace

#### Scenario: Duplicate names in different scopes
- **WHEN** same-named tables exist in separate schemas or catalogs and one explicit Scope Path is requested
- **THEN** its columns and sql_identifier refer only to the selected table

#### Scenario: Identifier arity matches the declared hierarchy
- **WHEN** a resolved table's sql_identifier is compared with its reported Scope Path
- **THEN** the identifier's container components are exactly that Scope Path, with no component repeated to fill an undeclared level
