"""Engine methods driven directly.

These paths are exercised end-to-end through a spawned server, so they are
proven but unmeasured. Calling them in process also lets each assertion target
one method rather than a whole protocol exchange.
"""
import asyncio
from unittest.mock import AsyncMock

import pytest

from dbridge.core.schema_registry import SchemaRegistry
from dbridge.core.session import SessionNotFoundError
from dbridge.exceptions import InvalidRequestError


async def test_connect_returns_a_session_id(engine):
    result = await engine.connect("sqlite", {"uri": ":memory:"})
    assert isinstance(result["session_id"], str) and result["session_id"]


async def test_connect_without_adapter_or_profile_is_invalid(engine):
    with pytest.raises(InvalidRequestError):
        await engine.connect()


def test_connect_registers_a_schema_registry(engine_session):
    engine, session_id = engine_session
    assert isinstance(engine._registries[session_id], SchemaRegistry)


async def test_disconnect_removes_session_and_registry(engine_session):
    engine, session_id = engine_session

    assert await engine.disconnect(session_id) == {"ok": True}

    assert session_id not in engine._registries
    with pytest.raises(SessionNotFoundError):
        engine.sessions.get(session_id)


async def test_disconnect_is_idempotent(engine_session):
    """A client that retries a disconnect does not get an error."""
    engine, session_id = engine_session
    assert await engine.disconnect(session_id) == {"ok": True}
    assert await engine.disconnect(session_id) == {"ok": True}


async def test_list_databases(engine_session):
    engine, session_id = engine_session
    assert await engine.list_databases(session_id) == [{"name": "main", "internal": False}]


async def test_list_schemas(engine_session):
    engine, session_id = engine_session
    assert await engine.list_schemas(session_id, ("main",)) == []


async def test_list_schemas_with_explicit_database(engine_session):
    engine, session_id = engine_session
    assert await engine.list_schemas(session_id, ("main",)) == []


async def test_list_tables_reflects_created_tables(engine_session):
    engine, session_id = engine_session
    await engine.execute(session_id, "CREATE TABLE users (id INTEGER)")
    assert await engine.list_tables(session_id, ("main",)) == [{"name": "users", "sql_identifier": '"main"."users"'}]


async def test_get_table_schema_returns_columns(engine_session):
    engine, session_id = engine_session
    await engine.execute(session_id, "CREATE TABLE users (id INTEGER, name TEXT)")

    schema = await engine.get_table_schema(session_id, ("main",), "users")

    assert schema["name"] == "users"
    assert [c["name"] for c in schema["columns"]] == ["id", "name"]


async def test_get_table_schema_serializes_key_constraints(engine_session):
    engine, session_id = engine_session
    await engine.execute(session_id, "CREATE TABLE parent (a INTEGER, b INTEGER, PRIMARY KEY (b, a))")
    await engine.execute(session_id, (
        "CREATE TABLE child (x INTEGER, y INTEGER, PRIMARY KEY (y, x), "
        "FOREIGN KEY (y, x) REFERENCES parent (b, a))"
    ))

    schema = await engine.get_table_schema(session_id, ("main",), "child")

    assert schema["scope"] == ["main"]
    assert schema["primary_key"] == {"name": None, "columns": ["y", "x"]}
    assert schema["foreign_keys"] == [{
        "name": None, "columns": ["y", "x"], "referenced_path": ["main"],
        "referenced_table": "parent", "referenced_columns": ["b", "a"],
    }]
    assert "primary_keys" not in schema


async def test_get_erd_reports_not_implemented_with_tables(engine_session):
    engine, session_id = engine_session
    await engine.execute(session_id, "CREATE TABLE t (id INTEGER)")

    erd = await engine.get_erd(session_id, ("main",))

    assert erd["status"] == "not_implemented"
    assert "t" in [entry["name"] for entry in erd["tables"]]


async def test_refresh_schema_clears_the_cache(engine_session):
    engine, session_id = engine_session
    await engine.execute(session_id, "CREATE TABLE before (id INTEGER)")
    await engine.list_tables(session_id, ("main",))

    await engine.execute(session_id, "CREATE TABLE after (id INTEGER)")
    assert (await engine.refresh_schema(session_id))["default_path"] == ["main"]

    assert "after" in [t["name"] for t in await engine.list_tables(session_id, ("main",))]


async def test_complete_returns_tables_in_a_from_position(engine_session):
    engine, session_id = engine_session
    await engine.execute(session_id, "CREATE TABLE users (id INTEGER)")

    items = await engine.complete(session_id, "SELECT * FROM ", path=await engine.sessions.get(session_id).adapter.default_scope())

    assert {i["kind"] for i in items} == {"table"}
    assert "users" in [i["label"] for i in items]


