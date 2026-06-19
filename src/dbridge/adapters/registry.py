from dbridge.adapters.base import DBAdapter
from dbridge.adapters.sqlite import SqliteAdapter
from dbridge.exceptions import AdapterError

# DuckDB is registered in a later slice; mysql/postgres/snowflake are parked.
_REGISTRY: dict[str, type[DBAdapter]] = {
    "sqlite": SqliteAdapter,
}

INSTALLED_ADAPTERS = list(_REGISTRY.keys())


def create_adapter(adapter_name: str, config: dict[str, str]) -> DBAdapter:
    cls = _REGISTRY.get(adapter_name)
    if cls is None:
        raise AdapterError(f"adapter '{adapter_name}' is not supported")
    return cls(config)
