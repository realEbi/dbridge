## MODIFIED Requirements

### Requirement: Return executable table identifiers

getTableSchema SHALL add a server-owned sql_identifier for a resolved SQLite or DuckDB table. Adapters SHALL quote each literal component by wrapping it in double quotes and doubling embedded double quotes. An identifier SHALL name the table's Scope Path components in declared order followed by the table name, so a SQLite identifier has one container component and a DuckDB identifier has two. An unresolved table SHALL have a null identifier. SQLite introspection SHALL expose attached namespaces as first-level containers, and listings and metadata SHALL stay within the requested Scope Path.

#### Scenario: Literal punctuation and keywords
- **WHEN** a table name contains spaces, a keyword, embedded double quotes, or a literal dot
- **THEN** executing SELECT with its returned sql_identifier reads that exact table

#### Scenario: Attached SQLite namespace
- **WHEN** a SQLite database is attached with a literal namespace name
- **THEN** the database listing exposes it as a first-level container and its table listing stays within that namespace

#### Scenario: Duplicate names in different scopes
- **WHEN** same-named tables exist in separate schemas or catalogs and one explicit Scope Path is requested
- **THEN** its columns and sql_identifier refer only to the selected table

#### Scenario: Identifier arity matches the declared hierarchy
- **WHEN** a resolved table's sql_identifier is compared with its reported Scope Path
- **THEN** the identifier's container components are exactly that Scope Path, with no component repeated to fill an undeclared level

## REMOVED Requirements

### Requirement: Preserve compatibility and structured identity

**Reason**: Both of this requirement's compatibility guarantees are deliberately
broken. `listTables` no longer returns strings — bare names cannot distinguish
same-named tables in different containers, which produced duplicate indistinguishable
entries and completion text that failed to execute. The dot-separated `fqn` string no
longer resolves a table, because maintaining it alongside structured identity left two
input shapes for one lookup and made "unscoped" mean different things to listing and
resolution. The `dbridge-2.0` line accepts breaking protocol changes rather than
carrying compatibility shims.

The requirement's surviving guarantees are re-homed rather than dropped. Cache
separation by full literal identity and `refreshSchema` invalidation are restated, in
Scope Path terms and extended to container listings, under the `scope-addressing`
capability's *Cache and invalidate every introspection result by Scope Path*.
Rejecting a malformed table identity with `INVALID_REQUEST` is restated under that
capability's *Require an explicit Scope Path for metadata operations* and *Address
tables by Scope Path and name*.

**Migration**: Replace `fqn: "catalog.schema.table"` and
`table: {name, database?, schema?}` with a literal Scope Path plus a table name, whose
arity comes from the Scope Levels reported by `dbridge/connect`. A caller that
previously sent only a table name and relied on the Adapter filling the rest from its
current catalog and schema SHALL send the default Scope Path returned by
`dbridge/connect` instead. Callers reading `listTables` strings SHALL read the `name`
field of each returned entry, and MAY use each entry's `sql_identifier` in place of a
follow-up `getTableSchema` request made only to learn how to quote the table.