async def test_complete_returns_columns_at_a_cursor_position(engine_session):
    engine, session_id = engine_session
    await engine.execute(session_id, "CREATE TABLE users (id INTEGER, name TEXT)")

    items = await engine.complete(session_id, "SELECT  FROM users", path=await engine.sessions.get(session_id).adapter.default_scope(), position=7)

    assert {i["kind"] for i in items} == {"column"}
    assert [i["label"] for i in items] == ["id", "name"]


@pytest.mark.parametrize("adapter", ["sqlite", "duckdb"])
@pytest.mark.parametrize("marked_sql, table, columns", [
    (
        "SELECT p.|name, p.category FROM products p LIMIT 100",
        "products", ["id", "name", "category"],
    ),
    (
        "SELECT p.name, p.|category FROM products p LIMIT 100",
        "products", ["id", "name", "category"],
    ),
    (
        "SELECT p.name, p.ca|tegory FROM products p LIMIT 100",
        "products", ["category"],
    ),
    (
        "SELECT p.|name FROM products p JOIN orders o ON p.id = o.product_id",
        "products", ["id", "name", "category"],
    ),
    (
        "SELECT p.name FROM products p JOIN orders o ON p.id = o.|product_id",
        "orders", ["id", "product_id", "order_reference"],
    ),
    (
        "SELECT 'café', p.|name FROM products p",
        "products", ["id", "name", "category"],
    ),
], ids=["first-column", "after-comma", "prefix", "join-product", "join-order", "utf8"])
async def test_complete_resolves_alias_columns_with_real_adapter(
    engine, adapter, marked_sql, table, columns,
):
    session_id = (await engine.connect(adapter, {"uri": ":memory:"}))["session_id"]
    try:
        await engine.execute(
            session_id, "CREATE TABLE products (id INTEGER, name TEXT, category TEXT)"
        )
        await engine.execute(
            session_id,
            "CREATE TABLE orders (id INTEGER, product_id INTEGER, order_reference TEXT)",
        )
        before, _, after = marked_sql.partition("|")

        items = await engine.complete(
            session_id, before + after, path=await engine.sessions.get(session_id).adapter.default_scope(), position=len(before.encode("utf-8"))
        )

        assert [item["label"] for item in items] == columns
        assert {item["kind"] for item in items} == {"column"}
        assert [item["insert_text"] for item in items] == columns
        assert [item["detail"] for item in items] == [
            f"{table}.{column}" for column in columns
        ]
    finally:
        await engine.disconnect(session_id)


async def test_complete_duckdb_alias_uses_the_source_schema(engine):
    session_id = (await engine.connect("duckdb", {"uri": ":memory:"}))["session_id"]
    try:
        await engine.execute(session_id, "CREATE SCHEMA retail")
        await engine.execute(session_id, "CREATE SCHEMA warehouse")
        await engine.execute(
            session_id, "CREATE TABLE retail.products (id INTEGER, name TEXT, category TEXT)"
        )
        await engine.execute(
            session_id,
            "CREATE TABLE warehouse.products (id INTEGER, stock_quantity INTEGER, bin_code TEXT)",
        )

        for schema, columns in [
            ("retail", ["id", "name", "category"]),
            ("warehouse", ["id", "stock_quantity", "bin_code"]),
        ]:
            items = await engine.complete(
                session_id, f"SELECT p. FROM {schema}.products p", path=await engine.sessions.get(session_id).adapter.default_scope(),
                position=len("SELECT p.".encode("utf-8")),
            )

            assert [item["label"] for item in items] == columns, schema
            assert [item["insert_text"] for item in items] == columns, schema
            assert {item["kind"] for item in items} == {"column"}, schema
    finally:
        await engine.disconnect(session_id)


async def test_complete_falls_back_to_keywords(engine_session):
    engine, session_id = engine_session
    items = await engine.complete(session_id, "", path=await engine.sessions.get(session_id).adapter.default_scope())
    assert {i["kind"] for i in items} == {"keyword"}


