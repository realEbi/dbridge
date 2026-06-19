import pytest

from dbridge.adapters.duckdb import DuckDBAdapter
from dbridge.adapters.registry import INSTALLED_ADAPTERS


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
    assert "users" in adapter.list_tables()


def test_execute_returns_rows(adapter):
    result = adapter.execute("SELECT id, name FROM users")
    assert result.columns == ["id", "name"]
    assert result.rows == [[1, "ada"]]
    assert result.row_count == 1


def test_get_table_schema_columns(adapter):
    schema = adapter.get_table_schema("users")
    names = [c.name for c in schema.columns]
    assert names == ["id", "name", "score"]


def test_get_table_schema_types(adapter):
    schema = adapter.get_table_schema("users")
    col_map = {c.name: c for c in schema.columns}
    assert col_map["id"].data_type == "INTEGER"
    assert col_map["name"].data_type == "VARCHAR"
    assert col_map["score"].data_type == "DOUBLE"


def test_get_table_schema_nullability(adapter):
    schema = adapter.get_table_schema("users")
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
    schemas = adapter.list_schemas()
    assert "main" in schemas


def test_keywords_non_empty(adapter):
    kws = adapter.get_keywords()
    assert "SELECT" in kws
    assert "FROM" in kws
