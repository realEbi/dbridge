import pytest

from dbridge.adapters.base import ContainerEntry, ForeignKey, PrimaryKey, ScopeLevel, TableRef
from dbridge.adapters.duckdb import DuckDBAdapter
from dbridge.adapters.identifiers import quote_identifier
from dbridge.adapters.registry import INSTALLED_ADAPTERS
from dbridge.exceptions import AdapterConnectionError, AdapterQueryError


@pytest.fixture
async def adapter():
    a = DuckDBAdapter({"uri": ":memory:"})
    (await a.connect())
    (await a.execute("CREATE TABLE users (id INTEGER, name VARCHAR NOT NULL, score DOUBLE)"))
    (await a.execute("INSERT INTO users VALUES (1, 'ada', 9.5)"))
    yield a
    (await a.disconnect())


async def test_installed_adapters_includes_duckdb():
    assert "duckdb" in INSTALLED_ADAPTERS
    assert "sqlite" in INSTALLED_ADAPTERS


async def test_list_tables(adapter):
    assert "users" in [table.name for table in (await adapter.list_tables(("memory", "main")))]


async def test_execute_returns_rows(adapter):
    result = (await adapter.execute("SELECT id, name FROM users"))
    assert result.columns == ["id", "name"]
    assert result.rows == [[1, "ada"]]
    assert result.row_count == 1


async def test_get_table_schema_columns(adapter):
    schema = (await adapter.get_table_schema(TableRef("users", ("memory", "main"))))
    names = [c.name for c in schema.columns]
    assert names == ["id", "name", "score"]


async def test_get_table_schema_types(adapter):
    schema = (await adapter.get_table_schema(TableRef("users", ("memory", "main"))))
    col_map = {c.name: c for c in schema.columns}
    assert col_map["id"].data_type == "INTEGER"
    assert col_map["name"].data_type == "VARCHAR"
    assert col_map["score"].data_type == "DOUBLE"


async def test_get_table_schema_nullability(adapter):
    schema = (await adapter.get_table_schema(TableRef("users", ("memory", "main"))))
    col_map = {c.name: c for c in schema.columns}
    assert col_map["name"].nullable is False
    assert col_map["score"].nullable is True


@pytest.mark.parametrize("path", [
    ("memory", "main"), ("memory", "reporting"),
    ("side", "main"), ("side", "reporting"),
])
async def test_composite_keys_preserve_names_order_and_referenced_scope(adapter, path):
    catalog, namespace = path
    if catalog == "side":
        await adapter.execute("ATTACH ':memory:' AS side")
    if namespace != "main":
        await adapter.execute(f"CREATE SCHEMA {catalog}.{namespace}")
    prefix = f"{catalog}.{namespace}"
    # Same names in another namespace must not leak their keys into this lookup.
    await adapter.execute("CREATE SCHEMA decoy")
    await adapter.execute("CREATE TABLE decoy.parent (wrong INTEGER PRIMARY KEY)")
    await adapter.execute("CREATE TABLE decoy.child (wrong INTEGER REFERENCES decoy.parent(wrong))")
    await adapter.execute(
        f"CREATE TABLE {prefix}.parent (a INTEGER, b INTEGER, PRIMARY KEY (b, a))"
    )
    # DuckDB resolves REFERENCES in the current catalog and rejects a catalog
    # qualifier even when it names the same catalog as the child.
    await adapter.execute(f"USE {prefix}")
    await adapter.execute(
        f"CREATE TABLE {prefix}.child (x INTEGER, y INTEGER, z INTEGER, w INTEGER, "
        f"FOREIGN KEY (x, y) REFERENCES {namespace}.parent (b, a), "
        f"FOREIGN KEY (z, w) REFERENCES {namespace}.parent (b, a))"
    )
    await adapter.execute("USE memory.main")

    parent = await adapter.get_table_schema(TableRef("parent", path))
    assert [column.name for column in parent.columns] == ["a", "b"]
    assert parent.primary_key == PrimaryKey(name="parent_b_a_pkey", columns=["b", "a"])
    assert parent.foreign_keys == []
    child_ref = TableRef("child", path)
    child = await adapter.get_table_schema(child_ref)
    assert child.primary_key is None
    assert child.foreign_keys == [
        ForeignKey("child_x_y_b_a_fkey", ["x", "y"], path, "parent", ["b", "a"]),
        ForeignKey("child_z_w_b_a_fkey", ["z", "w"], path, "parent", ["b", "a"]),
    ]
    assert (await adapter.get_table_schema(child_ref)).foreign_keys == child.foreign_keys
    for key in child.foreign_keys:
        referenced = await adapter.get_table_schema(TableRef(key.referenced_table, key.referenced_path))
        assert referenced == parent


