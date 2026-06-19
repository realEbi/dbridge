import time

import duckdb

from dbridge.adapters.base import (
    ColumnDef,
    DBAdapter,
    ForeignKey,
    QueryResult,
    TableSchema,
)
from dbridge.exceptions import AdapterConnectionError, AdapterQueryError

_DUCKDB_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS",
    "ON", "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "INSERT", "INTO",
    "VALUES", "UPDATE", "SET", "DELETE", "CREATE", "TABLE", "DROP", "DISTINCT",
    "AS", "AND", "OR", "NOT", "NULL", "IS", "IN", "LIKE", "BETWEEN", "UNION",
    "ALL", "WITH", "RECURSIVE", "OVER", "PARTITION", "WINDOW",
]


class DuckDBAdapter(DBAdapter):
    adapter_name = "duckdb"

    def __init__(self, config: dict[str, str]) -> None:
        super().__init__(config)
        self.uri: str = config.get("uri", ":memory:")
        self.con: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> None:
        try:
            self.con = duckdb.connect(self.uri)
        except Exception as e:
            raise AdapterConnectionError(str(e)) from e

    def disconnect(self) -> None:
        if self.con is not None:
            self.con.close()
            self.con = None

    def _cur(self) -> duckdb.DuckDBPyConnection:
        assert self.con is not None, "adapter not connected"
        return self.con

    def execute(self, sql: str) -> QueryResult:
        start = time.perf_counter()
        try:
            rel = self._cur().execute(sql)
            columns = [d[0] for d in rel.description] if rel.description else []
            rows = [list(r) for r in rel.fetchall()]
        except Exception as e:
            raise AdapterQueryError(str(e)) from e
        elapsed = (time.perf_counter() - start) * 1000
        return QueryResult(
            columns=columns, rows=rows, row_count=len(rows),
            execution_time_ms=elapsed, warnings=[],
        )

    def list_databases(self) -> list[str]:
        rel = self._cur().execute(
            "SELECT DISTINCT catalog_name FROM information_schema.schemata"
        )
        return [r[0] for r in rel.fetchall()]

    def list_schemas(self, database: str | None = None) -> list[str]:
        rel = self._cur().execute(
            "SELECT DISTINCT schema_name FROM information_schema.schemata"
        )
        return [r[0] for r in rel.fetchall()]

    def list_tables(
        self, database: str | None = None, schema: str | None = None
    ) -> list[str]:
        schema = schema or "main"
        rel = self._cur().execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema=?",
            [schema],
        )
        return [r[0] for r in rel.fetchall()]

    def get_table_schema(self, fqn: str) -> TableSchema:
        table = fqn.split(".")[-1]
        rel = self._cur().execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name=? ORDER BY ordinal_position",
            [table],
        )
        columns = [
            ColumnDef(
                name=name,
                data_type=dtype,
                nullable=(nullable == "YES"),
            )
            for name, dtype, nullable in rel.fetchall()
        ]
        return TableSchema(
            name=table, schema="main", database=None,
            columns=columns, primary_keys=[], foreign_keys=[],
        )

    def dialect_name(self) -> str:
        return "duckdb"

    def get_keywords(self) -> list[str]:
        return list(_DUCKDB_KEYWORDS)
