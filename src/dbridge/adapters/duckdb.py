import time

import duckdb

from dbridge.adapters.base import (
    ColumnDef,
    DBAdapter,
    QueryResult,
    TableRef,
    TableSchema,
)
from dbridge.adapters.identifiers import quote_identifier
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
        # Scope to the catalog when given: duckdb attaches several (system,
        # temp, the file itself), and an unscoped query returns their schemas
        # mixed together.
        if database is None:
            rel = self._cur().execute(
                "SELECT DISTINCT schema_name FROM information_schema.schemata"
            )
        else:
            rel = self._cur().execute(
                "SELECT DISTINCT schema_name FROM information_schema.schemata "
                "WHERE catalog_name=?",
                [database],
            )
        return [r[0] for r in rel.fetchall()]

    def list_tables(
        self, database: str | None = None, schema: str | None = None
    ) -> list[str]:
        schema = schema or "main"
        if database is None:
            rel = self._cur().execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=?",
                [schema],
            )
        else:
            rel = self._cur().execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=? AND table_catalog=?",
                [schema, database],
            )
        return [r[0] for r in rel.fetchall()]

    def get_table_schema(self, fqn: str | TableRef) -> TableSchema:
        if isinstance(fqn, TableRef):
            table, schema, catalog = fqn.name, fqn.schema, fqn.database
        else:
            parts = fqn.split(".")
            table = parts[-1]
            schema = parts[-2] if len(parts) >= 2 else None
            catalog = parts[-3] if len(parts) >= 3 else None
        try:
            if schema is None or catalog is None:
                current = self._cur().execute(
                    "SELECT current_database(), current_schema()"
                ).fetchone()
                assert current is not None, "current database/schema query returned no row"
                current_catalog, current_schema = current
                schema = schema or current_schema
                catalog = catalog or current_catalog
            rel = self._cur().execute(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name=? AND table_schema=? AND table_catalog=? "
                "ORDER BY ordinal_position",
                [table, schema, catalog],
            )
            columns = [
                ColumnDef(name=name, data_type=dtype, nullable=(nullable == "YES"))
                for name, dtype, nullable in rel.fetchall()
            ]
        except Exception as e:
            raise AdapterQueryError(str(e)) from e
        identifier = ".".join(quote_identifier(part) for part in (catalog, schema, table))
        return TableSchema(
            name=table, schema=schema, database=catalog,
            columns=columns, primary_keys=[], foreign_keys=[],
            sql_identifier=identifier if columns else None,
        )

    def dialect_name(self) -> str:
        return "duckdb"

    def get_keywords(self) -> list[str]:
        return list(_DUCKDB_KEYWORDS)
