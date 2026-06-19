import time

from dbridge.adapters.base import DBAdapter, TableSchema


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

    def list_tables(
        self, database: str | None = None, schema: str | None = None
    ) -> list[str]:
        return self._get(
            ("tables", database, schema),
            lambda: self._adapter.list_tables(database, schema),
        )

    def get_table_schema(self, fqn: str) -> TableSchema:
        return self._get(("schema", fqn), lambda: self._adapter.get_table_schema(fqn))

    def refresh(self) -> None:
        self._cache.clear()
