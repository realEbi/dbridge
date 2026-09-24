"""Exercise concurrent intake, reply framing and shutdown over real OS pipes."""

import asyncio
from contextlib import asynccontextmanager
import io
import os
import threading

import pytest

from dbridge.adapters.sqlite import SqliteAdapter
from dbridge.protocol import errors
from dbridge.protocol.handlers import Dispatcher
from dbridge.protocol.transport.stdio import (
    StdioTransport,
    read_message,
    write_message,
)


@asynccontextmanager
async def served(engine):
    input_read, input_write = os.pipe()
    output_read, output_write = os.pipe()
    with (
        os.fdopen(input_read, "rb") as stdin,
        os.fdopen(input_write, "wb") as client_in,
        os.fdopen(output_read, "rb") as client_out,
        os.fdopen(output_write, "wb") as stdout,
    ):
        dispatcher = Dispatcher(engine)
        serving = asyncio.create_task(StdioTransport(stdin, stdout).serve(dispatcher))

        async def receive():
            return await asyncio.wait_for(
                asyncio.to_thread(read_message, client_out), 4
            )

        try:
            yield dispatcher, client_in, receive, serving
        finally:
            client_in.close()
            await asyncio.wait_for(serving, 4)
            stdout.close()


def request(request_id, method, **params):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "dbridge/" + method,
        "params": params,
    }


async def test_fast_reply_overtakes_gated_slow_request(engine, isolated_profiles):
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow(params):
        entered.set()
        await release.wait()
        return "slow"

    async with served(engine) as (dispatcher, stream, receive, _):
        dispatcher._methods["dbridge/slow"] = slow
        write_message(stream, request(1, "slow"))
        await asyncio.wait_for(entered.wait(), 2)
        write_message(stream, request(2, "listProfiles"))
        assert await receive() == {"jsonrpc": "2.0", "id": 2, "result": {}}
        release.set()
        assert await receive() == {"jsonrpc": "2.0", "id": 1, "result": "slow"}
        assert not dispatcher.pending


async def test_many_replies_are_complete_and_correlated(engine):
    sessions = [
        (await engine.connect("sqlite", {"uri": ":memory:"}))["session_id"]
        for _ in range(3)
    ]
    async with served(engine) as (dispatcher, stream, receive, _):
        for request_id in range(60):
            write_message(
                stream,
                request(
                    request_id,
                    "execute",
                    session_id=sessions[request_id % 3],
                    sql=f"SELECT {request_id}",
                ),
            )
        replies = [await receive() for _ in range(60)]
        assert {reply["id"] for reply in replies} == set(range(60))
        assert all(reply["result"]["rows"] == [[reply["id"]]] for reply in replies)
        assert not dispatcher.pending


async def test_notifications_produce_no_reply(engine, isolated_profiles):
    async with served(engine) as (_, stream, receive, _):
        write_message(
            stream, {"jsonrpc": "2.0", "method": "dbridge/ignored", "params": {}}
        )
        write_message(
            stream,
            {"jsonrpc": "2.0", "method": "$/cancelRequest", "params": {"id": 99}},
        )
        write_message(stream, request(3, "listProfiles"))
        assert (await receive())["id"] == 3


@pytest.mark.parametrize("body", [b"{", b"\xff"])
async def test_parse_error_during_request_preserves_query_and_next_frame(engine, body):
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow(params):
        entered.set()
        await release.wait()
        return 42

    async with served(engine) as (dispatcher, stream, receive, _):
        dispatcher._methods["dbridge/slow"] = slow
        write_message(stream, request(1, "slow"))
        await entered.wait()
        stream.write(b"Content-Length: 1\r\n\r\n" + body)
        stream.flush()
        reply = await receive()
        assert reply["id"] is None and reply["error"]["code"] == errors.PARSE_ERROR
        write_message(stream, request(2, "nope"))
        assert (await receive())["error"]["code"] == errors.METHOD_NOT_FOUND
        release.set()
        assert (await receive())["result"] == 42


