"""Optional native-async MySQL adapter.

Driver readers are shielded from task cancellation. A separate, account-scoped
connection sends KILL QUERY while the Channel keeps its FIFO lock, then the
reader drains the server's reply before another operation can use that Channel.
"""

import asyncio
from collections.abc import Callable, Coroutine
import importlib
from itertools import groupby
import struct
import time
from typing import Any, TypeVar

import aiomysql  # type: ignore[import-untyped, import-not-found]
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.tokens import TokenType

from dbridge.adapters.base import (
    ColumnDef, ContainerEntry, DBAdapter, ForeignKey, PrimaryKey, QueryResult,
    ScopeLevel, ScopePath, TableEntry, TableRef, TableSchema,
)
from dbridge.exceptions import AdapterConnectionError, AdapterQueryError
from dbridge.logging import get_logger

# Check the complete extra even when PyMySQL previously cached its optional
# authentication imports. MySQL's default authentication needs this package.
importlib.import_module("cryptography")

T = TypeVar("T")
_INTERNAL_DATABASES = {"information_schema", "mysql", "performance_schema", "sys"}
_MYSQL_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "INNER", "OUTER", "ON", "GROUP",
    "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "INSERT", "INTO", "VALUES",
    "UPDATE", "SET", "DELETE", "CREATE", "TABLE", "DROP", "DISTINCT", "AS",
    "AND", "OR", "NOT", "NULL", "IS", "IN", "LIKE", "BETWEEN", "UNION", "ALL",
    "WITH", "SHOW", "DESCRIBE", "EXPLAIN", "USE", "DATABASE", "CALL",
]


