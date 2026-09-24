import sqlite3
import time

from dbridge.adapters.base import (
    ColumnDef,
    ContainerEntry,
    DBAdapter,
    ForeignKey,
    QueryResult,
    ScopeLevel,
    ScopePath,
    TableEntry,
    TableRef,
    TableSchema,
)
from dbridge.adapters.identifiers import quote_identifier
from dbridge.exceptions import AdapterConnectionError, AdapterQueryError

# A small dialect keyword set is enough for tier-1 completion.
_SQLITE_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "INNER", "OUTER", "ON", "GROUP",
    "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "INSERT", "INTO", "VALUES",
    "UPDATE", "SET", "DELETE", "CREATE", "TABLE", "DROP", "DISTINCT", "AS",
    "AND", "OR", "NOT", "NULL", "IS", "IN", "LIKE", "BETWEEN", "UNION", "ALL",
]


class SqliteAdapter(DBAdapter):
    adapter_name = "sqlite"

    def __init__(self, config: dict[str, str]) -> None:
        super().__init__(config)
        uri = self.config.get("uri")
        if not uri:
            raise AdapterConnectionError("sqlite adapter requires a 'uri' config key")
        self.uri = uri
        self.con: sqlite3.Connection | None = None

    def connect(self) -> None:
        try:
            # isolation_level=None puts the driver in autocommit mode. Without it
            # sqlite3 opens an implicit transaction before every INSERT/UPDATE/
            # DELETE, and disconnect() closing the connection rolls those writes
            # back. Phase 1 exposes no transaction control (ADR-0001), so there
            # is nothing that would ever issue the commit.
            self.con = sqlite3.connect(self.uri, isolation_level=None)
        except sqlite3.Error as e:
            raise AdapterConnectionError(str(e)) from e

    def disconnect(self) -> None:
        if self.con is not None:
            self.con.close()
            self.con = None

    def _cur(self) -> sqlite3.Cursor:
        assert self.con is not None, "adapter not connected"
        return self.con.cursor()

    def execute(self, sql: str) -> QueryResult:
        start = time.perf_counter()
        try:
            cur = self._cur()
            cur.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
        except sqlite3.Error as e:
            raise AdapterQueryError(str(e)) from e
        elapsed = (time.perf_counter() - start) * 1000
        return QueryResult(
            columns=columns, rows=rows, row_count=len(rows),
            execution_time_ms=elapsed, warnings=[],
        )

    def scope_levels(self) -> list[ScopeLevel]:
        return [ScopeLevel(name="namespace", label="Namespace")]

    def default_scope(self) -> ScopePath:
        databases = self.list_databases()
        return (next(entry.name for entry in databases if entry.name == "main"),)

    def list_databases(self) -> list[ContainerEntry]:
        try:
            rows = self._cur().execute("PRAGMA database_list").fetchall()
        except sqlite3.Error as e:
            raise AdapterQueryError(str(e)) from e
        return [ContainerEntry(name=row[1], internal=row[1] == "temp") for row in rows]

    def list_schemas(self, path: ScopePath) -> list[ContainerEntry]:
        self._namespace(path)
        return []

    @staticmethod
    def _namespace(path: ScopePath) -> str:
        if len(path) != 1 or not all(isinstance(part, str) and part for part in path):
            raise AdapterQueryError("SQLite requires a one-component Scope Path")
        return path[0]

    def list_tables(self, path: ScopePath) -> list[TableEntry]:
        cur = self._cur()
        namespace = quote_identifier(self._namespace(path))
        try:
            cur.execute(f"SELECT name FROM {namespace}.sqlite_master WHERE type='table'")
            return [
                TableEntry(name=row[0], sql_identifier=f"{namespace}.{quote_identifier(row[0])}")
                for row in cur.fetchall()
            ]
        except sqlite3.Error as e:
            raise AdapterQueryError(str(e)) from e

    def get_table_schema(self, table: TableRef) -> TableSchema:
        namespace = self._namespace(table.path)
        cur = self._cur()
        identifier = f"{quote_identifier(namespace)}.{quote_identifier(table.name)}"
        try:
            cur.execute(f"PRAGMA {quote_identifier(namespace)}.table_info({quote_identifier(table.name)})")
            column_rows = cur.fetchall()
            cur.execute(f"PRAGMA {quote_identifier(namespace)}.foreign_key_list({quote_identifier(table.name)})")
            foreign_rows = cur.fetchall()
        except sqlite3.Error as e:
            raise AdapterQueryError(str(e)) from e
        columns, pks = [], []
        for _cid, name, ctype, notnull, dflt, pk in column_rows:
            columns.append(
                ColumnDef(
                    name=name, data_type=ctype or "",
                    nullable=not notnull, default=dflt, comment=None,
                )
            )
            if pk:
                pks.append(name)
        fks: list[ForeignKey] = []
        for row in foreign_rows:
            # row: id, seq, table, from, to, on_update, on_delete, match
            fks.append(
                ForeignKey(
                    column=row[3], referenced_table=row[2], referenced_column=row[4]
                )
            )
        return TableSchema(
            name=table.name, scope=table.path,
            columns=columns, primary_keys=pks, foreign_keys=fks,
            sql_identifier=identifier if columns else None,
        )

    def dialect_name(self) -> str:
        return "sqlite"

    def get_keywords(self) -> list[str]:
        return list(_SQLITE_KEYWORDS)
