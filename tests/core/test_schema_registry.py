from dbridge.adapters.base import TableSchema
from dbridge.core.schema_registry import SchemaRegistry


class FakeAdapter:
    def __init__(self):
        self.table_calls = 0

    def list_tables(self, database=None, schema=None):
        self.table_calls += 1
        return ["a", "b"]

    def get_table_schema(self, fqn):
        return None


def test_caches_within_ttl():
    fake = FakeAdapter()
    reg = SchemaRegistry(fake, ttl_seconds=60)
    assert reg.list_tables() == ["a", "b"]
    assert reg.list_tables() == ["a", "b"]
    assert fake.table_calls == 1


def test_refresh_clears_cache():
    fake = FakeAdapter()
    reg = SchemaRegistry(fake, ttl_seconds=60)
    reg.list_tables()
    reg.refresh()
    reg.list_tables()
    assert fake.table_calls == 2


def test_ttl_expiry():
    fake = FakeAdapter()
    reg = SchemaRegistry(fake, ttl_seconds=0)
    reg.list_tables()
    reg.list_tables()
    assert fake.table_calls == 2


class _CountingAdapter:
    """Counts get_table_schema calls and returns a distinct object per fqn."""

    def __init__(self):
        self.schema_calls = 0

    def list_tables(self, database=None, schema=None):
        return ["users", "orders"]

    def get_table_schema(self, fqn):
        self.schema_calls += 1
        return TableSchema(name=fqn, schema="main", database="main")


def test_get_table_schema_is_cached():
    """A second lookup of the same fqn must not re-query the adapter."""
    adapter = _CountingAdapter()
    registry = SchemaRegistry(adapter, ttl_seconds=60)

    first = registry.get_table_schema("users")
    second = registry.get_table_schema("users")

    assert first is second
    assert adapter.schema_calls == 1


def test_get_table_schema_caches_per_fqn():
    adapter = _CountingAdapter()
    registry = SchemaRegistry(adapter, ttl_seconds=60)

    registry.get_table_schema("users")
    registry.get_table_schema("orders")

    assert adapter.schema_calls == 2


def test_refresh_clears_the_table_schema_cache():
    adapter = _CountingAdapter()
    registry = SchemaRegistry(adapter, ttl_seconds=60)

    registry.get_table_schema("users")
    registry.refresh()
    registry.get_table_schema("users")

    assert adapter.schema_calls == 2


def test_expired_table_schema_entry_is_refetched():
    adapter = _CountingAdapter()
    registry = SchemaRegistry(adapter, ttl_seconds=0)

    registry.get_table_schema("users")
    registry.get_table_schema("users")

    assert adapter.schema_calls == 2
