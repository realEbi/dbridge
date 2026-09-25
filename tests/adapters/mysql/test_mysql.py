"""Real MySQL contract checks, including server-side evidence of interruption."""
import asyncio
from time import monotonic
from uuid import uuid4

import pytest

from dbridge.adapters.base import ScopeLevel, TableRef
from dbridge.exceptions import AdapterConnectionError, AdapterQueryError
from dbridge.core import executor
from dbridge.core.session import Session


def marker():
    return "mysql_test_" + uuid4().hex


async def cancelled(task):
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)


async def capped(adapter, sql):
    return await executor.execute(Session("test", adapter), sql, max_rows=100)


async def test_seed_and_unprivileged_account(mysql_adapter, observer):
    assert (await mysql_adapter.execute("SELECT COUNT(*) FROM million_rows")).rows == [[1000000]]
    grants = (await mysql_adapter.execute("SHOW GRANTS")).rows
    for grant in grants:
        assert not any(name in grant[0] for name in ("PROCESS", "CONNECTION_ADMIN", "SUPER"))
    assert await observer.query("SELECT @@version")


@pytest.mark.parametrize("bad", [{"password": "wrong"}, {"user": ""}, {"port": "nonsense"}])
async def test_failed_connect_leaks_no_connection(mysql_module, mysql_config, observer, bad):
    before = await observer.connections(mysql_config["user"])
    with pytest.raises(AdapterConnectionError):
        adapter = mysql_module.MySQLAdapter({**mysql_config, **bad})
        try:
            await adapter.connect()
        finally:
            await adapter.disconnect()
    assert await observer.connections(mysql_config["user"]) == before


async def test_missing_user_fails(mysql_module, mysql_config):
    config = {k: v for k, v in mysql_config.items() if k != "user"}
    with pytest.raises(AdapterConnectionError):
        adapter = mysql_module.MySQLAdapter(config)
        try:
            await adapter.connect()
        finally:
            await adapter.disconnect()


async def test_execution_multistatement_error_and_autocommit(adapter_factory):
    adapter = await adapter_factory()
    result = await adapter.execute("SET @x = 5; SELECT @x AS x; SET @x = 6")
    assert result.columns == ["x"] and result.rows == [[5]]
    with pytest.raises(AdapterQueryError):
        await adapter.execute("SELEC 1")
    assert (await adapter.execute("SELECT 1")).rows == [[1]]
    value = marker()
    await adapter.execute(f"INSERT INTO persisted VALUES ('{value}')")
    await adapter.disconnect()
    other = await adapter_factory()
    try:
        assert (await other.execute(f"SELECT marker FROM persisted WHERE marker='{value}'")).rows == [[value]]
    finally:
        await other.execute(f"DELETE FROM persisted WHERE marker='{value}'")


async def test_five_queued_executes_keep_order(mysql_adapter, observer):
    tag = marker()
    await mysql_adapter.execute("SET @order = ''")
    first = asyncio.create_task(mysql_adapter.execute(f"SELECT SLEEP(30) /*{tag}*/"))
    await observer.wait_running(tag)
    tasks = []
    for index in range(5):
        tasks.append(asyncio.create_task(mysql_adapter.execute(
            f"SET @order = CONCAT(@order, '{index}'); SELECT @order"
        )))
        await asyncio.sleep(0)
    await cancelled(first)
    results = await asyncio.gather(*tasks)
    assert [r.rows for r in results] == [[["01234"[:i + 1]]] for i in range(5)]


async def test_control_sharing_and_account_isolation(adapter_factory, mysql_config, second_config, observer):
    initial = await observer.connections(mysql_config["user"])
    a = await adapter_factory()
    ids_a = await observer.connections(mysql_config["user"]) - initial
    assert len(ids_a) == 3
    b = await adapter_factory()
    ids_b = await observer.connections(mysql_config["user"]) - initial
    assert len(ids_b) == 5
    assert a._control is b._control
    c = await adapter_factory(second_config)
    assert c._control is not a._control
    assert len(await observer.connections(second_config["user"])) == 3
    await a.disconnect()
    assert len(await observer.connections(mysql_config["user"]) - initial) == 3
    await b.disconnect()
    await observer.wait_gone(ids_b)
    ids_c = await observer.connections(second_config["user"])
    await c.disconnect()
    await observer.wait_gone(ids_c)


