import asyncio
from dataclasses import asdict

from dbridge.adapters.base import ScopePath, TableRef
from dbridge.config.profiles import delete_profile, get_profile, load_profiles, save_profile
from dbridge.config.settings import settings
from dbridge.core import executor
from dbridge.core.completion import complete as _complete
from dbridge.core.schema_registry import SchemaRegistry
from dbridge.core.session import SessionManager
from dbridge.exceptions import InvalidRequestError
from dbridge.logging import get_logger


class Engine:
    def __init__(self) -> None:
        self.sessions = SessionManager()
        self._registries: dict[str, SchemaRegistry] = {}

    async def connect(
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
        session = await self.sessions.create(adapter_name, config or {})
        try:
            self._registries[session.id] = SchemaRegistry(
                session.adapter, ttl_seconds=settings.cache_ttl_seconds
            )
            return {
                "session_id": session.id,
                **await self._hierarchy(session.id),
                "dialect": session.adapter.dialect_name(),
            }
        except BaseException:
            # A failed handshake must not leave a live Session the client cannot address.
            await self.disconnect(session.id)
            raise

    async def _hierarchy(self, session_id: str) -> dict:
        adapter = self.sessions.get(session_id).adapter
        return {
            "levels": [asdict(level) for level in adapter.scope_levels()],
            "default_path": list(await adapter.default_scope()),
        }

    async def disconnect(self, session_id: str) -> dict:
        self._registries.pop(session_id, None)
        await self.sessions.close(session_id)
        return {"ok": True}

    async def close_all(self) -> None:
        """Close remaining Sessions after the Dispatcher has drained their work."""
        for session_id in self.sessions.ids():
            self.sessions.mark_closing(session_id)
        results = await asyncio.gather(
            *(self.disconnect(sid) for sid in self.sessions.ids()), return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                get_logger().warning("Could not disconnect Session during shutdown: %s", result)

    def abandon(self) -> None:
        """Detach Sessions whose work exceeded the shutdown grace period."""
        self._registries.clear()
        self.sessions.abandon_all()

    async def execute(self, session_id: str, sql: str) -> dict:
        session = self.sessions.get(session_id)
        result = await executor.execute(session, sql, settings.max_rows)
        return asdict(result)

    async def list_databases(self, session_id: str) -> list[dict]:
        self.sessions.get(session_id)
        return [asdict(entry) for entry in await self._registries[session_id].list_databases()]

    async def list_schemas(self, session_id: str, path: ScopePath) -> list[dict]:
        self.sessions.get(session_id)
        return [asdict(entry) for entry in await self._registries[session_id].list_schemas(path)]

    async def list_tables(self, session_id: str, path: ScopePath) -> list[dict]:
        self.sessions.get(session_id)
        return [asdict(entry) for entry in await self._registries[session_id].list_tables(path)]

    async def get_table_schema(self, session_id: str, path: ScopePath, name: str) -> dict:
        self.sessions.get(session_id)
        result = asdict(
            await self._registries[session_id].get_table_schema(TableRef(name, path))
        )
        result["scope"] = list(result["scope"])
        return result

    async def get_erd(self, session_id: str, path: ScopePath) -> dict:
        return {"status": "not_implemented", "tables": await self.list_tables(session_id, path)}

    async def refresh_schema(self, session_id: str) -> dict:
        self.sessions.get(session_id)
        self._registries[session_id].refresh()
        return {"ok": True, **await self._hierarchy(session_id)}

    async def complete(
        self, session_id: str, sql: str, path: ScopePath, position: int | None = None,
    ) -> list[dict]:
        session = self.sessions.get(session_id)
        registry = self._registries[session_id]

        async def get_columns(table: TableRef) -> list[str]:
            schema = await registry.get_table_schema(table)
            return [column.name for column in schema.columns]

        return await _complete(
            sql,
            list_tables_fn=lambda: registry.list_tables(path),
            get_columns_fn=get_columns,
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