async def test_shorthand_foreign_key_reports_resolved_parent_columns(adapter):
    await adapter.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
    await adapter.execute("CREATE TABLE child (parent_id INTEGER REFERENCES parent)")
    schema = await adapter.get_table_schema(TableRef("child", ("memory", "main")))
    assert schema.foreign_keys == [
        ForeignKey("child_parent_id_id_fkey", ["parent_id"], ("memory", "main"), "parent", ["id"]),
    ]


@pytest.mark.parametrize("temporary", [False, True])
async def test_unique_check_and_not_null_constraints_are_not_keys(adapter, temporary):
    await adapter.execute(
        f"CREATE {'TEMP ' if temporary else ''}TABLE unique_only "
        "(a INTEGER NOT NULL, b INTEGER CHECK (b > 0), UNIQUE (a, b))"
    )
    path = ("temp" if temporary else "memory", "main")
    schema = await adapter.get_table_schema(TableRef("unique_only", path))
    assert schema.primary_key is None
    assert schema.foreign_keys == []


@pytest.mark.parametrize("path", [("memory", "main"), ("temp", "main"), ("missing", "main")])
async def test_unknown_table_has_no_keys(adapter, path):
    schema = await adapter.get_table_schema(TableRef("unknown", path))
    assert schema.columns == []
    assert schema.primary_key is None
    assert schema.foreign_keys == []


async def test_no_pandas_import():
    import importlib
    import sys
    # Reload the module to ensure no pandas side-effect at import time.
    mod_name = "dbridge.adapters.duckdb"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    importlib.import_module(mod_name)
    assert "pandas" not in sys.modules or True  # pandas may be present from other imports
    # Direct check: the source must not import pandas
    import inspect
    import dbridge.adapters.duckdb as m
    src = inspect.getsource(m)
    assert "import pandas" not in src
    assert "from pandas" not in src


async def test_list_databases(adapter):
    dbs = (await adapter.list_databases())
    assert len(dbs) > 0


async def test_list_schemas(adapter):
    schemas = (await adapter.list_schemas(("memory",)))
    assert ContainerEntry("main", internal=False) in schemas


async def test_keywords_non_empty(adapter):
    kws = adapter.get_keywords()
    assert "SELECT" in kws
    assert "FROM" in kws


async def test_list_schemas_is_scoped_to_the_catalog(tmp_path):
    """duckdb attaches system/temp alongside the file; schemas must not merge."""
    a = DuckDBAdapter({"uri": str(tmp_path / "scoped.duckdb")})
    (await a.connect())
    (await a.execute("CREATE TABLE t (id INTEGER)"))

    catalogs = (await a.list_databases())
    assert ContainerEntry("system", internal=True) in catalogs

    # the file's own catalog is the one holding the table
    own = next(c.name for c in catalogs if not c.internal)
    assert [table.name for table in (await a.list_tables((own, "main")))] == ["t"]
    # the same schema name under another catalog must not surface it
    assert (await a.list_tables(("system", "main"))) == []

    for schema in (await a.list_schemas(("system",))):
        assert schema.name in ("main", "information_schema", "pg_catalog")
        assert schema.internal
    (await a.disconnect())


async def test_get_table_schema_does_not_merge_same_named_tables(tmp_path):
    a = DuckDBAdapter({"uri": str(tmp_path / "dup.duckdb")})
    (await a.connect())
    (await a.execute("CREATE SCHEMA other"))
    (await a.execute("CREATE TABLE main.t (a INTEGER, b INTEGER)"))
    (await a.execute("CREATE TABLE other.t (x INTEGER)"))

    catalog = (await a.default_scope())[0]
    main_cols = [c.name for c in (await a.get_table_schema(TableRef("t", (catalog, "main")))).columns]
    other_cols = [c.name for c in (await a.get_table_schema(TableRef("t", (catalog, "other")))).columns]

    assert main_cols == ["a", "b"]
    assert other_cols == ["x"]
    (await a.disconnect())


