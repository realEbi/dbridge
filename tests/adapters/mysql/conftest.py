"""Opt-in real MySQL fixtures; the default suite imports no optional driver."""
import asyncio
import importlib
import os
from time import monotonic

import pytest


@pytest.fixture(autouse=True)
def mysql_enabled():
    if not any(name.startswith("DBRIDGE_TEST_MYSQL_") for name in os.environ):
        pytest.skip("set DBRIDGE_TEST_MYSQL_HOST or run make test-mysql")


@pytest.fixture
def mysql_config():
    return {
        "host": os.getenv("DBRIDGE_TEST_MYSQL_HOST", "127.0.0.1"),
        "port": os.getenv("DBRIDGE_TEST_MYSQL_PORT", "33084"),
        "user": os.getenv("DBRIDGE_TEST_MYSQL_USER", "dbridge"),
        "password": os.getenv("DBRIDGE_TEST_MYSQL_PASSWORD", "dbridge"),
        "database": os.getenv("DBRIDGE_TEST_MYSQL_DATABASE", "dbridge_test"),
    }


@pytest.fixture
def second_config(mysql_config):
    return {
        **mysql_config,
        "user": os.getenv("DBRIDGE_TEST_MYSQL_SECOND_USER", "dbridge_second"),
        "password": os.getenv("DBRIDGE_TEST_MYSQL_SECOND_PASSWORD", "dbridge_second"),
    }


@pytest.fixture
def mysql_module(mysql_enabled):
    # Deliberately fails if enabled without the extra, instead of silently skipping.
    return importlib.import_module("dbridge.adapters.mysql")


@pytest.fixture
async def adapter_factory(mysql_module, mysql_config):
    adapters = []

    async def create(config=None):
        adapter = mysql_module.MySQLAdapter(config or mysql_config)
        adapters.append(adapter)
        await adapter.connect()
        return adapter

    yield create
    for adapter in reversed(adapters):
        await asyncio.wait_for(adapter.disconnect(), timeout=5)


@pytest.fixture
async def mysql_adapter(adapter_factory):
    return await adapter_factory()


class Observer:
    def __init__(self, connection):
        self.connection = connection

    async def query(self, sql, args=None):
        async with self.connection.cursor() as cursor:
            await cursor.execute(sql, args)
            return list(await cursor.fetchall())

    async def connections(self, user):
        rows = await self.query(
            "SELECT ID FROM performance_schema.processlist WHERE USER=%s", (user,)
        )
        return {row[0] for row in rows}

    async def running(self, marker):
        rows = await self.query(
            "SELECT ID FROM performance_schema.processlist "
            "WHERE USER <> CURRENT_USER() AND INFO LIKE %s AND ID <> CONNECTION_ID()",
            (f"%{marker}%",),
        )
        return {row[0] for row in rows}

    async def wait_running(self, marker, timeout=5):
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            if ids := await self.running(marker):
                return ids
            await asyncio.sleep(0.01)
        pytest.fail(f"statement did not start: {marker}")

    async def wait_gone(self, thread_ids, timeout=3):
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            rows = await self.query("SELECT ID FROM performance_schema.processlist")
            if not thread_ids.intersection(row[0] for row in rows):
                return
            await asyncio.sleep(0.01)
        pytest.fail(f"server connections remained open: {thread_ids}")

    async def history(self, sql):
        return await self.query(
            "SELECT SQL_TEXT FROM performance_schema.events_statements_history_long "
            "WHERE SQL_TEXT=%s", (sql,),
        )


@pytest.fixture
async def observer(mysql_enabled, mysql_config):
    driver = importlib.import_module("aiomysql")
    connection = await driver.connect(
        host=mysql_config["host"], port=int(mysql_config["port"]),
        user=os.getenv("DBRIDGE_TEST_MYSQL_OBSERVER_USER", "dbridge_observer"),
        password=os.getenv("DBRIDGE_TEST_MYSQL_OBSERVER_PASSWORD", "dbridge_observer"),
        autocommit=True,
    )
    try:
        yield Observer(connection)
    finally:
        await connection.ensure_closed()
