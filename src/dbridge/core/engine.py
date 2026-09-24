from dataclasses import asdict

from dbridge.adapters.base import ScopePath, TableRef
from dbridge.config.profiles import delete_profile, get_profile, load_profiles, save_profile
from dbridge.config.settings import settings
from dbridge.core import executor
from dbridge.core.completion import complete as _complete
from dbridge.core.schema_registry import SchemaRegistry
from dbridge.core.session import SessionManager
from dbridge.exceptions import InvalidRequestError


class Engine:
    def __init__(self) -> None:
        self.sessions = SessionManager()
        self._registries: dict[str, SchemaRegistry] = {}

    def connect(
        self,
        adapter_name: str | None = None,
        config: dict | None = None,
        profile: str | None = None,
    ) -> dict:
        """Open a session either from a saved profile name or an inline adapter+config."""
        if profile is not None:
            entry = get_profile(profile)
            adapter_name, config = entry["adapter"], entry["config"]
        if adapter_name is None:
            raise InvalidRequestError("connect requires either 'profile' or 'adapter'")
        session = self.sessions.create(adapter_name, config or {})
        try:
            self._registries[session.id] = SchemaRegistry(
                session.adapter, ttl_seconds=settings.cache_ttl_seconds
            )
            return {
                "session_id": session.id,
                **self._hierarchy(session.id),
                "dialect": session.adapter.dialect_name(),
            }
        except Exception:
            # A failed handshake must not leave a live Session the client cannot address.
            self.disconnect(session.id)
            raise

    def _hierarchy(self, session_id: str) -> dict:
        adapter = self.sessions.get(session_id).adapter
        return {
            "levels": [asdict(level) for level in adapter.scope_levels()],
            "default_path": list(adapter.default_scope()),
        }

    def disconnect(self, session_id: str) -> dict:
        self.sessions.close(session_id)
        self._registries.pop(session_id, None)
        return {"ok": True}

    def execute(self, session_id: str, sql: str) -> dict:
        session = self.sessions.get(session_id)
        result = executor.execute(session, sql, settings.max_rows)
        return asdict(result)

    def list_databases(self, session_id: str) -> list[dict]:
        self.sessions.get(session_id)
        return [asdict(entry) for entry in self._registries[session_id].list_databases()]

    def list_schemas(self, session_id: str, path: ScopePath) -> list[dict]:
        self.sessions.get(session_id)
        return [asdict(entry) for entry in self._registries[session_id].list_schemas(path)]

    def list_tables(self, session_id: str, path: ScopePath) -> list[dict]:
        self.sessions.get(session_id)
        return [asdict(entry) for entry in self._registries[session_id].list_tables(path)]

    def get_table_schema(self, session_id: str, path: ScopePath, name: str) -> dict:
        self.sessions.get(session_id)
        result = asdict(
            self._registries[session_id].get_table_schema(TableRef(name, path))
        )
        result["scope"] = list(result["scope"])
        return result

    def get_erd(self, session_id: str, path: ScopePath) -> dict:
        return {"status": "not_implemented", "tables": self.list_tables(session_id, path)}

    def refresh_schema(self, session_id: str) -> dict:
        self.sessions.get(session_id)
        self._registries[session_id].refresh()
        return {"ok": True, **self._hierarchy(session_id)}

    def complete(
        self, session_id: str, sql: str, path: ScopePath, position: int | None = None,
    ) -> list[dict]:
        session = self.sessions.get(session_id)
        registry = self._registries[session_id]
        return _complete(
            sql,
            list_tables_fn=lambda: registry.list_tables(path),
            get_columns_fn=lambda t: [c.name for c in registry.get_table_schema(t).columns],
            get_keywords_fn=session.adapter.get_keywords,
            path=path,
            position=position,
        )

    def list_profiles(self) -> dict:
        return load_profiles()

    def save_profile(self, name: str, adapter: str, config: dict) -> dict:
        save_profile(name, adapter, config)
        return {"ok": True}

    def delete_profile(self, name: str) -> dict:
        existed = delete_profile(name)
        return {"ok": existed}