@pytest.mark.parametrize("sql", ["SELECT SLEEP(30)", "SELECT n, SLEEP(30) FROM million_rows"])
async def test_cancel_stops_server_and_preserves_state(mysql_adapter, observer, sql):
    await mysql_adapter.execute("SET @marker=7; CREATE TEMPORARY TABLE temp_keep (n INT); INSERT INTO temp_keep VALUES (1)")
    thread = (await mysql_adapter.execute("SELECT CONNECTION_ID()")).rows[0][0]
    tag = marker()
    task = asyncio.create_task(mysql_adapter.execute(f"{sql} /*{tag}*/"))
    assert thread in await observer.wait_running(tag)
    start = monotonic()
    await cancelled(task)
    assert monotonic() - start < 2
    assert not await observer.running(tag)
    assert (await mysql_adapter.execute("SELECT @marker, COUNT(*), CONNECTION_ID() FROM temp_keep")).rows == [[7, 1, thread]]
    assert await mysql_adapter.default_scope() == ("dbridge_test",)


async def test_cancelled_queued_statement_never_reaches_server(mysql_adapter, observer):
    running_tag, queued_tag = marker(), marker()
    first = asyncio.create_task(mysql_adapter.execute(f"SELECT SLEEP(30) /*{running_tag}*/"))
    await observer.wait_running(running_tag)
    sql = f"SELECT 97 /*{queued_tag}*/"
    queued = asyncio.create_task(mysql_adapter.execute(sql))
    await asyncio.sleep(0)
    await cancelled(queued)
    # Cancelling a queued request must leave the running request alone.
    assert await observer.running(running_tag)
    await cancelled(first)
    assert (await mysql_adapter.execute("SELECT 1")).rows == [[1]]
    positive = f"SELECT 98 /*{marker()}*/"
    await mysql_adapter.execute(positive)
    assert await observer.history(positive), "statement history must record completed queries"
    assert await observer.history(sql) == []


async def test_late_kill_ack_cannot_interrupt_next(mysql_adapter, observer, monkeypatch):
    tag = marker()
    ack_pending, release_ack = asyncio.Event(), asyncio.Event()
    original_kill = mysql_adapter._control.kill

    async def delayed_ack(thread_id, options):
        await original_kill(thread_id, options)
        ack_pending.set()
        await release_ack.wait()

    monkeypatch.setattr(mysql_adapter._control, "kill", delayed_ack)
    first = asyncio.create_task(mysql_adapter.execute(f"SELECT SLEEP(30) /*{tag}*/"))
    await observer.wait_running(tag)
    first.cancel()
    await asyncio.wait_for(ack_pending.wait(), 2)
    next_sql = f"SELECT 22 /*{marker()}*/"
    second = asyncio.create_task(mysql_adapter.execute(next_sql))
    await asyncio.sleep(0)
    # The server has accepted the kill but the Adapter has no acknowledgement.
    # A queued next statement must not enter that unconfirmed interruption window.
    assert not second.done()
    assert await observer.history(next_sql) == []
    release_ack.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(first, 2)
    assert (await second).rows == [[22]]
    assert await observer.history(next_sql)


