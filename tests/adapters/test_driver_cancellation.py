"""Real driver probes: bounded interruption, reuse, and sibling isolation."""

import asyncio
import sqlite3
import threading
import time

import duckdb
import pytest

from dbridge.adapters.base import TableRef
from dbridge.adapters.duckdb import DuckDBAdapter
from dbridge.adapters.sqlite import SqliteAdapter


SQLITE_SLOW = "WITH RECURSIVE t(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM t) SELECT sum(n) FROM t"
DUCKDB_SLOW = "SELECT sum(hash(i)) FROM range(20000000000) t(i)"


async def reached(event):
    assert await asyncio.wait_for(asyncio.to_thread(event.wait, 3), 4)


async def started_execute(adapter, sql, monkeypatch):
    started = threading.Event()
    execute = adapter._execute

    def observed(statement, *, row_limit=None):
        started.set()
        return execute(statement, row_limit=row_limit)

    monkeypatch.setattr(adapter, "_execute", observed)
    task = asyncio.create_task(adapter.execute(sql))
    await reached(started)
    return task


async def cancelled(task, adapter):
    task.cancel()
    done, _ = await asyncio.wait([task], timeout=3)
    if not done:
        adapter.abandon()
        await asyncio.gather(task, return_exceptions=True)
        pytest.fail("driver did not stop within the cancellation timeout")
    with pytest.raises(asyncio.CancelledError):
        await task


async def cleanup(adapter, task=None):
    """Stop real work even when an earlier assertion or metadata wait failed."""
    if task is not None and not task.done():
        task.cancel()
        done, _ = await asyncio.wait([task], timeout=3)
        if not done:
            adapter.abandon()
        await asyncio.gather(task, return_exceptions=True)
    disconnect = asyncio.create_task(adapter.disconnect())
    done, _ = await asyncio.wait([disconnect], timeout=3)
    if not done:
        adapter.abandon()
    # Abandonment deliberately releases lifecycle waiters with CancelledError;
    # cleanup must not replace the assertion that triggered this fallback.
    result = (await asyncio.gather(disconnect, return_exceptions=True))[0]
    if isinstance(result, Exception):
        raise result


@pytest.mark.parametrize("adapter_type,sql", [(SqliteAdapter, SQLITE_SLOW), (DuckDBAdapter, DUCKDB_SLOW)])
async def test_real_query_cancel_interrupts_and_session_remains_usable(adapter_type, sql, monkeypatch):
    adapter = adapter_type({"uri": ":memory:"})
    await adapter.connect()
    task = await started_execute(adapter, sql, monkeypatch)
    try:
        await cancelled(task, adapter)
        assert (await adapter.execute("SELECT 42")).rows == [[42]]
    finally:
        await cleanup(adapter, task)


async def test_sqlite_keeps_driver_same_thread_check_enabled():
    adapter = SqliteAdapter({"uri": ":memory:"})
    await adapter.connect()
    try:
        with pytest.raises(sqlite3.ProgrammingError, match="same thread"):
            adapter.con.execute("SELECT 1")
        assert (await adapter.execute("SELECT 1")).rows == [[1]]
    finally:
        await adapter.disconnect()


async def test_duckdb_metadata_runs_beside_query_and_sees_attached_catalog(monkeypatch):
    adapter = DuckDBAdapter({})
    await adapter.connect()
    await adapter.execute("ATTACH ':memory:' AS side; CREATE TABLE side.main.visible (n INTEGER)")
    task = await started_execute(adapter, DUCKDB_SLOW, monkeypatch)
    try:
        tables = await asyncio.wait_for(adapter.list_tables(("side", "main")), 3)
        assert [table.name for table in tables] == ["visible"]
        assert not task.done()
        await cancelled(task, adapter)
        assert [table.name for table in await adapter.list_tables(("side", "main"))] == ["visible"]
    finally:
        await cleanup(adapter, task)


async def test_failed_metadata_check_still_interrupts_query_and_closes_both_lanes(monkeypatch):
    adapter = DuckDBAdapter({})
    await adapter.connect()
    lanes = list(adapter._lanes.values())
    task = await started_execute(adapter, DUCKDB_SLOW, monkeypatch)

    def failed_listing(path):
        raise RuntimeError("metadata check failed")

    monkeypatch.setattr(adapter, "_list_tables", failed_listing)
    with pytest.raises(RuntimeError, match="metadata check failed"):
        try:
            await adapter.list_tables(("memory", "main"))
        finally:
            await cleanup(adapter, task)
    assert task.cancelled()
    assert adapter.con is None
    assert all(not lane.thread.is_alive() for lane in lanes)


