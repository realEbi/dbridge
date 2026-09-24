import time

from dbridge.adapters.base import (
    ContainerEntry, DBAdapter, ScopePath, TableEntry, TableRef, TableSchema,
)


class SchemaRegistry:
    def __init__(self, adapter: DBAdapter, ttl_seconds: float = 60) -> None:
        self._adapter = adapter
        self._ttl = ttl_seconds
        self._cache: dict[tuple, tuple[float, object]] = {}

    def _get(self, key: tuple, producer):
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit is not None and (now - hit[0]) < self._ttl:
            return hit[1]
        value = producer()
        self._cache[key] = (now, value)
        return value

    def list_databases(self) -> list[ContainerEntry]:
        return self._get(("databases",), self._adapter.list_databases)

    def list_schemas(self, path: ScopePath) -> list[ContainerEntry]:
        return self._get(("schemas", path), lambda: self._adapter.list_schemas(path))

    def list_tables(self, path: ScopePath) -> list[TableEntry]:
        return self._get(("tables", path), lambda: self._adapter.list_tables(path))

    def get_table_schema(self, table: TableRef) -> TableSchema:
        return self._get(("table", table), lambda: self._adapter.get_table_schema(table))

    def refresh(self) -> None:
        self._cache.clear()