async def test_cancel_after_result_during_snapshot_keeps_result(mysql_adapter, observer, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    channel = mysql_adapter._query

    async def operation():
        async with channel.connection.cursor() as cursor:
            await cursor.execute("SELECT 11")
            return list(await cursor.fetchall())

    async def after():
        entered.set()
        await release.wait()

    first = asyncio.create_task(channel.run(operation, after))
    await asyncio.wait_for(entered.wait(), 2)
    first.cancel()
    second = asyncio.create_task(mysql_adapter.execute("SELECT 22"))
    release.set()
    assert await first == [(11,)]
    assert (await second).rows == [[22]]


async def test_other_sessions_and_metadata_stay_responsive(mysql_adapter, adapter_factory, observer):
    tag = marker()
    task = asyncio.create_task(mysql_adapter.execute(f"SELECT SLEEP(30) /*{tag}*/"))
    await observer.wait_running(tag)
    other = await adapter_factory()
    assert (await asyncio.wait_for(other.execute("SELECT 9"), 1)).rows == [[9]]
    tables = await asyncio.wait_for(mysql_adapter.list_tables(("dbridge_test",)), 1)
    assert "million_rows" in [table.name for table in tables]
    await cancelled(task)


async def test_metadata_channel_cancellation(mysql_adapter, observer):
    tag = marker()
    channel = mysql_adapter._metadata

    async def slow_metadata():
        async with channel.connection.cursor() as cursor:
            await cursor.execute(f"SELECT SLEEP(30) /*{tag}*/")
            return await cursor.fetchall()

    task = asyncio.create_task(channel.run(slow_metadata))
    await observer.wait_running(tag)
    await cancelled(task)
    assert not await observer.running(tag)
    assert await mysql_adapter.list_tables(("dbridge_test",))


@pytest.mark.parametrize("sql, expected", [
    ("SELECT 1", True),
    ("WITH t AS (SELECT 1 AS n) SELECT * FROM t", True),
    ("SHOW DATABASES", True),
    ("SELECT 1 UNION SELECT 2", True),
    ("TABLE million_rows", True),
    ("TABLE dbridge_test.million_rows ORDER BY n LIMIT 100", True),
    ("TABLE `tick`` space.dot`", True),
    ("TABLE t WHERE x=1", False),
    ("TABLE t; SELECT 1", False),
    ("CALL p()", False),
    ("SELECT 1; SELECT 2", False),
    ("SELEC ???", False),
])
def test_killable_classification(mysql_module, sql, expected):
    assert mysql_module._is_killable(sql) is expected


async def test_million_row_cap_preserves_temporary_state(mysql_adapter, observer):
    await mysql_adapter.execute("CREATE TEMPORARY TABLE cap_keep (n INT); INSERT INTO cap_keep VALUES (7)")
    tag = marker()
    start = monotonic()
    result = await capped(mysql_adapter, f"SELECT * FROM million_rows /*{tag}*/")
    assert monotonic() - start < 1
    assert result.columns == ["n", "payload"]
    assert len(result.rows) == result.row_count == 100
    assert result.warnings == ["result truncated to 100 rows"]
    assert not await observer.running(tag)
    assert (await mysql_adapter.execute("SELECT * FROM cap_keep")).rows == [[7]]


@pytest.mark.parametrize("statement", ["CALL capped_insert('{value}')", "SELECT n FROM million_rows LIMIT 1000; INSERT INTO procedure_effects VALUES ('{value}')"])
async def test_capped_procedure_and_multistatement_finish_writes(mysql_adapter, statement):
    value = marker()
    result = await capped(mysql_adapter, statement.format(value=value))
    try:
        assert result.row_count == 100
        assert result.warnings == ["result truncated to 100 rows"]
        assert (await mysql_adapter.execute(f"SELECT marker FROM procedure_effects WHERE marker='{value}'")).rows == [[value]]
    finally:
        await mysql_adapter.execute(f"DELETE FROM procedure_effects WHERE marker='{value}'")


async def test_exact_cap_has_no_warning(mysql_adapter):
    result = await capped(mysql_adapter, "SELECT n FROM million_rows LIMIT 100")
    assert result.row_count == 100 and result.warnings == []


@pytest.mark.parametrize("abandon", [False, True])
async def test_disconnect_and_abandon_remove_server_work(mysql_adapter, mysql_config, observer, abandon):
    ids = await observer.connections(mysql_config["user"])
    tag = marker()
    task = asyncio.create_task(mysql_adapter.execute(f"SELECT SLEEP(30) /*{tag}*/"))
    await observer.wait_running(tag)
    if abandon:
        mysql_adapter.abandon()
    else:
        await asyncio.wait_for(mysql_adapter.disconnect(), timeout=2)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)
    await observer.wait_gone(ids)


