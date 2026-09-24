import pytest

from dbridge.adapters.base import ContainerEntry, ScopeLevel, TableRef
from dbridge.adapters.identifiers import quote_identifier
from dbridge.adapters.sqlite import SqliteAdapter
from dbridge.exceptions import AdapterConnectionError, AdapterQueryError


@pytest.fixture
async def adapter():
    a = SqliteAdapter({"uri": ":memory:"})
    (await a.connect())
    (await a.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))
    (await a.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id))"
    ))
    (await a.execute("INSERT INTO users (id, name) VALUES (1, 'ada')"))
    yield a
    (await a.disconnect())


async def test_list_tables(adapter):
    assert {table.name for table in (await adapter.list_tables(("main",)))} == {"users", "orders"}


async def test_execute_returns_rows(adapter):
    result = (await adapter.execute("SELECT id, name FROM users"))
    assert result.columns == ["id", "name"]
    assert result.rows == [[1, "ada"]]
    assert result.row_count == 1


async def test_get_table_schema(adapter):
    schema = (await adapter.get_table_schema(TableRef("users", ("main",))))
    assert [c.name for c in schema.columns] == ["id", "name"]
    assert schema.primary_keys == ["id"]
    name_col = next(c for c in schema.columns if c.name == "name")
    assert name_col.nullable is False


async def test_foreign_keys(adapter):
    schema = (await adapter.get_table_schema(TableRef("orders", ("main",))))
    assert schema.foreign_keys[0].referenced_table == "users"


async def test_writes_persist_across_reconnect(tmp_path):
    """Without autocommit, sqlite3 rolls DML back when the connection closes."""
    uri = str(tmp_path / "persist.db")

    a = SqliteAdapter({"uri": uri})
    (await a.connect())
    (await a.execute("CREATE TABLE t (id INTEGER, label TEXT)"))
    (await a.execute("INSERT INTO t VALUES (1, 'one')"))
    (await a.execute("INSERT INTO t VALUES (2, 'two')"))
    (await a.disconnect())

    b = SqliteAdapter({"uri": uri})
    (await b.connect())
    result = (await b.execute("SELECT id, label FROM t ORDER BY id"))
    (await b.disconnect())

    assert result.rows == [[1, "one"], [2, "two"]]


async def test_update_and_delete_persist_across_reconnect(tmp_path):
    uri = str(tmp_path / "persist2.db")

    a = SqliteAdapter({"uri": uri})
    (await a.connect())
    (await a.execute("CREATE TABLE t (id INTEGER)"))
    (await a.execute("INSERT INTO t VALUES (1), (2), (3)"))
    (await a.execute("UPDATE t SET id = 99 WHERE id = 1"))
    (await a.execute("DELETE FROM t WHERE id = 2"))
    (await a.disconnect())

    b = SqliteAdapter({"uri": uri})
    (await b.connect())
    rows = (await b.execute("SELECT id FROM t ORDER BY id")).rows
    (await b.disconnect())

    assert rows == [[3], [99]]


# ── construction, connection, and error mapping ───────────────────────────────

async def test_missing_uri_is_rejected_at_construction():
    """The adapter refuses to exist without a uri rather than failing at connect."""
    with pytest.raises(AdapterConnectionError, match="uri"):
        SqliteAdapter({})


async def test_empty_uri_is_rejected():
    with pytest.raises(AdapterConnectionError):
        SqliteAdapter({"uri": ""})


async def test_unopenable_path_raises_adapter_connection_error(tmp_path):
    """A driver-level failure is translated, not leaked as sqlite3.Error."""
    unopenable = tmp_path / "no-such-dir" / "db.sqlite"
    adapter = SqliteAdapter({"uri": str(unopenable)})
    with pytest.raises(AdapterConnectionError):
        (await adapter.connect())


async def test_invalid_sql_raises_adapter_query_error(adapter):
    with pytest.raises(AdapterQueryError):
        (await adapter.execute("SELECT * FROM no_such_table"))


async def test_syntax_error_raises_adapter_query_error(adapter):
    with pytest.raises(AdapterQueryError):
        (await adapter.execute("NOT VALID SQL"))


async def test_disconnect_on_never_connected_adapter_is_a_noop():
    (await SqliteAdapter({"uri": ":memory:"}).disconnect())


async def test_disconnect_is_idempotent(tmp_path):
    adapter = SqliteAdapter({"uri": str(tmp_path / "db.sqlite")})
    (await adapter.connect())
    (await adapter.disconnect())
    (await adapter.disconnect())
    assert adapter.con is None


# ── single-namespace introspection and dialect ────────────────────────────────

async def test_list_databases_is_the_single_namespace(adapter):
    assert (await adapter.list_databases()) == [ContainerEntry("main", internal=False)]