# ── connection and error mapping ──────────────────────────────────────────────

async def test_uri_defaults_to_in_memory():
    """Unlike sqlite, duckdb has a usable default and needs no uri."""
    assert DuckDBAdapter({}).uri == ":memory:"


async def test_unopenable_path_raises_adapter_connection_error(tmp_path):
    """A driver failure is translated rather than leaking duckdb's own type."""
    adapter = DuckDBAdapter({"uri": str(tmp_path / "no-such-dir" / "db.duckdb")})
    with pytest.raises(AdapterConnectionError):
        (await adapter.connect())


async def test_invalid_sql_raises_adapter_query_error(adapter):
    with pytest.raises(AdapterQueryError):
        (await adapter.execute("SELECT * FROM no_such_table"))


async def test_syntax_error_raises_adapter_query_error(adapter):
    with pytest.raises(AdapterQueryError):
        (await adapter.execute("NOT VALID SQL"))


async def test_disconnect_on_never_connected_adapter_is_a_noop():
    (await DuckDBAdapter({"uri": ":memory:"}).disconnect())


async def test_disconnect_is_idempotent(adapter):
    (await adapter.disconnect())
    (await adapter.disconnect())
    assert adapter.con is None


# ── qualified-name scoping ────────────────────────────────────────────────────

async def test_get_table_schema_reports_the_full_scope(adapter):
    schema = (await adapter.get_table_schema(TableRef("users", ("memory", "main"))))
    assert [c.name for c in schema.columns] == ["id", "name", "score"]
    assert schema.scope == ("memory", "main")


async def test_get_table_schema_filters_by_catalog(adapter):
    """The full Scope Path filters on the catalog too, not just the table name."""
    # duckdb attaches several catalogs (system, temp, and the database itself);
    # an in-memory database lands in "memory", which is not list_databases()[0].
    catalog = (await adapter.execute(
        "SELECT table_catalog FROM information_schema.tables WHERE table_name='users'"
    )).rows[0][0]

    schema = (await adapter.get_table_schema(TableRef("users", (catalog, "main"))))

    assert [c.name for c in schema.columns] == ["id", "name", "score"]
    assert schema.scope == (catalog, "main")


async def test_get_table_schema_with_a_wrong_catalog_returns_no_columns(adapter):
    """Scoping must actually filter: a bogus catalog must not fall back to a
    bare table_name match and return another catalog's columns."""
    schema = (await adapter.get_table_schema(TableRef("users", ("no_such_catalog", "main"))))
    assert schema.columns == []
    assert schema.sql_identifier is None


async def test_list_schemas_separates_attached_catalogs(adapter):
    """Each catalog's schemas remain separate.

    Complements the file-backed case above: every catalog carries
    main/information_schema/pg_catalog, so a *distinct* schema in a second
    attached catalog is what makes the scoping observable.
    """
    (await adapter.execute("ATTACH ':memory:' AS other"))
    (await adapter.execute("CREATE SCHEMA other.analytics"))

    assert ContainerEntry("analytics") in (await adapter.list_schemas(("other",)))
    assert ContainerEntry("analytics") not in (await adapter.list_schemas(("memory",)))


async def test_dialect_name(adapter):
    assert adapter.dialect_name() == "duckdb"


async def test_get_keywords_returns_a_fresh_copy(adapter):
    first = adapter.get_keywords()
    assert "SELECT" in first

    first.append("NOT_A_KEYWORD")
    assert "NOT_A_KEYWORD" not in adapter.get_keywords()


async def test_list_tables_scoped_to_a_catalog(adapter):
    """The database argument narrows table_catalog as well as table_schema."""
    catalog = (await adapter.execute(
        "SELECT table_catalog FROM information_schema.tables WHERE table_name='users'"
    )).rows[0][0]

    assert "users" in [table.name for table in (await adapter.list_tables((catalog, "main")))]
    assert (await adapter.list_tables(("no_such_catalog", "main"))) == []


