from dbridge.core.engine import Engine
from dbridge.core.session import SessionNotFoundError
from dbridge.exceptions import AdapterConnectionError, AdapterError, AdapterQueryError
from dbridge.protocol import errors
from dbridge.protocol.messages import JsonRpcRequest, make_error, make_response


class Dispatcher:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        # Method surface grows as later slices add introspection/completion/erd.
        self._methods = {
            "dbridge/connect": lambda p: engine.connect(p["adapter"], p.get("config", {})),
            "dbridge/disconnect": lambda p: engine.disconnect(p["session_id"]),
            "dbridge/execute": lambda p: engine.execute(p["session_id"], p["sql"]),
            "dbridge/listDatabases": lambda p: engine.list_databases(p["session_id"]),
            "dbridge/listSchemas": lambda p: engine.list_schemas(p["session_id"], p.get("database")),
            "dbridge/listTables": lambda p: engine.list_tables(p["session_id"], p.get("database"), p.get("schema")),
            "dbridge/getTableSchema": lambda p: engine.get_table_schema(p["session_id"], p["fqn"]),
            "dbridge/complete": lambda p: engine.complete(p["session_id"], p["sql"]),
            "dbridge/getERD": lambda p: engine.get_erd(p["session_id"]),
            "dbridge/refreshSchema": lambda p: engine.refresh_schema(p["session_id"]),
        }

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
