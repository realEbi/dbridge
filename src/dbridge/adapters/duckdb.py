import time

import duckdb

from dbridge.adapters.base import (
    ColumnDef,
    ContainerEntry,
    DBAdapter,
    QueryResult,
    ScopeLevel,
    ScopePath,
    TableEntry,
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

    def scope_levels(self) -> list[ScopeLevel]:
        return [ScopeLevel(name="catalog", label="Catalog"), ScopeLevel(name="schema", label="Schema")]

    def default_scope(self) -> ScopePath:
        try:
            current = self._cur().execute(
                "SELECT current_database(), current_schema()"
            ).fetchone()
            assert current is not None, "current database/schema query returned no row"
            return (current[0], current[1])
        except Exception as e:
            raise AdapterQueryError(str(e)) from e

    @staticmethod
    def _validate_path(path: ScopePath, arity: int) -> None:
        if len(path) != arity or not all(isinstance(part, str) and part for part in path):
            raise AdapterQueryError(f"DuckDB requires a {arity}-component Scope Path")

    def list_databases(self) -> list[ContainerEntry]:
        try:
            rel = self._cur().execute(
                "SELECT database_name, internal FROM duckdb_databases()"
            )
            return [ContainerEntry(name=name, internal=internal) for name, internal in rel.fetchall()]
        except Exception as e:
            raise AdapterQueryError(str(e)) from e

    def list_schemas(self, path: ScopePath) -> list[ContainerEntry]:
        self._validate_path(path, 1)
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

    def list_tables(self, path: ScopePath) -> list[TableEntry]:
        self._validate_path(path, 2)
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

    def get_table_schema(self, table: TableRef) -> TableSchema:
        self._validate_path(table.path, 2)
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
