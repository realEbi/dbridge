from dataclasses import asdict

from dbridge.config.settings import settings
from dbridge.core import executor
from dbridge.core.schema_registry import SchemaRegistry
from dbridge.core.session import SessionManager


class Engine:
    def __init__(self) -> None:
        self.sessions = SessionManager()
        self._registries: dict[str, SchemaRegistry] = {}

    def connect(self, adapter_name: str, config: dict) -> dict:
        session = self.sessions.create(adapter_name, config)
        self._registries[session.id] = SchemaRegistry(
            session.adapter, ttl_seconds=settings.cache_ttl_seconds
        )
        return {"session_id": session.id}

    def disconnect(self, session_id: str) -> dict:
        self.sessions.close(session_id)
        self._registries.pop(session_id, None)
        return {"ok": True}

    def execute(self, session_id: str, sql: str) -> dict:
        session = self.sessions.get(session_id)
        result = executor.execute(session, sql, settings.max_rows)
        return asdict(result)

    def list_databases(self, session_id: str) -> list[str]:
        return self.sessions.get(session_id).adapter.list_databases()

    def list_schemas(self, session_id: str, database: str | None = None) -> list[str]:
        return self.sessions.get(session_id).adapter.list_schemas(database)

    def list_tables(self, session_id: str, database=None, schema=None) -> list[str]:
        # Touch the session first so an unknown id raises before cache lookup.
        self.sessions.get(session_id)
        return self._registries[session_id].list_tables(database, schema)

    def get_table_schema(self, session_id: str, fqn: str) -> dict:
        self.sessions.get(session_id)
        return asdict(self._registries[session_id].get_table_schema(fqn))
