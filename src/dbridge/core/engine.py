from dataclasses import asdict

from dbridge.config.settings import settings
from dbridge.core import executor
from dbridge.core.session import SessionManager


class Engine:
    def __init__(self) -> None:
        self.sessions = SessionManager()

    def connect(self, adapter_name: str, config: dict) -> dict:
        session = self.sessions.create(adapter_name, config)
        return {"session_id": session.id}

    def disconnect(self, session_id: str) -> dict:
        self.sessions.close(session_id)
        return {"ok": True}

    def execute(self, session_id: str, sql: str) -> dict:
        session = self.sessions.get(session_id)
        result = executor.execute(session, sql, settings.max_rows)
        return asdict(result)
