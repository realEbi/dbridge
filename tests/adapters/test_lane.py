import asyncio
import inspect
import threading

import pytest

from dbridge.adapters.base import DBAdapter, QueryResult
from dbridge.adapters.lane import Lane
from dbridge.adapters.threaded import ThreadBackedAdapter


async def reached(event):
    assert await asyncio.wait_for(asyncio.to_thread(event.wait, 3), 4)


async def test_lane_preserves_fifo_and_thread_identity_and_exceptions():
    lane = Lane("test-fifo", lambda: None, lambda error: False)
    calls = []

    def call(number):
        calls.append((number, threading.get_ident()))
        if number == 1:
            raise ValueError("driver error")
        return number

    try:
        results = await asyncio.gather(
            *(lane.run(lambda number=number: call(number)) for number in range(3)),
            return_exceptions=True,
        )
        assert results[0] == 0
        assert isinstance(results[1], ValueError)
        assert str(results[1]) == "driver error"
        assert results[2] == 2
        assert [number for number, _ in calls] == [0, 1, 2]
        assert {identity for _, identity in calls} == {lane.thread.ident}
        assert lane.thread.ident != threading.get_ident()
        assert lane.thread.daemon
    finally:
        await lane.close()
    assert not lane.thread.is_alive()
    with pytest.raises(RuntimeError, match="closed"):
        await lane.run(lambda: None)


async def test_queued_cancel_never_runs_or_interrupts_current_job():
    started, release = threading.Event(), threading.Event()
    effects, interrupts = [], []
    lane = Lane("test-queued", lambda: interrupts.append(True), lambda error: True)

    def first():
        started.set()
        assert release.wait(3)
        return "first"

    first_task = asyncio.create_task(lane.run(first))
    try:
        await reached(started)
        second_task = asyncio.create_task(lane.run(lambda: effects.append("insert")))
        await asyncio.sleep(0)  # Submit the second coroutine to the blocked lane.
        second_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(second_task, 1)
        assert interrupts == []
        release.set()
        assert await asyncio.wait_for(first_task, 1) == "first"
        assert effects == []
    finally:
        release.set()
        await lane.close()


async def test_running_cancel_maps_only_interrupt_errors():
    started, interrupted = threading.Event(), threading.Event()
    lane = Lane("test-running", interrupted.set, lambda error: isinstance(error, InterruptedError))

    def query():
        started.set()
        assert interrupted.wait(3)
        raise InterruptedError("stopped")

    task = asyncio.create_task(lane.run(query))
    try:
        await reached(started)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert await lane.run(lambda: "usable") == "usable"
    finally:
        interrupted.set()
        await lane.close()


@pytest.mark.parametrize("fails", [False, True])
async def test_uninterruptible_work_retains_actual_outcome(fails):
    started, release = threading.Event(), threading.Event()
    lane = Lane("test-best-effort", release.set, lambda error: isinstance(error, InterruptedError))

    def query():
        started.set()
        assert release.wait(3)
        if fails:
            raise ValueError("ordinary driver failure")
        return "completed before interruption took effect"

    task = asyncio.create_task(lane.run(query))
    try:
        await reached(started)
        task.cancel()
        if fails:
            with pytest.raises(ValueError, match="ordinary driver failure"):
                await asyncio.wait_for(task, 1)
        else:
            assert await asyncio.wait_for(task, 1) == "completed before interruption took effect"
    finally:
        release.set()
        await lane.close()


async def test_cancel_retries_when_first_interrupt_arrives_before_driver_starts():
    marked_current, first_interrupt, driver_started = (
        threading.Event(), threading.Event(), threading.Event()
    )
    stopped = threading.Event()

    def interrupt():
        first_interrupt.set()
        if driver_started.is_set():
            stopped.set()

    lane = Lane("test-start-gap", interrupt, lambda error: isinstance(error, InterruptedError))

    def query():
        marked_current.set()
        assert first_interrupt.wait(3)
        driver_started.set()
        assert stopped.wait(3)
        raise InterruptedError("stopped after entering driver")

    task = asyncio.create_task(lane.run(query))
    try:
        await reached(marked_current)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert driver_started.is_set()
        assert stopped.is_set()
    finally:
        first_interrupt.set()
        stopped.set()
        await lane.close()


