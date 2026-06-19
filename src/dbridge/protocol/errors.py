PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
CONNECTION_FAILED = -32001
QUERY_ERROR = -32002
SESSION_NOT_FOUND = -32003
ADAPTER_NOT_SUPPORTED = -32005


class DspError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
