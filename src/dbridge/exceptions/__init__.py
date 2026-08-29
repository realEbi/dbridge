class InvalidRequestError(Exception):
    """Raised when a request is well-formed JSON-RPC but semantically invalid.

    Distinct from a driver failure: the client sent params the engine cannot act on.
    """


class AdapterError(Exception):
    """Base for adapter-raised errors."""


class AdapterConnectionError(AdapterError):
    """Raised when an adapter cannot connect."""


class AdapterQueryError(AdapterError):
    """Raised when query execution fails inside an adapter."""
