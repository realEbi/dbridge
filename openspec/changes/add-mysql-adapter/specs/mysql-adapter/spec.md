## Purpose

Let clients query and browse MySQL through an optional Adapter that stops server
work on cancellation and row caps. It carries the same Session, cancellation, and
result contracts as the shipped Adapters, and names the limits it does not solve.

## ADDED Requirements

### Requirement: Install MySQL support as an optional Adapter

`dbridge/connect` SHALL accept `adapter: "mysql"`. The MySQL driver SHALL be an
optional dependency installed through the package's `mysql` extra, never part of
the default install. The server SHALL start and serve every other Adapter without
the extra. A connect request for `mysql` without the extra SHALL reply with
`ADAPTER_NOT_SUPPORTED` (-32005) and a message naming the missing extra. The
request SHALL create no Session, and the server SHALL keep serving.

#### Scenario: Extra not installed
- **WHEN** the `mysql` extra is not installed and a client connects with
  `adapter: "mysql"`
- **THEN** the reply is `ADAPTER_NOT_SUPPORTED` and its message names the `mysql`
  extra
- **AND** a following SQLite connect on the same server succeeds

#### Scenario: Server starts without the driver
- **WHEN** the server starts in an environment without the MySQL driver
- **THEN** it serves SQLite and DuckDB Sessions without importing the driver

### Requirement: Connect a MySQL Session from Profile configuration

A MySQL Profile or inline config SHALL accept these keys:

- `host`, default `127.0.0.1`
- `port`, default `3306`, given as an integer or a numeric string
- `user`, required
- `password`, optional
- `database`, optional

A connect that is missing `user`, that the server cannot reach, or that the
server refuses SHALL reply with `CONNECTION_FAILED` (-32001). Such a connect SHALL
create no Session and SHALL leave no server connection open. A MySQL Session SHALL
run in autocommit mode: each statement's changes SHALL be committed when the
statement completes, and SHALL survive disconnect.

#### Scenario: Wrong password
- **WHEN** a client connects with a valid `user` and a wrong `password`
- **THEN** the reply is `CONNECTION_FAILED` and no Session exists
- **AND** the MySQL server shows no connection left open by that attempt

#### Scenario: Writes survive disconnect
- **WHEN** a client inserts a row on a MySQL Session, disconnects, and reads the
  table from a new Session
- **THEN** the new Session sees the inserted row

### Requirement: Execute MySQL requests with ordered results

A MySQL `dbridge/execute` SHALL run the request's statements in order and reply
under the query-results contract. When the request produces several result sets,
as a multi-statement request or a `CALL` can, the reply SHALL carry the last
result set that has columns. When no statement produces columns, the reply SHALL
have empty `columns` and `rows`. A statement error SHALL reply with `QUERY_ERROR`
(-32002), and the Session SHALL run its next request normally.

#### Scenario: Multi-statement request
- **WHEN** a client executes `SET @x = 5; SELECT @x AS x`
- **THEN** the reply has `columns` `["x"]` and `rows` `[[5]]`

#### Scenario: Syntax error keeps the Session usable
- **WHEN** a client executes `SELEC 1` and then `SELECT 1`
- **THEN** the first reply is `QUERY_ERROR` and the second replies `[[1]]`

### Requirement: Stop the MySQL server's work when a request is cancelled

Cancelling a running MySQL request SHALL stop its statement on the MySQL server,
not only the server's wait for it. The request SHALL reply `QUERY_CANCELLED`
(-32004), and the statement SHALL no longer be running on the MySQL server.
The Session SHALL keep its connection state: user variables, temporary tables,
and the current database set before the cancel SHALL still be present. Stopping
a statement SHALL require no privilege beyond what the Session's MySQL account
needs to run it.

Once the server has begun interrupting a statement, the request SHALL reply
`QUERY_CANCELLED` even if MySQL reports the statement as completed. A statement
whose result reached the server before interruption began SHALL reply with that
result. Cancelling SHALL NOT interrupt any other request, including the next
request queued on the same Session. Metadata requests on a MySQL Session SHALL be
cancellable under the same rules.

#### Scenario: Cancel a long statement
- **WHEN** a client executes `SELECT n, SLEEP(30) FROM t` over several rows and
  cancels it after it starts
- **THEN** the reply is `QUERY_CANCELLED` within 2 seconds
- **AND** the MySQL process list shows no statement running for that Session

#### Scenario: Interrupted statement that MySQL reports as finished
- **WHEN** a client executes `SELECT SLEEP(30)` and cancels it after it starts
- **THEN** the reply is `QUERY_CANCELLED`, although MySQL returns `1` for an
  interrupted lone `SLEEP` rather than an error

#### Scenario: Session state survives a cancel
- **WHEN** a client sets `@marker = 7`, creates a temporary table, cancels a
  running statement, and then selects `@marker` and counts the temporary table