async def test_metadata_defaults_keys_identifiers(mysql_adapter, adapter_factory):
    assert mysql_adapter.scope_levels() == [ScopeLevel("database", "Database")]
    assert mysql_adapter.dialect_name() == "mysql"
    assert await mysql_adapter.default_scope() == ("dbridge_test",)
    assert await mysql_adapter.list_schemas(("dbridge_test",)) == []
    databases = await mysql_adapter.list_databases()
    assert {entry.name for entry in databases if not entry.internal} == {"dbridge_other", "dbridge_test"}
    assert next(entry for entry in databases if entry.name == "information_schema").internal
    await mysql_adapter.execute("CREATE TEMPORARY TABLE hidden_temp (n INT)")
    tables = await mysql_adapter.list_tables(("dbridge_test",))
    names = [entry.name for entry in tables]
    assert "hidden_temp" not in names and "tiny_view" in names
    schema = await mysql_adapter.get_table_schema(TableRef("child", ("dbridge_test",)))
    assert [column.name for column in schema.columns] == ["id", "a", "b", "label"]
    assert schema.columns[-1].data_type == "varchar(40)"
    assert schema.columns[-1].nullable is True
    assert schema.columns[-1].default == "untitled"
    assert schema.columns[-1].comment == "display label"
    assert schema.columns[0].nullable is False
    assert schema.primary_key.name == "PRIMARY"
    assert schema.primary_key.columns == ["b", "id"]
    assert len(schema.foreign_keys) == 1
    key = schema.foreign_keys[0]
    assert (key.name, key.columns, key.referenced_path, key.referenced_table, key.referenced_columns) == (
        "parent_pair", ["b", "a"], ("dbridge_other",), "parent", ["b", "a"],
    )
    odd = await mysql_adapter.get_table_schema(TableRef("tick` space.dot", ("dbridge_test",)))
    assert odd.sql_identifier == "`dbridge_test`.`tick`` space.dot`"
    assert (await mysql_adapter.execute(f"SELECT * FROM {odd.sql_identifier}")).rows == [[42]]
    missing = await mysql_adapter.get_table_schema(TableRef("absent", ("dbridge_test",)))
    assert missing.columns == [] and missing.sql_identifier is None
    await mysql_adapter.execute("USE dbridge_other")
    assert await mysql_adapter.default_scope() == ("dbridge_other",)
    config = {key: value for key, value in mysql_adapter.config.items() if key != "database"}
    no_database = await adapter_factory(config)
    assert await no_database.default_scope() == ("dbridge_other",)


async def test_closed_control_reopens_without_losing_session(mysql_adapter, observer):
    control = mysql_adapter._control
    old_control_id = control.connection.thread_id()
    query_id = (await mysql_adapter.execute("SET @keep=8; SELECT CONNECTION_ID()")).rows[0][0]
    control.connection.close()
    tag = marker()
    task = asyncio.create_task(mysql_adapter.execute(f"SELECT SLEEP(30) /*{tag}*/"))
    await observer.wait_running(tag)
    await cancelled(task)
    assert control.connection.thread_id() != old_control_id
    assert (await mysql_adapter.execute("SELECT @keep, CONNECTION_ID()")).rows == [[8, query_id]]
    assert mysql_adapter._query.reconnect_count == 0


async def test_later_capped_result_stays_unbuffered(mysql_adapter, monkeypatch):
    connection = mysql_adapter._query.connection
    original_read = connection._read_query_result
    result_modes = []

    async def read_result(unbuffered=False):
        result_modes.append(unbuffered)
        return await original_read(unbuffered=unbuffered)

    monkeypatch.setattr(connection, "_read_query_result", read_result)
    result = await capped(mysql_adapter, "SELECT 0; SELECT n FROM million_rows LIMIT 10000")
    assert result.rows == [[n] for n in range(1, 101)]
    assert result.warnings == ["result truncated to 100 rows"]
    # The final buffered read is the bounded SELECT DATABASE() snapshot. Both
    # user result sets must stream, including the second one reached by nextset.
    assert result_modes[:2] == [True, True]


async def test_unconfirmed_kill_reconnects_and_logs_state_loss(mysql_adapter, observer, monkeypatch, caplog):
    original_kill = mysql_adapter._control.kill

    async def lose_acknowledgement(thread_id, options):
        # The kill reaches the real server, then the acknowledgement is lost.
        # This forces the documented recovery path without stranding test work.
        await original_kill(thread_id, options)
        raise ConnectionError("injected lost kill acknowledgement")

    monkeypatch.setattr(mysql_adapter._control, "kill", lose_acknowledgement)
    old_id = (await mysql_adapter.execute("SET @lost=8; SELECT CONNECTION_ID()")).rows[0][0]
    tag = marker()
    task = asyncio.create_task(mysql_adapter.execute(f"SELECT SLEEP(30) /*{tag}*/"))
    await observer.wait_running(tag)
    await cancelled(task)
    assert mysql_adapter._query.reconnect_count == 1
    result = await mysql_adapter.execute("SELECT @lost, CONNECTION_ID()")
    assert result.rows[0][0] is None and result.rows[0][1] != old_id
    assert "Session state" in caplog.text and "lost" in caplog.text


