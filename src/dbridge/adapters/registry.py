from collections.abc import Callable

from dbridge.adapters.base import DBAdapter
from dbridge.adapters.duckdb import DuckDBAdapter
from dbridge.adapters.sqlite import SqliteAdapter
from dbridge.exceptions import AdapterError

def _mysql(config: dict[str, str]) -> DBAdapter:
    try:
        from dbridge.adapters.mysql import MySQLAdapter
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.split(".")[0] in {"aiomysql", "cryptography", "pymysql"}:
            raise AdapterError("MySQL support requires the dbridge[mysql] extra") from exc
        raise
    return MySQLAdapter(config)


_REGISTRY: dict[str, Callable[[dict[str, str]], DBAdapter]] = {
    "sqlite": SqliteAdapter,
    "duckdb": DuckDBAdapter,
    "mysql": _mysql,
}

INSTALLED_ADAPTERS = list(_REGISTRY.keys())


def create_adapter(adapter_name: str, config: dict[str, str]) -> DBAdapter:
    cls = _REGISTRY.get(adapter_name)
    if cls is None:
        raise AdapterError(f"adapter '{adapter_name}' is not supported")
    return cls(config)
