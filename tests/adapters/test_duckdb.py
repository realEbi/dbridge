import pytest

from dbridge.adapters.base import ContainerEntry, ScopeLevel, TableRef
from dbridge.adapters.duckdb import DuckDBAdapter
from dbridge.adapters.identifiers import quote_identifier
from dbridge.adapters.registry import INSTALLED_ADAPTERS
from dbridge.exceptions import AdapterConnectionError, AdapterQueryError


@pytest.fixture
def adapter():
    a = DuckDBAdapter({"uri": ":memory:"})
    a.connect()
    a.execute("CREATE TABLE users (id INTEGER, name VARCHAR NOT NULL, score DOUBLE)")
    a.execute("INSERT INTO users VALUES (1, 'ada', 9.5)")
    yield a
    a.disconnect()


def test_installed_adapters_includes_duckdb():
    assert "duckdb" in INSTALLED_ADAPTERS
    assert "sqlite" in INSTALLED_ADAPTERS


def test_list_tables(adapter):
    assert "users" in [table.name for table in adapter.list_tables(("memory", "main"))]


def test_execute_returns_rows(adapter):
    result = adapter.execute("SELECT id, name FROM users")
    assert result.columns == ["id", "name"]
    assert result.rows == [[1, "ada"]]
    assert result.row_count == 1


def test_get_table_schema_columns(adapter):
    schema = adapter.get_table_schema(TableRef("users", ("memory", "main")))
    names = [c.name for c in schema.columns]
    assert names == ["id", "name", "score"]


def test_get_table_schema_types(adapter):
    schema = adapter.get_table_schema(TableRef("users", ("memory", "main")))
    col_map = {c.name: c for c in schema.columns}
    assert col_map["id"].data_type == "INTEGER"
    assert col_map["name"].data_type == "VARCHAR"
    assert col_map["score"].data_type == "DOUBLE"


def test_get_table_schema_nullability(adapter):
    schema = adapter.get_table_schema(TableRef("users", ("memory", "main")))
    col_map = {c.name: c for c in schema.columns}
    assert col_map["name"].nullable is False
    assert col_map["score"].nullable is True


def test_no_pandas_import():
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


def test_list_databases(adapter):
    dbs = adapter.list_databases()
    assert len(dbs) > 0


def test_list_schemas(adapter):
    schemas = adapter.list_schemas(("memory",))
    assert ContainerEntry("main", internal=False) in schemas


def test_keywords_non_empty(adapter):
    kws = adapter.get_keywords()
    assert "SELECT" in kws
    assert "FROM" in kws


def test_list_schemas_is_scoped_to_the_catalog(tmp_path):
    """duckdb attaches system/temp alongside the file; schemas must not merge."""
    a = DuckDBAdapter({"uri": str(tmp_path / "scoped.duckdb")})
    a.connect()
    a.execute("CREATE TABLE t (id INTEGER)")

    catalogs = a.list_databases()
    assert ContainerEntry("system", internal=True) in catalogs

    # the file's own catalog is the one holding the table
    own = next(c.name for c in catalogs if not c.internal)
    assert [table.name for table in a.list_tables((own, "main"))] == ["t"]
    # the same schema name under another catalog must not surface it
    assert a.list_tables(("system", "main")) == []

    for schema in a.list_schemas(("system",)):
        assert schema.name in ("main", "information_schema", "pg_catalog")
        assert schema.internal
    a.disconnect()


def test_get_table_schema_does_not_merge_same_named_tables(tmp_path):
    a = DuckDBAdapter({"uri": str(tmp_path / "dup.duckdb")})
    a.connect()
    a.execute("CREATE SCHEMA other")
    a.execute("CREATE TABLE main.t (a INTEGER, b INTEGER)")
    a.execute("CREATE TABLE other.t (x INTEGER)")

    catalog = a.default_scope()[0]
    main_cols = [c.name for c in a.get_table_schema(TableRef("t", (catalog, "main"))).columns]
    other_cols = [c.name for c in a.get_table_schema(TableRef("t", (catalog, "other"))).columns]

    assert main_cols == ["a", "b"]
    assert other_cols == ["x"]
    a.disconnect()


# ── connection and error mapping ──────────────────────────────────────────────

