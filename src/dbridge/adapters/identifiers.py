def quote_identifier(component: str) -> str:
    """Quote one literal SQL identifier component for SQLite and DuckDB."""
    return '"' + component.replace('"', '""') + '"'
