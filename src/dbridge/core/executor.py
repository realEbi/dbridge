from dbridge.adapters.base import QueryResult
from dbridge.core.session import Session


async def execute(session: Session, sql: str, max_rows: int) -> QueryResult:
    result = await session.adapter.execute(sql, row_limit=max(max_rows, 0) + 1)
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
