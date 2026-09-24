# request-cancellation Specification

## Purpose

Let a client stop an outstanding request, most importantly a long-running query,
without disturbing any other request or leaving the Session unusable.

## Requirements

### Requirement: Cancel an outstanding request by its id

The server SHALL accept a `$/cancelRequest` notification whose params contain `id`,
the JSON-RPC id of a request the client sent earlier. Because it is a notification,
the server SHALL NOT reply to it. When the named request is still outstanding, the
server SHALL attempt to stop it, subject to the best-effort rule below. A request
whose work is stopped SHALL reply with a `QUERY_CANCELLED`
(-32004) error instead of its result. Any request method MAY be cancelled.
Cancellation SHALL NOT close the Session: after a cancelled request, the Session
SHALL accept and run new requests.

#### Scenario: Cancel a running query
- **WHEN** a long-running `dbridge/execute` is running and the client sends
  `$/cancelRequest` naming its id
- **THEN** that request replies with `QUERY_CANCELLED` well before the query would have
  finished
- **AND** no reply is sent for the cancel notification

#### Scenario: Session stays usable after a cancel
- **WHEN** a query on a Session has been cancelled
- **THEN** a following `dbridge/execute` on the same Session returns its normal result

#### Scenario: Cancel works for SQLite and DuckDB
- **WHEN** a long-running query is cancelled on a SQLite Session and on a DuckDB
  Session
- **THEN** each replies with `QUERY_CANCELLED`

### Requirement: Cancel a queued request without running it

A request that is waiting behind other work on its Session and has not started SHALL
be removed from the queue when cancelled. It SHALL reply with `QUERY_CANCELLED` and
SHALL NOT run afterwards.

#### Scenario: Cancel a statement waiting behind a long query
- **WHEN** a long-running `dbridge/execute` is running on a Session, the client sends
  `INSERT INTO t VALUES (1)` as a second `dbridge/execute` on that Session, and then
  cancels the second request
- **THEN** the second request replies with `QUERY_CANCELLED`
- **AND** after the first query finishes, table `t` contains no row from the cancelled
  insert

### Requirement: Never stop a request other than the one named

Cancelling a request SHALL NOT stop, fail, or alter the result of any other request,
including a request that starts on the same Session just as the cancelled one finishes,
and a request running concurrently on the same Session.

#### Scenario: Cancel races with completion
- **WHEN** the client cancels a request at the moment it finishes and the next queued
  request on that Session starts
- **THEN** the next request completes with its normal result
- **AND** the finished request keeps the reply it produced, either its result or
  `QUERY_CANCELLED`, never both

#### Scenario: Cancel a query while metadata runs beside it
- **WHEN** a DuckDB Session is running a long query and a metadata request at the same
  time, and the client cancels the query
- **THEN** the query replies with `QUERY_CANCELLED` and the metadata request replies
  with its normal result

#### Scenario: Cancel on one Session leaves another alone
- **WHEN** long queries run on two Sessions and the client cancels one of them
- **THEN** the other query completes with its normal result

### Requirement: Ignore a cancel that has nothing to stop

A `$/cancelRequest` whose id names no outstanding request — because the request has
already been answered, was never sent, or the params are malformed — SHALL be ignored.
The server SHALL NOT reply to it, SHALL NOT log it as an error, and SHALL keep serving.

#### Scenario: Cancel after the reply
- **WHEN** a request has already been answered and the client then sends
  `$/cancelRequest` for its id
- **THEN** no further reply is sent and later requests are served normally

#### Scenario: Cancel for an unknown id
- **WHEN** the client sends `$/cancelRequest` naming an id it never used, or with no
  `id` in its params
- **THEN** no reply is sent and later requests are served normally

### Requirement: Make cancellation effects predictable

Cancelling a request SHALL be best effort. Work that finishes before the cancel takes
effect, and work that cannot be interrupted, SHALL complete and reply normally.
Cancelling an `execute` SHALL stop the statement that is running; effects of
statements in the same request that finished before the cancel SHALL remain, and the
server SHALL NOT roll them back. A cancelled request's reply SHALL NOT contain a
partial result.

#### Scenario: Earlier statements in a cancelled request persist
- **WHEN** a DuckDB `dbridge/execute` contains `INSERT INTO t VALUES (1)` followed by
  a long-running statement, and the client cancels it while the second statement runs
- **THEN** the request replies with `QUERY_CANCELLED`
- **AND** table `t` contains the inserted row

#### Scenario: Cancel loses the race to a fast request
- **WHEN** a request finishes before its cancel is processed
- **THEN** the request's normal reply is the only reply it receives
