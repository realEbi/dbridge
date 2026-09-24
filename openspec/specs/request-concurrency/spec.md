# request-concurrency Specification

## Purpose

Define how the server accepts, schedules, and answers requests while other requests
are still running, so one slow query cannot make the rest of the server unresponsive.

## Requirements

### Requirement: Keep accepting requests while others run

The server SHALL continue reading and dispatching requests while earlier requests are
still running. A request SHALL NOT wait to be read because another request, on the
same Session or a different one, has not finished. Profile requests and requests that
fail validation SHALL be answered without waiting for any running query.

#### Scenario: Metadata on another Session during a long query
- **WHEN** a client starts a long-running `dbridge/execute` on one Session and then
  sends `dbridge/listTables` for a second Session
- **THEN** the listing reply arrives before the long query's reply

#### Scenario: Profile listing during a long query
- **WHEN** a long-running `dbridge/execute` is outstanding and the client sends
  `dbridge/listProfiles`
- **THEN** the Profile reply arrives before the long query's reply

#### Scenario: Invalid request during a long query
- **WHEN** a long-running `dbridge/execute` is outstanding and the client sends a
  request for an unknown method
- **THEN** the `METHOD_NOT_FOUND` reply arrives before the long query's reply

### Requirement: Correlate replies by id in completion order

The server SHALL send exactly one reply for each request that carries an id, and each
reply SHALL carry that request's id. Replies SHALL be sent when their requests finish,
which MAY differ from the order in which the requests arrived. The server SHALL NOT
send a reply for a notification. A request whose id equals the id of a request that
is still outstanding SHALL be rejected with `INVALID_REQUEST` and SHALL NOT affect the
outstanding request; ids MAY be reused once their request has been answered. Every frame on stdout SHALL be one complete protocol
message; replies from concurrent requests SHALL NOT interleave within a frame, and
diagnostics SHALL NOT be written to stdout.

#### Scenario: A fast request overtakes a slow one
- **WHEN** a client sends a long-running `dbridge/execute` with id 1 and then
  `dbridge/listProfiles` with id 2
- **THEN** the reply with id 2 arrives first and the reply with id 1 arrives later
- **AND** each reply carries the result belonging to its own request

#### Scenario: Many concurrent replies stay well framed
- **WHEN** a client sends many requests across several Sessions without waiting for
  replies
- **THEN** every reply parses as one complete framed message with a matching id
- **AND** each id receives exactly one reply

#### Scenario: An outstanding id is reused
- **WHEN** a long-running `dbridge/execute` with id 5 is outstanding and the client
  sends another request with id 5
- **THEN** the second request is rejected with `INVALID_REQUEST`
- **AND** the long query later replies with id 5 and its normal result

### Requirement: Run different Sessions in parallel

Work on one Session SHALL NOT wait for work on another Session. A long-running request
on one Session SHALL NOT delay the start or completion of a request on a different
Session.

#### Scenario: Two Sessions query at the same time
- **WHEN** a client starts a long-running `dbridge/execute` on one Session and a short
  `dbridge/execute` on another Session
- **THEN** the short query's reply arrives before the long query's reply

### Requirement: Order work within one Session

`dbridge/execute` requests on one Session SHALL run one at a time, in the order the
server received them, so a later statement observes the effects of an earlier one.
Metadata requests on a Session MAY run while an `execute` on that Session is running
when its Adapter supports concurrent metadata access; otherwise they SHALL wait and
run in arrival order. A DuckDB Session SHALL answer metadata while an `execute` runs.
A SQLite Session SHALL run all of its database work in arrival order. A metadata
request answered from the Session's introspection cache SHALL NOT wait for database
work on any Adapter. A client that needs a
metadata result to reflect an `execute` SHALL wait for that `execute`'s reply before
sending the metadata request; the server does not order a metadata request after an
earlier, still-running `execute`.

#### Scenario: Statements on one Session keep their order
- **WHEN** a client sends `CREATE TABLE t (a INT)`, then `INSERT INTO t VALUES (1)`,
  then `SELECT count(*) FROM t` as three `dbridge/execute` requests on one Session
  without waiting for replies
- **THEN** all three succeed and the count is 1

#### Scenario: DuckDB metadata during a long query
- **WHEN** a long-running `dbridge/execute` is running on a DuckDB Session and the
  client sends `dbridge/listTables` for that Session
- **THEN** the listing reply arrives before the long query's reply

#### Scenario: SQLite requests keep arrival order
- **WHEN** a long-running `dbridge/execute` is running on a SQLite Session and the
  client sends `dbridge/listTables` for a Scope Path whose listing is not cached
- **THEN** the listing reply arrives after the long query's reply

#### Scenario: Cached completion during a long query
- **WHEN** completion metadata for a Scope Path is already cached, a long-running
  `dbridge/execute` is running on the same Session, and the client sends
  `dbridge/complete` for that Scope Path
- **THEN** the completion reply arrives before the long query's reply, for SQLite and
  DuckDB Sessions alike

### Requirement: Disconnect a Session with work in flight

`dbridge/disconnect` SHALL cancel every outstanding request on that Session, each of
which SHALL reply with `QUERY_CANCELLED`, and SHALL then close the Session's Adapter
and reply. After the disconnect reply, a request naming that Session SHALL return
`SESSION_NOT_FOUND`. Disconnecting one Session SHALL NOT affect requests on other
Sessions.

#### Scenario: Disconnect during a long query
- **WHEN** a long-running `dbridge/execute` is running on a Session and the client
  sends `dbridge/disconnect` for that Session
- **THEN** the query replies with `QUERY_CANCELLED` and the disconnect replies with
  success
- **AND** a later request on that Session returns `SESSION_NOT_FOUND`

#### Scenario: Other Sessions are unaffected
- **WHEN** one Session is disconnected while another Session has a query running
- **THEN** the other Session's query completes with its normal result

### Requirement: Shut down cleanly at end of input

When the client closes the server's input, the server SHALL cancel all outstanding
requests, stop accepting Session work, and attempt to close every Session's Adapter
within a fixed shutdown grace period. It SHALL exit with a success status within a
bounded time, even if a database driver ignores interruption. If a driver cannot be
closed before the deadline, the server SHALL abandon its unfinished work,
detach the Session, and report the incomplete connection cleanup on stderr; it SHALL
NOT wait indefinitely for that driver. Replies to
requests cancelled during shutdown MAY be omitted, because the client has closed the
channel.

#### Scenario: Input closes during a long query
- **WHEN** a long-running `dbridge/execute` is running and the client closes the
  server's input
- **THEN** the server process exits with a success status without waiting for the
  query to finish on its own

#### Scenario: A driver ignores shutdown interruption
- **WHEN** input closes while a driver call ignores interruption past the shutdown grace period
- **THEN** the server detaches that Session and exits within the bounded shutdown time
- **AND** stderr reports that connection cleanup could not finish
- **AND** queued database work never starts
