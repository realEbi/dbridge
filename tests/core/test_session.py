import pytest

from dbridge.core.session import SessionManager, SessionNotFoundError
from dbridge.exceptions import AdapterError


def test_create_and_get():
    mgr = SessionManager()
    s = mgr.create("sqlite", {"uri": ":memory:"})
    assert mgr.get(s.id) is s


def test_unknown_session_raises():
    mgr = SessionManager()
    with pytest.raises(SessionNotFoundError):
        mgr.get("nope")


def test_close_removes_session():
    mgr = SessionManager()
    s = mgr.create("sqlite", {"uri": ":memory:"})
    mgr.close(s.id)
    with pytest.raises(SessionNotFoundError):
        mgr.get(s.id)


def test_close_unknown_session_is_a_noop():
    """pop(id, None) means closing an unknown id does not raise."""
    mgr = SessionManager()
    mgr.close("no-such-session")


def test_close_disconnects_the_adapter():
    mgr = SessionManager()
    session = mgr.create("sqlite", {"uri": ":memory:"})
    adapter = session.adapter

    mgr.close(session.id)

    assert adapter.con is None


def test_sessions_have_distinct_ids():
    mgr = SessionManager()
    first = mgr.create("sqlite", {"uri": ":memory:"})
    second = mgr.create("sqlite", {"uri": ":memory:"})
    assert first.id != second.id


def test_new_session_has_no_active_scope():
    """Metadata scope belongs to each request, not the Session."""
    mgr = SessionManager()
    session = mgr.create("sqlite", {"uri": ":memory:"})
    assert not hasattr(session, "active_database")
    assert not hasattr(session, "active_schema")


def test_unsupported_adapter_raises():
    mgr = SessionManager()
    with pytest.raises(AdapterError):
        mgr.create("oracle", {})
