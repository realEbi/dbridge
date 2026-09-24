import uuid
from dataclasses import dataclass

from dbridge.adapters.base import DBAdapter
from dbridge.adapters.registry import create_adapter


class SessionNotFoundError(Exception):
    pass


@dataclass
class Session:
    id: str
    adapter: DBAdapter
    closing: bool = False


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._connecting: set[DBAdapter] = set()

    async def create(self, adapter_name: str, config: dict[str, str]) -> Session:
        adapter = create_adapter(adapter_name, config)
        self._connecting.add(adapter)
        try:
            await adapter.connect()
        except BaseException:
            # Failed or cancelled connects must not strand an unreported Adapter.
            await adapter.disconnect()
            raise
        finally:
            self._connecting.discard(adapter)
        session = Session(id=str(uuid.uuid4()), adapter=adapter)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None or session.closing:
            raise SessionNotFoundError(session_id)
        return session

    def mark_closing(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.closing = True

    def ids(self) -> tuple[str, ...]:
        return tuple(self._sessions)

    async def close(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.closing = True
            try:
                await session.adapter.disconnect()
            finally:
                self._sessions.pop(session_id, None)

    def abandon_all(self) -> None:
        """Release work that outlived the Transport's shutdown deadline."""
        adapters = self._connecting | {s.adapter for s in self._sessions.values()}
        self._connecting.clear()
        self._sessions.clear()
        for adapter in adapters:
            adapter.abandon()