async def test_cancelled_multistatement_keeps_earlier_effects_and_default_scope(monkeypatch):
    adapter = DuckDBAdapter({})
    await adapter.connect()
    await adapter.execute("CREATE SCHEMA working; CREATE TABLE working.saved (n INTEGER)")
    task = await started_execute(
        adapter,
        "USE memory.working; CREATE TEMP TABLE partial_temp (n INTEGER); "
        "INSERT INTO saved VALUES (7); " + DUCKDB_SLOW,
        monkeypatch,
    )
    try:
        # Observing the committed row from the sibling cursor proves the first
        # statements have completed before cancellation targets the long one.
        async def earlier_statement_visible():
            while True:
                rows = await adapter._lanes["metadata"].run(
                    lambda: adapter._metadata.execute("SELECT * FROM working.saved").fetchall()
                )
                if rows:
                    return rows
                await asyncio.sleep(0)

        assert await asyncio.wait_for(earlier_statement_visible(), 3) == [(7,)]
        await cancelled(task, adapter)
        assert await adapter.default_scope() == ("memory", "working")
        assert [table.name for table in await adapter.list_tables(("temp", "main"))] == ["partial_temp"]
        schema = await adapter.get_table_schema(TableRef("partial_temp", ("temp", "main")))
        assert [column.name for column in schema.columns] == ["n"]
        assert (await adapter.execute("SELECT * FROM saved")).rows == [[7]]
    finally:
        await cleanup(adapter, task)


async def test_cancel_after_sql_finishes_keeps_result_and_temporary_metadata(monkeypatch):
    adapter = DuckDBAdapter({})
    await adapter.connect()
    started, release = threading.Event(), threading.Event()
    read_snapshot = adapter._read_session_metadata

    def delayed_snapshot():
        started.set()
        assert release.wait(3)
        read_snapshot()

    monkeypatch.setattr(adapter, "_read_session_metadata", delayed_snapshot)
    task = asyncio.create_task(adapter.execute("CREATE TEMP TABLE finished (n INTEGER)"))
    try:
        await reached(started)
        task.cancel()
        await asyncio.sleep(0)  # Deliver the cancel while post-SQL discovery runs.
        release.set()
        result = await asyncio.wait_for(task, 3)
        assert result.columns == ["Count"]
        assert [table.name for table in await adapter.list_tables(("temp", "main"))] == ["finished"]
    finally:
        release.set()
        await cleanup(adapter, task)


@pytest.mark.parametrize("driver", ["sqlite", "duckdb"])
async def test_cross_thread_interrupt_stops_driver(driver):
    ready, finished = threading.Event(), threading.Event()
    connections, errors = [], []

    def worker():
        con = sqlite3.connect(":memory:") if driver == "sqlite" else duckdb.connect(":memory:")
        connections.append(con)
        try:
            ready.set()
            try:
                con.execute(SQLITE_SLOW if driver == "sqlite" else DUCKDB_SLOW).fetchall()
            except Exception as error:
                errors.append(error)
        finally:
            con.close()
            finished.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    await reached(ready)
    deadline = time.monotonic() + 3
    while not finished.is_set() and time.monotonic() < deadline:
        # Retry also covers the idle interval before execute enters the driver.
        try:
            connections[0].interrupt()
        except (sqlite3.ProgrammingError, duckdb.ConnectionException):
            # The worker may have completed its final query and closed already.
            pass
        await asyncio.sleep(0.01)
    assert finished.is_set(), "cross-thread interrupt failed to stop the driver"
    thread.join(1)
    assert len(errors) == 1
    if driver == "sqlite":
        assert isinstance(errors[0], sqlite3.OperationalError)
        assert errors[0].sqlite_errorcode == sqlite3.SQLITE_INTERRUPT
    else:
        assert isinstance(errors[0], duckdb.InterruptException)


@pytest.mark.parametrize("adapter_type", [SqliteAdapter, DuckDBAdapter])
async def test_idle_interrupt_does_not_affect_next_query(adapter_type):
    adapter = adapter_type({"uri": ":memory:"})
    await adapter.connect()
    try:
        adapter.con.interrupt()
        assert (await adapter.execute("SELECT 42")).rows == [[42]]
    finally:
        await adapter.disconnect()


async def test_interrupting_duckdb_parent_does_not_stop_cursor_query():
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    con = duckdb.connect(":memory:")
    results, errors = [], []

    def gated():
        started.set()
        assert release.wait(3)
        return 7

    con.create_function("gated", gated, [], "INTEGER", side_effects=True)

    def worker():
        cursor = con.cursor()
        try:
            results.extend(cursor.execute("SELECT gated()").fetchall())
        except Exception as error:
            errors.append(error)
        finally:
            cursor.close()
            finished.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        await reached(started)
        con.interrupt()
        release.set()
        await reached(finished)
        thread.join(1)
        assert errors == []
        assert results == [(7,)]
        assert con.execute("SELECT 42").fetchall() == [(42,)]
    finally:
        release.set()
        thread.join(3)
        con.close()
