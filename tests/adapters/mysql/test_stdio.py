"""The public framed DSP flow against the disposable MySQL service."""
import asyncio
import io
import json
import os
import sys
from time import monotonic
from uuid import uuid4

import pytest

from dbridge.protocol.transport.stdio import read_message


class Client:
    def __init__(self, process):
        self.process = process
        self.request_id = 0

    async def send(self, method, params=None, *, notification=False):
        self.request_id += 1
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notification:
            message["id"] = self.request_id
        body = json.dumps(message).encode("utf-8")
        self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        await self.process.stdin.drain()
        return self.request_id

    async def read(self):
        async def frame():
            header = await self.process.stdout.readuntil(b"\r\n\r\n")
            assert header.startswith(b"Content-Length: "), header
            size = int(header.removeprefix(b"Content-Length: ").strip())
            return json.loads(await self.process.stdout.readexactly(size))
        return await asyncio.wait_for(frame(), timeout=5)

    async def rpc(self, method, **params):
        request_id = await self.send("dbridge/" + method, params)
        response = await self.read()
        assert response["id"] == request_id
        assert "error" not in response, response
        return response["result"]


@pytest.fixture
async def client(tmp_path, request):
    command = [sys.executable, "-m", "dbridge.server"]
    if getattr(request, "param", None) == "abandon":
        command = [sys.executable, "-c", (
            "import dbridge.protocol.transport.stdio as s; "
            "s.SHUTDOWN_GRACE_SECONDS = 0; "
            "from dbridge.server import main; main()"
        )]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "XDG_CONFIG_HOME": str(tmp_path), "APPDATA": str(tmp_path), "DBRIDGE_MAX_ROWS": "100"},
    )
    try:
        yield Client(process)
    finally:
        if process.returncode is None:
            process.stdin.close()
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 5)
        except TimeoutError:
            process.kill()
            await process.communicate()
            pytest.fail("dbridge subprocess failed to exit")
        assert process.returncode == 0, stderr.decode()
        assert b"Traceback" not in stderr
        # Every remaining stdout byte must still be a protocol frame.
        frames = io.BytesIO(stdout)
        while (frame := read_message(frames)) is not None:
            assert isinstance(frame, dict)


async def test_profile_dsp_flow(client, mysql_config, observer):
    await client.rpc("saveProfile", name="mysql-local", adapter="mysql", config=mysql_config)
    connected = await client.rpc("connect", profile="mysql-local")
    assert connected["dialect"] == "mysql"
    assert connected["levels"] == [{"name": "database", "label": "Database"}]
    assert connected["default_path"] == [mysql_config["database"]]
    sid = connected["session_id"]
    assert (await client.rpc("execute", session_id=sid, sql="SELECT 'café ☕' AS label"))["rows"] == [["café ☕"]]
    tag = "dsp_" + uuid4().hex
    request_id = await client.send("dbridge/execute", {"session_id": sid, "sql": f"SELECT n, SLEEP(30) FROM million_rows /*{tag}*/"})
    await observer.wait_running(tag)
    await client.send("$/cancelRequest", {"id": request_id}, notification=True)
    response = await client.read()
    assert response["id"] == request_id and response["error"]["code"] == -32004
    assert not await observer.running(tag)
    result = await client.rpc("execute", session_id=sid, sql="SELECT * FROM million_rows")
    assert result["row_count"] == 100 and result["warnings"] == ["result truncated to 100 rows"]
    tables = await client.rpc("listTables", session_id=sid, path=[mysql_config["database"]])
    assert "child" in [table["name"] for table in tables]
    schema = await client.rpc("getTableSchema", session_id=sid, path=[mysql_config["database"]], name="child")
    assert schema["primary_key"] == {"name": "PRIMARY", "columns": ["b", "id"]}
    assert schema["foreign_keys"][0]["referenced_path"] == ["dbridge_other"]
    await client.rpc("execute", session_id=sid, sql="USE dbridge_other")
    assert (await client.rpc("refreshSchema", session_id=sid))["default_path"] == ["dbridge_other"]
    assert await client.rpc("disconnect", session_id=sid) == {"ok": True}


@pytest.mark.parametrize("bad", [{"password": "wrong"}, {"user": ""}])
async def test_connection_failed_wire_code_and_recovery(client, mysql_config, observer, bad):
    before = await observer.connections(mysql_config["user"])
    request_id = await client.send("dbridge/connect", {"adapter": "mysql", "config": {**mysql_config, **bad}})
    response = await client.read()
    assert response["id"] == request_id and response["error"]["code"] == -32001
    assert await observer.connections(mysql_config["user"]) == before
    connected = await client.rpc("connect", adapter="mysql", config=mysql_config)
    sid = connected["session_id"]
    request_id = await client.send("dbridge/execute", {"session_id": sid, "sql": "SELEC 1"})
    response = await client.read()
    assert response["id"] == request_id and response["error"]["code"] == -32002
    assert (await client.rpc("execute", session_id=sid, sql="SELECT 1"))["rows"] == [[1]]
    await client.rpc("disconnect", session_id=sid)


@pytest.mark.parametrize("client", ["normal", "abandon"], indirect=True)
async def test_close_input_stops_mysql_server_statement(client, mysql_config, observer):
    connected = await client.rpc("connect", adapter="mysql", config=mysql_config)
    ids = await observer.connections(mysql_config["user"])
    tag = "shutdown_" + uuid4().hex
    await client.send("dbridge/execute", {"session_id": connected["session_id"], "sql": f"SELECT SLEEP(30) /*{tag}*/"})
    await observer.wait_running(tag)
    start = monotonic()
    client.process.stdin.close()
    await asyncio.wait_for(client.process.wait(), timeout=3)
    assert client.process.returncode == 0
    assert monotonic() - start < 3
    await observer.wait_gone(ids)
