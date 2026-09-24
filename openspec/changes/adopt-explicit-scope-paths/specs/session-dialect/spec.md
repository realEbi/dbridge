## Purpose

Report a Session's SQL dialect to clients so they can apply dialect-specific syntax
handling without inferring it from an Adapter name or the shape of a response.

## ADDED Requirements

### Requirement: Report the Session's SQL dialect

`dbridge/connect` SHALL return the dialect of the Session's Adapter alongside the
`session_id`. The value SHALL be the Adapter's own dialect name — `sqlite` for a
SQLite Session and `duckdb` for a DuckDB Session — and SHALL remain constant for the
life of that Session. The dialect SHALL NOT be the mechanism by which a client learns
the Session's container hierarchy; Scope Levels carry that, so a client rendering a
tree does not need per-engine knowledge.

#### Scenario: Dialect accompanies a new Session
- **WHEN** a client connects from a saved Profile or from inline Adapter data
- **THEN** the response reports the Adapter's dialect together with the `session_id`

#### Scenario: Dialect is stable for the Session
- **WHEN** a client attaches another container and calls `dbridge/refreshSchema`
- **THEN** the Session's reported dialect is unchanged

#### Scenario: Two Sessions with different Adapters
- **WHEN** a client holds one SQLite Session and one DuckDB Session
- **THEN** each reports its own dialect and neither value depends on the other
