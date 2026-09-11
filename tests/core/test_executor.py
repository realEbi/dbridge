"""Result truncation.

Proven end-to-end through a spawned server, but the cap, the row_count, and the
warning text were never asserted in process. Truncation applies after the
adapter has materialized the rows (AGENTS.md — Engineering conventions).
"""
from dbridge.adapters.base import QueryResult
from dbridge.core.executor import execute
from dbridge.core.session import Session


class _StubAdapter:
    """Returns a canned QueryResult; executor never inspects anything else."""

    def __init__(self, result):
        self._result = result
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)
        return self._result


def _session(rows, columns=("n",), warnings=None):
    result = QueryResult(
        columns=list(columns),
        rows=rows,
        row_count=len(rows),
        execution_time_ms=1.5,
        warnings=list(warnings or []),
    )
    return Session(id="s", adapter=_StubAdapter(result)), result


def test_result_under_the_cap_is_returned_untouched():
    session, original = _session([[1], [2], [3]])

    result = execute(session, "SELECT n FROM t", max_rows=100)

    assert result is original
    assert result.rows == [[1], [2], [3]]
    assert result.warnings == []


def test_result_exactly_at_the_cap_is_not_truncated():
    """The cap is inclusive: len(rows) > max_rows triggers truncation."""
    session, original = _session([[i] for i in range(10)])

    result = execute(session, "SELECT n FROM t", max_rows=10)

    assert result is original
    assert result.row_count == 10
    assert result.warnings == []


def test_result_over_the_cap_is_truncated_and_warned():
    session, _ = _session([[i] for i in range(150)])

    result = execute(session, "SELECT n FROM t", max_rows=100)

    assert len(result.rows) == 100
    assert result.row_count == 100
    assert result.rows[0] == [0] and result.rows[-1] == [99]
    assert any("truncated" in w for w in result.warnings)
    assert "100" in " ".join(result.warnings)


def test_truncation_preserves_columns_and_timing():
    session, original = _session([[i] for i in range(5)], columns=("a",))

    result = execute(session, "SELECT a FROM t", max_rows=2)

    assert result.columns == ["a"]
    assert result.execution_time_ms == original.execution_time_ms


def test_truncation_appends_to_existing_warnings():
    """An adapter warning must survive truncation, not be replaced by it."""
    session, _ = _session([[i] for i in range(5)], warnings=["adapter said something"])

    result = execute(session, "SELECT n FROM t", max_rows=2)

    assert result.warnings[0] == "adapter said something"
    assert any("truncated" in w for w in result.warnings[1:])


def test_sql_is_passed_through_to_the_adapter():
    session, _ = _session([[1]])
    execute(session, "SELECT 1", max_rows=100)
    assert session.adapter.executed == ["SELECT 1"]
