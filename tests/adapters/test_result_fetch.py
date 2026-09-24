"""Real-driver guarantees for bounded result fetching."""

import asyncio
from contextlib import closing
import sqlite3

import pytest

from dbridge.adapters.duckdb import DuckDBAdapter
from dbridge.adapters.sqlite import SqliteAdapter
from dbridge.core.executor import execute
from dbridge.core.session import Session


INSERT_THOUSAND = (
    "WITH RECURSIVE s(x) AS "
    "(SELECT 1 UNION ALL SELECT x + 1 FROM s WHERE x < 1000) "
    "INSERT INTO numbers SELECT x FROM s"
)


@pytest.fixture(params=[SqliteAdapter, DuckDBAdapter], ids=["sqlite", "duckdb"])
async def adapter(request):
    instance = request.param({"uri": ":memory:"})
    await instance.connect()
    try:
        yield instance
    finally:
        await instance.disconnect()


async def test_bounded_executor_preserves_driver_ddl_result_columns(adapter):
    session = Session(id="ddl-result", adapter=adapter)

    result = await execute(session, "CREATE TABLE numbers (x INTEGER)", max_rows=100)

    assert result.columns == {"sqlite": [], "duckdb": ["Count"]}[adapter.adapter_name]
    assert result.rows == []
    assert result.row_count == 0
    assert result.warnings == []


async def test_bounded_read_returns_first_rows_and_session_stays_usable(adapter):
    if isinstance(adapter, SqliteAdapter):
        sql = "WITH RECURSIVE s(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM s) SELECT x FROM s"
        first = 1
    else:
        sql = "SELECT * FROM range(1000000000000)"
        first = 0

    result = await asyncio.wait_for(adapter.execute(sql, row_limit=101), timeout=3)

    assert result.rows == [[value] for value in range(first, first + 101)]
    assert result.row_count == 101
    assert (await asyncio.wait_for(adapter.execute("SELECT 42"), timeout=3)).rows == [[42]]


async def test_capped_sqlite_read_releases_file_lock_before_reply(tmp_path):
    uri = str(tmp_path / "bounded.sqlite")
    adapter = SqliteAdapter({"uri": uri})
    await adapter.connect()
    try:
        await adapter.execute("CREATE TABLE numbers (x INTEGER)")
        await adapter.execute(INSERT_THOUSAND)

        result = await adapter.execute("SELECT x FROM numbers", row_limit=101)
        assert len(result.rows) == 101

        # A pending read cursor prevents this second connection's autocommit.
        with closing(sqlite3.connect(uri, timeout=0.1, isolation_level=None)) as writer:
            writer.execute("INSERT INTO numbers VALUES (1001)")

        assert (await adapter.execute("SELECT count(*) FROM numbers")).rows == [[1001]]
    finally:
        await adapter.disconnect()


async def test_capped_insert_returning_applies_every_insert(adapter):
    await adapter.execute("CREATE TABLE numbers (x INTEGER)")

    result = await adapter.execute(INSERT_THOUSAND + " RETURNING x", row_limit=101)

    assert len(result.rows) == 101
    assert result.row_count == 101
    assert (await adapter.execute("SELECT count(*) FROM numbers")).rows == [[1000]]


async def test_capped_delete_returning_applies_every_delete(adapter):
    await adapter.execute("CREATE TABLE numbers (x INTEGER)")
    await adapter.execute(INSERT_THOUSAND)

    result = await adapter.execute("DELETE FROM numbers RETURNING x", row_limit=101)

    assert len(result.rows) == 101
    assert result.row_count == 101
    assert (await adapter.execute("SELECT count(*) FROM numbers")).rows == [[0]]
