import pytest

from dbridge.adapters.sqlite import SqliteAdapter


@pytest.fixture
def adapter():
    a = SqliteAdapter({"uri": ":memory:"})
    a.connect()
    a.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    a.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id))"
    )
    a.execute("INSERT INTO users (id, name) VALUES (1, 'ada')")
    yield a
    a.disconnect()


def test_list_tables(adapter):
    assert set(adapter.list_tables()) == {"users", "orders"}


def test_execute_returns_rows(adapter):
    result = adapter.execute("SELECT id, name FROM users")
    assert result.columns == ["id", "name"]
    assert result.rows == [[1, "ada"]]
    assert result.row_count == 1


def test_get_table_schema(adapter):
    schema = adapter.get_table_schema("users")
    assert [c.name for c in schema.columns] == ["id", "name"]
    assert schema.primary_keys == ["id"]
    name_col = next(c for c in schema.columns if c.name == "name")
    assert name_col.nullable is False


def test_foreign_keys(adapter):
    schema = adapter.get_table_schema("orders")
    assert schema.foreign_keys[0].referenced_table == "users"
