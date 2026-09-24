import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from dbridge.core.session import SessionManager, SessionNotFoundError
from dbridge.exceptions import AdapterError


@pytest.fixture
async def manager():
    manager = SessionManager()
    yield manager
    for session_id in manager.ids():
        await manager.close(session_id)


async def test_create_and_get(manager):
    mgr = manager
    s = await mgr.create("sqlite", {"uri": ":memory:"})
    assert mgr.get(s.id) is s


def test_unknown_session_raises(manager):
    mgr = manager
    with pytest.raises(SessionNotFoundError):
        mgr.get("nope")


async def test_close_removes_session(manager):
    mgr = manager
    s = await mgr.create("sqlite", {"uri": ":memory:"})
    await mgr.close(s.id)
    with pytest.raises(SessionNotFoundError):
        mgr.get(s.id)


async def test_close_unknown_session_is_a_noop(manager):
    """Closing an unknown id remains a no-op."""
    mgr = manager
    await mgr.close("no-such-session")


async def test_close_disconnects_the_adapter(manager):
    mgr = manager
    session = await mgr.create("sqlite", {"uri": ":memory:"})
    adapter = session.adapter

    await mgr.close(session.id)

    assert adapter.con is None


async def test_sessions_have_distinct_ids(manager):
    mgr = manager
    first = await mgr.create("sqlite", {"uri": ":memory:"})
    second = await mgr.create("sqlite", {"uri": ":memory:"})
    assert first.id != second.id


async def test_new_session_has_no_active_scope(manager):
    """Metadata scope belongs to each request, not the Session."""
    mgr = manager
    session = await mgr.create("sqlite", {"uri": ":memory:"})
    assert not hasattr(session, "active_database")
    assert not hasattr(session, "active_schema")


async def test_unsupported_adapter_raises(manager):
    mgr = manager
    with pytest.raises(AdapterError):
        await mgr.create("oracle", {})


async def test_closing_session_rejects_new_work_but_can_be_closed(manager):
    session = await manager.create("sqlite", {"uri": ":memory:"})
    manager.mark_closing(session.id)
    with pytest.raises(SessionNotFoundError):
        manager.get(session.id)
    assert session.id in manager.ids()
    await manager.close(session.id)
    assert session.adapter.con is None
    assert manager.ids() == ()


def test_mark_closing_unknown_session_is_a_noop(manager):
    manager.mark_closing("missing")
    assert manager.ids() == ()


@pytest.mark.parametrize("failure", [RuntimeError("connect failed"), asyncio.CancelledError()])
async def test_failed_connect_disconnects_unreported_adapter(manager, monkeypatch, failure):
    adapter = AsyncMock()
    adapter.connect.side_effect = failure
    monkeypatch.setattr("dbridge.core.session.create_adapter", lambda *_: adapter)
    with pytest.raises(type(failure)):
        await manager.create("fake", {})
    adapter.disconnect.assert_awaited_once()
    assert manager.ids() == ()


async def test_abandon_reaches_session_whose_disconnect_is_still_running(manager, monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def disconnect():
        started.set()
        await release.wait()

    adapter = Mock(connect=AsyncMock(), disconnect=AsyncMock(side_effect=disconnect))
    adapter.abandon.side_effect = release.set
    monkeypatch.setattr("dbridge.core.session.create_adapter", lambda *_: adapter)
    session = await manager.create("fake", {})
    closing = asyncio.create_task(manager.close(session.id))
    await asyncio.wait_for(started.wait(), timeout=1)

    assert session.id in manager.ids()
    manager.abandon_all()
    adapter.abandon.assert_called_once()
    assert manager.ids() == ()
    await closing


async def test_abandon_reaches_adapter_still_connecting(manager, monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def connect():
        started.set()
        await release.wait()
        raise asyncio.CancelledError()

    adapter = Mock(connect=AsyncMock(side_effect=connect), disconnect=AsyncMock())
    adapter.abandon.side_effect = release.set
    monkeypatch.setattr("dbridge.core.session.create_adapter", lambda *_: adapter)
    connecting = asyncio.create_task(manager.create("fake", {}))
    await asyncio.wait_for(started.wait(), timeout=1)
    manager.abandon_all()
    adapter.abandon.assert_called_once()
    with pytest.raises(asyncio.CancelledError):
        await connecting
    adapter.disconnect.assert_awaited_once()
    assert manager.ids() == ()
