import pytest

from dbridge.core.session import SessionManager, SessionNotFoundError


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
