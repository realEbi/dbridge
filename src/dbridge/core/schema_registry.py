import time
from collections.abc import Awaitable, Callable
from typing import TypeVar, cast

from dbridge.adapters.base import (
    ContainerEntry, DBAdapter, ScopePath, TableEntry, TableRef, TableSchema,
)

_T = TypeVar("_T")


class SchemaRegistry:
    def __init__(self, adapter: DBAdapter, ttl_seconds: float = 60) -> None:
        self._adapter = adapter
        self._ttl = ttl_seconds
        self._cache: dict[tuple, tuple[float, object]] = {}
        self._generation = 0

    async def _get(self, key: tuple, producer: Callable[[], Awaitable[_T]]) -> _T:
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit is not None and (now - hit[0]) < self._ttl:
            return cast(_T, hit[1])
        generation = self._generation
        value = await producer()
        # A refresh is authoritative even when older introspection is still in
        # flight. Cancellation propagates before this result can be cached.
        if generation == self._generation:
            self._cache[key] = (time.monotonic(), value)
        return value

    async def list_databases(self) -> list[ContainerEntry]:
        return await self._get(("databases",), self._adapter.list_databases)

    async def list_schemas(self, path: ScopePath) -> list[ContainerEntry]:
        return await self._get(("schemas", path), lambda: self._adapter.list_schemas(path))

    async def list_tables(self, path: ScopePath) -> list[TableEntry]:
        return await self._get(("tables", path), lambda: self._adapter.list_tables(path))

    async def get_table_schema(self, table: TableRef) -> TableSchema:
        return await self._get(("table", table), lambda: self._adapter.get_table_schema(table))

    def refresh(self) -> None:
        self._cache.clear()
        self._generation += 1
