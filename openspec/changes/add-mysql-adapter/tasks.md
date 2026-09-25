All tasks are owned by the dbridge repository. MySQL checks run locally against
the compose server from task 1.1; CI runs only the skipped form.

## 1. Local MySQL verification setup

- [ ] 1.1 Add a MySQL 8.4 compose file with a seed script to the test tree. The
      seed provides an unprivileged account (no `PROCESS`, `CONNECTION_ADMIN`, or
      `SUPER`) and a 1,000,000-row table. Add `make mysql-up` and `make test-mysql`.
      Verify: `make mysql-up` reports the container healthy and the seeded row
      count is 1,000,000.
- [ ] 1.2 Add the `tests/adapters/mysql/` fixtures. The server comes from
      `DBRIDGE_TEST_MYSQL_*` variables, and the tests skip when those are unset.
      Add an independent observer connection that reads the process list and
      statement history. Verify: `make test` without the variables reports the
      MySQL tests as skipped, with no failures.

## 2. Optional packaging and registration

- [ ] 2.1 Change the `mysql` extra to `aiomysql>=0.3.2,<0.4` plus `cryptography`.
      Add `src/dbridge/adapters/mysql.py` to the coverage `omit` list. Delete
      `adapters/_parked/mysql.py`. Verify: `uv sync --extra mysql` installs both
      packages, and the parked-adapter omit still covers PostgreSQL and Snowflake.
- [ ] 2.2 Register `mysql` in `adapters/registry.py` through a loader that imports
      the adapter module only inside `create_adapter`. A missing driver raises
      `AdapterError` naming `dbridge[mysql]`. Verify with in-process tests:
      - a connect with a blocked `aiomysql` import replies `ADAPTER_NOT_SUPPORTED`
        naming the extra
      - a following SQLite connect succeeds
      - importing the registry does not import `aiomysql`

## 3. Connection and execution

- [ ] 3.1 Implement config parsing: host and port defaults, a numeric-string
      port, required `user`, optional `password` and `database`, autocommit, and
      utf8mb4. Map connect failures to `AdapterConnectionError`. Verify with
      real-server tests:
      - a wrong password replies `CONNECTION_FAILED` and leaves no server
        connection open
      - a missing `user` fails the same way
      - an inserted row survives disconnect and reconnect
- [ ] 3.2 Implement the `_Channel`. It holds one aiomysql connection, a FIFO lock,
      and the thread id, and runs each operation as a shielded reader task. The
      Session owns query and metadata Channels. `execute` reads through an
      unbuffered cursor in converted chunks and replies with the last result set
      that has columns. Verify with real-server tests:
      - `SET @x = 5; SELECT @x AS x` replies `[[5]]`
      - `SELEC 1` replies `QUERY_ERROR`, then `SELECT 1` works
      - five queued executes finish in arrival order

## 4. Interruption through the shared control connection

- [ ] 4.1 Implement the control-connection registry keyed by `(host, port, user)`.
      It opens eagerly, is reference-counted, closes with the last Session,
      serializes kills with a lock, and reopens after a failure. Verify with
      real-server tests:
      - two Sessions on one account share one control connection
      - a Session on a second account gets its own
      - the control connection disappears from the process list after the last
        disconnect
- [ ] 4.2 Implement cancellation on both Channels. Return a finished result.
      Otherwise mark interruption issued, send `KILL QUERY`, wait for the kill and
      the reader, and raise `CancelledError`. The lock is held throughout, and
      queued cancels leave without server contact. The reconnect fallback is logged.
      Verify by porting spike scenarios S1, S2, S5, and S7 as real-server tests,
      plus these:
      - a Session's state survives a cancel (a variable and a temporary table)
      - a cancelled metadata request stops its statement
      - a queued statement never appears in the server's statement history

## 5. Row caps

- [ ] 5.1 Classify requests with sqlglot's MySQL dialect. Only a single parsed
      query statement is killed at the cap; `CALL`, several statements, and
      unparsable SQL are drained. Verify with in-module unit tests run by
      `make test-mysql`:
      - `SELECT`, `WITH`, `SHOW`, and a `UNION` are killable
      - `CALL p()`, `SELECT 1; SELECT 2`, and invalid SQL are not
- [ ] 5.2 Release capped killable statements through the kill path, discarding
      in-flight rows until 1317 and clearing the unbuffered flag. Drain everything
      else. Verify with real-server tests through the executor with `max_rows`
      100:
      - the 1M-row `SELECT` replies within 1 second with a truncation warning,
        and no statement is left running
      - the Session's temporary table survives the cap
      - a procedure returning 1,000 rows and then inserting a row keeps its insert

