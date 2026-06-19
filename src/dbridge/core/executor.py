from dbridge.adapters.base import QueryResult
from dbridge.core.session import Session


def execute(session: Session, sql: str, max_rows: int) -> QueryResult:
    result = session.adapter.execute(sql)
    if len(result.rows) > max_rows:
        truncated = result.rows[:max_rows]
        result = QueryResult(
            columns=result.columns,
            rows=truncated,
            row_count=len(truncated),
            execution_time_ms=result.execution_time_ms,
            warnings=[*result.warnings, f"result truncated to {max_rows} rows"],
        )
    return result