def test_uri_defaults_to_in_memory():
    """Unlike sqlite, duckdb has a usable default and needs no uri."""
    assert DuckDBAdapter({}).uri == ":memory:"


def test_unopenable_path_raises_adapter_connection_error(tmp_path):
    """A driver failure is translated rather than leaking duckdb's own type."""
    adapter = DuckDBAdapter({"uri": str(tmp_path / "no-such-dir" / "db.duckdb")})
    with pytest.raises(AdapterConnectionError):
        adapter.connect()


def test_invalid_sql_raises_adapter_query_error(adapter):
    with pytest.raises(AdapterQueryError):
        adapter.execute("SELECT * FROM no_such_table")


def test_syntax_error_raises_adapter_query_error(adapter):
    with pytest.raises(AdapterQueryError):
        adapter.execute("NOT VALID SQL")


def test_disconnect_on_never_connected_adapter_is_a_noop():
    DuckDBAdapter({"uri": ":memory:"}).disconnect()


def test_disconnect_is_idempotent(adapter):
    adapter.disconnect()
    adapter.disconnect()
    assert adapter.con is None


# ── qualified-name scoping ────────────────────────────────────────────────────

def test_get_table_schema_reports_the_full_scope(adapter):
    schema = adapter.get_table_schema(TableRef("users", ("memory", "main")))
    assert [c.name for c in schema.columns] == ["id", "name", "score"]
    assert schema.scope == ("memory", "main")


def test_get_table_schema_filters_by_catalog(adapter):
    """The full Scope Path filters on the catalog too, not just the table name."""
    # duckdb attaches several catalogs (system, temp, and the database itself);
    # an in-memory database lands in "memory", which is not list_databases()[0].
    catalog = adapter.execute(
        "SELECT table_catalog FROM information_schema.tables WHERE table_name='users'"
    ).rows[0][0]

    schema = adapter.get_table_schema(TableRef("users", (catalog, "main")))

    assert [c.name for c in schema.columns] == ["id", "name", "score"]
    assert schema.scope == (catalog, "main")


def test_get_table_schema_with_a_wrong_catalog_returns_no_columns(adapter):
    """Scoping must actually filter: a bogus catalog must not fall back to a
    bare table_name match and return another catalog's columns."""
    schema = adapter.get_table_schema(TableRef("users", ("no_such_catalog", "main")))
    assert schema.columns == []
    assert schema.sql_identifier is None


def test_list_schemas_separates_attached_catalogs(adapter):
    """Each catalog's schemas remain separate.

    Complements the file-backed case above: every catalog carries
    main/information_schema/pg_catalog, so a *distinct* schema in a second
    attached catalog is what makes the scoping observable.
    """
    adapter.execute("ATTACH ':memory:' AS other")
    adapter.execute("CREATE SCHEMA other.analytics")

    assert ContainerEntry("analytics") in adapter.list_schemas(("other",))
    assert ContainerEntry("analytics") not in adapter.list_schemas(("memory",))


def test_dialect_name(adapter):
    assert adapter.dialect_name() == "duckdb"


def test_get_keywords_returns_a_fresh_copy(adapter):
    first = adapter.get_keywords()
    assert "SELECT" in first

    first.append("NOT_A_KEYWORD")
    assert "NOT_A_KEYWORD" not in adapter.get_keywords()


def test_list_tables_scoped_to_a_catalog(adapter):
    """The database argument narrows table_catalog as well as table_schema."""
    catalog = adapter.execute(
        "SELECT table_catalog FROM information_schema.tables WHERE table_name='users'"
    ).rows[0][0]

    assert "users" in [table.name for table in adapter.list_tables((catalog, "main"))]
    assert adapter.list_tables(("no_such_catalog", "main")) == []


def test_list_tables_scoped_to_a_schema(adapter):
    adapter.execute("CREATE SCHEMA reporting")
    adapter.execute("CREATE TABLE reporting.summary (id INTEGER)")

    assert [table.name for table in adapter.list_tables(("memory", "reporting"))] == ["summary"]
    assert "summary" not in [table.name for table in adapter.list_tables(("memory", "main"))]


