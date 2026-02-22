from __future__ import annotations

from pathlib import Path

import pytest

from rdc.services import session_service


def test_open_session_rejects_existing_live_session(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_close_session_without_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_service, "load_session", lambda: None)
    ok, _msg = session_service.close_session()
    assert ok is False


def test_open_session_cross_name_no_conflict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Opening session 'b' while 'a' is alive succeeds (conflict is per-name)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(session_service, "_renderdoc_available", lambda: False)

    # Open session "a"
    monkeypatch.setenv("RDC_SESSION", "a")
    ok_a, _ = session_service.open_session(Path("alpha.rdc"))
    assert ok_a is True

    # Opening session "b" must succeed even though "a" is alive
    monkeypatch.setenv("RDC_SESSION", "b")
    ok_b, msg_b = session_service.open_session(Path("beta.rdc"))
    assert ok_b is True, f"expected success but got: {msg_b}"


def test_open_session_same_name_alive_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Opening the same session name twice (alive pid) returns error."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RDC_SESSION", "alpha")
    monkeypatch.setattr(session_service, "_renderdoc_available", lambda: False)

    ok1, _ = session_service.open_session(Path("alpha.rdc"))
    assert ok1 is True

    # Second open with same name and live pid must fail
    monkeypatch.setattr(session_service, "is_pid_alive", lambda pid: True)
    ok2, msg2 = session_service.open_session(Path("alpha.rdc"))
    assert ok2 is False
    assert "active session exists" in msg2