async def test_finished_cancel_does_not_interrupt_next_job_or_replace_result():
    first_started, first_release = threading.Event(), threading.Event()
    second_started, second_release = threading.Event(), threading.Event()
    interrupts = []
    lane = Lane("test-finished", lambda: interrupts.append(True), lambda error: True)

    def first():
        first_started.set()
        assert first_release.wait(3)
        return "finished"

    def second():
        second_started.set()
        assert second_release.wait(3)
        return "successor"

    first_task = asyncio.create_task(lane.run(first))
    try:
        await reached(first_started)
        second_task = asyncio.create_task(lane.run(second))
        await asyncio.sleep(0)
        # Hold the loop while the worker finishes the first and starts the next:
        # the first result is produced but has not reached its awaiting task.
        first_release.set()
        assert second_started.wait(3)
        first_task.cancel()
        assert await asyncio.wait_for(first_task, 1) == "finished"
        assert interrupts == []
        second_release.set()
        assert await asyncio.wait_for(second_task, 1) == "successor"
    finally:
        first_release.set()
        second_release.set()
        await lane.close()


async def test_abandon_releases_stuck_waiters_then_cleans_up_on_own_thread():
    started, release, cleaned = threading.Event(), threading.Event(), threading.Event()
    effects, cleanup_threads = [], []
    lane = Lane("test-abandon", lambda: None, lambda error: False)

    def stuck():
        started.set()
        assert release.wait(3)

    def cleanup():
        cleanup_threads.append(threading.get_ident())
        cleaned.set()

    task = asyncio.create_task(lane.run(stuck))
    try:
        await reached(started)
        queued = asyncio.create_task(lane.run(lambda: effects.append("must not run")))
        await asyncio.sleep(0)
        task.cancel()
        lane.abandon(cleanup)
        for pending in (task, queued):
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(pending, 1)
        assert lane.thread.is_alive()
        release.set()
        await reached(cleaned)
        lane.thread.join(1)
        assert not lane.thread.is_alive()
        assert effects == []
        assert cleanup_threads == [lane.thread.ident]
    finally:
        release.set()


class FakeAdapter(ThreadBackedAdapter):
    adapter_name = "fake"
    metadata_lane = "metadata"

    def __init__(self):
        super().__init__({})
        self.calls = []

    def _record(self, operation):
        self.calls.append((operation, threading.get_ident()))

    def _connect(self):
        self._record("connect")

    def _connect_metadata(self):
        self._record("connect_metadata")

    def _disconnect(self):
        self._record("disconnect")

    def _disconnect_metadata(self):
        self._record("disconnect_metadata")

    def _interrupt(self, lane):
        pass

    def _is_interruption(self, error):
        return isinstance(error, InterruptedError)

    def _execute(self, sql):
        self._record("execute")
        return QueryResult([], [], 0, 0)

    def _default_scope(self):
        self._record("default_scope")
        return ("main",)

    def _list_databases(self):
        return []

    def _list_schemas(self, path):
        return []

    def _list_tables(self, path):
        return []

    def _get_table_schema(self, table):
        raise NotImplementedError

    def scope_levels(self):
        return []

    def dialect_name(self):
        return "fake"

    def get_keywords(self):
        return []


async def test_threaded_base_routes_methods_and_stops_both_threads():
    adapter = FakeAdapter()
    await adapter.connect()
    lanes = dict(adapter._lanes)
    await adapter.execute("select 1")
    assert await adapter.default_scope() == ("main",)
    await adapter.disconnect()
    assert all(not lane.thread.is_alive() for lane in lanes.values())
    threads = dict(adapter.calls)
    assert threads["connect"] == threads["execute"] == threads["disconnect"]
    assert threads["connect_metadata"] == threads["default_scope"] == threads["disconnect_metadata"]
    assert threads["connect"] != threads["connect_metadata"]
    for method in ("connect", "disconnect", "execute", "default_scope", "list_databases",
                   "list_schemas", "list_tables", "get_table_schema"):
        assert inspect.iscoroutinefunction(getattr(DBAdapter, method))
        assert inspect.iscoroutinefunction(getattr(adapter, method))
    for method in ("scope_levels", "dialect_name", "get_keywords"):
        assert not inspect.iscoroutinefunction(getattr(DBAdapter, method))
        assert not inspect.iscoroutinefunction(getattr(adapter, method))


