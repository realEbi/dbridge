"""Behavioral request scheduling/cancellation checks, using gates and real drivers."""

import asyncio
import threading

import pytest

from dbridge.adapters.sqlite import SqliteAdapter
from dbridge.protocol import errors
from dbridge.protocol.handlers import Dispatcher


class Interrupted(Exception):
    pass


class GatedSqlite(SqliteAdapter):
    def __init__(self):
        super().__init__({"uri": ":memory:"})
        self.entered = threading.Event()
        self.release = threading.Event()
        self.interrupted = False

    def _execute(self, sql, *, row_limit=None):
        if sql == "slow":
            self.entered.set()
            if not self.release.wait(5):
                raise TimeoutError("test gate not released")
            if self.interrupted:
                raise Interrupted
            return super()._execute("SELECT 1", row_limit=row_limit)
        return super()._execute(sql, row_limit=row_limit)

    def _interrupt(self, lane):
        self.interrupted = True
        self.release.set()

    def _is_interruption(self, error):
        return isinstance(error, Interrupted) or super()._is_interruption(error)


def rpc(request_id, method, **params):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "dbridge/" + method,
        "params": params,
    }


def start(dispatcher, request):
    reply = asyncio.get_running_loop().create_future()
    dispatcher.submit(request, reply.set_result)
    return reply


async def cancel(dispatcher, request_id):
    assert (
        await dispatcher.handle(
            {
                "jsonrpc": "2.0",
                "method": "$/cancelRequest",
                "params": {"id": request_id},
            }
        )
        is None
    )


async def gated_session(engine, monkeypatch):
    adapter = GatedSqlite()
    monkeypatch.setattr("dbridge.core.session.create_adapter", lambda *args: adapter)
    sid = (await engine.connect("sqlite"))["session_id"]
    return sid, adapter


async def entered(adapter):
    assert await asyncio.to_thread(adapter.entered.wait, 2)


async def test_other_session_metadata_query_profiles_and_invalid_request_stay_responsive(
    engine, monkeypatch, isolated_profiles
):
    other = (await engine.connect("sqlite", {"uri": ":memory:"}))["session_id"]
    sid, adapter = await gated_session(engine, monkeypatch)
    dispatcher = Dispatcher(engine)
    slow = start(dispatcher, rpc(1, "execute", session_id=sid, sql="slow"))
    await entered(adapter)
    try:
        for request in [
            rpc(2, "listTables", session_id=other, path=["main"]),
            rpc(3, "listProfiles"),
            rpc(4, "nope"),
            rpc(5, "execute", session_id=other, sql="SELECT 2"),
        ]:
            response = await asyncio.wait_for(dispatcher.handle(request), 1)
            assert response["id"] == request["id"]
            if request["id"] == 4:
                assert response["error"]["code"] == errors.METHOD_NOT_FOUND
            else:
                assert "result" in response
            assert not slow.done()
    finally:
        adapter.release.set()
    assert (await slow)["result"]["rows"] == [[1]]
    assert not dispatcher.pending


async def test_duplicate_outstanding_id_is_rejected_until_reply_then_reusable(
    engine, monkeypatch, isolated_profiles
):
    sid, adapter = await gated_session(engine, monkeypatch)
    dispatcher = Dispatcher(engine)
    first = start(dispatcher, rpc(5, "execute", session_id=sid, sql="slow"))
    await entered(adapter)
    try:
        duplicate = await dispatcher.handle(rpc(5, "listProfiles"))
        assert duplicate["error"]["code"] == errors.INVALID_REQUEST
        assert dispatcher.pending[5].session_id == sid
        assert not first.done()
    finally:
        adapter.release.set()
    assert (await first)["result"]["rows"] == [[1]]
    assert (await dispatcher.handle(rpc(5, "listProfiles")))["result"] == {}
    assert not dispatcher.pending


async def test_one_session_statements_keep_arrival_order(engine):
    sid = (await engine.connect("sqlite", {"uri": ":memory:"}))["session_id"]
    dispatcher = Dispatcher(engine)
    replies = [
        start(dispatcher, rpc(i, "execute", session_id=sid, sql=sql))
        for i, sql in enumerate(
            [
                "CREATE TABLE t(a INT)",
                "INSERT INTO t VALUES(1)",
                "SELECT count(*) FROM t",
            ]
        )
    ]
    responses = await asyncio.gather(*replies)
    assert all("result" in response for response in responses)
    assert responses[-1]["result"]["rows"] == [[1]]
    assert not dispatcher.pending