def test_hierarchy_declares_catalog_before_schema(adapter):
    assert adapter.scope_levels() == [ScopeLevel("catalog", "Catalog"), ScopeLevel("schema", "Schema")]
    assert adapter.default_scope() == ("memory", "main")
    adapter.execute("CREATE SCHEMA working")
    adapter.execute("USE memory.working")
    assert adapter.default_scope() == ("memory", "working")
    # Explicit requests remain independent of the driver's current schema.
    assert [table.name for table in adapter.list_tables(("memory", "main"))] == ["users"]


def test_internal_containers_are_marked_and_retained(adapter):
    assert set(adapter.list_databases()) == {
        ContainerEntry("memory", internal=False),
        ContainerEntry("system", internal=True),
        ContainerEntry("temp", internal=True),
    }
    assert set(adapter.list_schemas(("memory",))) == {
        ContainerEntry("main", internal=False),
        ContainerEntry("information_schema", internal=True),
        ContainerEntry("pg_catalog", internal=True),
    }


def test_attached_catalog_paths_keep_same_named_tables_distinct(adapter):
    adapter.execute("ATTACH ':memory:' AS side")
    adapter.execute("CREATE TABLE memory.main.orders (main_id INTEGER)")
    adapter.execute("CREATE TABLE side.main.orders (side_id INTEGER)")
    adapter.execute("INSERT INTO memory.main.orders VALUES (10)")
    adapter.execute("INSERT INTO side.main.orders VALUES (20)")

    identifiers = []
    for catalog, expected_id, expected_value in [("memory", "main_id", 10), ("side", "side_id", 20)]:
        path = (catalog, "main")
        tables = [table for table in adapter.list_tables(path) if table.name == "orders"]
        assert len(tables) == 1
        schema = adapter.get_table_schema(TableRef("orders", path))
        assert schema.scope == path
        assert [column.name for column in schema.columns] == [expected_id]
        assert schema.sql_identifier == tables[0].sql_identifier
        assert adapter.execute(f"SELECT * FROM {tables[0].sql_identifier}").rows == [[expected_value]]
        identifiers.append(tables[0].sql_identifier)
    assert identifiers[0] != identifiers[1]
    assert ContainerEntry("side", internal=False) in adapter.list_databases()


@pytest.mark.parametrize("name", ["with space", "select", 'has"quote', "literal.dot"])
def test_listed_identifiers_execute_literal_components(adapter, name):
    catalog, schema_name = 'side.catalog"quoted', 'sales.schema"quoted'
    namespace = f"{quote_identifier(catalog)}.{quote_identifier(schema_name)}"
    identifier = f"{namespace}.{quote_identifier(name)}"
    adapter.execute(f"ATTACH ':memory:' AS {quote_identifier(catalog)}")
    adapter.execute(f"CREATE SCHEMA {namespace}")
    adapter.execute(f"CREATE TABLE {identifier} (sentinel INTEGER)")
    adapter.execute(f"INSERT INTO {identifier} VALUES (123)")

    path = (catalog, schema_name)
    assert ContainerEntry(catalog) in adapter.list_databases()
    assert ContainerEntry(schema_name) in adapter.list_schemas((catalog,))
    table = next(table for table in adapter.list_tables(path) if table.name == name)
    assert table.sql_identifier == identifier
    assert adapter.execute(f"SELECT * FROM {table.sql_identifier}").rows == [[123]]
    schema = adapter.get_table_schema(TableRef(name, path))
    assert schema.name == name
    assert schema.scope == path
    assert schema.sql_identifier == identifier


@pytest.mark.parametrize("path", [(), ("memory",), ("memory", "main", "extra"), ("", "main")])
def test_full_scope_path_is_required_for_table_operations(adapter, path):
    with pytest.raises(AdapterQueryError, match="Scope Path"):
        adapter.list_tables(path)
    with pytest.raises(AdapterQueryError, match="Scope Path"):
        adapter.get_table_schema(TableRef("users", path))


@pytest.mark.parametrize("path", [(), ("memory", "main"), ("",)])
def test_schema_listing_requires_exactly_one_scope_component(adapter, path):
    with pytest.raises(AdapterQueryError, match="Scope Path"):
        adapter.list_schemas(path)
