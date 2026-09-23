import sqlite3
import time

from dbridge.adapters.base import (
    ColumnDef,
    DBAdapter,
    ForeignKey,
    QueryResult,
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

    def list_databases(self) -> list[str]:
        return [row[1] for row in self._cur().execute("PRAGMA database_list").fetchall()]

    def list_schemas(self, database: str | None = None) -> list[str]:
        namespace = database or "main"
        return [namespace] if namespace in self.list_databases() else []

    @staticmethod
    def _namespace(database: str | None, schema: str | None) -> str:
        if database and schema and database != schema:
            raise AdapterQueryError("SQLite database and schema must name the same namespace")
        return schema or database or "main"

    def list_tables(
        self, database: str | None = None, schema: str | None = None
    ) -> list[str]:
        cur = self._cur()
        namespace = quote_identifier(self._namespace(database, schema))
        try:
            cur.execute(f"SELECT name FROM {namespace}.sqlite_master WHERE type='table'")
            return [r[0] for r in cur.fetchall()]
        except sqlite3.Error as e:
            raise AdapterQueryError(str(e)) from e

    def get_table_schema(self, fqn: str | TableRef) -> TableSchema:
        if isinstance(fqn, TableRef):
            table = fqn.name
            namespace = self._namespace(fqn.database, fqn.schema)
        else:
            parts = fqn.split(".")
            table = parts[-1]
            namespace = parts[-2] if len(parts) >= 2 else "main"
        cur = self._cur()
        identifier = f"{quote_identifier(namespace)}.{quote_identifier(table)}"
        try:
            cur.execute(f"PRAGMA {quote_identifier(namespace)}.table_info({quote_identifier(table)})")
            column_rows = cur.fetchall()
            cur.execute(f"PRAGMA {quote_identifier(namespace)}.foreign_key_list({quote_identifier(table)})")
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
            name=table, schema=namespace, database=namespace,
            columns=columns, primary_keys=pks, foreign_keys=fks,
            sql_identifier=identifier if columns else None,
        )

    def dialect_name(self) -> str:
        return "sqlite"

    def get_keywords(self) -> list[str]:
        return list(_SQLITE_KEYWORDS)