@pytest.mark.parametrize("call", [
    lambda e, s: e.execute(s, "SELECT 1"),
    lambda e, s: e.list_databases(s),
    lambda e, s: e.list_schemas(s, ("main",)),
    lambda e, s: e.list_tables(s, ("main",)),
    lambda e, s: e.get_table_schema(s, ("main",), "t"),
    lambda e, s: e.get_erd(s, ("main",)),
    lambda e, s: e.refresh_schema(s),
    lambda e, s: e.complete(s, "SELECT", path=("main",)),
])
async def test_unknown_session_raises_before_touching_the_cache(engine, call):
    """Every session-scoped method must reject an unknown id, not KeyError."""
    with pytest.raises(SessionNotFoundError):
        await call(engine, "no-such-session")


def test_profile_roundtrip_through_the_engine(engine, isolated_profiles):
    assert engine.list_profiles() == {}

    assert engine.save_profile("mem", "sqlite", {"uri": ":memory:"}) == {"ok": True}
    assert engine.list_profiles() == {"mem": {"adapter": "sqlite", "config": {"uri": ":memory:"}}}

    assert engine.delete_profile("mem") == {"ok": True}
    assert engine.delete_profile("mem") == {"ok": False}


async def test_connect_by_profile_name(engine, isolated_profiles):
    engine.save_profile("mem", "sqlite", {"uri": ":memory:"})
    session_id = (await engine.connect(profile="mem"))["session_id"]
    assert await engine.list_databases(session_id) == [{"name": "main", "internal": False}]


@pytest.mark.parametrize("adapter", ["sqlite", "duckdb"])
@pytest.mark.parametrize("name,previous_name", [("new", "old"), ("old", None)])
async def test_profile_edit_preserves_live_session(
    engine, isolated_profiles, tmp_path, adapter, name, previous_name,
):
    engine.save_profile("old", adapter, {"uri": ":memory:"})
    session_id = (await engine.connect(profile="old"))["session_id"]
    await engine.execute(session_id, "CREATE TABLE marker AS SELECT 42 AS value")
    new_config = {"uri": str(tmp_path / "next.db")}

    assert engine.save_profile(name, adapter, new_config, previous_name) == {"ok": True}

    assert engine.list_profiles() == {name: {"adapter": adapter, "config": new_config}}
    assert engine.sessions.ids() == (session_id,)
    assert (await engine.execute(session_id, "SELECT value FROM marker"))["rows"] == [[42]]
    assert not (tmp_path / "next.db").exists()


@pytest.mark.parametrize("adapter", ["sqlite", "duckdb"])
@pytest.mark.parametrize("marked_sql, table, columns", [
    ("SELECT id, | FROM products", "products", ["id", "name", "category"]),
    ("SELECT id, ca|tegory FROM products", "products", ["category"]),
    ("SELECT 'café ☕',\n COALESCE(na|me, '') FROM products", "products", ["name"]),
    (
        "SELECT (SELECT | FROM orders) FROM products", "orders",
        ["id", "product_id", "order_reference"],
    ),
    (
        "SELECT id FROM products; SELECT | FROM orders", "orders",
        ["id", "product_id", "order_reference"],
    ),
])
async def test_complete_unqualified_select_with_real_adapter(
    engine, adapter, marked_sql, table, columns,
):
    session_id = (await engine.connect(adapter, {"uri": ":memory:"}))["session_id"]
    try:
        await engine.execute(
            session_id, "CREATE TABLE products (id INTEGER, name TEXT, category TEXT)"
        )
        await engine.execute(
            session_id,
            "CREATE TABLE orders (id INTEGER, product_id INTEGER, order_reference TEXT)",
        )
        before, after = marked_sql.split("|")
        items = await engine.complete(
            session_id, before + after, path=await engine.sessions.get(session_id).adapter.default_scope(), position=len(before.encode("utf-8"))
        )
        assert [item["label"] for item in items] == columns
        assert [item["insert_text"] for item in items] == columns
        assert {item["kind"] for item in items} == {"column"}
        assert [item["detail"] for item in items] == [f"{table}.{c}" for c in columns]
    finally:
        await engine.disconnect(session_id)


@pytest.mark.parametrize("adapter", ["sqlite", "duckdb"])
async def test_bare_select_returns_session_dialect_keywords(engine, adapter):
    session_id = (await engine.connect(adapter, {"uri": ":memory:"}))["session_id"]
    try:
        items = await engine.complete(session_id, "SELECT ", path=await engine.sessions.get(session_id).adapter.default_scope())
        assert items == await engine.complete(session_id, "", path=await engine.sessions.get(session_id).adapter.default_scope())
        assert {item["kind"] for item in items} == {"keyword"}
        assert "FROM" in [item["label"] for item in items]
    finally:
        await engine.disconnect(session_id)


