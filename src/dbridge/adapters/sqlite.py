import sqlite3
import time

from dbridge.adapters.base import (
    ColumnDef,
    DBAdapter,
    ForeignKey,
    QueryResult,
    TableSchema,
)
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
        # SQLite has a single database namespace.
        return ["main"]

    def list_schemas(self, database: str | None = None) -> list[str]:
        return ["main"]

    def list_tables(
        self, database: str | None = None, schema: str | None = None
    ) -> list[str]:
        cur = self._cur()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [r[0] for r in cur.fetchall()]

    def get_table_schema(self, fqn: str) -> TableSchema:
        table = fqn.split(".")[-1]
        cur = self._cur()
        cur.execute(f"PRAGMA table_info('{table}')")
        columns, pks = [], []
        for _cid, name, ctype, notnull, dflt, pk in cur.fetchall():
            columns.append(
                ColumnDef(
                    name=name, data_type=ctype or "",
                    nullable=not notnull, default=dflt, comment=None,
                )
            )
            if pk:
                pks.append(name)
        fks: list[ForeignKey] = []
        cur.execute(f"PRAGMA foreign_key_list('{table}')")
        for row in cur.fetchall():
            # row: id, seq, table, from, to, on_update, on_delete, match
            fks.append(
                ForeignKey(
                    column=row[3], referenced_table=row[2], referenced_column=row[4]
                )
            )
        return TableSchema(
            name=table, schema="main", database="main",
            columns=columns, primary_keys=pks, foreign_keys=fks,
        )

    def dialect_name(self) -> str:
        return "sqlite"

    def get_keywords(self) -> list[str]:
        return list(_SQLITE_KEYWORDS)
