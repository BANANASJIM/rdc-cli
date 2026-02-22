from __future__ import annotations

from pathlib import Path

from rdc.services import session_service


def test_open_session_rejects_existing_live_session(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class DummyState:
        pid = 123

    monkeypatch.setattr(session_service, "load_session", lambda: DummyState())
    monkeypatch.setattr(session_service, "is_pid_alive", lambda pid: True)

    ok, msg = session_service.open_session(Path("capture.rdc"))
    assert ok is False
    assert "active session exists" in msg


def test_goto_session_rejects_negative_eid() -> None:
    ok, msg = session_service.goto_session(-1)
    assert ok is False
    assert "eid must be >= 0" in msg


def test_close_session_without_state(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(session_service, "load_session", lambda: None)
    ok, _msg = session_service.close_session()
    assert ok is False
