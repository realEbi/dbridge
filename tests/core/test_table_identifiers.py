"""Real Adapter identities and additive DSP compatibility for generated queries."""
import pytest

from dbridge.adapters.identifiers import quote_identifier
from dbridge.exceptions import AdapterQueryError
from dbridge.protocol.errors import INVALID_REQUEST
from dbridge.protocol.handlers import Dispatcher


@pytest.fixture(params=["sqlite", "duckdb"])
def connected(engine, request):
    sid = engine.connect(request.param, {"uri": ":memory:"})["session_id"]
    yield engine, sid, request.param
    engine.disconnect(sid)


@pytest.mark.parametrize("name", ["order items", "select", 'odd"name', "a.b", "it's a table"])
def test_structured_table_identifier_executes_literal_name(connected, name):
    engine, sid, adapter = connected
    quoted = quote_identifier(name)
    engine.execute(sid, f"CREATE TABLE {quoted} (id INTEGER)")
    engine.execute(sid, f"INSERT INTO {quoted} VALUES (42)")
    database = "main" if adapter == "sqlite" else "memory"
    table = {"name": name, "schema": "main", "database": database}
    d = Dispatcher(engine)
    response = d.handle({
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/getTableSchema",
        "params": {"session_id": sid, "fqn": "intentionally.wrong.name", "table": table},
    })
    schema = response["result"]
    prefix = '"main"' if adapter == "sqlite" else '"memory"."main"'
    assert schema["sql_identifier"] == f"{prefix}.{quoted}"
    assert schema["name"] == name
    assert [c["name"] for c in schema["columns"]] == ["id"]
    assert engine.execute(sid, f'SELECT * FROM {schema["sql_identifier"]}')['rows'] == [[42]]
    assert name in engine.list_tables(sid, database, "main")


def test_legacy_fqn_and_missing_table_identifier(connected):
    engine, sid, adapter = connected
    engine.execute(sid, "CREATE TABLE products (id INTEGER)")
    result = engine.get_table_schema(sid, "main.products")
    expected = '"main"."products"' if adapter == "sqlite" else '"memory"."main"."products"'
    assert result["sql_identifier"] == expected
    assert engine.get_table_schema(sid, "main.absent")["sql_identifier"] is None


def test_identity_defaults_resolve_current_scope(connected):
    engine, sid, adapter = connected
    engine.execute(sid, "CREATE TABLE products (id INTEGER)")
    schema = engine.get_table_schema(sid, "ignored", {"name": "products"})
    assert schema["schema"] == "main"
    assert schema["database"] == ("main" if adapter == "sqlite" else "memory")


@pytest.mark.parametrize("bad", [[], "products", {}, {"name": ""}, {"name": 1},
                                     {"name": "products", "schema": []},
                                     {"name": "products", "database": ""}])
def test_invalid_structured_identity_is_an_rpc_error(engine_session, bad):
    engine, sid = engine_session
    response = Dispatcher(engine).handle({
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/getTableSchema",
        "params": {"session_id": sid, "fqn": "products", "table": bad},
    })
    assert response["error"]["code"] == INVALID_REQUEST
    assert engine.execute(sid, "SELECT 1")["rows"] == [[1]]


def test_sqlite_attached_namespaces_preserve_literal_scope_and_cache(engine_session):
    engine, sid = engine_session
    namespace = 'other."db'
    engine.execute(sid, f"ATTACH ':memory:' AS {quote_identifier(namespace)}")
    for scope, column in [("main", "original"), (namespace, "attached")]:
        identifier = f'{quote_identifier(scope)}."products"'
        engine.execute(sid, f'CREATE TABLE {identifier} ({column} INTEGER)')
        engine.execute(sid, f'INSERT INTO {identifier} VALUES (1)')
        ref = {"name": "products", "schema": scope, "database": scope}
        schema = engine.get_table_schema(sid, "same.legacy.name", ref)
        assert [c["name"] for c in schema["columns"]] == [column]
        assert schema["sql_identifier"] == identifier
        for before in ("SELECT ", "SELECT p."):
            items = engine.complete(sid, before + f" FROM {identifier} p", len(before))
            assert [item["label"] for item in items] == [column]
        assert engine.execute(sid, f'SELECT * FROM {schema["sql_identifier"]}')["columns"] == [column]
        assert engine.list_schemas(sid, scope) == [scope]
        assert engine.list_tables(sid, scope, scope) == ["products"]
    assert namespace in engine.list_databases(sid)
    engine.execute(sid, "ATTACH ':memory:' AS attached")
    engine.execute(sid, "CREATE TABLE attached.products (attached_id INTEGER)")
    items = engine.complete(sid, "SELECT p. FROM attached.products p", position=len("SELECT p."))
    assert [item["label"] for item in items] == ["attached_id"]
    engine.execute(sid, f'ALTER TABLE {quote_identifier(namespace)}.products ADD COLUMN extra TEXT')
    assert len(engine.get_table_schema(sid, "same.legacy.name", ref)["columns"]) == 1
    engine.refresh_schema(sid)
    assert len(engine.get_table_schema(sid, "same.legacy.name", ref)["columns"]) == 2
    with pytest.raises(AdapterQueryError, match="same namespace"):
        engine.get_table_schema(sid, "ignored", {"name": "products", "database": "main", "schema": namespace})
    with pytest.raises(AdapterQueryError):
        engine.get_table_schema(sid, "unknown.products")
    with pytest.raises(AdapterQueryError):
        engine.list_tables(sid, "unknown", "unknown")


