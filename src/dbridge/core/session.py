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
    active_database: str | None = None
    active_schema: str | None = None


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, adapter_name: str, config: dict[str, str]) -> Session:
        adapter = create_adapter(adapter_name, config)
        adapter.connect()
        session = Session(id=str(uuid.uuid4()), adapter=adapter)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def close(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            session.adapter.disconnect()