def _quote_identifier(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _is_killable(sql: str) -> bool:
    """Only stop a parsed, single row-producing statement early."""
    try:
        tokens = sqlglot.tokenize(sql, read="mysql")
        is_table = bool(tokens and tokens[0].token_type == TokenType.TABLE)
        text = "SELECT * FROM " + sql[tokens[0].end + 1:] if is_table else sql
        statements = [statement for statement in sqlglot.parse(text, read="mysql") if statement]
    except SqlglotError:
        return False
    if len(statements) != 1:
        return False
    query = statements[0]
    if not is_table:
        return isinstance(query, (exp.Query, exp.Show, exp.Describe, exp.Values))
    # sqlglot currently treats MySQL's TABLE query as a column/alias expression.
    # Parse its equivalent SELECT to validate the table, ORDER BY and LIMIT
    # grammar; accept no joins, filters or other SELECT-only clauses.
    if not isinstance(query, exp.Select):
        return False
    allowed = {"expressions", "from_", "from", "order", "limit", "offset"}
    if any(value for key, value in query.args.items() if key not in allowed):
        return False
    tables = list(query.find_all(exp.Table))
    return len(tables) == 1 and not tables[0].args.get("alias")


def _consume_exception(task: asyncio.Task[Any]) -> None:
    # Abandon may release the awaiter before a closed socket wakes its reader.
    if not task.cancelled():
        task.exception()


async def _finish(task: asyncio.Task[T]) -> T:
    """Finish cleanup even if its caller receives another cancellation."""
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done():
                return task.result()


async def _connect(options: dict[str, Any], pending: set[asyncio.Task[Any]]) -> Any:
    async def open_connection() -> Any:
        return await aiomysql.connect(**options)

    task = asyncio.create_task(open_connection())
    pending.add(task)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # A cancelled handshake must not strand an authenticated connection.
        connection = await _finish(task)
        connection.close()
        raise
    finally:
        pending.discard(task)


class _Control:
    def __init__(self, key: tuple[str, int, str]) -> None:
        self.key = key
        self.references = 0
        self.connection: Any = None
        self.lock = asyncio.Lock()
        self._opening: set[asyncio.Task[Any]] = set()
        self._tainted = False

    async def _open(self, options: dict[str, Any]) -> None:
        if self._tainted and self.connection is not None:
            self.connection.close()
        if self.connection is None or self.connection.closed:
            # The control connection must not depend on the selected database.
            self.connection = await _connect({**options, "db": None}, self._opening)
            self._tainted = False

    async def open(self, options: dict[str, Any]) -> None:
        async with self.lock:
            await self._open(options)

    async def kill(self, thread_id: int, options: dict[str, Any]) -> None:
        async with self.lock:
            await self._open(options)
            try:
                async with self.connection.cursor() as cursor:
                    await cursor.execute(f"KILL QUERY {thread_id:d}")
            except BaseException:
                self.connection.close()
                raise

    def kill_nowait(self, thread_ids: list[int]) -> None:
        if self.connection is None or self.connection.closed:
            return
        for thread_id in thread_ids:
            # COM_QUERY uses sequence 0. Each write includes the entire packet;
            # even a pending ordinary kill cannot interleave its packet bytes.
            payload = b"\x03" + f"KILL {thread_id:d}".encode("ascii")
            packet = struct.pack("<I", len(payload)) + payload
            self.connection._writer.write(packet)
            self._tainted = True


_controls: dict[tuple[str, int, str], _Control] = {}


class _Channel:
    def __init__(self, options: dict[str, Any], control: _Control) -> None:
        self.options = options
        self.control = control
        self.connection: Any = None
        self.lock = asyncio.Lock()
        self.reconnect_count = 0
        self._closing = False
        self._abandoned = False
        self._waiters: set[asyncio.Task[Any]] = set()
        self._reader: asyncio.Task[Any] | None = None
        self._interruption: asyncio.Task[None] | None = None
        self._opening: set[asyncio.Task[Any]] = set()

    @property
    def thread_id(self) -> int:
        return self.connection.thread_id()

    async def connect(self) -> None:
        self.connection = await _connect(self.options, self._opening)

    async def _kill(self) -> None:
        try:
            await self.control.kill(self.thread_id, self.options)
        except Exception:
            get_logger().warning(
                "MySQL interruption could not be confirmed; reconnecting Channel; "
                "Session state on that connection is lost", exc_info=True,
            )
            self.connection.close()
            if not self._abandoned:
                await self.connect()
                self.reconnect_count += 1

    async def interrupt(self) -> None:
        if self._interruption is None:
            self._interruption = asyncio.create_task(self._kill())
        await asyncio.shield(self._interruption)

    async def _wait(self, task: asyncio.Task[T]) -> T:
        while True:
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                if self._abandoned:
                    raise
                if task.done():
                    return task.result()

    async def run(
        self, operation: Callable[[], Coroutine[Any, Any, T]],
        after: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ) -> T:
        if self._closing:
            raise AdapterQueryError("MySQL Session is closing")
        caller = asyncio.current_task()
        assert caller is not None
        self._waiters.add(caller)
        try:
            # asyncio.Lock preserves the arrival order of its waiting tasks.
            async with self.lock:
                if self._closing:
                    raise asyncio.CancelledError
                self._interruption = None
                reader = self._reader = asyncio.create_task(operation())
                reader.add_done_callback(_consume_exception)
                try:
                    try:
                        return await asyncio.shield(reader)
                    except asyncio.CancelledError:
                        if self._abandoned:
                            raise
                        if reader.done():
                            return reader.result()
                        # Once issued, interruption wins even when MySQL reports
                        # normal completion (notably a lone interrupted SLEEP).
                        kill = asyncio.create_task(self.interrupt())
                        try:
                            await self._wait(kill)
                        finally:
                            try:
                                await self._wait(reader)
                            except Exception:
                                pass
                        raise asyncio.CancelledError
                finally:
                    self._reader = None
                    # The SQL outcome is established. A late cancel during this
                    # snapshot must not kill its SELECT or replace that outcome.
                    if after is not None and not self._abandoned:
                        snapshot = asyncio.create_task(after())
                        snapshot.add_done_callback(_consume_exception)
                        try:
                            await self._wait(snapshot)
                        except Exception:
                            get_logger().warning("Could not update MySQL default Scope Path", exc_info=True)
        finally:
            self._waiters.discard(caller)

    async def close(self) -> None:
        self._closing = True
        pending = list(self._waiters)
        for waiter in pending:
            waiter.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        if self.connection is not None:
            await self.connection.ensure_closed()

    def abandon(self) -> None:
        self._closing = self._abandoned = True
        if self.connection is not None:
            self.connection.close()
        # Driver I/O is only cancelled after its socket has been discarded.
        if self._reader is not None:
            self._reader.cancel()
        if self._interruption is not None:
            self._interruption.cancel()
        for task in self._opening:
            # No statement exists during the handshake. aiomysql closes the
            # socket when its handshake read is cancelled.
            task.cancel()
        for waiter in self._waiters:
            waiter.cancel()


class MySQLAdapter(DBAdapter):
    adapter_name = "mysql"

    def __init__(self, config: dict[str, str]) -> None:
        super().__init__(config)
        user = config.get("user")
        if not user:
            raise AdapterConnectionError("mysql adapter requires a 'user' config key")
        try:
            port = int(config.get("port", "3306"))
            if not 1 <= port <= 65535:
                raise ValueError
        except (ValueError, TypeError) as error:
            raise AdapterConnectionError("mysql port must be an integer from 1 to 65535") from error
        self._options: dict[str, Any] = {
            "host": config.get("host", "127.0.0.1"), "port": port,
            "user": user, "password": config.get("password", ""),
            "db": config.get("database") or None,
            "autocommit": True, "charset": "utf8mb4",
        }
        self._control: _Control | None = None
        self._query: _Channel | None = None
        self._metadata: _Channel | None = None
        self._default_path: ScopePath = ("information_schema",)
        self._connecting_task: asyncio.Task[Any] | None = None
        self._disconnect_task: asyncio.Task[None] | None = None
        self._closing = False

    async def connect(self) -> None:
        self._connecting_task = asyncio.current_task()
        try:
            key = (self._options["host"], self._options["port"], self._options["user"])
            control = self._control = _controls.setdefault(key, _Control(key))
            control.references += 1
            await control.open(self._options)
            self._query = _Channel(self._options, control)
            await self._query.connect()
            self._metadata = _Channel(self._options, control)
            await self._metadata.connect()
            await self._query.run(self._snapshot_scope)
        except BaseException as error:
            await self.disconnect()
            if isinstance(error, asyncio.CancelledError):
                raise
            raise AdapterConnectionError(str(error)) from error
        finally:
            self._connecting_task = None

    async def disconnect(self) -> None:
        self._closing = True
        if self._disconnect_task is None:
            self._disconnect_task = asyncio.create_task(self._disconnect())
        await _finish(self._disconnect_task)

    async def _disconnect(self) -> None:
        try:
            await asyncio.gather(*(
                channel.close() for channel in (self._query, self._metadata)
                if channel is not None
            ))
        finally:
            control, self._control = self._control, None
            if control is not None:
                control.references -= 1
                if control.references == 0:
                    _controls.pop(control.key, None)
                    async with control.lock:
                        if control.connection is not None:
                            await control.connection.ensure_closed()

    def abandon(self) -> None:
        self._closing = True
        if self._connecting_task is not None:
            self._connecting_task.cancel()
        channels = [channel for channel in (self._query, self._metadata) if channel is not None]
        control, self._control = self._control, None
        if control is not None:
            for task in control._opening:
                task.cancel()
            try:
                control.kill_nowait([
                    channel.thread_id for channel in channels
                    if channel.connection is not None and not channel.connection.closed
                ])
            except Exception:
                self.logger.warning("Could not send MySQL abandonment kills", exc_info=True)
        for channel in channels:
            channel.abandon()
        if control is not None:
            # Keep the stream for other Sessions abandoned synchronously in the
            # same shutdown pass. Ordinary reuse notices its unread replies and
            # opens a fresh control connection instead.
            control.references -= 1
            if control.references == 0:
                _controls.pop(control.key, None)
                if control.connection is not None:
                    control.connection.close()

    def _channel(self, *, metadata: bool = False) -> _Channel:
        if self._closing:
            raise AdapterQueryError("MySQL Session is closing")
        channel = self._metadata if metadata else self._query
        assert channel is not None, "adapter not connected"
        return channel

    @staticmethod
    async def _rows(connection: Any, sql: str, params: tuple = ()) -> list[tuple]:
        async with connection.cursor() as cursor:
            await cursor.execute(sql, params)
            return list(await cursor.fetchall())

    async def _snapshot_scope(self) -> None:
        assert self._query is not None
        rows = await self._rows(self._query.connection, "SELECT DATABASE()")
        database = rows[0][0]
        if database is None:
            rows = await self._rows(
                self._query.connection,
                "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME",
            )
            database = next((row[0] for row in rows if row[0] not in _INTERNAL_DATABASES), "information_schema")
        self._default_path = (database,)

    async def execute(self, sql: str, *, row_limit: int | None = None) -> QueryResult:
        if row_limit is not None and row_limit < 1:
            raise ValueError("row_limit must be at least 1")
        channel = self._channel()
        try:
            return await channel.run(
                lambda: self._execute(channel, sql, row_limit), self._snapshot_scope,
            )
        except aiomysql.Error as error:
            raise AdapterQueryError(str(error)) from error

    async def _execute(self, channel: _Channel, sql: str, row_limit: int | None) -> QueryResult:
        started = time.perf_counter()
        connection = channel.connection
        cursor = await connection.cursor(aiomysql.SSCursor)
        columns: list[str] = []
        rows: list[list] = []
        try:
            await cursor.execute(sql)
            while True:
                if cursor.description:
                    columns = [description[0] for description in cursor.description]
                    rows = []
                    while True:
                        size = 256 if row_limit is None else min(256, row_limit - len(rows))
                        batch = await cursor.fetchmany(size)
                        rows.extend(list(row) for row in batch)
                        if not batch:
                            break
                        if row_limit is not None and len(rows) == row_limit:
                            if _is_killable(sql):
                                await channel.interrupt()
                                # SSCursor.close discards packets without decoding
                                # rows. A killed streaming query terminates in 1317.
                                try:
                                    if connection is channel.connection:
                                        await cursor.close()
                                except aiomysql.OperationalError as error:
                                    if error.args[0] != 1317:
                                        raise
                                finally:
                                    if connection._result is not None:
                                        connection._result.unbuffered_active = False
                                return QueryResult(columns, rows, len(rows), (time.perf_counter() - started) * 1000)
                            # Preserve every later procedure/multi-statement
                            # effect while bounding retained memory by the cap.
                            while await cursor.fetchmany(256):
                                await asyncio.sleep(0)
                            break
                        await asyncio.sleep(0)
                # aiomysql's inherited nextset() buffers later result sets even
                # for SSCursor. Keep them streaming, then attach that result to
                # the existing cursor using its result-initialization helper.
                if not connection._result.has_next:
                    break
                await connection._read_query_result(unbuffered=True)
                await cursor._do_get_result()
        except aiomysql.OperationalError as error:
            if error.args[0] == 1317 and connection._result is not None:
                connection._result.unbuffered_active = False
            raise
        finally:
            if not connection.closed:
                await cursor.close()
        return QueryResult(columns, rows, len(rows), (time.perf_counter() - started) * 1000)

    def scope_levels(self) -> list[ScopeLevel]:
        return [ScopeLevel("database", "Database")]

    async def default_scope(self) -> ScopePath:
        self._channel(metadata=True)
        return self._default_path

    @staticmethod
    def _database(path: ScopePath) -> str:
        if len(path) != 1 or not all(isinstance(part, str) and part for part in path):
            raise AdapterQueryError("MySQL requires a one-component Scope Path")
        return path[0]

    async def _read_metadata(self, operation: Callable[[], Coroutine[Any, Any, T]]) -> T:
        try:
            return await self._channel(metadata=True).run(operation)
        except aiomysql.Error as error:
            raise AdapterQueryError(str(error)) from error

    async def list_databases(self) -> list[ContainerEntry]:
        channel = self._channel(metadata=True)
        rows = await self._read_metadata(lambda: self._rows(
            channel.connection, "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME",
        ))
        return [ContainerEntry(row[0], row[0] in _INTERNAL_DATABASES) for row in rows]

    async def list_schemas(self, path: ScopePath) -> list[ContainerEntry]:
        self._channel(metadata=True)
        self._database(path)
        return []

    async def list_tables(self, path: ScopePath) -> list[TableEntry]:
        database = self._database(path)
        channel = self._channel(metadata=True)
        rows = await self._read_metadata(lambda: self._rows(
            channel.connection,
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE IN ('BASE TABLE', 'VIEW') ORDER BY TABLE_NAME",
            (database,),
        ))
        return [TableEntry(row[0], f"{_quote_identifier(database)}.{_quote_identifier(row[0])}") for row in rows]

    async def get_table_schema(self, table: TableRef) -> TableSchema:
        database = self._database(table.path)
        channel = self._channel(metadata=True)

        async def read() -> TableSchema:
            params = (database, table.name)
            columns = await self._rows(
                channel.connection,
                "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT "
                "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                "ORDER BY ORDINAL_POSITION", params,
            )
            if channel._interruption is not None:
                raise asyncio.CancelledError
            keys = await self._rows(
                channel.connection,
                "SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA, "
                "REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
                "FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                "ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION", params,
            )
            primary = None
            foreign = []
            for name, members in groupby(keys, key=lambda row: row[0]):
                parts = list(members)
                if name == "PRIMARY":
                    primary = PrimaryKey("PRIMARY", [part[1] for part in parts])
                elif parts[0][2] is not None:
                    foreign.append(ForeignKey(
                        name=name, columns=[part[1] for part in parts],
                        referenced_path=(parts[0][2],), referenced_table=parts[0][3],
                        referenced_columns=[part[4] for part in parts],
                    ))
            return TableSchema(
                name=table.name, scope=table.path,
                columns=[ColumnDef(row[0], row[1], row[2] == "YES", row[3], row[4]) for row in columns],
                primary_key=primary, foreign_keys=foreign,
                sql_identifier=f"{_quote_identifier(database)}.{_quote_identifier(table.name)}" if columns else None,
            )

        return await self._read_metadata(read)

    def dialect_name(self) -> str:
        return "mysql"

    def get_keywords(self) -> list[str]:
        return list(_MYSQL_KEYWORDS)
