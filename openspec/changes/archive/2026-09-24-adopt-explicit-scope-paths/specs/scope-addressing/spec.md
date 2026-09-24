## Purpose

Address database metadata by explicit, Adapter-declared Scope Paths so that every
listing and lookup states where it applies, and clients render each engine's real
container hierarchy instead of assuming a fixed database/schema pair.

## ADDED Requirements

### Requirement: Describe the Adapter's scope hierarchy

An Adapter SHALL declare its Scope Levels: an ordered list of the container tiers
that locate a table, each with a stable name and a client-facing label. SQLite SHALL
declare one level; DuckDB SHALL declare two. `dbridge/connect` SHALL return that
declaration together with a default Scope Path valid for the new Session, so a client
can issue scoped operations without a discovery request. `dbridge/refreshSchema`
SHALL return the current declaration and default Scope Path. The declaration returned
by `refreshSchema` SHALL be authoritative; the copy returned by `connect` describes
the hierarchy as of connect time. The wire declaration SHALL use `levels: [{name, label}]` and
`default_path: [string, ...]`. Connect SHALL include `session_id` and `dialect`;
refresh SHALL include `ok: true`. A Session SHALL NOT expose a method that changes
its hierarchy.

#### Scenario: SQLite declares a single level
- **WHEN** a client connects to a SQLite Profile
- **THEN** the response declares exactly one Scope Level and a default Scope Path of
  one component naming the `main` namespace
- **AND** no level duplicates another level's value for the same table

#### Scenario: DuckDB declares two levels
- **WHEN** a client connects to a DuckDB Profile
- **THEN** the response declares two ordered Scope Levels, catalog before schema
- **AND** the default Scope Path names the Session's current catalog and current schema

#### Scenario: Hierarchy grows while the Session is live
- **WHEN** a DuckDB Session attaches a second catalog and the client calls
  `dbridge/refreshSchema`
- **THEN** the response returns the current Scope Levels and default Scope Path
- **AND** the next database listing includes the attached catalog
- **AND** the Scope Paths the client already holds continue to resolve their tables

### Requirement: Require an explicit Scope Path for metadata operations

`dbridge/listSchemas`, `dbridge/listTables`, `dbridge/getTableSchema`,
`dbridge/getERD`, and `dbridge/complete` SHALL require a Scope Path in `path`. A Scope Path
SHALL be an ordered list of nonempty literal strings whose length matches the number
of leading Scope Levels the operation addresses. A request whose Scope Path is
missing, is not a list of nonempty strings, or has an arity the Adapter did not
declare SHALL return `INVALID_REQUEST` without terminating the server. The server
SHALL NOT retain an active or current scope for a Session, and SHALL NOT substitute
one when a request omits its Scope Path. `dbridge/listDatabases` SHALL NOT take a
Scope Path, because it enumerates the first Scope Level.
`listSchemas` SHALL take a one-component leading path; SQLite SHALL return an empty
list because it declares no second tier. Table listings, table metadata, ERD, and
completion SHALL require a full declared path.

#### Scenario: Scope Path omitted
- **WHEN** a client calls `dbridge/listTables` without a Scope Path
- **THEN** the request returns `INVALID_REQUEST` and the server stays available

#### Scenario: Wrong arity for the Adapter
- **WHEN** a client sends a two-component Scope Path to a SQLite Session, which
  declares one level
- **THEN** the request returns `INVALID_REQUEST` rather than silently ignoring a
  component or treating the two components as one namespace

#### Scenario: Same Scope Path from two clients
- **WHEN** two requests carrying different Scope Paths are handled in sequence for one
  Session
- **THEN** each result reflects only the Scope Path in its own request
- **AND** neither request changes what a later request without that Scope Path returns

### Requirement: Address tables by Scope Path and name

`dbridge/getTableSchema` SHALL identify a table by a `path` plus a literal table
`name`, both top-level request parameters. The dot-separated `fqn` parameter SHALL no longer be accepted. Every component
and the table name SHALL be treated as a literal string: a component containing a
dot, a space, an embedded double quote, or a reserved word SHALL NOT be split or
reinterpreted. The returned metadata SHALL report the table's Scope Path in `scope` with exactly
the arity its Adapter declares, and SHALL NOT report the same container value under
two different level names. A resolved table SHALL carry an executable
`sql_identifier`; an unresolved table SHALL carry a null identifier.

#### Scenario: SQLite reports one container, not two
- **WHEN** a client requests the schema of a table in a SQLite Session
- **THEN** the response reports a one-component Scope Path
- **AND** its `sql_identifier` has the same arity as that Scope Path plus the table name

#### Scenario: Duplicate table names in different catalogs
- **WHEN** same-named tables exist in two DuckDB catalogs and a client requests one by
  its full Scope Path
- **THEN** the columns and `sql_identifier` describe only that table
- **AND** requesting the other Scope Path returns the other table's columns

#### Scenario: Literal dot in a component
- **WHEN** a Scope Path component or table name contains a literal dot
- **THEN** that component is preserved whole and MUST NOT select a table in a
  differently named container

#### Scenario: Table absent from the requested scope
- **WHEN** a client requests a table that exists in another container but not in the
  requested Scope Path
- **THEN** the response reports no columns and a null `sql_identifier` for that
  Scope Path, rather than metadata for the same-named table elsewhere

### Requirement: Return identity and container role with listing entries

`dbridge/listTables` SHALL return an entry per table carrying its literal name and an
executable `sql_identifier`, so a client can build runnable SQL without a further
metadata request. `dbridge/listDatabases` and `dbridge/listSchemas` SHALL return an
entry per container carrying its literal `name` and an `internal` boolean indicating
whether the engine treats it as internal rather than user data. Engine-internal containers SHALL be marked and
returned, not omitted.

#### Scenario: Two catalogs no longer collapse into indistinguishable entries
- **WHEN** same-named tables exist in two DuckDB catalogs and a client lists each
  catalog's tables
- **THEN** each listing returns that catalog's table with an `sql_identifier`
  naming its own catalog
- **AND** the two entries are distinguishable without a further request

#### Scenario: Listed table is executable
- **WHEN** a client lists tables for a Scope Path and executes a statement built from
  a returned `sql_identifier`
- **THEN** the statement reads that exact table

#### Scenario: Engine-internal containers are marked
- **WHEN** a client lists databases for a DuckDB Session
- **THEN** the engine-internal containers appear, each marked internal
- **AND** the catalogs holding user data appear unmarked

### Requirement: Cache and invalidate every introspection result by Scope Path

Database listings, schema listings, table listings, and table metadata SHALL all be
served through the Session's introspection cache, keyed by the full literal Scope
Path of the request and, for table metadata, the literal table name. Results for
different Scope Paths SHALL remain separate, including for same-named containers or
tables. `dbridge/refreshSchema` SHALL invalidate all cached introspection results for
that Session, not a subset. Query execution SHALL NOT invalidate the cache
automatically; that remains a known gap.

#### Scenario: Refresh covers container listings
- **WHEN** a schema is created in a database and a client calls
  `dbridge/refreshSchema`
- **THEN** the next schema listing for that Scope Path includes the new schema
  without waiting for cache expiry

#### Scenario: Cached results stay separated by Scope Path
- **WHEN** table listings are requested for two Scope Paths that differ only in their
  first component
- **THEN** each listing returns its own container's tables
- **AND** a cached result for one Scope Path is never returned for the other

#### Scenario: DDL does not invalidate the cache
- **WHEN** a client executes a statement that creates a table and then lists tables
  for that Scope Path without refreshing
- **THEN** the listing may omit the new table until refresh or cache expiry
