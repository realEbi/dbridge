## MODIFIED Requirements

### Requirement: Describe the Adapter's scope hierarchy

An Adapter SHALL declare its Scope Levels: an ordered list of the container tiers
that locate a table, each with a stable name and a client-facing label. SQLite SHALL
declare one level; DuckDB SHALL declare two; MySQL SHALL declare one level, named
`database`. `dbridge/connect` SHALL return that
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

#### Scenario: MySQL declares a single database level
- **WHEN** a client connects to a MySQL Profile
- **THEN** the response declares exactly one Scope Level named `database`
- **AND** the default Scope Path has one component naming a database the Session can
  list tables in

#### Scenario: Hierarchy grows while the Session is live
- **WHEN** a DuckDB Session attaches a second catalog and the client calls
  `dbridge/refreshSchema`
- **THEN** the response returns the current Scope Levels and default Scope Path
- **AND** the next database listing includes the attached catalog
- **AND** the Scope Paths the client already holds continue to resolve their tables