async def test_sqlite_uncached_metadata_waits_but_cached_completion_does_not(
    engine, monkeypatch
):
    sid, adapter = await gated_session(engine, monkeypatch)
    await engine.execute(sid, "CREATE TABLE products(id INT)")
    await engine.complete(sid, "SELECT  FROM products", ("main",), 7)
    dispatcher = Dispatcher(engine)
    slow = start(dispatcher, rpc(1, "execute", session_id=sid, sql="slow"))
    await entered(adapter)
    metadata = start(dispatcher, rpc(2, "listTables", session_id=sid, path=["main"]))
    try:
        completion = await asyncio.wait_for(
            dispatcher.handle(
                rpc(
                    3,
                    "complete",
                    session_id=sid,
                    path=["main"],
                    sql="SELECT  FROM products",
                    position=7,
                )
            ),
            1,
        )
        assert [item["label"] for item in completion["result"]] == ["id"]
        assert not metadata.done() and not slow.done()
    finally:
        adapter.release.set()
    assert (await slow)["result"]["rows"] == [[1]]
    assert (await metadata)["result"] == [
        {"name": "products", "sql_identifier": '"main"."products"'}
    ]


async def test_cancel_queued_insert_never_executes_and_cancel_running_query_reuses_session(
    engine, monkeypatch
):
    sid, adapter = await gated_session(engine, monkeypatch)
    await engine.execute(sid, "CREATE TABLE t(a INT)")
    dispatcher = Dispatcher(engine)
    slow = start(dispatcher, rpc(1, "execute", session_id=sid, sql="slow"))
    await entered(adapter)
    queued = start(
        dispatcher, rpc(2, "execute", session_id=sid, sql="INSERT INTO t VALUES(1)")
    )
    await asyncio.sleep(0)  # Submit the second job to the occupied lane.
    await cancel(dispatcher, 2)
    assert (await asyncio.wait_for(queued, 1))["error"][
        "code"
    ] == errors.QUERY_CANCELLED
    assert not slow.done()
    await cancel(dispatcher, 1)
    assert (await asyncio.wait_for(slow, 1))["error"]["code"] == errors.QUERY_CANCELLED
    result = await dispatcher.handle(
        rpc(3, "execute", session_id=sid, sql="SELECT count(*) FROM t")
    )
    assert result["result"]["rows"] == [[0]]
    assert not dispatcher.pending


@pytest.mark.parametrize(
    "params", [None, {}, [], {"id": []}, {"id": True}, {"id": 99}, {"id": "unknown"}]
)
async def test_malformed_or_unknown_cancel_is_silent_and_server_stays_available(
    engine, isolated_profiles, params, caplog
):
    dispatcher = Dispatcher(engine)
    assert (
        await dispatcher.handle(
            {"jsonrpc": "2.0", "method": "$/cancelRequest", "params": params}
        )
        is None
    )
    assert (await dispatcher.handle(rpc(1, "listProfiles")))["result"] == {}
    assert not any(record.levelno >= 30 for record in caplog.records)