@pytest.mark.parametrize("adapter,levels,path", [
    ("sqlite", [{"name": "namespace", "label": "Namespace"}], ["main"]),
    ("duckdb", [{"name": "catalog", "label": "Catalog"}, {"name": "schema", "label": "Schema"}],
     ["memory", "main"]),
])
@pytest.mark.parametrize("profile", [False, True])
async def test_connect_and_refresh_report_hierarchy_and_dialect(
    engine, isolated_profiles, adapter, levels, path, profile,
):
    if profile:
        engine.save_profile("sample", adapter, {"uri": ":memory:"})
        connected = await engine.connect(profile="sample")
    else:
        connected = await engine.connect(adapter, {"uri": ":memory:"})
    sid = connected["session_id"]
    try:
        assert connected == {"session_id": sid, "levels": levels, "default_path": path, "dialect": adapter}
        await engine.execute(sid, "ATTACH ':memory:' AS side")
        assert await engine.refresh_schema(sid) == {"ok": True, "levels": levels, "default_path": path}
        assert {"name": "side", "internal": False} in await engine.list_databases(sid)
        assert engine.sessions.get(sid).adapter.dialect_name() == adapter
    finally:
        await engine.disconnect(sid)


async def test_completion_and_metadata_use_each_requests_catalog(engine):
    sid = (await engine.connect("duckdb", {"uri": ":memory:"}))["session_id"]
    try:
        await engine.execute(sid, "ATTACH ':memory:' AS side")
        for catalog, marker in (("memory", 1), ("side", 2)):
            await engine.execute(sid, f'CREATE SCHEMA {catalog}.sales')
            await engine.execute(sid, f'CREATE TABLE {catalog}.sales.products ({catalog}_id INTEGER)')
            await engine.execute(sid, f'CREATE TABLE {catalog}.main.shipments AS SELECT {marker} AS marker')
        for catalog, marker in (("memory", 1), ("side", 2), ("memory", 1)):
            path = (catalog, "main")
            items = await engine.complete(sid, "SELECT * FROM ", path)
            assert [item["label"] for item in items] == ["shipments"]
            assert (await engine.execute(sid, 'SELECT * FROM ' + items[0]["insert_text"]))["rows"] == [[marker]]
            columns = await engine.complete(sid, "SELECT p. FROM sales.products p", path, len("SELECT p."))
            assert [item["label"] for item in columns] == [catalog + "_id"]
        assert await engine.sessions.get(sid).adapter.default_scope() == ("memory", "main")
    finally:
        await engine.disconnect(sid)


async def test_failed_hierarchy_discovery_closes_unreported_session(engine, monkeypatch):
    from dbridge.adapters.sqlite import SqliteAdapter
    from dbridge.exceptions import AdapterQueryError

    adapters = []

    async def fail_discovery(adapter):
        adapters.append(adapter)
        raise AdapterQueryError("cannot discover default scope")

    monkeypatch.setattr(SqliteAdapter, "default_scope", fail_discovery)
    with pytest.raises(AdapterQueryError, match="cannot discover default scope"):
        await engine.connect("sqlite", {"uri": ":memory:"})
    assert adapters[0].con is None
    assert engine.sessions._sessions == {}
    assert engine._registries == {}


async def test_cancelled_hierarchy_discovery_closes_unreported_session(engine, monkeypatch):
    from dbridge.adapters.sqlite import SqliteAdapter

    started = asyncio.Event()
    adapters = []

    async def blocked_discovery(adapter):
        adapters.append(adapter)
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(SqliteAdapter, "default_scope", blocked_discovery)
    task = asyncio.create_task(engine.connect("sqlite", {"uri": ":memory:"}))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert adapters[0].con is None
    assert engine.sessions.ids() == ()
    assert engine._registries == {}


async def test_close_all_attempts_every_session_when_one_disconnect_fails(engine, monkeypatch):
    first = await engine.connect("sqlite", {"uri": ":memory:"})
    second = await engine.connect("sqlite", {"uri": ":memory:"})
    failing = engine.sessions.get(first["session_id"]).adapter
    other = engine.sessions.get(second["session_id"]).adapter
    real_disconnect = failing.disconnect

    async def close_then_fail():
        await real_disconnect()
        raise RuntimeError("failed after close")

    disconnect = AsyncMock(side_effect=close_then_fail)
    monkeypatch.setattr(failing, "disconnect", disconnect)
    await engine.close_all()
    disconnect.assert_awaited_once()
    assert failing.con is None
    assert other.con is None
    assert engine.sessions.ids() == ()
    assert engine._registries == {}