@pytest.mark.parametrize(
    "raw", [b"Content-Length: 100\r\n\r\n{", b"Content-Length: nope\r\n\r\n"]
)
async def test_fatal_frame_logs_and_closes_all_sessions(engine, raw, caplog):
    connected = await engine.connect("sqlite", {"uri": ":memory:"})
    adapter = engine.sessions.get(connected["session_id"]).adapter
    lanes = list(adapter._lanes.values())
    output = io.BytesIO()
    await StdioTransport(io.BytesIO(raw), output).serve(Dispatcher(engine))
    assert not engine.sessions.ids()
    assert all(not lane.thread.is_alive() for lane in lanes)
    assert "framing error" in caplog.text
    output.seek(0)
    assert read_message(output) is None


class IgnoringSQLite(SqliteAdapter):
    """An intentionally uninterruptible database job for the shutdown deadline."""

    def __init__(self, config):
        super().__init__(config)
        self.entered = threading.Event()
        self.release = threading.Event()
        self.closed = threading.Event()
        self.queued_ran = False

    def _execute(self, sql):
        if sql == "blocked":
            self.entered.set()
            self.release.wait(10)
        if sql == "queued":
            self.queued_ran = True
        return super()._execute("SELECT 1")

    def _interrupt(self, lane):
        pass

    def _disconnect(self):
        super()._disconnect()
        self.closed.set()


async def test_shutdown_abandons_stuck_driver_and_discards_queued_work(
    engine, monkeypatch, caplog
):
    adapter = IgnoringSQLite({"uri": ":memory:"})
    monkeypatch.setattr("dbridge.core.session.create_adapter", lambda *args: adapter)
    monkeypatch.setattr("dbridge.protocol.transport.stdio.SHUTDOWN_GRACE_SECONDS", 0.05)
    sid = (await engine.connect("sqlite"))["session_id"]
    lane = adapter._lanes["query"]
    try:
        async with served(engine) as (_, stream, _, serving):
            write_message(stream, request(1, "execute", session_id=sid, sql="blocked"))
            assert await asyncio.to_thread(adapter.entered.wait, 2)
            write_message(stream, request(2, "execute", session_id=sid, sql="queued"))
            stream.close()
            await asyncio.wait_for(asyncio.shield(serving), 0.8)
            assert not engine.sessions.ids()
            assert not adapter.queued_ran
            assert "connection cleanup incomplete" in caplog.text
            assert lane.thread.daemon
    finally:
        adapter.release.set()
        await asyncio.to_thread(lane.thread.join, 2)
    assert adapter.closed.is_set()
    assert not lane.thread.is_alive()


async def test_empty_input_closes_connected_adapters(engine):
    sid = (await engine.connect("sqlite", {"uri": ":memory:"}))["session_id"]
    lane = engine.sessions.get(sid).adapter._lanes["query"]
    await StdioTransport(io.BytesIO(), io.BytesIO()).serve(Dispatcher(engine))
    assert not lane.thread.is_alive()
    assert not engine.sessions.ids()


async def test_closed_output_does_not_prevent_shutdown(engine, isolated_profiles):
    class ClosedOutput(io.BytesIO):
        def write(self, data):
            raise BrokenPipeError

    stream = io.BytesIO()
    write_message(stream, request(1, "listProfiles"))
    stream.seek(0)
    await StdioTransport(stream, ClosedOutput()).serve(Dispatcher(engine))


async def test_excessive_json_nesting_does_not_kill_reader(engine, isolated_profiles):
    body = b"[" * 10000 + b"]" * 10000
    async with served(engine) as (_, stream, receive, _):
        stream.write(b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        stream.flush()
        assert (await receive())["error"]["code"] == errors.PARSE_ERROR
        write_message(stream, request(2, "listProfiles"))
        assert (await receive())["result"] == {}