async def test_disconnect_cancellation_still_closes_connections_and_stops_threads(monkeypatch):
    adapter = FakeAdapter()
    await adapter.connect()
    lanes = dict(adapter._lanes)
    started, release = threading.Event(), threading.Event()

    def query(sql):
        started.set()
        assert release.wait(3)
        return QueryResult([], [], 0, 0)

    monkeypatch.setattr(adapter, "_execute", query)
    task = asyncio.create_task(adapter.execute("gated"))
    try:
        await reached(started)
        disconnect = asyncio.create_task(adapter.disconnect())
        await asyncio.sleep(0)
        disconnect.cancel()
        release.set()
        await asyncio.wait_for(task, 1)
        await asyncio.wait_for(disconnect, 1)
        assert all(not lane.thread.is_alive() for lane in lanes.values())
        assert {call for call, _ in adapter.calls} >= {"disconnect", "disconnect_metadata"}
    finally:
        release.set()
        await adapter.disconnect()


async def test_partial_connect_failure_closes_connections_and_stops_lanes(monkeypatch):
    adapter = FakeAdapter()
    lanes = []

    def failed_metadata_connect():
        lanes.extend(adapter._lanes.values())
        raise ValueError("metadata connection failed")

    monkeypatch.setattr(adapter, "_connect_metadata", failed_metadata_connect)
    with pytest.raises(ValueError, match="metadata connection failed"):
        await adapter.connect()
    assert len(lanes) == 2
    assert all(not lane.thread.is_alive() for lane in lanes)
    assert {call for call, _ in adapter.calls} >= {"disconnect", "disconnect_metadata"}


async def test_metadata_close_failure_still_closes_query_connection_and_stops_lanes(monkeypatch):
    adapter = FakeAdapter()
    await adapter.connect()
    lanes = list(adapter._lanes.values())

    def failed_metadata_close():
        raise ValueError("metadata close failed")

    monkeypatch.setattr(adapter, "_disconnect_metadata", failed_metadata_close)
    with pytest.raises(ValueError, match="metadata close failed"):
        await adapter.disconnect()
    assert all(not lane.thread.is_alive() for lane in lanes)
    assert "disconnect" in {call for call, _ in adapter.calls}


@pytest.mark.parametrize("phase", ["connect", "disconnect"])
async def test_abandon_during_lifecycle_releases_waiters_and_defers_cleanup(phase, monkeypatch):
    adapter = FakeAdapter()
    started, release = threading.Event(), threading.Event()
    if phase == "disconnect":
        await adapter.connect()
    original = getattr(adapter, "_" + phase)

    def stalled():
        started.set()
        assert release.wait(3)
        original()

    monkeypatch.setattr(adapter, "_" + phase, stalled)
    task = asyncio.create_task(getattr(adapter, phase)())
    try:
        await reached(started)
        lanes = list(adapter._lanes.values())
        task.cancel()
        adapter.abandon()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert any(lane.thread.is_alive() for lane in lanes)
        release.set()
        for lane in lanes:
            await asyncio.to_thread(lane.thread.join, 1)
        assert all(not lane.thread.is_alive() for lane in lanes)
        assert "disconnect" in {call for call, _ in adapter.calls}
    finally:
        release.set()


async def test_abandoned_parent_closes_only_after_metadata_lane_stops(monkeypatch):
    adapter = FakeAdapter()
    await adapter.connect()
    lanes = dict(adapter._lanes)
    started, release, parent_closed = threading.Event(), threading.Event(), threading.Event()

    def metadata():
        started.set()
        assert release.wait(3)
        assert not parent_closed.is_set()
        return ("main",)

    def close_parent():
        assert not lanes["metadata"].thread.is_alive()
        parent_closed.set()

    monkeypatch.setattr(adapter, "_default_scope", metadata)
    monkeypatch.setattr(adapter, "_disconnect", close_parent)
    task = asyncio.create_task(adapter.default_scope())
    try:
        await reached(started)
        adapter.abandon()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert not parent_closed.is_set()
        release.set()
        await reached(parent_closed)
        for lane in lanes.values():
            await asyncio.to_thread(lane.thread.join, 1)
        assert all(not lane.thread.is_alive() for lane in lanes.values())
    finally:
        release.set()