def test_duckdb_duplicate_tables_stay_in_selected_catalog_and_schema(engine):
    sid = engine.connect("duckdb", {"uri": ":memory:"})["session_id"]
    try:
        catalog, schema = 'other."db', 'order."schema'
        engine.execute(sid, f"ATTACH ':memory:' AS {quote_identifier(catalog)}")
        engine.execute(sid, f'CREATE SCHEMA "memory".{quote_identifier(schema)}')
        engine.execute(sid, f'CREATE SCHEMA {quote_identifier(catalog)}.{quote_identifier(schema)}')
        for database, namespace, column in [
            ("memory", "main", "default_col"),
            ("memory", schema, "schema_col"),
            (catalog, schema, "catalog_col"),
        ]:
            identifier = ".".join(quote_identifier(p) for p in (database, namespace, "products"))
            engine.execute(sid, f'CREATE TABLE {identifier} ({column} INTEGER)')
            engine.execute(sid, f'INSERT INTO {identifier} VALUES (3)')
            ref = {"name": "products", "database": database, "schema": namespace}
            result = engine.get_table_schema(sid, "same.legacy.name", ref)
            assert result["sql_identifier"] == identifier
            for before in ("SELECT ", "SELECT p."):
                items = engine.complete(sid, before + f" FROM {identifier} p", len(before))
                assert [item["label"] for item in items] == [column]
            assert [c["name"] for c in result["columns"]] == [column]
            assert engine.execute(sid, f'SELECT * FROM {result["sql_identifier"]}')["columns"] == [column]
        assert [c["name"] for c in engine.get_table_schema(sid, "products")["columns"]] == ["default_col"]
    finally:
        engine.disconnect(sid)


@pytest.mark.parametrize(("projection", "expected"), [
    ("SELECT |", ["intended_id", "intended_name"]),
    ("SELECT 1, intended_na|me", ["intended_name"]),
    ("SELECT p.|", ["intended_id", "intended_name"]),
    ("SELECT 1, p.intended_na|me", ["intended_name"]),
])
def test_completion_does_not_confuse_a_literal_dot_with_a_namespace(
    connected, projection, expected,
):
    engine, sid, adapter = connected
    engine.execute(sid, 'CREATE TABLE "sales.products" (intended_id INTEGER, intended_name TEXT)')
    if adapter == "sqlite":
        engine.execute(sid, "ATTACH ':memory:' AS sales")
    else:
        engine.execute(sid, "CREATE SCHEMA sales")
    engine.execute(sid, "CREATE TABLE sales.products (wrong_schema_only INTEGER)")
    metadata = engine.get_table_schema(sid, "unused", {
        "name": "sales.products", "schema": "main",
        "database": "main" if adapter == "sqlite" else "memory",
    })
    # Exercise both user-entered names and the server-generated SELECT source.
    for identifier in ['"sales.products"', metadata["sql_identifier"]]:
        before, after = projection.split("|")
        sql = before + after + f" FROM {identifier} p"
        items = engine.complete(sid, sql, position=len(before.encode("utf-8")))
        assert [item["label"] for item in items] == expected
        assert [item["insert_text"] for item in items] == expected
        assert {item["kind"] for item in items} == {"column"}
    # The genuinely qualified source still resolves its own metadata/cache key.
    items = engine.complete(sid, "SELECT p. FROM sales.products p", len("SELECT p."))
    assert [item["label"] for item in items] == ["wrong_schema_only"]
