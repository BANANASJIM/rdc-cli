from __future__ import annotations

import inspect
import time
from pathlib import Path
from unittest.mock import MagicMock

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


def test_wait_for_ping_default_timeout_is_15() -> None:
    sig = inspect.signature(session_service.wait_for_ping)
    assert sig.parameters["timeout_s"].default == 15.0


def test_wait_for_ping_returns_early_on_process_exit() -> None:
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1
    mock_proc.returncode = 1
    mock_proc.stderr = None

    start = time.monotonic()
    ok, reason = session_service.wait_for_ping("127.0.0.1", 1, "tok", timeout_s=5.0, proc=mock_proc)
    elapsed = time.monotonic() - start

    assert ok is False
    assert "process exited" in reason
    assert elapsed < 1.0


def test_wait_for_ping_succeeds_returns_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        session_service,
        "send_request",
        lambda *args, **kwargs: {"result": {"ok": True}},
    )
    ok, reason = session_service.wait_for_ping("127.0.0.1", 1, "tok", timeout_s=1.0)
    assert ok is True
    assert reason == ""


def test_wait_for_ping_works_without_proc(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*args: object, **kwargs: object) -> None:
        raise ConnectionRefusedError

    monkeypatch.setattr(session_service, "send_request", _refuse)
    ok, reason = session_service.wait_for_ping("127.0.0.1", 1, "tok", timeout_s=0.2)
    assert ok is False
    assert "timeout" in reason


def test_open_session_reports_stderr_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(session_service, "load_session", lambda: None)
    monkeypatch.setattr(session_service, "_renderdoc_available", lambda: False)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1
    mock_proc.returncode = 1
    mock_proc.pid = 999
    mock_proc.kill.return_value = None
    mock_proc.communicate.return_value = ("", "some error msg\n")

    detail = (False, "process exited: exit code 1")
    monkeypatch.setattr(session_service, "start_daemon", lambda *a, **kw: mock_proc)
    monkeypatch.setattr(session_service, "wait_for_ping", lambda *a, **kw: detail)

    ok, msg = session_service.open_session(Path("test.rdc"))
    assert ok is False
    assert "some error msg" in msg


def test_open_session_failure_with_empty_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(session_service, "load_session", lambda: None)
    monkeypatch.setattr(session_service, "_renderdoc_available", lambda: False)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1
    mock_proc.returncode = 1
    mock_proc.pid = 999
    mock_proc.kill.return_value = None
    mock_proc.communicate.return_value = ("", "")

    detail = (False, "process exited: exit code 1")
    monkeypatch.setattr(session_service, "start_daemon", lambda *a, **kw: mock_proc)
    monkeypatch.setattr(session_service, "wait_for_ping", lambda *a, **kw: detail)

    ok, msg = session_service.open_session(Path("test.rdc"))
    assert ok is False
    assert msg  # message must be non-empty


def test_start_daemon_idle_timeout_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_service, "_renderdoc_available", lambda: False)
    captured_cmd: list[str] = []

    def fake_popen(cmd: list[str], **kwargs: object) -> MagicMock:
        captured_cmd.extend(cmd)
        return MagicMock()

    monkeypatch.setattr(session_service.subprocess, "Popen", fake_popen)
    session_service.start_daemon("test.rdc", 9999, "tok", idle_timeout=120)
    idx = captured_cmd.index("--idle-timeout")
    assert captured_cmd[idx + 1] == "120"


def test_start_daemon_idle_timeout_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_service, "_renderdoc_available", lambda: False)
    captured_cmd: list[str] = []

    def fake_popen(cmd: list[str], **kwargs: object) -> MagicMock:
        captured_cmd.extend(cmd)
        return MagicMock()

    monkeypatch.setattr(session_service.subprocess, "Popen", fake_popen)
    session_service.start_daemon("test.rdc", 9999, "tok")
    idx = captured_cmd.index("--idle-timeout")
    assert captured_cmd[idx + 1] == "1800"