async def test_scope_snapshot_keeps_effects_before_error_and_cancel(mysql_adapter, observer):
    with pytest.raises(AdapterQueryError):
        await mysql_adapter.execute("USE dbridge_other; SELEC 1")
    assert await mysql_adapter.default_scope() == ("dbridge_other",)
    tag = marker()
    task = asyncio.create_task(mysql_adapter.execute(f"USE dbridge_test; SELECT SLEEP(30) /*{tag}*/"))
    await observer.wait_running(tag)
    await cancelled(task)
    assert await mysql_adapter.default_scope() == ("dbridge_test",)


async def test_cancel_disconnect_still_finishes_cleanup(mysql_adapter, observer, mysql_config, monkeypatch):
    pending, release = asyncio.Event(), asyncio.Event()
    original_kill = mysql_adapter._control.kill

    async def delayed_kill(thread_id, options):
        pending.set()
        await release.wait()
        await original_kill(thread_id, options)

    monkeypatch.setattr(mysql_adapter._control, "kill", delayed_kill)
    ids = await observer.connections(mysql_config["user"])
    tag = marker()
    task = asyncio.create_task(mysql_adapter.execute(f"SELECT SLEEP(30) /*{tag}*/"))
    await observer.wait_running(tag)
    disconnect = asyncio.create_task(mysql_adapter.disconnect())
    await asyncio.wait_for(pending.wait(), 2)
    disconnect.cancel()
    release.set()
    assert await asyncio.wait_for(disconnect, 2) is None
    with pytest.raises(asyncio.CancelledError):
        await task
    await observer.wait_gone(ids)


async def test_abandon_two_sessions_sharing_control_stops_both(adapter_factory, mysql_config, observer):
    first, second = await adapter_factory(), await adapter_factory()
    ids = await observer.connections(mysql_config["user"])
    tags = [marker(), marker()]
    tasks = [asyncio.create_task(adapter.execute(f"SELECT SLEEP(30) /*{tag}*/"))
             for adapter, tag in zip((first, second), tags)]
    for tag in tags:
        await observer.wait_running(tag)
    first.abandon()
    second.abandon()
    for task in tasks:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
    await observer.wait_gone(ids)


async def test_abandon_stalled_connection_handshake(mysql_module):
    accepted, disconnected = asyncio.Event(), asyncio.Event()

    async def withhold_greeting(reader, writer):
        accepted.set()
        try:
            assert await reader.read() == b""
        finally:
            writer.close()
            await writer.wait_closed()
            disconnected.set()

    server = await asyncio.start_server(withhold_greeting, "127.0.0.1", 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        adapter = mysql_module.MySQLAdapter({"host": "127.0.0.1", "port": str(port), "user": "stalled"})
        task = asyncio.create_task(adapter.connect())
        try:
            await asyncio.wait_for(accepted.wait(), 2)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done(), "a normal cancel must shield the pending driver handshake"
            adapter.abandon()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 1)
            await asyncio.wait_for(disconnected.wait(), 1)
            assert ("127.0.0.1", port, "stalled") not in mysql_module._controls
        finally:
            adapter.abandon()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_surviving_session_reopens_control_after_shared_abandon(adapter_factory, observer):
    first, second = await adapter_factory(), await adapter_factory()
    old_control_id = second._control.connection.thread_id()
    first_tag, second_tag = marker(), marker()
    first_task = asyncio.create_task(first.execute(f"SELECT SLEEP(30) /*{first_tag}*/"))
    await observer.wait_running(first_tag)
    first.abandon()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(first_task, 2)
    second_task = asyncio.create_task(second.execute(f"SELECT SLEEP(30) /*{second_tag}*/"))
    await observer.wait_running(second_tag)
    await cancelled(second_task)
    assert not await observer.running(first_tag)
    assert not await observer.running(second_tag)
    assert second._control.connection.thread_id() != old_control_id
    assert (await second.execute("SELECT 1")).rows == [[1]]
    assert second._query.reconnect_count == 0
