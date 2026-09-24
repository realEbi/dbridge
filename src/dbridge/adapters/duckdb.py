from collections.abc import Mapping
from copy import deepcopy
import threading
import time
from types import MappingProxyType

import duckdb

from dbridge.adapters.base import (
    ColumnDef,
    ContainerEntry,
    QueryResult,
    ScopeLevel,
    ScopePath,
    TableEntry,
    TableRef,
    TableSchema,
)
from dbridge.adapters.identifiers import quote_identifier
from dbridge.adapters.threaded import ThreadBackedAdapter
from dbridge.exceptions import AdapterConnectionError, AdapterQueryError

_DUCKDB_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS",
    "ON", "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "INSERT", "INTO",
    "VALUES", "UPDATE", "SET", "DELETE", "CREATE", "TABLE", "DROP", "DISTINCT",
    "AS", "AND", "OR", "NOT", "NULL", "IS", "IN", "LIKE", "BETWEEN", "UNION",
    "ALL", "WITH", "RECURSIVE", "OVER", "PARTITION", "WINDOW",
]


class DuckDBAdapter(ThreadBackedAdapter):
    adapter_name = "duckdb"
    metadata_lane = "metadata"

    def __init__(self, config: dict[str, str]) -> None:
        super().__init__(config)
        self.uri: str = config.get("uri", ":memory:")
        self.con: duckdb.DuckDBPyConnection | None = None
        self._metadata: duckdb.DuckDBPyConnection | None = None
        self._scope: ScopePath = ()
        self._temp_tables: Mapping[TableRef, TableSchema] = MappingProxyType({})
        self._temp_schemas: tuple[ContainerEntry, ...] = ()
        self._query_state_lock = threading.Lock()
        self._snapshotting = False

    def _connect(self) -> None:
        try:
            self.con = duckdb.connect(self.uri)
            self._capture_session_metadata()
        except Exception as e:
            raise AdapterConnectionError(str(e)) from e

    def _disconnect(self) -> None:
        if self.con is not None:
            self.con.close()
            self.con = None

    def _connect_metadata(self) -> None:
        assert self.con is not None, "adapter not connected"
        self._metadata = self.con.cursor()

    def _disconnect_metadata(self) -> None:
        if self._metadata is not None:
            self._metadata.close()
            self._metadata = None

    def _interrupt(self, lane: str) -> None:
        if lane == "query":
            with self._query_state_lock:
                # The SQL outcome is already known when discovery runs. Retried
                # interrupts must not discard its partial-effect metadata.
                if self.con is not None and not self._snapshotting:
                    self.con.interrupt()
        elif self._metadata is not None:
            self._metadata.interrupt()

    def _is_interruption(self, error: BaseException) -> bool:
        cause = error.__cause__ if isinstance(error, AdapterQueryError) else error
        return isinstance(cause, duckdb.InterruptException)

    def _cur(self) -> duckdb.DuckDBPyConnection:
        assert self._metadata is not None, "adapter not connected"
        return self._metadata

    def _execute(self, sql: str, *, row_limit: int | None = None) -> QueryResult:
        start = time.perf_counter()
        try:
            assert self.con is not None, "adapter not connected"
            rel = self.con.execute(sql)
            columns = [d[0] for d in rel.description] if rel.description else []
            rows = [list(r) for r in (rel.fetchall() if row_limit is None else rel.fetchmany(row_limit))]
        except Exception as e:
            raise AdapterQueryError(str(e)) from e
        finally:
            # A sibling cursor has its own USE state. Publish the query lane's
            # discovery scope, including effects before a later statement fails.
            # These queries also replace the query connection's pending result,
            # releasing a partly read statement before the Lane job completes.
            try:
                self._capture_session_metadata()
            except Exception:
                # A transaction error must keep its original driver exception.
                pass
        elapsed = (time.perf_counter() - start) * 1000
        return QueryResult(
            columns=columns, rows=rows, row_count=len(rows),
            execution_time_ms=elapsed, warnings=[],
        )

    def scope_levels(self) -> list[ScopeLevel]:
        return [ScopeLevel(name="catalog", label="Catalog"), ScopeLevel(name="schema", label="Schema")]

    def _capture_session_metadata(self) -> None:
        with self._query_state_lock:
            self._snapshotting = True
        try:
            self._read_session_metadata()
        finally:
            with self._query_state_lock:
                self._snapshotting = False

    def _read_session_metadata(self) -> None:
        assert self.con is not None, "adapter not connected"
        current = self.con.execute("SELECT current_database(), current_schema()").fetchone()
        assert current is not None, "current database/schema query returned no row"
        self._scope = (current[0], current[1])
        # Temporary objects belong to the parent connection and are invisible to
        # its sibling cursor. Publish a replacement snapshot; metadata readers
        # never access the query connection or observe a partially built table.
        schemas = self.con.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE catalog_name='temp'"
        ).fetchall()
        rows = self.con.execute(
            "SELECT t.table_schema, t.table_name, c.column_name, c.data_type, c.is_nullable "
            "FROM information_schema.tables t LEFT JOIN information_schema.columns c "
            "ON c.table_catalog=t.table_catalog AND c.table_schema=t.table_schema "
            "AND c.table_name=t.table_name WHERE t.table_catalog='temp' "
            "ORDER BY t.table_schema, t.table_name, c.ordinal_position"
        ).fetchall()
        tables: dict[TableRef, TableSchema] = {}
        for schema, name, column, data_type, nullable in rows:
            table = TableRef(name, ("temp", schema))
            if table not in tables:
                tables[table] = TableSchema(
                    name=name, scope=table.path,
                    sql_identifier=".".join(quote_identifier(part) for part in (*table.path, name)),
                )
            if column is not None:
                tables[table].columns.append(
                    ColumnDef(name=column, data_type=data_type, nullable=nullable == "YES")
                )
        self._temp_schemas = tuple(ContainerEntry(name=row[0], internal=True) for row in schemas)
        self._temp_tables = MappingProxyType(tables)

    def _default_scope(self) -> ScopePath:
        return self._scope

    @staticmethod
    def _validate_path(path: ScopePath, arity: int) -> None:
        if len(path) != arity or not all(isinstance(part, str) and part for part in path):
            raise AdapterQueryError(f"DuckDB requires a {arity}-component Scope Path")

    def _list_databases(self) -> list[ContainerEntry]:
        try:
            rel = self._cur().execute(
                "SELECT database_name, internal FROM duckdb_databases()"
            )
            return [ContainerEntry(name=name, internal=internal) for name, internal in rel.fetchall()]
        except Exception as e:
            raise AdapterQueryError(str(e)) from e

    def _list_schemas(self, path: ScopePath) -> list[ContainerEntry]:
        self._validate_path(path, 1)
        if path == ("temp",):
            return list(self._temp_schemas)
        try:
            rel = self._cur().execute(
                "SELECT schema_name FROM information_schema.schemata WHERE catalog_name=?",
                [path[0]],
            )
            return [
                ContainerEntry(
                    name=row[0],
                    internal=path[0] in {"system", "temp"}
                    or row[0] in {"information_schema", "pg_catalog"},
                )
                for row in rel.fetchall()
            ]
        except Exception as e:
            raise AdapterQueryError(str(e)) from e

    def _list_tables(self, path: ScopePath) -> list[TableEntry]:
        self._validate_path(path, 2)
        if path[0] == "temp":
            return [
                TableEntry(
                    name=table.name,
                    sql_identifier=".".join(quote_identifier(part) for part in (*path, table.name)),
                )
                for table in self._temp_tables if table.path == path
            ]
        try:
            rel = self._cur().execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog=? AND table_schema=?",
                list(path),
            )
            return [
                TableEntry(
                    name=row[0],
                    sql_identifier=".".join(quote_identifier(part) for part in (*path, row[0])),
                )
                for row in rel.fetchall()
            ]
        except Exception as e:
            raise AdapterQueryError(str(e)) from e

    def _get_table_schema(self, table: TableRef) -> TableSchema:
        self._validate_path(table.path, 2)
        if table.path[0] == "temp":
            return deepcopy(self._temp_tables.get(table, TableSchema(name=table.name, scope=table.path)))
        catalog, schema = table.path
        try:
            rel = self._cur().execute(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name=? AND table_schema=? AND table_catalog=? "
                "ORDER BY ordinal_position",
                [table.name, schema, catalog],
            )
            columns = [
                ColumnDef(name=name, data_type=dtype, nullable=(nullable == "YES"))
                for name, dtype, nullable in rel.fetchall()
            ]
        except Exception as e:
            raise AdapterQueryError(str(e)) from e
        identifier = ".".join(quote_identifier(part) for part in (*table.path, table.name))
        return TableSchema(
            name=table.name, scope=table.path,
            columns=columns, primary_keys=[], foreign_keys=[],
            sql_identifier=identifier if columns else None,
        )

    def dialect_name(self) -> str:
        return "duckdb"

    def get_keywords(self) -> list[str]:
        return list(_DUCKDB_KEYWORDS)
