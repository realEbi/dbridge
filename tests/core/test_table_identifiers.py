"""Real Adapter Scope Paths and executable identifiers for generated queries."""
import pytest

from dbridge.adapters.identifiers import quote_identifier
from dbridge.exceptions import AdapterQueryError
from dbridge.protocol.handlers import Dispatcher


@pytest.fixture(params=["sqlite", "duckdb"])
async def connected(engine, request):
    result = await engine.connect(request.param, {"uri": ":memory:"})
    sid = result["session_id"]
    yield engine, sid, request.param, tuple(result["default_path"])
    await engine.disconnect(sid)


@pytest.mark.parametrize("name", ["order items", "select", 'odd"name', "a.b", "it's a table"])
async def test_structured_table_identifier_executes_literal_name(connected, name):
    engine, sid, adapter, path = connected
    quoted = quote_identifier(name)
    await engine.execute(sid, f"CREATE TABLE {quoted} (id INTEGER)")
    await engine.execute(sid, f"INSERT INTO {quoted} VALUES (42)")
    d = Dispatcher(engine)
    response = await d.handle({
        "jsonrpc": "2.0", "id": 1, "method": "dbridge/getTableSchema",
        "params": {"session_id": sid, "path": list(path), "name": name},
    })
    schema = response["result"]
    prefix = '"main"' if adapter == "sqlite" else '"memory"."main"'
    assert schema["sql_identifier"] == f"{prefix}.{quoted}"
    assert schema["name"] == name
    assert schema["scope"] == list(path)
    assert [c["name"] for c in schema["columns"]] == ["id"]
    assert (await engine.execute(sid, f'SELECT * FROM {schema["sql_identifier"]}'))['rows'] == [[42]]
    assert {"name": name, "sql_identifier": schema["sql_identifier"]} in await engine.list_tables(sid, path)


async def test_missing_table_identifier_does_not_resolve_another_scope(connected):
    engine, sid, adapter, path = connected
    await engine.execute(sid, "CREATE TABLE products (id INTEGER)")
    result = await engine.get_table_schema(sid, path, "products")
    expected = '"main"."products"' if adapter == "sqlite" else '"memory"."main"."products"'
    assert result["sql_identifier"] == expected
    assert (await engine.get_table_schema(sid, path, "absent"))["sql_identifier"] is None
    await engine.execute(sid, "ATTACH ':memory:' AS empty")
    empty_path = ("empty",) if adapter == "sqlite" else ("empty", "main")
    missing = await engine.get_table_schema(sid, empty_path, "products")
    assert missing["scope"] == list(empty_path)
    assert missing["columns"] == []
    assert missing["sql_identifier"] is None


async def test_sqlite_attached_namespaces_preserve_literal_scope_and_cache(engine_session):
    engine, sid = engine_session
    namespace = 'other."db'
    await engine.execute(sid, f"ATTACH ':memory:' AS {quote_identifier(namespace)}")
    for scope, column in [("main", "original"), (namespace, "attached")]:
        identifier = f'{quote_identifier(scope)}."products"'
        await engine.execute(sid, f'CREATE TABLE {identifier} ({column} INTEGER)')
        await engine.execute(sid, f'INSERT INTO {identifier} VALUES (1)')
        path = (scope,)
        schema = await engine.get_table_schema(sid, path, "products")
        assert schema["scope"] == [scope]
        assert [c["name"] for c in schema["columns"]] == [column]
        assert schema["sql_identifier"] == identifier
        for before in ("SELECT ", "SELECT p."):
            items = await engine.complete(sid, before + f" FROM {identifier} p", ("main",), len(before))
            assert [item["label"] for item in items] == [column]
        assert (await engine.execute(sid, f'SELECT * FROM {schema["sql_identifier"]}'))["columns"] == [column]
        assert await engine.list_schemas(sid, path) == []
        assert await engine.list_tables(sid, path) == [{"name": "products", "sql_identifier": identifier}]
    for scope, column in [("main", "original"), (namespace, "attached")]:
        assert [
            c["name"] for c in (await engine.get_table_schema(sid, (scope,), "products"))["columns"]
        ] == [column]
    assert {"name": namespace, "internal": False} in await engine.list_databases(sid)
    await engine.execute(sid, "ATTACH ':memory:' AS attached")
    await engine.execute(sid, "CREATE TABLE attached.products (attached_id INTEGER)")
    items = await engine.complete(
        sid, "SELECT p. FROM attached.products p", ("main",), position=len("SELECT p."),
    )
    assert [item["label"] for item in items] == ["attached_id"]
    await engine.execute(sid, f'ALTER TABLE {quote_identifier(namespace)}.products ADD COLUMN extra TEXT')
    assert len((await engine.get_table_schema(sid, (namespace,), "products"))["columns"]) == 1
    await engine.refresh_schema(sid)
    assert len((await engine.get_table_schema(sid, (namespace,), "products"))["columns"]) == 2
    with pytest.raises(AdapterQueryError):
        await engine.get_table_schema(sid, ("unknown",), "products")
    with pytest.raises(AdapterQueryError):
        await engine.list_tables(sid, ("unknown",))


