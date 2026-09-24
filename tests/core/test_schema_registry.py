import asyncio

import pytest

from dbridge.adapters.base import ContainerEntry, TableEntry, TableRef, TableSchema
from dbridge.core.schema_registry import SchemaRegistry


class CountingAdapter:
    def __init__(self):
        self.calls = {"databases": 0, "schemas": 0, "tables": 0, "metadata": 0}

    async def list_databases(self):
        self.calls["databases"] += 1
        return [ContainerEntry("first"), ContainerEntry("second")]

    async def list_schemas(self, path):
        self.calls["schemas"] += 1
        return [ContainerEntry(path[0] + "_schema")]

    async def list_tables(self, path):
        self.calls["tables"] += 1
        return [TableEntry("orders", f'"{path[0]}"."main"."orders"')]

    async def get_table_schema(self, table):
        self.calls["metadata"] += 1
        return TableSchema(name=table.name, scope=table.path)


async def _introspect(registry):
    return (
        await registry.list_databases(),
        await registry.list_schemas(("first",)),
        await registry.list_tables(("first", "main")),
        await registry.get_table_schema(TableRef("orders", ("first", "main"))),
    )


async def test_every_introspection_result_is_cached():
    adapter = CountingAdapter()
    registry = SchemaRegistry(adapter)
    first = await _introspect(registry)
    second = await _introspect(registry)
    assert first == second
    assert all(a is b for a, b in zip(first, second))
    assert adapter.calls == dict.fromkeys(adapter.calls, 1)


async def test_refresh_clears_every_introspection_result():
    adapter = CountingAdapter()
    registry = SchemaRegistry(adapter)
    await _introspect(registry)
    registry.refresh()
    await _introspect(registry)
    assert adapter.calls == dict.fromkeys(adapter.calls, 2)


async def test_every_introspection_result_expires():
    adapter = CountingAdapter()
    registry = SchemaRegistry(adapter, ttl_seconds=0)
    await _introspect(registry)
    await _introspect(registry)
    assert adapter.calls == dict.fromkeys(adapter.calls, 2)


async def test_cache_separates_full_literal_paths_and_table_names():
    adapter = CountingAdapter()
    registry = SchemaRegistry(adapter)
    paths = [("first.with.dot", "main"), ("second", "main")]
    for path in paths:
        assert await registry.list_schemas(path[:1]) == [ContainerEntry(path[0] + "_schema")]
        assert (await registry.list_tables(path))[0].sql_identifier == f'"{path[0]}"."main"."orders"'
        for name in ("orders", "orders.with.dot"):
            table = TableRef(name, path)
            first = await registry.get_table_schema(table)
            assert first.scope == path
            assert first.name == name
            assert await registry.get_table_schema(table) is first
    assert adapter.calls == {"databases": 0, "schemas": 2, "tables": 2, "metadata": 4}


async def test_refresh_reveals_new_catalog_schema_and_table(engine):
    sid = (await engine.connect("duckdb", {"uri": ":memory:"}))["session_id"]
    try:
        databases = await engine.list_databases(sid)
        schemas = await engine.list_schemas(sid, ("memory",))
        tables = await engine.list_tables(sid, ("memory", "main"))
        await engine.execute(sid, "ATTACH ':memory:' AS side")
        await engine.execute(sid, "CREATE SCHEMA memory.sales")
        await engine.execute(sid, "CREATE TABLE memory.main.orders (id INTEGER)")
        assert await engine.list_databases(sid) == databases
        assert await engine.list_schemas(sid, ("memory",)) == schemas
        assert await engine.list_tables(sid, ("memory", "main")) == tables
        await engine.refresh_schema(sid)
        assert "side" in [e["name"] for e in await engine.list_databases(sid)]
        assert "sales" in [e["name"] for e in await engine.list_schemas(sid, ("memory",))]
        assert "orders" in [e["name"] for e in await engine.list_tables(sid, ("memory", "main"))]
    finally:
        await engine.disconnect(sid)


class GatedListingAdapter:
    """Capture the database state when fetching, then wait until released."""

    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.tables = [TableEntry("before", '"main"."before"')]
        self.calls = 0

    async def list_tables(self, path):
        self.calls += 1
        snapshot = list(self.tables)
        self.started.set()
        await self.release.wait()
        return snapshot


async def test_listing_started_before_refresh_does_not_repopulate_cache():
    adapter = GatedListingAdapter()
    registry = SchemaRegistry(adapter)
    stale = asyncio.create_task(registry.list_tables(("main",)))
    await asyncio.wait_for(adapter.started.wait(), timeout=1)
    adapter.tables.append(TableEntry("after", '"main"."after"'))

    registry.refresh()
    adapter.release.set()
    assert [table.name for table in await stale] == ["before"]
    assert [table.name for table in await registry.list_tables(("main",))] == ["before", "after"]
    assert adapter.calls == 2


async def test_cancelled_listing_leaves_no_cache_entry():
    adapter = GatedListingAdapter()
    registry = SchemaRegistry(adapter)
    cancelled = asyncio.create_task(registry.list_tables(("main",)))
    await asyncio.wait_for(adapter.started.wait(), timeout=1)
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled

    adapter.tables.append(TableEntry("after", '"main"."after"'))
    adapter.release.set()
    assert [table.name for table in await registry.list_tables(("main",))] == ["before", "after"]
    assert adapter.calls == 2


async def test_concurrent_misses_have_independent_cancellation():
    adapter = GatedListingAdapter()
    registry = SchemaRegistry(adapter)
    first = asyncio.create_task(registry.list_tables(("main",)))
    await asyncio.wait_for(adapter.started.wait(), timeout=1)
    adapter.started.clear()
    second = asyncio.create_task(registry.list_tables(("main",)))
    await asyncio.wait_for(adapter.started.wait(), timeout=1)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    adapter.release.set()
    assert await second == adapter.tables
    assert await registry.list_tables(("main",)) == adapter.tables
    assert adapter.calls == 2
