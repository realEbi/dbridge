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
