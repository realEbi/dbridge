import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dbridge.adapters.base import ScopePath
from dbridge.config.profiles import ProfileNotFoundError
from dbridge.core.engine import Engine
from dbridge.core.session import SessionNotFoundError
from dbridge.exceptions import (
    AdapterConnectionError,
    AdapterError,
    AdapterQueryError,
    InvalidRequestError,
)
from dbridge.logging import get_logger
from dbridge.protocol import errors
from dbridge.protocol.messages import JsonRpcRequest, make_error, make_response


@dataclass
class PendingRequest:
    task: asyncio.Task
    session_id: str | None
    method: str


logger = get_logger(__name__)


class Dispatcher:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.pending: dict[int | str, PendingRequest] = {}
        self._disconnecting: dict[str, asyncio.Task] = {}
        self._methods = {
            "dbridge/connect": lambda p: engine.connect(
                p.get("adapter"), p.get("config", {}), p.get("profile")
            ),
            "dbridge/disconnect": lambda p: self._disconnect(p["session_id"]),
            "dbridge/execute": lambda p: engine.execute(p["session_id"], p["sql"]),
            "dbridge/listDatabases": self._list_databases,
            "dbridge/listSchemas": lambda p: engine.list_schemas(
                p["session_id"], self._path(p, schemas=True)
            ),
            "dbridge/listTables": lambda p: engine.list_tables(
                p["session_id"], self._path(p)
            ),
            "dbridge/getTableSchema": self._get_table_schema,
            "dbridge/complete": lambda p: engine.complete(
                p["session_id"], p["sql"], self._path(p), p.get("position")
            ),
            "dbridge/getERD": lambda p: engine.get_erd(p["session_id"], self._path(p)),
            "dbridge/refreshSchema": lambda p: engine.refresh_schema(p["session_id"]),
            "dbridge/listProfiles": lambda p: engine.list_profiles(),
            "dbridge/saveProfile": lambda p: engine.save_profile(
                p["name"], p["adapter"], p.get("config", {})
            ),
            "dbridge/deleteProfile": lambda p: engine.delete_profile(p["name"]),
        }

    def _path(self, params: dict, *, schemas: bool = False) -> ScopePath:
        adapter = self.engine.sessions.get(params["session_id"]).adapter
        if any(key in params for key in ("database", "schema", "fqn", "table")):
            raise InvalidRequestError("use path and a literal name instead of legacy scope fields")
        path = params.get("path")
        arity = 1 if schemas else len(adapter.scope_levels())
        if (
            not isinstance(path, list)
            or len(path) != arity
            or any(not isinstance(part, str) or not part for part in path)
        ):
            raise InvalidRequestError(f"path requires {arity} nonempty string components")
        return tuple(path)

    async def _list_databases(self, params: dict) -> list[dict]:
        if "path" in params:
            raise InvalidRequestError("listDatabases does not accept a path")
        return await self.engine.list_databases(params["session_id"])

    async def _get_table_schema(self, params: dict) -> dict:
        path = self._path(params)
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise InvalidRequestError("name requires a nonempty string")
        return await self.engine.get_table_schema(params["session_id"], path, name)

    def submit(self, request: Any, respond: Callable[[dict], None]) -> asyncio.Task | None:
        """Register a request at intake; retain its id until its reply is written."""
        if (
            isinstance(request, dict)
            and request.get("method") == "$/cancelRequest"
            and request.get("id") is None
        ):
            self._cancel(request.get("params"))
            return None
        try:
            req = JsonRpcRequest.model_validate(request)
        except Exception:
            request_id = request.get("id") if isinstance(request, dict) else None
            respond(make_error(request_id, errors.INVALID_REQUEST, "invalid request"))
            return None

        if req.id is None:  # notification
            return None

        if req.id in self.pending:
            respond(make_error(req.id, errors.INVALID_REQUEST, "request id is still outstanding"))
            return None

        task = asyncio.create_task(self._invoke(req))
        request_id = req.id
        self.pending[request_id] = PendingRequest(task, req.params.get("session_id"), req.method)

        def finished(completed: asyncio.Task) -> None:
            try:
                try:
                    response = completed.result()
                except asyncio.CancelledError:
                    response = make_error(req.id, errors.QUERY_CANCELLED, "request cancelled")
                except Exception:
                    logger.exception("Request failed unexpectedly")
                    response = make_error(req.id, errors.INTERNAL_ERROR, "internal error")
                respond(response)
            finally:
                self.pending.pop(request_id, None)

        task.add_done_callback(finished)
        return task

    async def handle(self, request: Any) -> dict | None:
        """Await one request; Transport uses submit() to keep intake independent."""
        reply: asyncio.Future[dict] = asyncio.get_running_loop().create_future()

        def respond(response: dict) -> None:
            if not reply.done():
                reply.set_result(response)

        task = self.submit(request, respond)
        if task is None and not reply.done():
            return None
        try:
            return await asyncio.shield(reply)
        except asyncio.CancelledError:
            if task is not None:
                task.cancel()
            return await reply

    def _cancel(self, params: Any) -> None:
        request_id = params.get("id") if isinstance(params, dict) else None
        if not isinstance(request_id, (int, str)) or isinstance(request_id, bool):
            logger.debug("Ignoring malformed cancel notification")
            return
        pending = self.pending.get(request_id)
        if pending is None or pending.task.done():
            logger.debug("Ignoring cancel for an unknown or completed request")
            return
        pending.task.cancel()

    async def _disconnect(self, session_id: str) -> dict:
        cleanup = self._disconnecting.get(session_id)
        if cleanup is None:
            self.engine.sessions.mark_closing(session_id)
            tasks = [
                pending.task for pending in self.pending.values()
                if pending.session_id == session_id
                and pending.method != "dbridge/disconnect"
                and not pending.task.done()
            ]
            cleanup = asyncio.create_task(self._close_session(session_id, tasks))
            self._disconnecting[session_id] = cleanup
            cleanup.add_done_callback(lambda _: self._disconnecting.pop(session_id, None))
        # Once closing starts, finish resource cleanup even if disconnect is cancelled.
        while True:
            try:
                return await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                if cleanup.cancelled():
                    raise

    async def _close_session(self, session_id: str, tasks: list[asyncio.Task]) -> dict:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return await self.engine.disconnect(session_id)

    async def _invoke(self, req: JsonRpcRequest) -> dict:
        fn = self._methods.get(req.method)
        if fn is None:
            return make_error(req.id, errors.METHOD_NOT_FOUND, f"unknown method: {req.method}")

        try:
            result = fn(req.params)
            if inspect.isawaitable(result):
                result = await result
            return make_response(req.id, result)
        except ProfileNotFoundError as e:
            return make_error(req.id, errors.PROFILE_NOT_FOUND, f"unknown profile: {e}")
        except InvalidRequestError as e:
            return make_error(req.id, errors.INVALID_REQUEST, str(e))
        except SessionNotFoundError as e:
            return make_error(req.id, errors.SESSION_NOT_FOUND, str(e))
        except AdapterConnectionError as e:
            return make_error(req.id, errors.CONNECTION_FAILED, str(e))
        except AdapterQueryError as e:
            return make_error(req.id, errors.QUERY_ERROR, str(e))
        except AdapterError as e:
            return make_error(req.id, errors.ADAPTER_NOT_SUPPORTED, str(e))
        except KeyError as e:
            return make_error(req.id, errors.INVALID_REQUEST, f"missing param: {e}")
