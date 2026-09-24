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
from dbridge.protocol import errors
from dbridge.protocol.messages import JsonRpcRequest, make_error, make_response


class Dispatcher:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        # Method surface grows as later slices add introspection/completion/erd.
        self._methods = {
            "dbridge/connect": lambda p: engine.connect(
                p.get("adapter"), p.get("config", {}), p.get("profile")
            ),
            "dbridge/disconnect": lambda p: engine.disconnect(p["session_id"]),
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

    def _list_databases(self, params: dict) -> list[dict]:
        if "path" in params:
            raise InvalidRequestError("listDatabases does not accept a path")
        return self.engine.list_databases(params["session_id"])

    def _get_table_schema(self, params: dict) -> dict:
        path = self._path(params)
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise InvalidRequestError("name requires a nonempty string")
        return self.engine.get_table_schema(params["session_id"], path, name)

    def handle(self, request: dict) -> dict | None:
        try:
            req = JsonRpcRequest.model_validate(request)
        except Exception:
            return make_error(request.get("id"), errors.INVALID_REQUEST, "invalid request")

        if req.id is None:  # notification
            return None

        fn = self._methods.get(req.method)
        if fn is None:
            return make_error(req.id, errors.METHOD_NOT_FOUND, f"unknown method: {req.method}")

        try:
            return make_response(req.id, fn(req.params))
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
