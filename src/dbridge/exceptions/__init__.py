class AdapterError(Exception):
    """Base for adapter-raised errors."""


class AdapterConnectionError(AdapterError):
    """Raised when an adapter cannot connect."""


class AdapterQueryError(AdapterError):
    """Raised when query execution fails inside an adapter."""