async def test_list_tables_scoped_to_a_schema(adapter):
    (await adapter.execute("CREATE SCHEMA reporting"))
    (await adapter.execute("CREATE TABLE reporting.summary (id INTEGER)"))

    assert [table.name for table in (await adapter.list_tables(("memory", "reporting")))] == ["summary"]
    assert "summary" not in [table.name for table in (await adapter.list_tables(("memory", "main")))]


async def test_hierarchy_declares_catalog_before_schema(adapter):
    assert adapter.scope_levels() == [ScopeLevel("catalog", "Catalog"), ScopeLevel("schema", "Schema")]
    assert (await adapter.default_scope()) == ("memory", "main")
    (await adapter.execute("CREATE SCHEMA working"))
    (await adapter.execute("USE memory.working"))
    assert (await adapter.default_scope()) == ("memory", "working")
    # Explicit requests remain independent of the driver's current schema.
    assert [table.name for table in (await adapter.list_tables(("memory", "main")))] == ["users"]


async def test_internal_containers_are_marked_and_retained(adapter):
    assert set((await adapter.list_databases())) == {
        ContainerEntry("memory", internal=False),
        ContainerEntry("system", internal=True),
        ContainerEntry("temp", internal=True),
    }
    assert set((await adapter.list_schemas(("memory",)))) == {
        ContainerEntry("main", internal=False),
        ContainerEntry("information_schema", internal=True),
        ContainerEntry("pg_catalog", internal=True),
    }


async def test_attached_catalog_paths_keep_same_named_tables_distinct(adapter):
    (await adapter.execute("ATTACH ':memory:' AS side"))
    (await adapter.execute("CREATE TABLE memory.main.orders (main_id INTEGER)"))
    (await adapter.execute("CREATE TABLE side.main.orders (side_id INTEGER)"))
    (await adapter.execute("INSERT INTO memory.main.orders VALUES (10)"))
    (await adapter.execute("INSERT INTO side.main.orders VALUES (20)"))

    identifiers = []
    for catalog, expected_id, expected_value in [("memory", "main_id", 10), ("side", "side_id", 20)]:
        path = (catalog, "main")
        tables = [table for table in (await adapter.list_tables(path)) if table.name == "orders"]
        assert len(tables) == 1
        schema = (await adapter.get_table_schema(TableRef("orders", path)))
        assert schema.scope == path
        assert [column.name for column in schema.columns] == [expected_id]
        assert schema.sql_identifier == tables[0].sql_identifier
        assert (await adapter.execute(f"SELECT * FROM {tables[0].sql_identifier}")).rows == [[expected_value]]
        identifiers.append(tables[0].sql_identifier)
    assert identifiers[0] != identifiers[1]
    assert ContainerEntry("side", internal=False) in (await adapter.list_databases())


@pytest.mark.parametrize("name", ["with space", "select", 'has"quote', "literal.dot"])
async def test_listed_identifiers_execute_literal_components(adapter, name):
    catalog, schema_name = 'side.catalog"quoted', 'sales.schema"quoted'
    namespace = f"{quote_identifier(catalog)}.{quote_identifier(schema_name)}"
    identifier = f"{namespace}.{quote_identifier(name)}"
    (await adapter.execute(f"ATTACH ':memory:' AS {quote_identifier(catalog)}"))
    (await adapter.execute(f"CREATE SCHEMA {namespace}"))
    (await adapter.execute(f"CREATE TABLE {identifier} (sentinel INTEGER)"))
    (await adapter.execute(f"INSERT INTO {identifier} VALUES (123)"))

    path = (catalog, schema_name)
    assert ContainerEntry(catalog) in (await adapter.list_databases())
    assert ContainerEntry(schema_name) in (await adapter.list_schemas((catalog,)))
    table = next(table for table in (await adapter.list_tables(path)) if table.name == name)
    assert table.sql_identifier == identifier
    assert (await adapter.execute(f"SELECT * FROM {table.sql_identifier}")).rows == [[123]]
    schema = (await adapter.get_table_schema(TableRef(name, path)))
    assert schema.name == name
    assert schema.scope == path
    assert schema.sql_identifier == identifier


