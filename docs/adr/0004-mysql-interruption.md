# MySQL interruption through a shared control connection

Status: accepted; complements [ADR-0003](0003-async-orchestration.md).

## Decision and rationale

The optional MySQL Adapter uses aiomysql with separate native async query and
metadata Channels. Each Channel owns a connection, its server thread id, and a
FIFO asyncio lock. Driver operations run as shielded reader tasks: cancellation
of the caller must never reach driver I/O, which can break the connection.

Interruption sends SQL `KILL QUERY <thread id>` through a separate control
connection. Cancelling a queued caller removes it without server contact. For a
running caller, the Channel first returns any result already received; otherwise
it records that interruption was issued, sends the kill, and waits for both the
kill acknowledgement and reader completion before raising `CancelledError`.
The Channel holds its lock throughout, so the next statement cannot begin while
a kill is in flight. MySQL 8.4 discards a kill delivered to an idle thread.
An interrupted lone `SLEEP` can return a normal value, so the Adapter's recorded
interruption, rather than a particular server error, determines cancellation.

The control connection is shared per `(host, port, user)`, opened eagerly,
reference-counted, and closed with its last Session. One lock serializes kill
commands. Sharing per account allows cancellation without `PROCESS`,
`CONNECTION_ADMIN`, or `SUPER`; sharing only per host could target another
account's threads. A broken control connection is reopened with the requesting
Session's credentials. If interruption cannot be confirmed, the affected Channel
discards and reopens its connection and logs the loss of Session state.

The same kill path releases a capped single query after reading `max_rows + 1`
rows. The Adapter discards in-flight bytes and clears the driver's unbuffered
state before releasing the Channel. A MySQL-dialect parse must establish that the
request is a single query. `CALL`, multi-statement, and unclassified SQL instead
drain every remaining row/result set while retaining only the cap, preserving
later writes and procedure steps. The reply carries the last result set with
columns. Killing every capped request would lose those effects; draining every
query would make reply time grow with the discarded result; dropping connections
would lose user variables, temporary tables, and the current database.

Disconnect uses normal interruption and drains work before closing both Channels
and releasing the control reference. At the bounded shutdown deadline,
`abandon()` writes whole `COM_QUERY` packets containing `KILL <thread id>` through
the control connection, releases awaiters, and closes sockets without waiting
for acknowledgements. Closing a socket alone does not stop a running MySQL
statement. Whole-packet writes preserve byte-stream order during abandonment.

The driver spike favored aiomysql's smaller use of private internals and lack of
driver-defect workarounds over asyncmy's faster full fetch and Connector/Python's
unsafe cancellation behavior. The package extra pins aiomysql below 0.4 and
includes cryptography for MySQL 8.4's default password authentication. The
[change design](../../openspec/changes/archive/2026-09-25-add-mysql-adapter/design.md) retains the
comparison and alternatives.

## Consequences and revisit trigger

Two connections per Session plus one shared control connection are accepted;
Session pooling remains [backlog 046](../backlog/046-adapter-pooling.md). Metadata
can proceed while the query Channel is busy, but does not see its temporary
tables. A published default-database snapshot avoids reading a busy query
connection for metadata defaults.

Proxies and load balancers are unsupported. A thread id is meaningful only on
the server that owns it; routing the control connection elsewhere can kill an
unrelated statement. There is no proxy detection. Only MySQL 8.4 is verified;
other MySQL versions and MariaDB remain
[backlog 060](../backlog/060-mysql-server-versions.md).

Real-server regressions cover ordering, state preservation, late and queued
cancellation, row caps, metadata, and cleanup. They run locally via
`make test-mysql`; CI skips them. Revisit this decision when a driver upgrade
changes private unbuffered/writer behavior or the cursor bridge that keeps later
result sets unbuffered, another server version changes kill
semantics, or support for routed connections is proposed. Driver value conversion
for JSON is a separate shared limitation in
[backlog 061](../backlog/061-non-json-result-values.md).