async def test_cancel_before_task_starts_still_replies_once(engine, isolated_profiles):
    dispatcher = Dispatcher(engine)
    replies = []
    dispatcher.submit(rpc(1, "listProfiles"), replies.append)
    dispatcher.submit(
        {"method": "$/cancelRequest", "params": {"id": 1}}, replies.append
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert len(replies) == 1
    assert replies[0]["error"]["code"] == errors.QUERY_CANCELLED
    assert not dispatcher.pending


async def test_cancel_after_completion_keeps_normal_reply_and_successor(
    engine, isolated_profiles
):
    dispatcher = Dispatcher(engine)
    replies = []
    dispatcher.submit(rpc(1, "listProfiles"), replies.append)
    await asyncio.sleep(0)  # The task is done; its completion callback is still queued.
    await cancel(dispatcher, 1)
    successor = start(dispatcher, rpc(2, "listProfiles"))
    await asyncio.sleep(0)
    assert replies == [{"jsonrpc": "2.0", "id": 1, "result": {}}]
    await cancel(dispatcher, 1)
    assert (await successor)["result"] == {}
    assert not dispatcher.pending


async def test_disconnect_cancels_session_work_rejects_new_work_and_leaves_other_session(
    engine, monkeypatch
):
    other = (await engine.connect("sqlite", {"uri": ":memory:"}))["session_id"]
    sid, adapter = await gated_session(engine, monkeypatch)
    dispatcher = Dispatcher(engine)
    slow = start(dispatcher, rpc(1, "execute", session_id=sid, sql="slow"))
    await entered(adapter)
    closing = start(dispatcher, rpc(2, "disconnect", session_id=sid))
    await asyncio.sleep(0)
    rejected = await dispatcher.handle(
        rpc(3, "execute", session_id=sid, sql="SELECT 1")
    )
    assert rejected["error"]["code"] == errors.SESSION_NOT_FOUND
    assert (
        await dispatcher.handle(rpc(4, "execute", session_id=other, sql="SELECT 2"))
    )["result"]["rows"] == [[2]]
    assert (await slow)["error"]["code"] == errors.QUERY_CANCELLED
    assert (await closing)["result"] == {"ok": True}
    assert sid not in engine.sessions.ids()
    assert not dispatcher.pending


@pytest.mark.parametrize("adapter_name", ["sqlite", "duckdb"])
async def test_real_query_cancellation_isolated_and_session_reusable(
    engine, adapter_name
):
    connected = await engine.connect(adapter_name, {"uri": ":memory:"})
    sid = connected["session_id"]
    other = (await engine.connect(adapter_name, {"uri": ":memory:"}))["session_id"]
    await engine.execute(sid, "CREATE TABLE products(id INT)")
    await engine.complete(
        sid, "SELECT  FROM products", tuple(connected["default_path"]), 7
    )
    dispatcher = Dispatcher(engine)
    sql = (
        "WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t) SELECT sum(n) FROM t"
        if adapter_name == "sqlite"
        else "SELECT sum(hash(i)) FROM range(20000000000) t(i)"
    )
    slow = start(dispatcher, rpc(1, "execute", session_id=sid, sql=sql))
    await asyncio.sleep(0.03)
    assert not slow.done()
    completion = await asyncio.wait_for(
        dispatcher.handle(
            rpc(
                2,
                "complete",
                session_id=sid,
                path=connected["default_path"],
                sql="SELECT  FROM products",
                position=7,
            )
        ),
        2,
    )
    assert [item["label"] for item in completion["result"]] == ["id"]
    unaffected = start(dispatcher, rpc(3, "execute", session_id=other, sql="SELECT 3"))
    if adapter_name == "duckdb":
        metadata = start(
            dispatcher,
            rpc(4, "listTables", session_id=sid, path=connected["default_path"]),
        )
        assert [
            table["name"]
            for table in (await asyncio.wait_for(asyncio.shield(metadata), 2))["result"]
        ] == ["products"]
        assert not slow.done()
    await cancel(dispatcher, 1)
    assert (await asyncio.wait_for(slow, 3))["error"]["code"] == errors.QUERY_CANCELLED
    assert (await unaffected)["result"]["rows"] == [[3]]
    assert (await dispatcher.handle(rpc(5, "execute", session_id=sid, sql="SELECT 5")))[
        "result"
    ]["rows"] == [[5]]
    assert not dispatcher.pending


async def test_disconnect_leaves_another_sessions_running_query_intact(
    engine, monkeypatch
):
    first, second = GatedSqlite(), GatedSqlite()
    adapters = iter([first, second])
    monkeypatch.setattr(
        "dbridge.core.session.create_adapter", lambda *args: next(adapters)
    )
    sid1 = (await engine.connect("sqlite"))["session_id"]
    sid2 = (await engine.connect("sqlite"))["session_id"]
    dispatcher = Dispatcher(engine)
    slow1 = start(dispatcher, rpc(1, "execute", session_id=sid1, sql="slow"))
    slow2 = start(dispatcher, rpc(2, "execute", session_id=sid2, sql="slow"))
    await entered(first)
    await entered(second)
    try:
        closed = await asyncio.wait_for(
            dispatcher.handle(rpc(3, "disconnect", session_id=sid1)), 2
        )
        assert closed["result"] == {"ok": True}
        assert (await slow1)["error"]["code"] == errors.QUERY_CANCELLED
        assert not slow2.done() and not second.interrupted
    finally:
        first.release.set()
        second.release.set()
    assert (await slow2)["result"]["rows"] == [[1]]


@pytest.mark.parametrize("adapter_name", ["sqlite", "duckdb"])
async def test_cancel_leaves_real_query_on_another_session_running(
    engine, adapter_name
):
    first = (await engine.connect(adapter_name, {"uri": ":memory:"}))["session_id"]
    second = (await engine.connect(adapter_name, {"uri": ":memory:"}))["session_id"]
    adapter = engine.sessions.get(second).adapter
    started, release = threading.Event(), threading.Event()

    def gated():
        started.set()
        assert release.wait(5)
        return 17

    def register():
        if adapter_name == "sqlite":
            adapter.con.create_function("gated", 0, gated)
        else:
            adapter.con.create_function(
                "gated", gated, [], "INTEGER", side_effects=True
            )

    await adapter._lanes["query"].run(register)
    sql = (
        "WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t) SELECT sum(n) FROM t"
        if adapter_name == "sqlite"
        else "SELECT sum(hash(i)) FROM range(20000000000) t(i)"
    )
    dispatcher = Dispatcher(engine)
    first_reply = start(dispatcher, rpc(1, "execute", session_id=first, sql=sql))
    second_reply = start(
        dispatcher, rpc(2, "execute", session_id=second, sql="SELECT gated()")
    )
    try:
        assert await asyncio.to_thread(started.wait, 2)
        await cancel(dispatcher, 1)
        assert (await asyncio.wait_for(first_reply, 3))["error"][
            "code"
        ] == errors.QUERY_CANCELLED
        assert not second_reply.done()
    finally:
        release.set()
    assert (await asyncio.wait_for(second_reply, 2))["result"]["rows"] == [[17]]


async def test_cancelling_duckdb_query_preserves_inflight_metadata(engine, monkeypatch):
    connected = await engine.connect("duckdb")
    sid = connected["session_id"]
    await engine.execute(sid, "CREATE TABLE products(id INT)")
    adapter = engine.sessions.get(sid).adapter
    listing = adapter._list_tables
    entered_metadata, release = threading.Event(), threading.Event()

    def gated_listing(path):
        entered_metadata.set()
        assert release.wait(5)
        return listing(path)

    monkeypatch.setattr(adapter, "_list_tables", gated_listing)
    dispatcher = Dispatcher(engine)
    query = start(
        dispatcher,
        rpc(
            1,
            "execute",
            session_id=sid,
            sql="SELECT sum(hash(i)) FROM range(20000000000) t(i)",
        ),
    )
    metadata = start(
        dispatcher, rpc(2, "listTables", session_id=sid, path=connected["default_path"])
    )
    try:
        assert await asyncio.to_thread(entered_metadata.wait, 2)
        await cancel(dispatcher, 1)
        assert (await asyncio.wait_for(query, 3))["error"][
            "code"
        ] == errors.QUERY_CANCELLED
        assert not metadata.done()
    finally:
        release.set()
    assert [
        entry["name"] for entry in (await asyncio.wait_for(metadata, 2))["result"]
    ] == ["products"]


async def test_unexpected_handler_failure_replies_once_and_releases_id(
    engine, isolated_profiles
):
    dispatcher = Dispatcher(engine)

    def broken(params):
        raise ValueError("unexpected failure")

    dispatcher._methods["dbridge/broken"] = broken
    response = await dispatcher.handle(rpc(1, "broken"))
    assert response["error"]["code"] == errors.INTERNAL_ERROR
    assert not dispatcher.pending
    assert (await dispatcher.handle(rpc(1, "listProfiles")))["result"] == {}


async def test_cancelled_repeated_disconnect_finishes_shared_cleanup(
    engine, monkeypatch
):
    sid = (await engine.connect("sqlite", {"uri": ":memory:"}))["session_id"]
    adapter = engine.sessions.get(sid).adapter
    disconnect = adapter.disconnect
    closing, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def gated_close():
        calls.append("close")
        closing.set()
        await release.wait()
        await disconnect()

    monkeypatch.setattr(adapter, "disconnect", gated_close)
    dispatcher = Dispatcher(engine)
    first = start(dispatcher, rpc(1, "disconnect", session_id=sid))
    await asyncio.wait_for(closing.wait(), 2)
    second = start(dispatcher, rpc(2, "disconnect", session_id=sid))
    await asyncio.sleep(0)
    await cancel(dispatcher, 1)
    assert not first.done() and not second.done()
    release.set()
    assert (await asyncio.wait_for(first, 2))["result"] == {"ok": True}
    assert (await asyncio.wait_for(second, 2))["result"] == {"ok": True}
    assert calls == ["close"]
    assert not engine.sessions.ids()
    assert not dispatcher.pending
