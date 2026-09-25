## Why

dbridge serves only SQLite and DuckDB, and the parked MySQL module targets an
interface that no longer exists. ADR-0003 calls the async Adapter cancellation
contract provisional until a native async MySQL driver implements it. A spike on
2026-09-25 compared aiomysql, asyncmy, and `mysql.connector.aio` against MySQL
8.4.11. All three passed 14 cancellation scenarios once the Adapter supplied the
safety none of the drivers provides. aiomysql did so with the fewest private
internals and no driver-defect workarounds. See
[backlog 019](../../../../docs/backlog/019-mysql-adapter.md).

## What Changes

- Add a `mysql` Adapter built on aiomysql. It is an optional feature, installed
  with the `dbridge[mysql]` extra. The extra replaces today's unused `pymysql`
  entry. The registry imports the driver only when a MySQL Session connects,
  and it reports a clear error when the extra is missing.
- MySQL Sessions execute SQL, cancel running and queued work, cap fetched rows,
  and disconnect under the same contracts as the shipped Adapters. Cancellation
  and row-cap release send `KILL QUERY` to the statement's server thread. It is
  sent over a control connection shared per server and account.
- MySQL declares one Scope Level, `database`, and lists databases, tables, and
  table metadata, including primary and foreign keys. `sql_identifier` quotes
  components with backticks.
- Known limits are documented and not solved:
  - Cancellation is unsafe through proxies or load balancers.
  - `TEMPORARY` tables are not listed.
  - Only MySQL 8.4 is verified.
  - Capped `CALL` and multi-statement requests read their remaining rows
    instead of stopping early.
- The removed parked module is replaced. PostgreSQL and Snowflake stay parked.
- The MySQL Adapter module is excluded from coverage measurement. Its tests need
  a real server, so they run locally when one is configured. CI does not run a
  MySQL service.

## Capabilities

### New Capabilities

- `mysql-adapter`: Installing and connecting a MySQL Session, and its Profile
  configuration. Also covers how cancellation and row caps stop server work, the
  metadata MySQL reports, and the documented limits.

### Modified Capabilities

- `scope-addressing`: MySQL declares one `database` Scope Level with a default
  Scope Path.
- `session-dialect`: `dbridge/connect` reports `mysql` for a MySQL Session.
- `table-identifiers`: MySQL identifiers use backtick quoting instead of the
  double quotes SQLite and DuckDB use.
- `query-results`: The early-stop guarantee has a MySQL exception for `CALL`
  and multi-statement requests.
- `test-coverage`: Optional Adapters are excluded from measurement. Their driver
  is an extra and their verification needs an external database server.

## Impact

**Roadmap and backlog.** Resolves [019](../../../../docs/backlog/019-mysql-adapter.md),
the MySQL outcome of milestone 3 (*Broader database support*). This validates
ADR-0003's contract for a native async driver. PostgreSQL (020) and Snowflake
(021) remain. A new backlog item covers verifying other server versions (MySQL
8.0 and 9.x, MariaDB). Sharing the control connection touches
[pooling (046)](../../../../docs/backlog/046-adapter-pooling.md) but does not
implement it.

**Repositories.** Only dbridge changes. dbridge.nvim already renders Scope Levels,
dialect, and `sql_identifier` from server data, so it needs no linked change. A
client-side MySQL check is optional manual verification.

**Protocol compatibility.** Additive. No existing method, parameter, or reply
field changes. The only new wire values are `adapter: "mysql"`, dialect `mysql`,
and Scope Level `database`.

**Code.**
- New: `adapters/mysql.py`.
- Changed: `adapters/registry.py` (lazy optional import), `pyproject.toml`
  (extra and coverage omit).
- Removed: `adapters/_parked/mysql.py`.
- The Dispatcher, executor, and Session manager are unchanged.

**Dependencies.** Optional only: `aiomysql` plus `cryptography`, which MySQL
8.4's default `caching_sha2_password` authentication needs.

**Documentation.** README (install, Profile config, limits), current
architecture, ADR-0003 status, a new ADR for the MySQL kill path,
`development.md` (local MySQL test command), roadmap milestone 3, and backlog.