async def test_list_schemas_has_no_second_tier(adapter):
    assert (await adapter.list_schemas(("main",))) == []


async def test_hierarchy_has_one_namespace_level(adapter):
    assert adapter.scope_levels() == [ScopeLevel("namespace", "Namespace")]
    assert (await adapter.default_scope()) == ("main",)
    schema = (await adapter.get_table_schema(TableRef("users", ("main",))))
    assert schema.scope == ("main",)
    assert schema.sql_identifier == '"main"."users"'


async def test_attached_namespace_listings_and_metadata_are_isolated(adapter):
    namespace = 'side.catalog "quoted"'
    quoted_namespace = quote_identifier(namespace)
    (await adapter.execute(f"ATTACH DATABASE ':memory:' AS {quoted_namespace}"))
    (await adapter.execute(f"CREATE TABLE {quoted_namespace}.users (attached_id INTEGER)"))
    (await adapter.execute(f"INSERT INTO {quoted_namespace}.users VALUES (42)"))

    assert ContainerEntry(namespace, internal=False) in (await adapter.list_databases())
    assert [table.name for table in (await adapter.list_tables((namespace,)))] == ["users"]
    assert {table.name for table in (await adapter.list_tables(("main",)))} == {"users", "orders"}
    schema = (await adapter.get_table_schema(TableRef("users", (namespace,))))
    assert schema.scope == (namespace,)
    assert [column.name for column in schema.columns] == ["attached_id"]
    assert schema.sql_identifier == f'{quoted_namespace}."users"'
    assert (await adapter.execute(f"SELECT * FROM {schema.sql_identifier}")).rows == [[42]]
    assert (await adapter.default_scope()) == ("main",)


async def test_temp_namespace_is_returned_and_marked_internal(adapter):
    (await adapter.execute("CREATE TEMP TABLE transient (id INTEGER)"))
    assert ContainerEntry("temp", internal=True) in (await adapter.list_databases())
    assert ContainerEntry("main", internal=False) in (await adapter.list_databases())


@pytest.mark.parametrize("name", ["with space", "select", 'has"quote', "literal.dot"])
async def test_listed_identifiers_execute_literal_table_names(adapter, name):
    (await adapter.execute(f"CREATE TABLE {quote_identifier(name)} (sentinel INTEGER)"))
    (await adapter.execute(f"INSERT INTO {quote_identifier(name)} VALUES (123)"))

    table = next(table for table in (await adapter.list_tables(("main",))) if table.name == name)
    assert table.sql_identifier == f'"main".{quote_identifier(name)}'
    assert (await adapter.execute(f"SELECT * FROM {table.sql_identifier}")).rows == [[123]]
    schema = (await adapter.get_table_schema(TableRef(name, ("main",))))
    assert schema.name == name
    assert schema.sql_identifier == table.sql_identifier


async def test_missing_table_does_not_fall_back_to_main(adapter):
    (await adapter.execute("ATTACH DATABASE ':memory:' AS empty"))
    schema = (await adapter.get_table_schema(TableRef("users", ("empty",))))
    assert schema.scope == ("empty",)
    assert schema.columns == []
    assert schema.sql_identifier is None


@pytest.mark.parametrize("path", [(), ("main", "main"), ("",)])
async def test_invalid_scope_path_is_rejected(adapter, path):
    with pytest.raises(AdapterQueryError, match="Scope Path"):
        (await adapter.list_schemas(path))
    with pytest.raises(AdapterQueryError, match="Scope Path"):
        (await adapter.list_tables(path))
    with pytest.raises(AdapterQueryError, match="Scope Path"):
        (await adapter.get_table_schema(TableRef("users", path)))


async def test_dialect_name(adapter):
    assert adapter.dialect_name() == "sqlite"


async def test_get_keywords_returns_a_fresh_copy(adapter):
    first = adapter.get_keywords()
    assert "SELECT" in first

    first.append("NOT_A_KEYWORD")
    assert "NOT_A_KEYWORD" not in adapter.get_keywords()


async def test_writes_persist_across_disconnect(tmp_path):
    """isolation_level=None means writes are committed, not rolled back on close."""
    uri = str(tmp_path / "db.sqlite")
    writer = SqliteAdapter({"uri": uri})
    (await writer.connect())
    (await writer.execute("CREATE TABLE t (id INTEGER)"))
    (await writer.execute("INSERT INTO t VALUES (1)"))
    (await writer.disconnect())

    reader = SqliteAdapter({"uri": uri})
    (await reader.connect())
    try:
        assert (await reader.execute("SELECT id FROM t")).rows == [[1]]
    finally:
        (await reader.disconnect())