- **THEN** both reads succeed and `@marker` is 7

#### Scenario: A late cancel never reaches the next statement
- **WHEN** a client sends a short statement and a second statement on the same
  Session, and cancels the first as it completes
- **THEN** the second statement replies with its normal result

#### Scenario: Unprivileged account can cancel
- **WHEN** the Profile's account has no `PROCESS`, `CONNECTION_ADMIN`, or `SUPER`
  privilege and a client cancels a running statement
- **THEN** the statement stops and the reply is `QUERY_CANCELLED`

### Requirement: Release capped MySQL results without reading them

When a request is a single statement that returns rows and produces more rows than
the cap, the server SHALL stop the statement on the MySQL server after reading one
row past the cap. It SHALL reply within a time that does not grow with the rows
past the cap, and the Session SHALL keep its connection state. When the request is
a `CALL` or holds several statements, the server SHALL NOT stop it early. It SHALL
instead read and discard the remaining rows, so every statement and procedure step
completes. Memory SHALL stay bounded by the cap, but reply time grows with the
discarded rows. This is a known gap.

#### Scenario: Capped query on a large table
- **WHEN** `max_rows` is 100 and a client executes `SELECT * FROM t` on a table of
  1,000,000 rows
- **THEN** the reply contains 100 rows and a truncation warning within 1 second
- **AND** the MySQL process list shows no statement running for that Session

#### Scenario: Capped procedure still completes its later changes
- **WHEN** `max_rows` is 100 and a client calls a procedure that returns 1,000 rows
  and then inserts a row into another table
- **THEN** the reply contains 100 rows and a truncation warning
- **AND** the procedure's insert is present afterwards

### Requirement: Close MySQL server work on disconnect and shutdown

`dbridge/disconnect` of a MySQL Session SHALL stop its running statements on the
MySQL server and close the Session's server connections. When the server's bounded
shutdown abandons a MySQL Session, it SHALL still ask the MySQL server to end that
Session's connections. It SHALL do this without waiting for a reply and without
holding up process exit. Closing the client socket alone does not stop a running
statement.

#### Scenario: Disconnect with a statement running
- **WHEN** a client disconnects a MySQL Session while a long statement runs
- **THEN** the MySQL process list no longer shows that Session's connections

#### Scenario: Shutdown with a statement running
- **WHEN** the client closes the server's input while a long MySQL statement runs
  and the shutdown grace period expires
- **THEN** the process exits
- **AND** the MySQL server ends that statement's connection

### Requirement: Browse MySQL databases and tables

A MySQL Session SHALL declare one Scope Level named `database` and labelled
`Database`. `dbridge/listDatabases` SHALL return every database the account can
see. It SHALL mark `information_schema`, `mysql`, `performance_schema`, and `sys`
as internal. `dbridge/listSchemas` SHALL return an empty list for a valid
one-component path. `dbridge/listTables` SHALL return the base tables and views
of the requested database. `TEMPORARY` tables SHALL NOT be listed; this is a known
gap. `dbridge/getTableSchema` SHALL report columns in declared order with their
full column type, nullability, default, and comment. It SHALL report key metadata
under the table-keys contract. The primary key's `name` SHALL be `PRIMARY`, and a
foreign key referencing another database SHALL report that database as its
`referenced_path`.

The default Scope Path SHALL be the Session's current database: the configured
`database`, or the one selected later by `USE`, reported after a refresh. With no
current database, it SHALL be the first non-internal database in name order. If
none exists, it SHALL be `information_schema`.

#### Scenario: Default path follows the configured database
- **WHEN** a client connects with `database: "shop"`
- **THEN** the connect reply declares the `database` level and a default Scope Path
  of `["shop"]`

#### Scenario: Default path follows USE after refresh
- **WHEN** a client executes `USE other` and calls `dbridge/refreshSchema`
- **THEN** the refresh reply's default Scope Path is `["other"]`

#### Scenario: Foreign key into another database
- **WHEN** table `shop.orders` has a composite foreign key to `crm.customers`
- **THEN** its entry lists both columns in key order with `referenced_path`
  `["crm"]` and `referenced_table` `customers`

### Requirement: Document MySQL deployment limits

The documentation SHALL state these limits:

- **Proxies.** Cancelling and releasing capped results target a MySQL thread by
  its id on the server a Session is connected to. Through a proxy or load
  balancer that routes connections to different backends, the interruption can
  reach a different server and stop an unrelated statement. Such deployments
  SHALL be documented as unsupported for MySQL Sessions.
- **Versions.** Only MySQL 8.4 SHALL be documented as verified. Other MySQL
  versions and MariaDB SHALL be documented as unverified.

#### Scenario: Limits are discoverable
- **WHEN** a user reads the README's MySQL section
- **THEN** it states the proxy limitation, the verified server version, and that
  `TEMPORARY` tables are not listed