async def test_duckdb_duplicate_tables_stay_in_selected_catalog_and_schema(engine):
    sid = (await engine.connect("duckdb", {"uri": ":memory:"}))["session_id"]
    try:
        catalog, schema = 'other."db', 'order."schema'
        await engine.execute(sid, f"ATTACH ':memory:' AS {quote_identifier(catalog)}")
        await engine.execute(sid, f'CREATE SCHEMA "memory".{quote_identifier(schema)}')
        await engine.execute(sid, f'CREATE SCHEMA {quote_identifier(catalog)}.{quote_identifier(schema)}')
        for database, namespace, column in [
            ("memory", "main", "default_col"),
            ("memory", schema, "schema_col"),
            (catalog, schema, "catalog_col"),
        ]:
            identifier = ".".join(quote_identifier(p) for p in (database, namespace, "products"))
            await engine.execute(sid, f'CREATE TABLE {identifier} ({column} INTEGER)')
            await engine.execute(sid, f'INSERT INTO {identifier} VALUES (3)')
            path = (database, namespace)
            result = await engine.get_table_schema(sid, path, "products")
            assert result["scope"] == list(path)
            assert result["sql_identifier"] == identifier
            for before in ("SELECT ", "SELECT p."):
                items = await engine.complete(
                    sid, before + f" FROM {identifier} p", ("memory", "main"), len(before),
                )
                assert [item["label"] for item in items] == [column]
            assert [c["name"] for c in result["columns"]] == [column]
            assert (await engine.execute(sid, f'SELECT * FROM {result["sql_identifier"]}'))["columns"] == [column]
            assert await engine.list_tables(sid, path) == [{"name": "products", "sql_identifier": identifier}]
        for path, column in [
            (("memory", "main"), "default_col"),
            (("memory", schema), "schema_col"),
            ((catalog, schema), "catalog_col"),
        ]:
            assert [
                c["name"] for c in (await engine.get_table_schema(sid, path, "products"))["columns"]
            ] == [column]
    finally:
        await engine.disconnect(sid)


@pytest.mark.parametrize(("projection", "expected"), [
    ("SELECT |", ["intended_id", "intended_name"]),
    ("SELECT 1, intended_na|me", ["intended_name"]),
    ("SELECT p.|", ["intended_id", "intended_name"]),
    ("SELECT 1, p.intended_na|me", ["intended_name"]),
])
async def test_completion_does_not_confuse_a_literal_dot_with_a_namespace(
    connected, projection, expected,
):
    engine, sid, adapter, path = connected
    await engine.execute(sid, 'CREATE TABLE "sales.products" (intended_id INTEGER, intended_name TEXT)')
    if adapter == "sqlite":
        await engine.execute(sid, "ATTACH ':memory:' AS sales")
    else:
        await engine.execute(sid, "CREATE SCHEMA sales")
    await engine.execute(sid, "CREATE TABLE sales.products (wrong_schema_only INTEGER)")
    metadata = await engine.get_table_schema(sid, path, "sales.products")
    # Exercise both user-entered names and the server-generated SELECT source.
    for identifier in ['"sales.products"', metadata["sql_identifier"]]:
        before, after = projection.split("|")
        sql = before + after + f" FROM {identifier} p"
        items = await engine.complete(sid, sql, path, position=len(before.encode("utf-8")))
        assert [item["label"] for item in items] == expected
        assert [item["insert_text"] for item in items] == expected
        assert {item["kind"] for item in items} == {"column"}
    # The genuinely qualified source still resolves its own metadata/cache key.
    items = await engine.complete(sid, "SELECT p. FROM sales.products p", path, len("SELECT p."))
    assert [item["label"] for item in items] == ["wrong_schema_only"]