## 6. Lifecycle

- [ ] 6.1 Implement `disconnect()`: cancel through the kill path, close both
      Channels, and release the control reference. Implement `abandon()`: write
      `KILL <thread id>` packets synchronously, fail pending awaiters, and close
      sockets. Verify by porting spike scenarios S6 (disconnect and abandon) as
      real-server tests. Also add a subprocess test that closes the server's input
      during a long MySQL statement: the process exits and the statement's
      connection disappears.

## 7. Metadata

- [ ] 7.1 Declare the `database` Scope Level. Implement the default Scope Path
      snapshot (`SELECT DATABASE()` after each execute, with fallbacks),
      `listDatabases` with internal marking, `listSchemas` returning an empty
      list, and `listTables` for base tables and views. Verify with real-server
      tests:
      - a configured database becomes the default path
      - `USE other` plus refresh reports `["other"]`
      - a Session with no database falls back to the first non-internal database
      - internal databases are marked
      - `TEMPORARY` tables are absent
- [ ] 7.2 Implement `getTableSchema`: ordered columns with full type,
      nullability, default, and comment; the `PRIMARY` key in key order; grouped
      foreign keys, including a cross-database `referenced_path`; and backtick
      `sql_identifier`s. Verify with real-server tests:
      - a composite primary key reports its columns in key order
      - a composite foreign key to another database reports the right path
      - a table named with a backtick, a space, and a dot executes through its
        `sql_identifier`
      - an unknown table reports no columns and a null identifier

## 8. Protocol integration

- [ ] 8.1 Add a real-server subprocess test for the full DSP flow on a MySQL
      Profile:
      - `dbridge/connect` reports dialect `mysql`, one `database` level, and the
        default path
      - `execute`, then a `$/cancelRequest` that replies `QUERY_CANCELLED`
      - a capped query with a truncation warning
      - `listTables` and `getTableSchema`
      - `disconnect`

      Verify: `make test-mysql` passes with the server up, and `make test` skips
      the suite without it.

## 9. Documentation

- [ ] 9.1 Update the README. Cover installing `dbridge[mysql]` and the MySQL
      Profile keys with an example, and list `mysql` among the supported Adapters.
      State the limits: proxies and load balancers are unsupported; only MySQL
      8.4 is verified; `TEMPORARY` tables are not listed; capped `CALL` and
      multi-statement requests drain; a result arriving just after the kill is
      reported as cancelled. Verify: the README's MySQL section covers each item
      in the mysql-adapter spec's documentation requirement.
- [ ] 9.2 Update `docs/architecture.md` (the queries and adapters section, the
      optional MySQL Adapter, Channels, the control connection, and cap release)
      and `CONTEXT.md` (the Lane entry notes MySQL's native Channels). Amend
      ADR-0003's consequences with the validated contract, the interruption-issued
      boundary, and the rule that cancellation never reaches driver I/O. Add
      ADR-0004 for the MySQL kill path and control connection. Verify: no document
      still says only SQLite and DuckDB are registered, or that the contract is
      provisional.
- [ ] 9.3 Update `docs/development.md` with `make mysql-up`, `make test-mysql`, and
      the test variables, and state that CI does not run MySQL. Add a MySQL check
      to `docs/manual-testing-guide.md`: connect, browse, run a capped query, and
      cancel. Verify: following the guide from a clean checkout reproduces each
      check.
- [ ] 9.4 Update the milestone 3 roadmap text: MySQL is shipped, and ADR-0003 is
      validated; PostgreSQL and Snowflake remain. Mark backlog 019 done with a
      link to the archived change and a short resolution. Keep 060 (other server
      versions) deferred. Verify: the roadmap and backlog links resolve.

## 10. Completion

- [ ] 10.1 Run the full verification in the topic worktree:
      - `make check`
      - `make test-cov`, which must stay at or above 85% with MySQL skipped
      - `make mysql-up && make test-mysql`, all passing
      - `openspec validate add-mysql-adapter --strict`

      Record the coverage total and the MySQL test count in the PR.
- [ ] 10.2 Synchronize the delta specs into `openspec/specs/`: the new
      `mysql-adapter`, plus `scope-addressing`, `session-dialect`,
      `table-identifiers`, `query-results`, and `test-coverage`. Archive the
      change and update backlog 019's link to the archive. Verify: `openspec list`
      shows no active `add-mysql-adapter`, and `openspec validate --specs --strict`
      passes.