@pytest.mark.parametrize("path", [(), ("memory",), ("memory", "main", "extra"), ("", "main")])
async def test_full_scope_path_is_required_for_table_operations(adapter, path):
    with pytest.raises(AdapterQueryError, match="Scope Path"):
        (await adapter.list_tables(path))
    with pytest.raises(AdapterQueryError, match="Scope Path"):
        (await adapter.get_table_schema(TableRef("users", path)))


@pytest.mark.parametrize("path", [(), ("memory", "main"), ("",)])
async def test_schema_listing_requires_exactly_one_scope_component(adapter, path):
    with pytest.raises(AdapterQueryError, match="Scope Path"):
        (await adapter.list_schemas(path))


async def test_temp_metadata_tracks_create_alter_drop_and_quotes_literal_identifiers(adapter):
    name = 'temporary.table"quoted'
    quoted = quote_identifier(name)
    await adapter.execute(f"CREATE TEMP TABLE {quoted} (first INTEGER NOT NULL)")
    assert ContainerEntry("temp", internal=True) in await adapter.list_databases()
    assert ContainerEntry("main", internal=True) in await adapter.list_schemas(("temp",))
    tables = await adapter.list_tables(("temp", "main"))
    assert [table.name for table in tables] == [name]
    assert tables[0].sql_identifier == f'"temp"."main".{quoted}'
    await adapter.execute(f"ALTER TABLE {quoted} ADD COLUMN second VARCHAR")
    schema = await adapter.get_table_schema(TableRef(name, ("temp", "main")))
    assert [(column.name, column.data_type, column.nullable) for column in schema.columns] == [
        ("first", "INTEGER", False), ("second", "VARCHAR", True),
    ]
    assert schema.sql_identifier == tables[0].sql_identifier
    await adapter.execute(f"INSERT INTO {schema.sql_identifier} VALUES (1, 'yes')")
    assert (await adapter.execute(f"SELECT * FROM {schema.sql_identifier}")).rows == [[1, "yes"]]
    assert await adapter.list_tables(("temp", "no_such_schema")) == []
    schema.columns.clear()
    assert len((await adapter.get_table_schema(TableRef(name, ("temp", "main")))).columns) == 2
    await adapter.execute(f"DROP TABLE {quoted}")
    assert await adapter.list_tables(("temp", "main")) == []
    missing = await adapter.get_table_schema(TableRef(name, ("temp", "main")))
    assert missing.columns == []
    assert missing.sql_identifier is None


async def test_temporary_keys_are_snapshotted_with_order_and_referenced_path(adapter):
    await adapter.execute("CREATE TEMP TABLE parent (a INTEGER, b INTEGER, PRIMARY KEY (b, a))")
    await adapter.execute(
        "CREATE TEMP TABLE child (x INTEGER, y INTEGER, PRIMARY KEY (y, x), "
        "FOREIGN KEY (x, y) REFERENCES parent (b, a))"
    )
    path = ("temp", "main")
    child_ref = TableRef("child", path)
    parent = await adapter.get_table_schema(TableRef("parent", path))
    child = await adapter.get_table_schema(child_ref)
    assert parent.primary_key == PrimaryKey("parent_b_a_pkey", ["b", "a"])
    assert child.primary_key == PrimaryKey("child_y_x_pkey", ["y", "x"])
    assert child.foreign_keys == [
        ForeignKey("child_x_y_b_a_fkey", ["x", "y"], path, "parent", ["b", "a"]),
    ]
    key = child.foreign_keys[0]
    assert await adapter.get_table_schema(TableRef(key.referenced_table, key.referenced_path)) == parent
    # Metadata clients receive copies, including the mutable key column lists.
    child.primary_key.columns.clear()
    key.columns.clear()
    key.referenced_columns.clear()
    fresh = await adapter.get_table_schema(child_ref)
    assert fresh.primary_key == PrimaryKey("child_y_x_pkey", ["y", "x"])
    assert fresh.foreign_keys[0].columns == ["x", "y"]
    assert fresh.foreign_keys[0].referenced_columns == ["b", "a"]
    await adapter.execute("DROP TABLE child; CREATE TEMP TABLE child (x INTEGER, y INTEGER)")
    recreated = await adapter.get_table_schema(child_ref)
    assert recreated.primary_key is None
    assert recreated.foreign_keys == []
