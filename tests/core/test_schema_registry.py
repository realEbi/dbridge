from dbridge.adapters.base import ContainerEntry, TableEntry, TableRef, TableSchema
from dbridge.core.schema_registry import SchemaRegistry


class CountingAdapter:
    def __init__(self):
        self.calls = {"databases": 0, "schemas": 0, "tables": 0, "metadata": 0}

    def list_databases(self):
        self.calls["databases"] += 1
        return [ContainerEntry("first"), ContainerEntry("second")]

    def list_schemas(self, path):
        self.calls["schemas"] += 1
        return [ContainerEntry(path[0] + "_schema")]

    def list_tables(self, path):
        self.calls["tables"] += 1
        return [TableEntry("orders", f'"{path[0]}"."main"."orders"')]

    def get_table_schema(self, table):
        self.calls["metadata"] += 1
        return TableSchema(name=table.name, scope=table.path)


def _introspect(registry):
    return (
        registry.list_databases(),
        registry.list_schemas(("first",)),
        registry.list_tables(("first", "main")),
        registry.get_table_schema(TableRef("orders", ("first", "main"))),
    )


def test_every_introspection_result_is_cached():
    adapter = CountingAdapter()
    registry = SchemaRegistry(adapter)
    first = _introspect(registry)
    second = _introspect(registry)
    assert first == second
    assert all(a is b for a, b in zip(first, second))
    assert adapter.calls == dict.fromkeys(adapter.calls, 1)


def test_refresh_clears_every_introspection_result():
    adapter = CountingAdapter()
    registry = SchemaRegistry(adapter)
    _introspect(registry)
    registry.refresh()
    _introspect(registry)
    assert adapter.calls == dict.fromkeys(adapter.calls, 2)


def test_every_introspection_result_expires():
    adapter = CountingAdapter()
    registry = SchemaRegistry(adapter, ttl_seconds=0)
    _introspect(registry)
    _introspect(registry)
    assert adapter.calls == dict.fromkeys(adapter.calls, 2)


def test_cache_separates_full_literal_paths_and_table_names():
    adapter = CountingAdapter()
    registry = SchemaRegistry(adapter)
    paths = [("first.with.dot", "main"), ("second", "main")]
    for path in paths:
        assert registry.list_schemas(path[:1]) == [ContainerEntry(path[0] + "_schema")]
        assert registry.list_tables(path)[0].sql_identifier == f'"{path[0]}"."main"."orders"'
        for name in ("orders", "orders.with.dot"):
            table = TableRef(name, path)
            first = registry.get_table_schema(table)
            assert first.scope == path
            assert first.name == name
            assert registry.get_table_schema(table) is first
    assert adapter.calls == {"databases": 0, "schemas": 2, "tables": 2, "metadata": 4}


def test_refresh_reveals_new_catalog_schema_and_table(engine):
    sid = engine.connect("duckdb", {"uri": ":memory:"})["session_id"]
    try:
        databases = engine.list_databases(sid)
        schemas = engine.list_schemas(sid, ("memory",))
        tables = engine.list_tables(sid, ("memory", "main"))
        engine.execute(sid, "ATTACH ':memory:' AS side")
        engine.execute(sid, "CREATE SCHEMA memory.sales")
        engine.execute(sid, "CREATE TABLE memory.main.orders (id INTEGER)")
        assert engine.list_databases(sid) == databases
        assert engine.list_schemas(sid, ("memory",)) == schemas
        assert engine.list_tables(sid, ("memory", "main")) == tables
        engine.refresh_schema(sid)
        assert "side" in [e["name"] for e in engine.list_databases(sid)]
        assert "sales" in [e["name"] for e in engine.list_schemas(sid, ("memory",))]
        assert "orders" in [e["name"] for e in engine.list_tables(sid, ("memory", "main"))]
    finally:
        engine.disconnect(sid)
